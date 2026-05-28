"""Offline backtest of the ML signal pipeline using OHLC data from PostgreSQL."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))

import pandas as pd
import config
from db import get_conn
from feature_engine import FeatureEngine
from ml_model import MLPredictor

LOOKBACK = config.FEATURE_LOOKBACK


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
    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM ohlc WHERE symbol='XAUUSD' AND timeframe='M5' ORDER BY bar_time ASC",
            conn,
        )

    if len(df) < LOOKBACK + 20:
        print(f"Insufficient data: {len(df)} rows")
        return

    fe = FeatureEngine(lookback=LOOKBACK)
    predictor = MLPredictor()
    trades = []
    bars = df.to_dict("records")

    pip_mult = 10 ** (-config.SYMBOL_DIGITS)
    for i in range(LOOKBACK, len(bars)):
        window = bars[i - LOOKBACK : i + 1]
        features = fe.compute(window)
        if not features:
            continue

        features["close"] = bars[i]["close"]
        action, conf = predictor.predict(features)
        if action == "hold":
            continue

        close = bars[i]["close"]
        sl = close - config.SL_PIPS * pip_mult if action == "buy" else close + config.SL_PIPS * pip_mult
        tp = close + config.TP_PIPS * pip_mult if action == "buy" else close - config.TP_PIPS * pip_mult

        exit_price, profit = simulate_exit(bars, i, action, sl, tp)
        trades.append({
            "entry_time": bars[i]["bar_time"],
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
