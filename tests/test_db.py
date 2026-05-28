import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))

import pytest

# NOTE: These tests require a running PostgreSQL with a mt5_gold_test database.
# Skip them if PostgreSQL is not available.
pytestmark = pytest.mark.skip(reason="Requires PostgreSQL running locally")

def test_insert_and_read_ohlc():
    from db import insert_ohlc, get_recent_bars
    row = {"symbol": "XAUUSD", "tf": "M5", "time": "2026-05-28T10:00:00+00:00",
           "open": 2650.0, "high": 2652.0, "low": 2649.0, "close": 2651.0, "volume": 100, "spread": 28}
    insert_ohlc(row)
    bars = get_recent_bars("XAUUSD", "M5", limit=10)
    assert len(bars) >= 1
    assert bars[-1]["close"] == 2651.0
