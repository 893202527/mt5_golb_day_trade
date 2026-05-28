import os
import sys
import tempfile
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))


def test_predict_no_model_returns_hold():
    from ml_model import MLPredictor
    predictor = MLPredictor(model_path="/nonexistent/model.json")
    action, conf = predictor.predict({})
    assert action == "hold"
    assert conf == 0.0
    assert not predictor.is_loaded()


def test_predict_with_model():
    import xgboost as xgb
    from ml_model import MLPredictor
    X = np.random.rand(100, 12)
    y = np.random.choice([0, 1, 2], 100)
    model = xgb.XGBClassifier(n_estimators=10, max_depth=3, random_state=42)
    model.fit(X, y)

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test_model.json")
        model.save_model(path)
        predictor = MLPredictor(model_path=path)
        assert predictor.is_loaded()

        features = {k: 0.0 for k in [
            "ret_1", "ret_5", "ret_20", "rsi", "ema_ratio", "macd",
            "bb_pos", "atr", "high_low_range", "vol_ratio", "h1_trend", "h4_trend"
        ]}
        action, conf = predictor.predict(features)
        assert action in ("buy", "sell", "hold")
        assert 0.0 <= conf <= 1.0


def test_confidence_threshold_respected():
    import xgboost as xgb
    from ml_model import MLPredictor
    import ai.config as cfg
    cfg.ML_CONFIDENCE_THRESHOLD = 0.99

    X = np.random.rand(50, 12)
    y = np.random.choice([0, 1, 2], 50)
    model = xgb.XGBClassifier(n_estimators=5, max_depth=2, random_state=42)
    model.fit(X, y)

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test_model.json")
        model.save_model(path)
        predictor = MLPredictor(model_path=path)
        assert predictor.is_loaded()

        features = {k: 0.0 for k in [
            "ret_1", "ret_5", "ret_20", "rsi", "ema_ratio", "macd",
            "bb_pos", "atr", "high_low_range", "vol_ratio", "h1_trend", "h4_trend"
        ]}
        action, conf = predictor.predict(features)
        assert action == "hold"
