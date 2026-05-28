"""Train XGBoost model from PostgreSQL OHLC data."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))

import numpy as np
import pandas as pd
import xgboost as xgb
from db import get_conn
from feature_engine import FeatureEngine, FEATURE_ORDER
from ml_model import MLPredictor

LOOKBACK = 50


def load_data(symbol="XAUUSD", tf="M5"):
    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM ohlc WHERE symbol=%s AND timeframe=%s ORDER BY bar_time ASC",
            conn, params=(symbol, tf),
        )
    return df


def create_labels(df: pd.DataFrame, horizon: int = 5) -> np.ndarray:
    closes = df["close"].values
    labels = np.zeros(len(closes), dtype=int)
    for i in range(len(closes) - horizon):
        future_ret = (closes[i + horizon] - closes[i]) / closes[i]
        threshold = 0.001
        if future_ret > threshold:
            labels[i] = 2  # buy
        elif future_ret < -threshold:
            labels[i] = 1  # sell
        else:
            labels[i] = 0  # hold
    return labels


def main():
    print("[train] loading data...")
    df = load_data()
    if len(df) < LOOKBACK + 20:
        print(f"[train] insufficient data: {len(df)} rows (need at least {LOOKBACK + 20})")
        return

    labels = create_labels(df)
    fe = FeatureEngine(lookback=LOOKBACK)

    X_list, y_list = [], []
    bars_dicts = df.to_dict("records")
    for i in range(LOOKBACK, len(bars_dicts)):
        window = bars_dicts[i - LOOKBACK : i + 1]
        features = fe.compute(window)
        if features:
            X_list.append([features.get(k, 0.0) for k in FEATURE_ORDER])
            y_list.append(labels[i])

    X = np.array(X_list)
    y = np.array(y_list)
    print(f"[train] {len(X)} samples, class dist: {dict(zip(*np.unique(y, return_counts=True)))}")

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
