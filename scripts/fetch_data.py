"""Fetch real gold historical data (works in China via Sina/akshare)."""
import os
import akshare as ak
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "features")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    # Daily bars from Sina Finance (COMEX gold futures, close proxy for XAUUSD)
    print("[1/2] Downloading daily bars (COMEX XAU, 2006–today) ...")
    df = ak.futures_foreign_hist(symbol="XAU")
    df = df.rename(columns={"date": "bar_time", "volume": "tick_volume"})
    df = df[["bar_time", "open", "high", "low", "close", "tick_volume"]]
    path = os.path.join(DATA_DIR, "xauusd_daily.csv")
    df.to_csv(path, index=False)
    print(f"  -> {len(df)} daily bars saved to {path}")

    # Aggregate H4 from daily (4-day bars)
    print("[2/2] Aggregating pseudo-intraday from daily ...")
    df["bar_time"] = pd.to_datetime(df["bar_time"])
    df.set_index("bar_time", inplace=True)
    h4 = df.resample("4D").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "tick_volume": "sum",
    }).dropna().reset_index()
    h4["bar_time"] = h4["bar_time"].astype(str)
    h4_path = os.path.join(DATA_DIR, "xauusd_h4.csv")
    h4.to_csv(h4_path, index=False)
    print(f"  -> {len(h4)} pseudo-H4 bars saved to {h4_path}")

    print(f"\nDone. Files in {DATA_DIR}/")


if __name__ == "__main__":
    main()
