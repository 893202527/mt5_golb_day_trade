"""Self-contained quickstart: generate synthetic multi-TF OHLC data, train model, run backtest.

No PostgreSQL or external services required. Uses in-memory data.
Generates M5, H1, and H4 bars from a shared price process for realistic trend features.
"""
import os
import sys
import random
import tempfile
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))

import config
from feature_engine import FeatureEngine, FEATURE_ORDER
from ml_model import MLPredictor

LOOKBACK = config.FEATURE_LOOKBACK
M5_PER_H1 = 12   # 1 H1 bar = 12 M5 bars
M5_PER_H4 = 48   # 1 H4 bar = 48 M5 bars


# ---------------------------------------------------------------------------
# Step 1: generate synthetic M5 bars, then aggregate into H1 and H4
# ---------------------------------------------------------------------------
def generate_m5_bars(n: int, start_price: float = 2650.0, drift: float = 0.00005, volatility: float = 0.002):
    """Generate synthetic M5 OHLC bars using a log-return random walk."""
    close = start_price
    bars = []
    for _ in range(n):
        ret = random.gauss(drift, volatility)
        close = close * (1.0 + ret)
        wick = abs(ret * close) * 0.5
        o = close - ret * close * 0.3
        h = max(o, close) + wick
        l = min(o, close) - wick
        vol = max(10, int(random.gauss(200, 80)))
        bars.append({
            "open": round(o, 2), "high": round(h, 2),
            "low": round(l, 2), "close": round(close, 2),
            "tick_volume": vol,
        })
    return bars


def aggregate_bars(m5_bars: list[dict], period: int) -> list[dict]:
    """Aggregate M5 bars into higher-timeframe bars."""
    aggregated = []
    for i in range(0, len(m5_bars) - period + 1, period):
        chunk = m5_bars[i:i + period]
        aggregated.append({
            "open": chunk[0]["open"],
            "high": max(b["high"] for b in chunk),
            "low": min(b["low"] for b in chunk),
            "close": chunk[-1]["close"],
            "tick_volume": sum(b["tick_volume"] for b in chunk),
        })
    return aggregated


# ---------------------------------------------------------------------------
# Step 2: create labels (future price direction)
# ---------------------------------------------------------------------------
def make_labels(bars: list[dict], horizon: int = 5, threshold: float = 0.001):
    closes = np.array([b["close"] for b in bars])
    labels = np.zeros(len(closes), dtype=int)
    for i in range(len(closes) - horizon):
        ret = (closes[i + horizon] - closes[i]) / closes[i]
        if ret > threshold:
            labels[i] = 2  # buy
        elif ret < -threshold:
            labels[i] = 1  # sell
        else:
            labels[i] = 0  # hold
    return labels


# ---------------------------------------------------------------------------
# Step 3: build feature matrix with multi-TF data
# ---------------------------------------------------------------------------
def build_features(m5: list[dict], h1: list[dict], h4: list[dict], fe: FeatureEngine):
    """Build feature matrix, mapping M5 index to corresponding H1/H4 windows."""
    X_list, y_list = [], []
    labels = make_labels(m5)

    for i in range(LOOKBACK, len(m5)):
        m5_window = m5[i - LOOKBACK:i + 1]

        # find last completed H1 bar index for this M5 bar
        h1_idx = i // M5_PER_H1 - 1
        h1_window = h1[max(0, h1_idx - 20):h1_idx + 1] if h1_idx >= 0 else []

        # find last completed H4 bar index for this M5 bar
        h4_idx = i // M5_PER_H4 - 1
        h4_window = h4[max(0, h4_idx - 10):h4_idx + 1] if h4_idx >= 0 else []

        features = fe.compute(m5_window, h1_window if len(h1_window) >= 3 else None,
                              h4_window if len(h4_window) >= 3 else None)
        if features:
            X_list.append([features.get(k, 0.0) for k in FEATURE_ORDER])
            y_list.append(labels[i])

    return np.array(X_list), np.array(y_list)


