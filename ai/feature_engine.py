import numpy as np
import pandas as pd

FEATURE_ORDER = [
    "ret_1", "ret_5", "ret_20", "rsi", "ema_ratio", "macd",
    "bb_pos", "atr", "high_low_range", "vol_ratio", "h1_trend", "h4_trend",
]


class FeatureEngine:
    def __init__(self, lookback=50):
        self.lookback = lookback

    def compute(self, bars: list[dict], h1_bars: list[dict] | None = None, h4_bars: list[dict] | None = None) -> dict:
        if len(bars) < self.lookback + 1:
            return {}
        df = pd.DataFrame(bars)
        closes = df["close"].values.astype(float)
        highs = df["high"].values.astype(float)
        lows = df["low"].values.astype(float)
        volumes = df.get("tick_volume", df.get("volume"))
        if volumes is None:
            volumes = np.ones_like(closes)
        else:
            volumes = volumes.values.astype(float)

        features = {}
        features["ret_1"] = (closes[-1] - closes[-2]) / closes[-2] if closes[-2] != 0 else 0.0
        features["ret_5"] = (closes[-1] - closes[-6]) / closes[-6] if len(closes) > 5 and closes[-6] != 0 else 0.0
        features["ret_20"] = (closes[-1] - closes[-21]) / closes[-21] if len(closes) > 20 and closes[-21] != 0 else 0.0
        features["rsi"] = self._rsi(closes, 14)
        ema20 = self._ema(closes, 20)
        ema50 = self._ema(closes, 50)
        features["ema_ratio"] = ema20 / ema50 if ema50 > 0 else 1.0
        features["macd"] = self._macd(closes)
        sma20 = np.mean(closes[-20:]) if len(closes) >= 20 else 0.0
        std20 = np.std(closes[-20:]) if len(closes) >= 20 else 1.0
        features["bb_pos"] = float((closes[-1] - sma20) / std20) if std20 > 0 else 0.0
        features["atr"] = self._atr(highs, lows, closes, 14)
        features["high_low_range"] = float((highs[-1] - lows[-1]) / closes[-1]) if closes[-1] != 0 else 0.0
        vol_mean = np.mean(volumes[-20:]) if len(volumes) >= 20 else 1.0
        features["vol_ratio"] = float(volumes[-1] / vol_mean) if vol_mean > 0 else 1.0
        features["h1_trend"] = self._trend_score(h1_bars) if h1_bars else 0.0
        features["h4_trend"] = self._trend_score(h4_bars) if h4_bars else 0.0
        return features

    def _rsi(self, closes: np.ndarray, period: int) -> float:
        if len(closes) < period + 1:
            return 50.0
        deltas = np.diff(closes[-(period + 1):])
        gains = np.sum(deltas[deltas > 0])
        losses = -np.sum(deltas[deltas < 0])
        avg_gain = gains / period
        avg_loss = losses / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100.0 - (100.0 / (1.0 + rs)))

    def _ema(self, data: np.ndarray, period: int) -> float:
        if len(data) < period:
            return float(np.mean(data))
        return float(pd.Series(data).ewm(span=period, adjust=False).mean().iloc[-1])

    def _macd(self, closes: np.ndarray) -> float:
        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        return float(ema12 - ema26)

    def _trend_score(self, bars: list[dict]) -> float:
        """Compute a directional trend score from bars. Positive=uptrend, negative=downtrend."""
        if len(bars) < 3:
            return 0.0
        closes = np.array([b["close"] for b in bars], dtype=float)
        short_ema = self._ema(closes, min(4, len(closes)))
        long_ema = self._ema(closes, min(12, len(closes)))
        if long_ema == 0:
            return 0.0
        return float((short_ema / long_ema) - 1.0) * 100

    def _atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> float:
        if len(closes) < period + 1:
            return 0.0
        trs = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)
        return float(np.mean(trs[-period:])) if trs else 0.0
