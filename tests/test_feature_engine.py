import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))

from feature_engine import FeatureEngine


def make_bars(n=60, base=2650.0):
    bars = []
    for i in range(n):
        o = base + i * 0.5
        bars.append({
            "open": o,
            "high": o + 2,
            "low": o - 1,
            "close": o + 1,
            "tick_volume": 100,
        })
    return bars


def test_feature_engine_returns_all_features():
    fe = FeatureEngine(lookback=50)
    bars = make_bars(60)
    features = fe.compute(bars)
    expected = {"ret_1", "ret_5", "ret_20", "rsi", "ema_ratio", "macd",
                "bb_pos", "atr", "high_low_range", "vol_ratio", "h1_trend", "h4_trend"}
    for key in expected:
        assert key in features, f"Missing feature: {key}"
    assert 0 <= features["rsi"] <= 100


def test_feature_engine_insufficient_bars():
    fe = FeatureEngine(lookback=50)
    bars = make_bars(30)
    features = fe.compute(bars)
    assert features == {}


def test_trend_score_from_h1_h4_bars():
    fe = FeatureEngine(lookback=10)
    m5_bars = make_bars(60, base=2650.0)

    # uptrend bars: price consistently rising
    up_bars = [{"open": 2600 + i, "high": 2602 + i, "low": 2599 + i, "close": 2601 + i, "tick_volume": 100} for i in range(20)]
    # downtrend bars: price consistently falling
    down_bars = [{"open": 2700 - i, "high": 2702 - i, "low": 2699 - i, "close": 2701 - i, "tick_volume": 100} for i in range(15)]

    features = fe.compute(m5_bars, up_bars, down_bars)
    assert features["h1_trend"] > 0, f"Expected positive H1 trend, got {features['h1_trend']}"
    assert features["h4_trend"] < 0, f"Expected negative H4 trend, got {features['h4_trend']}"


def test_trend_score_fallback_to_zero_when_no_bars():
    fe = FeatureEngine(lookback=50)
    bars = make_bars(60)
    features = fe.compute(bars)
    assert features["h1_trend"] == 0.0
    assert features["h4_trend"] == 0.0


def test_rsi_extreme_values():
    fe = FeatureEngine(lookback=10)
    # All up: RSI should be 100
    up_bars = [{"open": 100 + i, "high": 102 + i, "low": 99 + i, "close": 101 + i, "tick_volume": 100} for i in range(30)]
    features_up = fe.compute(up_bars)
    assert features_up["rsi"] == 100.0

    # All down: RSI should be 0
    down_bars = [{"open": 200 - i, "high": 202 - i, "low": 199 - i, "close": 201 - i, "tick_volume": 100} for i in range(30)]
    features_down = fe.compute(down_bars)
    assert features_down["rsi"] == 0.0
