import json
import signal
import zmq
from collections import deque
import config
from db import insert_ohlc, get_recent_bars, insert_signal
from feature_engine import FeatureEngine
from ml_model import MLPredictor
from llm_gate import confirm_signal

running = True
fe = FeatureEngine(lookback=config.FEATURE_LOOKBACK)
predictor = MLPredictor()

# In-memory ring buffers for recent bars, keyed by timeframe
# Avoids DB round-trips on every signal query
_bar_cache: dict[str, deque[dict]] = {
    "M5": deque(maxlen=60),
    "H1": deque(maxlen=50),
    "H4": deque(maxlen=20),
}


def _cache_append(tf: str, bar: dict):
    if tf in _bar_cache:
        _bar_cache[tf].append(bar)


def _cache_get(tf: str, limit: int) -> list[dict]:
    """Return up to `limit` most recent bars from cache, oldest first."""
    buf = _bar_cache.get(tf)
    if not buf:
        return []
    items = list(buf)
    return items[-limit:] if len(items) > limit else items


def handle_ohlc(data: dict):
    row = {
        "symbol": data["symbol"],
        "tf": data["tf"],
        "time": data["time"],
        "open": data["open"],
        "high": data["high"],
        "low": data["low"],
        "close": data["close"],
        "volume": data.get("tick_volume", 0),
        "spread": data.get("spread", 0),
    }
    _cache_append(data["tf"], {
        "bar_time": data["time"],
        "open": data["open"], "high": data["high"],
        "low": data["low"], "close": data["close"],
        "tick_volume": data.get("tick_volume", 0),
    })
    insert_ohlc(row)


def handle_query(data: dict) -> dict:
    symbol = data.get("symbol", config.SYMBOL)
    tf = data.get("tf", config.SIGNAL_TF)

    # Prefer in-memory cache, fall back to DB
    bars = _cache_get(tf, config.FEATURE_LOOKBACK + 10)
    if len(bars) < config.FEATURE_LOOKBACK + 1:
        bars = get_recent_bars(symbol, tf, limit=config.FEATURE_LOOKBACK + 10)

    if len(bars) < config.FEATURE_LOOKBACK + 1:
        return {
            "action": "hold", "confidence": 0.0,
            "entry_price": 0, "sl": 0, "tp": 0,
            "reason": "insufficient data",
        }

    h1_bars = _cache_get("H1", 30)
    if len(h1_bars) < 3:
        h1_bars = get_recent_bars(symbol, "H1", limit=30)

    h4_bars = _cache_get("H4", 20)
    if len(h4_bars) < 3:
        h4_bars = get_recent_bars(symbol, "H4", limit=20)

    features = fe.compute(bars, h1_bars if len(h1_bars) >= 3 else None, h4_bars if len(h4_bars) >= 3 else None)
    if not features:
        return {
            "action": "hold", "confidence": 0.0,
            "entry_price": 0, "sl": 0, "tp": 0,
            "reason": "feature computation failed",
        }

    close = bars[-1]["close"]
    features["close"] = close

    ml_action, ml_conf = predictor.predict(features)
    reason = f"ML: {ml_action} ({ml_conf:.3f})"

    if ml_action != "hold":
        approved, llm_resp = confirm_signal(ml_action, ml_conf, features)
        reason += f" | LLM: {llm_resp[:200]}"
        if not approved:
            ml_action = "hold"

    pip_mult = 10 ** (-config.SYMBOL_DIGITS)
    sl = tp = 0.0
    if ml_action == "buy":
        sl = round(close - config.SL_PIPS * pip_mult, config.SYMBOL_DIGITS)
        tp = round(close + config.TP_PIPS * pip_mult, config.SYMBOL_DIGITS)
    elif ml_action == "sell":
        sl = round(close + config.SL_PIPS * pip_mult, config.SYMBOL_DIGITS)
        tp = round(close - config.TP_PIPS * pip_mult, config.SYMBOL_DIGITS)

    try:
        insert_signal({
            "bar_time": bars[-1].get("bar_time", ""),
            "symbol": symbol,
            "timeframe": tf,
            "action": ml_action,
            "confidence": ml_conf,
            "entry": close,
            "sl": sl,
            "tp": tp,
            "ml_model": "XGBoost",
            "llm_response": reason,
        })
    except Exception:
        pass  # signal logging is best-effort

    return {
        "action": ml_action, "confidence": ml_conf,
        "entry_price": close, "sl": sl, "tp": tp,
        "reason": reason,
    }


def main():
    global running
    ctx = zmq.Context()

    sub = ctx.socket(zmq.SUB)
    sub.connect(f"tcp://127.0.0.1:{config.ZMQ_PUB_PORT}")
    sub.setsockopt_string(zmq.SUBSCRIBE, "OHLC")

    rep = ctx.socket(zmq.REP)
    rep.bind(f"tcp://127.0.0.1:{config.ZMQ_REP_PORT}")

    poller = zmq.Poller()
    poller.register(sub, zmq.POLLIN)
    poller.register(rep, zmq.POLLIN)

    def shutdown(sig, frame):
        global running
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"[server] listening on PUB:{config.ZMQ_PUB_PORT} REP:{config.ZMQ_REP_PORT}")
    while running:
        socks = dict(poller.poll(1000))
        if sub in socks:
            msg = sub.recv_string()
            _, body = msg.split(" ", 1)
            data = json.loads(body)
            if data.get("type") == "ohlc":
                handle_ohlc(data)
        if rep in socks:
            req = rep.recv_string()
            data = json.loads(req)
            if data.get("type") == "query":
                resp = handle_query(data)
                rep.send_string(json.dumps(resp))

    sub.close()
    rep.close()
    ctx.term()
    print("[server] stopped")


if __name__ == "__main__":
    main()
