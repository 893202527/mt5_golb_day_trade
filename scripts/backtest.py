"""Offline backtest with multi-timeframe features using OHLC data from PostgreSQL."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))

import pandas as pd
import config
from db import get_conn
from feature_engine import FeatureEngine
from ml_model import MLPredictor

LOOKBACK = config.FEATURE_LOOKBACK
H1_LOOKBACK = 20
H4_LOOKBACK = 10


def load_bars(symbol="XAUUSD", tf="M5"):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT bar_time, open, high, low, close, tick_volume FROM ohlc "
            "WHERE symbol=%s AND timeframe=%s ORDER BY bar_time ASC",
            (symbol, tf),
        )
        return [
            {"bar_time": row[0], "open": float(row[1]), "high": float(row[2]),
             "low": float(row[3]), "close": float(row[4]), "tick_volume": int(row[5])}
            for row in cur.fetchall()
        ]


def get_htf_window(htf_bars, m5_bar_time, lookback):
    completed = [b for b in htf_bars if b["bar_time"] < m5_bar_time]
    if len(completed) < 3:
        return None
    return completed[-lookback:]


def simulate_exit(bars, entry_idx, action, sl, tp):
    close = bars[entry_idx]["close"]
    end = min(entry_idx + 200, len(bars))
    for j in range(entry_idx + 1, end):
        h = bars[j]["high"]
        l = bars[j]["low"]
        if action == "buy":
            if l <= sl:
                return (sl, sl - close)
            if h >= tp:
                return (tp, tp - close)
        else:
            if h >= sl:
                return (sl, close - sl)
            if l <= tp:
                return (tp, close - tp)
    last_close = bars[end - 1]["close"]
    return (last_close, last_close - close if action == "buy" else close - last_close)


def drawdown(cum_pnl):
    peak = cum_pnl.cummax()
    dd = cum_pnl - peak
    return dd.min()


def run():
    print("[backtest] loading data...")
    m5_bars = load_bars("XAUUSD", "M5")
    h1_bars = load_bars("XAUUSD", "H1")
    h4_bars = load_bars("XAUUSD", "H4")

    if len(m5_bars) < LOOKBACK + 20:
        print(f"Insufficient M5 data: {len(m5_bars)} rows")
        return

    print(f"[backtest] M5: {len(m5_bars)} bars, H1: {len(h1_bars)} bars, H4: {len(h4_bars)} bars")

    fe = FeatureEngine(lookback=LOOKBACK)
    predictor = MLPredictor()
    trades = []

    pip_mult = 10 ** (-config.SYMBOL_DIGITS)
    for i in range(LOOKBACK, len(m5_bars)):
        m5_window = m5_bars[i - LOOKBACK : i + 1]
        h1_window = get_htf_window(h1_bars, m5_bars[i]["bar_time"], H1_LOOKBACK)
        h4_window = get_htf_window(h4_bars, m5_bars[i]["bar_time"], H4_LOOKBACK)
        features = fe.compute(m5_window, h1_window, h4_window)
        if not features:
            continue

        features["close"] = m5_bars[i]["close"]
        action, conf = predictor.predict(features)
        if action == "hold":
            continue

        close = m5_bars[i]["close"]
        sl = close - config.SL_PIPS * pip_mult if action == "buy" else close + config.SL_PIPS * pip_mult
        tp = close + config.TP_PIPS * pip_mult if action == "buy" else close - config.TP_PIPS * pip_mult

        exit_price, profit = simulate_exit(m5_bars, i, action, sl, tp)
        trades.append({
            "entry_time": m5_bars[i]["bar_time"],
            "action": action,
            "entry": close, "exit": exit_price,
            "sl": sl, "tp": tp,
            "profit": profit,
        })

    if not trades:
        print("No trades generated")
        return

    results = pd.DataFrame(trades)
    print(f"Total trades: {len(results)}")
    print(f"Win rate: {(results['profit'] > 0).mean():.2%}")
    print(f"Total profit: {results['profit'].sum():.2f}")
    cum_pnl = results["profit"].cumsum()
    print(f"Max drawdown: {drawdown(cum_pnl):.2f}")


if __name__ == "__main__":
    run()
