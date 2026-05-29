import os
import pickle
import numpy as np
import config
from feature_engine import FEATURE_ORDER


class MLPredictor:
    def __init__(self, model_path=None):
        self.model_path = model_path or config.MODEL_PATH
        self.model = None
        self._load()

    def _load(self):
        if os.path.exists(self.model_path):
            ext = os.path.splitext(self.model_path)[1]
            if ext == ".json":
                import xgboost as xgb
                self.model = xgb.XGBClassifier()
                self.model.load_model(self.model_path)
            elif ext == ".pkl":
                with open(self.model_path, "rb") as f:
                    self.model = pickle.load(f)

    def predict(self, features: dict) -> tuple:
        if self.model is None:
            return ("hold", 0.0)
        X = np.array([[features.get(k, 0.0) for k in FEATURE_ORDER]])
        proba = self.model.predict_proba(X)[0]
        idx = int(proba.argmax())
        confidence = float(proba.max())
        if confidence < config.ML_CONFIDENCE_THRESHOLD:
            return ("hold", confidence)
        if len(proba) == 2:
            return ("buy" if idx == 1 else "sell", confidence)
        labels = {0: "hold", 1: "sell", 2: "buy"}
        return (labels.get(idx, "hold"), confidence)

    def save(self, model, path=None):
        target = path or self.model_path
        os.makedirs(os.path.dirname(target), exist_ok=True)
        model.save_model(target)

    def is_loaded(self) -> bool:
        return self.model is not None