# ---------------------------------------------------------------------------
# Step 4: backtest with multi-TF data
# ---------------------------------------------------------------------------
def run_backtest(m5: list[dict], h1: list[dict], h4: list[dict],
                 predictor: MLPredictor, fe: FeatureEngine):
    pip_mult = 10 ** (-config.SYMBOL_DIGITS)
    trades = []

    for i in range(LOOKBACK, len(m5) - 10):
        m5_window = m5[i - LOOKBACK:i + 1]

        h1_idx = i // M5_PER_H1 - 1
        h1_window = h1[max(0, h1_idx - 20):h1_idx + 1] if h1_idx >= 0 else []

        h4_idx = i // M5_PER_H4 - 1
        h4_window = h4[max(0, h4_idx - 10):h4_idx + 1] if h4_idx >= 0 else []

        features = fe.compute(m5_window, h1_window if len(h1_window) >= 3 else None,
                              h4_window if len(h4_window) >= 3 else None)
        if not features:
            continue
        features["close"] = m5[i]["close"]
        action, conf = predictor.predict(features)
        if action == "hold":
            continue

        entry = m5[i]["close"]
        sl = entry - config.SL_PIPS * pip_mult if action == "buy" else entry + config.SL_PIPS * pip_mult
        tp = entry + config.TP_PIPS * pip_mult if action == "buy" else entry - config.SL_PIPS * pip_mult

        exit_price = None
        for j in range(i + 1, min(i + 200, len(m5))):
            h, l = m5[j]["high"], m5[j]["low"]
            if action == "buy":
                if l <= sl:
                    exit_price = sl; break
                if h >= tp:
                    exit_price = tp; break
            else:
                if h >= sl:
                    exit_price = sl; break
                if l <= tp:
                    exit_price = tp; break
        if exit_price is None:
            exit_price = m5[min(i + 199, len(m5) - 1)]["close"]

        pnl = exit_price - entry if action == "buy" else entry - exit_price
        trades.append({
            "entry_idx": i, "action": action, "confidence": conf,
            "entry": entry, "exit": exit_price, "pnl": pnl,
        })

    if not trades:
        return pd.DataFrame(), 0, 0.0
    results = pd.DataFrame(trades)
    return results, (results["pnl"] > 0).mean(), results["pnl"].sum()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 58)
    print("  XAUUSD Gold Trading — Quickstart (multi-timeframe)")
    print("=" * 58)

    # Generate data
    print("\n[1/4] Generating synthetic bars...")
    m5 = generate_m5_bars(5000, start_price=2650.0)
    h1 = aggregate_bars(m5, M5_PER_H1)
    h4 = aggregate_bars(m5, M5_PER_H4)
    print(f"  → M5: {len(m5)} bars  |  H1: {len(h1)} bars  |  H4: {len(h4)} bars")
    print(f"     (~{len(m5) * 5 / 60:.0f} trading hours total)")

    # Build features
    print("\n[2/4] Computing features (multi-TF)...")
    fe = FeatureEngine(lookback=LOOKBACK)
    X, y = build_features(m5, h1, h4, fe)
    unique, counts = np.unique(y, return_counts=True)
    dist = dict(zip(["hold", "sell", "buy"], counts))
    print(f"  → {len(X)} samples, class distribution: {dist}")

    # Show trend feature stats
    h1_vals, h4_vals = X[:, FEATURE_ORDER.index("h1_trend")], X[:, FEATURE_ORDER.index("h4_trend")]
    print(f"  → h1_trend  mean={h1_vals.mean():.3f}  std={h1_vals.std():.3f}  |  "
          f"h4_trend  mean={h4_vals.mean():.3f}  std={h4_vals.std():.3f}")

    # Train
    print("\n[3/4] Training XGBoost model...")
    import xgboost as xgb
    model = xgb.XGBClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.05,
        objective="multi:softprob", num_class=3, random_state=42,
    )
    model.fit(X, y, verbose=False)

    # Persist model to configured path
    os.makedirs(os.path.dirname(config.MODEL_PATH), exist_ok=True)
    model.save_model(config.MODEL_PATH)
    print(f"  -> Model saved to {config.MODEL_PATH}")

    with tempfile.TemporaryDirectory() as tmp:
        model_path = os.path.join(tmp, "model.json")
        model.save_model(model_path)
        predictor = MLPredictor(model_path=model_path)
        print(f"  → Model trained and loaded: {len(FEATURE_ORDER)} features")

        # Backtest
        print("\n[4/4] Running backtest (multi-TF)...")
        results, win_rate, total_pnl = run_backtest(m5, h1, h4, predictor, fe)

        print("\n" + "=" * 58)
        print("  BACKTEST RESULTS")
        print("=" * 58)
        print(f"  Total trades : {len(results)}")
        print(f"  Win rate     : {win_rate:.1%}")
        print(f"  Total P&L    : {total_pnl:+.2f} USD")
        if len(results) > 0:
            print(f"  Avg P&L/trade: {results['pnl'].mean():+.4f} USD")
            print(f"  Buy trades   : {(results['action'] == 'buy').sum()}")
            print(f"  Sell trades  : {(results['action'] == 'sell').sum()}")
            cum = results["pnl"].cumsum()
            dd = (cum - cum.cummax()).min()
            print(f"  Max drawdown : {dd:+.2f} USD")

            # Equity curve snippet
            print(f"\n  Equity curve (last 10 trades):")
            for _, row in results.tail(10).iterrows():
                bar = "+" if row["pnl"] > 0 else "-"
                print(f"    {row['action']:>4}  entry={row['entry']:7.2f}  "
                      f"exit={row['exit']:7.2f}  pnl={row['pnl']:+7.4f}  {bar}")
        print("=" * 58)


if __name__ == "__main__":
    main()
