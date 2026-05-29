"""Train and backtest on real XAUUSD daily data (from akshare)."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))

import numpy as np
import pandas as pd
import xgboost as xgb
from feature_engine import FeatureEngine, FEATURE_ORDER
from ml_model import MLPredictor
import config

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "features", "xauusd_daily.csv")
LOOKBACK = config.FEATURE_LOOKBACK


def main():
    df = pd.read_csv(DATA_FILE, parse_dates=["bar_time"])
    print(f"Loaded {len(df)} daily bars | {df.bar_time.iloc[0].date()} ~ {df.bar_time.iloc[-1].date()}")

    # Create labels: 3-day forward return, 0.5% threshold
    closes = df["close"].values
    labels = np.zeros(len(closes), dtype=int)
    horizon = 3
    threshold = 0.005
    for i in range(len(closes) - horizon):
        ret = (closes[i + horizon] - closes[i]) / closes[i]
        if ret > threshold:
            labels[i] = 2  # buy
        elif ret < -threshold:
            labels[i] = 1  # sell
        else:
            labels[i] = 0  # hold

    # Build features
    bars = df.to_dict("records")
    fe = FeatureEngine(lookback=LOOKBACK)
    X_list, y_list = [], []
    for i in range(LOOKBACK, len(bars)):
        window = bars[i - LOOKBACK : i + 1]
        features = fe.compute(window)
        if features:
            X_list.append([features.get(k, 0.0) for k in FEATURE_ORDER])
            y_list.append(labels[i])

    X, y = np.array(X_list), np.array(y_list)
    dist = dict(zip(["hold", "sell", "buy"], np.bincount(y, minlength=3)))
    print(f"Features: {X.shape}, class dist: {dist}\n")

    # Train-test split by time (80/20)
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    test_bars = bars[LOOKBACK + split:]

    model = xgb.XGBClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.05,
        objective="multi:softprob", num_class=3, random_state=42,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    # Evaluate
    from sklearn.metrics import classification_report
    y_pred = model.predict(X_test)
    print("Classification Report (test set):")
    print(classification_report(y_test, y_pred, target_names=["hold", "sell", "buy"], zero_division=0))

    # Save model
    os.makedirs(os.path.dirname(config.MODEL_PATH), exist_ok=True)
    model.save_model(config.MODEL_PATH)
    print(f"Model saved to {config.MODEL_PATH}")

    # Backtest with daily-appropriate SL/TP (based on ATR)
    predictor = MLPredictor(model_path=config.MODEL_PATH)
    trades = []

    for idx, i in enumerate(range(len(test_bars) - 10)):
        bar = test_bars[i]
        features = fe.compute(test_bars[max(0, i - LOOKBACK):i + 1])
        if not features:
            continue
        features["close"] = bar["close"]
        action, conf = predictor.predict(features)
        if action == "hold":
            continue

        entry = bar["close"]
        # Daily ATR-based stops: ~$50 SL, ~$100 TP
        atr_val = features.get("atr", entry * 0.01)
        sl = entry - atr_val if action == "buy" else entry + atr_val
        tp = entry + atr_val * 2 if action == "buy" else entry - atr_val * 2

        exit_price = None
        for j in range(i + 1, min(i + 200, len(test_bars))):
            h, l = test_bars[j]["high"], test_bars[j]["low"]
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
            exit_price = test_bars[min(i + 199, len(test_bars) - 1)]["close"]

        pnl = exit_price - entry if action == "buy" else entry - exit_price
        trades.append({"entry_idx": i, "action": action, "entry": entry,
                        "exit": exit_price, "pnl": pnl, "conf": conf})

    if not trades:
        print("No trades generated")
        return

    results = pd.DataFrame(trades)
    print(f"\nBacktest (test period, {len(results)} trades):")
    print(f"  Win rate:     {(results.pnl > 0).mean():.1%}")
    print(f"  Total P&L:    {results.pnl.sum():+.2f}")
    print(f"  Avg P&L:      {results.pnl.mean():+.4f}")
    print(f"  Max drawdown: {(results.pnl.cumsum() - results.pnl.cumsum().cummax()).min():+.2f}")
    print(f"  Buy: {sum(results.action == 'buy')}  Sell: {sum(results.action == 'sell')}")


if __name__ == "__main__":
    main()
