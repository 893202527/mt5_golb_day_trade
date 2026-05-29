"""Train XGBoost model from PostgreSQL OHLC data with multi-timeframe features."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))

import numpy as np
import xgboost as xgb
from db import get_conn
from feature_engine import FeatureEngine, FEATURE_ORDER
from ml_model import MLPredictor

LOOKBACK = 50
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
    """Return the most recent completed higher-TF bars before m5_bar_time."""
    completed = [b for b in htf_bars if b["bar_time"] < m5_bar_time]
    if len(completed) < 3:
        return None
    return completed[-lookback:]


def create_labels(closes: np.ndarray, horizon: int = 5) -> np.ndarray:
    labels = np.zeros(len(closes), dtype=int)
    for i in range(len(closes) - horizon):
        future_ret = (closes[i + horizon] - closes[i]) / closes[i]
        if future_ret > 0.001:
            labels[i] = 2  # buy
        elif future_ret < -0.001:
            labels[i] = 1  # sell
        else:
            labels[i] = 0  # hold
    return labels


def main():
    print("[train] loading data...")
    m5_bars = load_bars("XAUUSD", "M5")
    h1_bars = load_bars("XAUUSD", "H1")
    h4_bars = load_bars("XAUUSD", "H4")

    if len(m5_bars) < LOOKBACK + 20:
        print(f"[train] insufficient M5 data: {len(m5_bars)} rows (need at least {LOOKBACK + 20})")
        return

    print(f"[train] M5: {len(m5_bars)} bars, H1: {len(h1_bars)} bars, H4: {len(h4_bars)} bars")

    closes = np.array([b["close"] for b in m5_bars])
    labels = create_labels(closes)
    fe = FeatureEngine(lookback=LOOKBACK)

    X_list, y_list = [], []
    for i in range(LOOKBACK, len(m5_bars)):
        m5_window = m5_bars[i - LOOKBACK : i + 1]
        h1_window = get_htf_window(h1_bars, m5_bars[i]["bar_time"], H1_LOOKBACK)
        h4_window = get_htf_window(h4_bars, m5_bars[i]["bar_time"], H4_LOOKBACK)
        features = fe.compute(m5_window, h1_window, h4_window)
        if features:
            X_list.append([features.get(k, 0.0) for k in FEATURE_ORDER])
            y_list.append(labels[i])

    X = np.array(X_list)
    y = np.array(y_list)
    dist = dict(zip(["hold", "sell", "buy"], np.bincount(y, minlength=3)))
    print(f"[train] {len(X)} samples, class dist: {dist}")

    model = xgb.XGBClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.05,
        objective="multi:softprob", num_class=3, random_state=42,
    )
    model.fit(X, y, eval_set=[(X, y)], verbose=False)

    mp = MLPredictor()
    mp.save(model)
    print(f"[train] model saved to {mp.model_path}")


if __name__ == "__main__":
    main()
