import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))


def test_handle_query_insufficient_data(monkeypatch):
    os.environ["LLM_ENABLED"] = "false"
    import config
    config.LLM_ENABLED = False

    def mock_get_bars(symbol, tf, limit):
        return []  # empty = insufficient data

    import server
    monkeypatch.setattr(server, "get_recent_bars", mock_get_bars)
    resp = server.handle_query({"symbol": "XAUUSD", "tf": "M5"})
    assert resp["action"] == "hold"
    assert "insufficient" in resp["reason"].lower()


def test_handle_ohlc_no_error(monkeypatch):
    called = []

    def mock_insert(row):
        called.append(row)

    import server
    monkeypatch.setattr(server, "insert_ohlc", mock_insert)

    data = {
        "type": "ohlc", "symbol": "XAUUSD", "tf": "M5",
        "time": "2026-05-28T10:00:00",
        "open": 2650.0, "high": 2652.0, "low": 2649.0, "close": 2651.0,
        "tick_volume": 100, "spread": 28,
    }
    server.handle_ohlc(data)
    assert len(called) == 1
    assert called[0]["symbol"] == "XAUUSD"
    assert called[0]["close"] == 2651.0


def test_handle_query_with_data_returns_hold_when_no_model(monkeypatch):
    """Without a trained model, predictor returns hold."""
    os.environ["LLM_ENABLED"] = "false"
    import config
    config.LLM_ENABLED = False
    config.ML_CONFIDENCE_THRESHOLD = 0.0

    bars = [
        {"open": 2650 + i, "high": 2652 + i, "low": 2649 + i, "close": 2651 + i, "tick_volume": 100, "bar_time": f"2026-05-28T{i:02d}:00:00"}
        for i in range(60)
    ]

    def mock_get_bars(symbol, tf, limit):
        return bars

    import server
    monkeypatch.setattr(server, "get_recent_bars", mock_get_bars)

    # Replace server's module-level predictor with a no-model version
    from ml_model import MLPredictor
    predictor_no_model = MLPredictor(model_path="/nonexistent/model.json")
    monkeypatch.setattr(server, "predictor", predictor_no_model)

    resp = server.handle_query({"symbol": "XAUUSD", "tf": "M5"})
    assert resp["action"] == "hold"
    assert resp["confidence"] == 0.0
