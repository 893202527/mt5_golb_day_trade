"""Train XGBoost regressor on gold daily data — predict future return, trade on sign."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV
from sklearn.metrics import classification_report
from feature_engine import FeatureEngine, FEATURE_ORDER
import config

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "features", "xauusd_daily.csv")
LOOKBACK = config.FEATURE_LOOKBACK


def add_lags(df: pd.DataFrame, lags=(1, 2, 3, 5, 10, 20)) -> pd.DataFrame:
    """Add lagged returns as extra features."""
    df = df.copy()
    df["ret"] = df["close"].pct_change()
    for lag in lags:
        df[f"lag_{lag}"] = df["ret"].shift(lag)
    return df.dropna()


def main():
    df = pd.read_csv(DATA_FILE, parse_dates=["bar_time"])
    df = add_lags(df)
    print(f"Loaded {len(df)} bars: {df.bar_time.iloc[0].date()} ~ {df.bar_time.iloc[-1].date()}")

    closes = df["close"].values
    horizon = 3
    future_ret = np.array([(closes[i + horizon] - closes[i]) / closes[i]
                           for i in range(len(closes) - horizon)] + [0.0] * horizon)

    bars = df.to_dict("records")
    fe = FeatureEngine(lookback=LOOKBACK)

    LAG_NAMES = [f"lag_{lag}" for lag in [1, 2, 3, 5, 10, 20]]
    ALL_FEATURES = FEATURE_ORDER + LAG_NAMES

    X_list = []
    for i in range(LOOKBACK, len(bars)):
        window = bars[i - LOOKBACK : i + 1]
        tech_feats = fe.compute(window)
        if not tech_feats:
            continue
        tech_vec = [tech_feats.get(k, 0.0) for k in FEATURE_ORDER]
        lag_vec = [float(bars[i].get(k)) if not pd.isna(bars[i].get(k)) else 0.0 for k in LAG_NAMES]
        X_list.append(tech_vec + lag_vec)

    X = np.array(X_list)
    y = future_ret[LOOKBACK:LOOKBACK + len(X_list)]

    # 3-class: predict if return will be >+1.5%, <-1.5%, or in between
    # This targets "swing" moves, not everyday noise
    y_class = np.zeros(len(y), dtype=int)
    y_class[y > 0.015] = 2   # strong up
    y_class[y < -0.015] = 1  # strong down
    # else 0 = sideways

    print(f"Samples: {X.shape}, features: {X.shape[1]}")
    print(f"Target dist: up={sum(y_class==2)} ({sum(y_class==2)/len(y):.1%})  "
          f"down={sum(y_class==1)} ({sum(y_class==1)/len(y):.1%})  "
          f"sideways={sum(y_class==0)} ({sum(y_class==0)/len(y):.1%})")

    # Train/test split
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y_class[:split], y_class[split:]
    test_bars = bars[LOOKBACK + split:]

    # 3-class model with balanced class weights
    tscv = TimeSeriesSplit(n_splits=3)
    clf = xgb.XGBClassifier(
        n_estimators=300, random_state=42, objective="multi:softprob", num_class=3,
    )
    param_grid = {
        "max_depth": [3, 5],
        "learning_rate": [0.03, 0.05],
        "subsample": [0.8, 1.0],
    }
    grid = GridSearchCV(clf, param_grid, cv=tscv, scoring="f1_weighted", verbose=1, n_jobs=1)
    grid.fit(X_train, y_train)
    print(f"\nBest: {grid.best_params_}  CV f1: {grid.best_score_:.3f}\n")

    best = grid.best_estimator_
    best.set_params(n_estimators=500, early_stopping_rounds=30)
    best.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_pred = best.predict(X_test)
    print("Classification Report:")
    print(classification_report(y_test, y_pred, target_names=["sideways", "strong_down", "strong_up"], zero_division=0))

    # Importance
    importance = sorted(zip(ALL_FEATURES, best.feature_importances_), key=lambda x: -x[1])
    print("Top features:")
    for name, imp in importance[:10]:
        print(f"  {name:20s} {imp:.4f}")

    # Save for use with MLPredictor
    os.makedirs(os.path.dirname(config.MODEL_PATH), exist_ok=True)
    best.save_model(config.MODEL_PATH)
    print(f"\nModel saved to {config.MODEL_PATH}")

    # Backtest: only trade strong signals (class 1 or 2)
    fe2 = FeatureEngine(lookback=LOOKBACK)
    trades = []
    for i in range(len(test_bars) - 10):
        bar = test_bars[i]
        tech_feats = fe2.compute(test_bars[max(0, i - LOOKBACK):i + 1])
        if not tech_feats:
            continue
        tech_vec = [tech_feats.get(k, 0.0) for k in FEATURE_ORDER]
        lag_vec = [float(test_bars[i].get(k)) if not pd.isna(test_bars[i].get(k)) else 0.0 for k in LAG_NAMES]
        X_row = np.array(tech_vec + lag_vec).reshape(1, -1)
        proba = best.predict_proba(X_row)[0]
        pred_cls = proba.argmax()
        if pred_cls == 0:  # sideways
            continue
        action = "buy" if pred_cls == 2 else "sell"
        conf = float(proba.max())

        entry = bar["close"]
        atr_val = abs(bar["high"] - bar["low"]) or entry * 0.01
        sl = entry - atr_val if action == "buy" else entry + atr_val
        tp = entry + atr_val * 2 if action == "buy" else entry - atr_val * 2

        exit_price = None
        for j in range(i + 1, min(i + 200, len(test_bars))):
            h, l = test_bars[j]["high"], test_bars[j]["low"]
            if action == "buy":
                if l <= sl: exit_price = sl; break
                if h >= tp: exit_price = tp; break
            else:
                if h >= sl: exit_price = sl; break
                if l <= tp: exit_price = tp; break
        if exit_price is None:
            exit_price = test_bars[min(i + 199, len(test_bars) - 1)]["close"]
        pnl = exit_price - entry if action == "buy" else entry - exit_price
        trades.append({"action": action, "entry": entry, "exit": exit_price,
                        "pnl": pnl, "conf": conf})

    if not trades:
        print("\nNo trades — model didn't predict any strong moves in test period")
        return
    results = pd.DataFrame(trades)
    print(f"\nBacktest ({len(results)} trades, strong-signal only):")
    print(f"  Win rate:  {(results.pnl > 0).mean():.1%}")
    print(f"  Total P&L: {results.pnl.sum():+.2f}")
    print(f"  Avg P&L:   {results.pnl.mean():+.4f}")
    cum = results.pnl.cumsum()
    dd = (cum - cum.cummax()).min()
    print(f"  Max DD:    {dd:+.2f}")
    print(f"  Buy: {sum(results.action == 'buy')}  Sell: {sum(results.action == 'sell')}")


if __name__ == "__main__":
    main()
