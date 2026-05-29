import numpy as np
import pandas as pd

FEATURE_ORDER = [
    "ret_1", "ret_5", "ret_20", "rsi", "ema_ratio", "macd",
    "bb_pos", "atr", "high_low_range", "vol_ratio",
    "h1_trend", "h4_trend",
    "adx_14", "stoch_k", "volatility_20", "sma_ratio", "volume_sma",
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
        features["adx_14"] = self._adx(highs, lows, closes, 14)
        features["stoch_k"] = self._stoch_k(closes, highs, lows, 14)
        features["volatility_20"] = self._volatility(closes, 20)
        features["sma_ratio"] = self._sma_ratio(closes, 50, 200)
        features["volume_sma"] = self._volume_sma(volumes, 20)
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

    def _adx(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> float:
        """Average Directional Index — trend strength (0-100)."""
        if len(closes) < period * 2:
            return 25.0
        n = len(closes)
        tr_list, plus_dm, minus_dm = [], [], []
        for i in range(max(1, n - period * 2), n):
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
            tr_list.append(tr)
            up = highs[i] - highs[i - 1]
            dn = lows[i - 1] - lows[i]
            plus_dm.append(up if up > 0 and up > dn else 0)
            minus_dm.append(dn if dn > 0 and dn > up else 0)
        atr_val = np.mean(tr_list[-period:]) if tr_list else 1.0
        if atr_val == 0:
            return 25.0
        plus_di = 100 * np.mean(plus_dm[-period:]) / atr_val
        minus_di = 100 * np.mean(minus_dm[-period:]) / atr_val
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
        return float(dx)

    def _stoch_k(self, closes: np.ndarray, highs: np.ndarray, lows: np.ndarray, period: int) -> float:
        """Stochastic %K (0-100)."""
        if len(closes) < period:
            return 50.0
        recent_high = np.max(highs[-period:])
        recent_low = np.min(lows[-period:])
        rng = recent_high - recent_low
        return float(100 * (closes[-1] - recent_low) / rng) if rng > 0 else 50.0

    def _volatility(self, closes: np.ndarray, period: int) -> float:
        """Annualized return volatility."""
        if len(closes) < period + 1:
            return 0.0
        returns = np.diff(closes[-(period + 1):]) / closes[-(period + 1):-1]
        return float(np.std(returns) * np.sqrt(252))

    def _sma_ratio(self, closes: np.ndarray, short: int, long: int) -> float:
        """SMA(short) / SMA(long) ratio — long-term trend."""
        if len(closes) < long:
            if len(closes) < short:
                return 1.0
            return float(np.mean(closes[-short:]) / closes[-1])
        s = np.mean(closes[-short:])
        l = np.mean(closes[-long:])
        return float(s / l) if l > 0 else 1.0

    def _volume_sma(self, volumes: np.ndarray, period: int) -> float:
        """Volume relative to its SMA."""
        if len(volumes) < period or volumes[-1] == 0:
            return 1.0
        avg = np.mean(volumes[-period:])
        return float(volumes[-1] / avg) if avg > 0 else 1.0
