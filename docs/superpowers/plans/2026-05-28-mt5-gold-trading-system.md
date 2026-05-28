# MT5 Gold Trading System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Python AI backend + MQL5 EA scaffolding for the XAUUSD automated trading system.

**Architecture:** Python AI service communicates with MT5 EA via ZeroMQ PUB/SUB + REQ/REP. PostgreSQL stores OHLC data, signals, and trades. ML pipeline (XGBoost) generates raw signals, LLM gate confirms/rejects them.

**Tech Stack:** Python 3.11+, pyzmq, xgboost, psycopg2, pandas, numpy; MQL5; PostgreSQL 15+

---

### Task 1: Project Scaffolding

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `ai/requirements.txt`
- Create: `ai/__init__.py`

- [ ] **Step 1: Initialize git repo**

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && git init
```

- [ ] **Step 2: Write .gitignore**

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/.gitignore`:

```
# Python
__pycache__/
*.pyc
.venv/
*.egg-info/

# Model files
data/models/*.json
data/models/*.pkl

# Environment
.env

# IDE
.idea/
.vscode/

# MT5
ea/Libraries/zmq/
```

- [ ] **Step 3: Write README.md**

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/README.md`:

```markdown
# MT5 Gold Day Trade

Automated XAUUSD trading system: MT5 EA + Python AI signals via ZeroMQ.

## Structure

- `ea/` — MQL5 Expert Advisor source
- `ai/` — Python AI signal service
- `data/` — trained models and feature configs
- `scripts/` — training and backtest utilities

## Quick Start

1. `cd ai && pip install -r requirements.txt`
2. `python scripts/init_db.sql` (PostgreSQL)
3. `python ai/server.py`
4. Load `ea/Experts/GoldenBot.mq5` in MT5

## License

MIT
```

- [ ] **Step 4: Write requirements.txt**

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/ai/requirements.txt`:

```
pyzmq>=25.0
xgboost>=2.0
psycopg2-binary>=2.9
pandas>=2.0
numpy>=1.24
python-dotenv>=1.0
httpx>=0.25
```

- [ ] **Step 5: Create empty __init__.py**

```bash
touch "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/ai/__init__.py"
```

- [ ] **Step 6: Create gitignore entries for empty dirs and commit**

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && mkdir -p data/models data/features ea/Experts ea/Include scripts && touch data/models/.gitkeep data/features/.gitkeep ea/Experts/.gitkeep ea/Include/.gitkeep && git add -A && git commit -m "init: project scaffolding for MT5 gold trading system"
```

---

### Task 2: Database Schema and Connection

**Files:**
- Create: `scripts/init_db.sql`
- Create: `ai/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write init_db.sql**

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/scripts/init_db.sql`:

```sql
CREATE TABLE IF NOT EXISTS ohlc (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    bar_time TIMESTAMPTZ NOT NULL,
    open DECIMAL(10,2) NOT NULL,
    high DECIMAL(10,2) NOT NULL,
    low DECIMAL(10,2) NOT NULL,
    close DECIMAL(10,2) NOT NULL,
    tick_volume INT NOT NULL DEFAULT 0,
    spread INT NOT NULL DEFAULT 0,
    UNIQUE(symbol, timeframe, bar_time)
);

CREATE TABLE IF NOT EXISTS signals (
    id BIGSERIAL PRIMARY KEY,
    bar_time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    action VARCHAR(10) NOT NULL,
    confidence DECIMAL(4,3) NOT NULL,
    entry_price DECIMAL(10,2),
    sl DECIMAL(10,2),
    tp DECIMAL(10,2),
    ml_model VARCHAR(50),
    llm_response TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trades (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT REFERENCES signals(id),
    ticket BIGINT,
    symbol VARCHAR(10) NOT NULL,
    direction VARCHAR(5) NOT NULL,
    volume DECIMAL(5,2) NOT NULL,
    entry_price DECIMAL(10,2) NOT NULL,
    exit_price DECIMAL(10,2),
    sl DECIMAL(10,2),
    tp DECIMAL(10,2),
    profit DECIMAL(10,2),
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ,
    status VARCHAR(10) DEFAULT 'open'
);

CREATE INDEX IF NOT EXISTS idx_ohlc_symbol_tf_time ON ohlc(symbol, timeframe, bar_time);
CREATE INDEX IF NOT EXISTS idx_signals_time ON signals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
```

- [ ] **Step 2: Write db.py**

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/ai/db.py`:

```python
import os
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "mt5_gold"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

@contextmanager
def get_conn():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def insert_ohlc(row: dict):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO ohlc (symbol, timeframe, bar_time, open, high, low, close, tick_volume, spread)
               VALUES (%(symbol)s, %(tf)s, %(time)s, %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s, %(spread)s)
               ON CONFLICT (symbol, timeframe, bar_time) DO NOTHING""",
            row,
        )

def get_recent_bars(symbol: str, tf: str, limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM ohlc WHERE symbol=%s AND timeframe=%s ORDER BY bar_time DESC LIMIT %s",
            (symbol, tf, limit),
        )
        rows = cur.fetchall()
        return list(rows)[::-1]

def insert_signal(signal: dict):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO signals (bar_time, symbol, timeframe, action, confidence, entry_price, sl, tp, ml_model, llm_response)
               VALUES (%(bar_time)s, %(symbol)s, %(timeframe)s, %(action)s, %(confidence)s, %(entry)s, %(sl)s, %(tp)s, %(ml_model)s, %(llm_response)s)""",
            signal,
        )

def insert_trade(trade: dict):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO trades (signal_id, ticket, symbol, direction, volume, entry_price, sl, tp, entry_time, status)
               VALUES (%(signal_id)s, %(ticket)s, %(symbol)s, %(direction)s, %(volume)s, %(entry_price)s, %(sl)s, %(tp)s, %(entry_time)s, %(status)s)""",
            trade,
        )
```

- [ ] **Step 3: Write test_db.py (requires running PostgreSQL)**

```bash
mkdir -p "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/tests"
```

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/tests/test_db.py`:

```python
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))
os.environ["DB_NAME"] = "mt5_gold_test"

import pytest
from db import insert_ohlc, get_recent_bars, insert_signal, insert_trade, get_conn

@pytest.fixture(autouse=True)
def setup_tables():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS ohlc (LIKE ohlc_template INCLUDING ALL)")
        cur.execute("DROP TABLE IF EXISTS ohlc; CREATE TABLE ohlc (" +
            "id BIGSERIAL PRIMARY KEY, symbol VARCHAR(10) NOT NULL, timeframe VARCHAR(5) NOT NULL, "
            "bar_time TIMESTAMPTZ NOT NULL, open DECIMAL(10,2), high DECIMAL(10,2), "
            "low DECIMAL(10,2), close DECIMAL(10,2), tick_volume INT DEFAULT 0, spread INT DEFAULT 0, "
            "UNIQUE(symbol, timeframe, bar_time))")

def test_insert_and_read_ohlc():
    row = {"symbol": "XAUUSD", "tf": "M5", "time": "2026-05-28T10:00:00+00:00",
           "open": 2650.0, "high": 2652.0, "low": 2649.0, "close": 2651.0, "volume": 100, "spread": 28}
    insert_ohlc(row)
    bars = get_recent_bars("XAUUSD", "M5", limit=10)
    assert len(bars) >= 1
    assert bars[-1]["close"] == 2651.0
```

- [ ] **Step 4: Commit**

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && git add scripts/init_db.sql ai/db.py tests/test_db.py && git commit -m "feat: add database schema and connection module"
```

---

### Task 3: Config Module

**Files:**
- Create: `ai/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write config.py**

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/ai/config.py`:

```python
import os, json
from dotenv import load_dotenv

load_dotenv()

ZMQ_PUB_PORT = int(os.getenv("ZMQ_PUB_PORT", "5555"))
ZMQ_REP_PORT = int(os.getenv("ZMQ_REP_PORT", "5556"))
SYMBOL = os.getenv("TRADE_SYMBOL", "XAUUSD")
SIGNAL_TF = "M5"
TREND_TFS = ["H1", "H4"]

ML_CONFIDENCE_THRESHOLD = float(os.getenv("ML_CONFIDENCE_THRESHOLD", "0.6"))
FEATURE_LOOKBACK = int(os.getenv("FEATURE_LOOKBACK", "50"))
MODEL_PATH = os.getenv("MODEL_PATH", "data/models/xgb_model.json")

SL_PIPS = int(os.getenv("SL_PIPS", "30"))
TP_PIPS = int(os.getenv("TP_PIPS", "70"))
SYMBOL_DIGITS = int(os.getenv("SYMBOL_DIGITS", "2"))

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_API_BASE = os.getenv("LLM_API_BASE", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() == "true"
```

- [ ] **Step 2: Write test_config.py**

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/tests/test_config.py`:

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))

def test_default_config():
    os.environ.pop("ZMQ_PUB_PORT", None)
    import importlib, ai.config
    importlib.reload(ai.config)
    from ai import config
    assert config.ZMQ_PUB_PORT == 5555
    assert config.SYMBOL == "XAUUSD"
    assert config.ML_CONFIDENCE_THRESHOLD == 0.6
```

- [ ] **Step 3: Commit**

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && git add ai/config.py tests/test_config.py && git commit -m "feat: add config module with env var support"
```

**Note:** Task 3 will be reworked to use a plain Python config pattern (no importlib.reload needed) after we test — or we skip the config test and just test the values directly.

---

### Task 4: Feature Engineering

**Files:**
- Create: `ai/feature_engine.py`
- Create: `tests/test_feature_engine.py`

- [ ] **Step 1: Write feature_engine.py**

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/ai/feature_engine.py`:

```python
import numpy as np
import pandas as pd

class FeatureEngine:
    def __init__(self, lookback=50):
        self.lookback = lookback

    def compute(self, bars: list[dict]) -> dict:
        """bars: list of OHLC dicts sorted by bar_time ascending, at least lookback+1 long."""
        if len(bars) < self.lookback + 1:
            return {}
        df = pd.DataFrame(bars)
        closes = df["close"].values.astype(float)
        highs = df["high"].values.astype(float)
        lows = df["low"].values.astype(float)
        volumes = df["tick_volume"].values.astype(float) if "tick_volume" in df else np.zeros_like(closes)

        features = {}

        # Price change features
        features["ret_1"] = (closes[-1] - closes[-2]) / closes[-2]
        features["ret_5"] = (closes[-1] - closes[-6]) / closes[-6] if len(closes) > 5 else 0
        features["ret_20"] = (closes[-1] - closes[-21]) / closes[-21] if len(closes) > 20 else 0

        # RSI (14)
        features["rsi"] = self._rsi(closes, 14)

        # EMA crossover
        ema20 = self._ema(closes, 20)
        ema50 = self._ema(closes, 50)
        features["ema_ratio"] = ema20 / ema50 if ema50 > 0 else 1.0

        # MACD
        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        macd = ema12 - ema26
        signal_line = np.mean([self._ema(closes, 26)])  # placeholder; proper signal line uses EMA of MACD
        features["macd"] = float(macd) if not np.isnan(macd) else 0.0

        # Bollinger Bands position
        sma20 = np.mean(closes[-20:])
        std20 = np.std(closes[-20:])
        features["bb_pos"] = float((closes[-1] - sma20) / std20) if std20 > 0 else 0.0

        # ATR (14)
        features["atr"] = self._atr(highs, lows, closes, 14)

        # Range and volume
        features["high_low_range"] = float((highs[-1] - lows[-1]) / closes[-1])
        features["vol_ratio"] = float(volumes[-1] / np.mean(volumes[-20:])) if np.mean(volumes[-20:]) > 0 else 1.0

        # Trend labels (dummy — caller fills H1/H4 trend separately)
        features["h1_trend"] = 0
        features["h4_trend"] = 0

        return features

    def _rsi(self, closes: np.ndarray, period: int) -> float:
        deltas = np.diff(closes[-period-1:])
        gains = np.sum(deltas[deltas > 0]) if len(deltas[deltas > 0]) > 0 else 0
        losses = -np.sum(deltas[deltas < 0]) if len(deltas[deltas < 0]) > 0 else 0
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

    def _atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> float:
        if len(closes) < period + 1:
            return 0.0
        trs = []
        for i in range(1, len(closes)):
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            trs.append(tr)
        return float(np.mean(trs[-period:]))
```

- [ ] **Step 2: Write test_feature_engine.py**

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/tests/test_feature_engine.py`:

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))
from feature_engine import FeatureEngine

def make_bars(n=60, base=2650.0):
    bars = []
    for i in range(n):
        o = base + i * 0.5
        bars.append({"open": o, "high": o + 2, "low": o - 1, "close": o + 1, "tick_volume": 100, "bar_time": f"2026-05-28T{i:02d}:00:00"})
    return bars

def test_feature_engine_returns_features():
    fe = FeatureEngine(lookback=50)
    bars = make_bars(60)
    features = fe.compute(bars)
    assert "rsi" in features
    assert "bb_pos" in features
    assert "macd" in features
    assert 0 <= features["rsi"] <= 100

def test_feature_engine_insufficient_bars():
    fe = FeatureEngine(lookback=50)
    bars = make_bars(30)
    features = fe.compute(bars)
    assert features == {}
```

- [ ] **Step 3: Run tests**

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && python -m pytest tests/test_feature_engine.py -v
```

- [ ] **Step 4: Commit**

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && git add ai/feature_engine.py tests/test_feature_engine.py && git commit -m "feat: add feature engineering module (RSI, EMA, MACD, BB, ATR)"
```

---

### Task 5: ML Model (XGBoost)

**Files:**
- Create: `ai/ml_model.py`
- Create: `tests/test_ml_model.py`

- [ ] **Step 1: Write ml_model.py**

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/ai/ml_model.py`:

```python
import json, pickle, os
import numpy as np
from config import MODEL_PATH, ML_CONFIDENCE_THRESHOLD

FEATURE_ORDER = [
    "ret_1", "ret_5", "ret_20", "rsi", "ema_ratio", "macd",
    "bb_pos", "atr", "high_low_range", "vol_ratio", "h1_trend", "h4_trend",
]

class MLPredictor:
    def __init__(self, model_path=None):
        self.model_path = model_path or MODEL_PATH
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

    def predict(self, features: dict) -> tuple[str, float]:
        if self.model is None:
            return ("hold", 0.0)
        X = np.array([[features.get(k, 0.0) for k in FEATURE_ORDER]])
        proba = self.model.predict_proba(X)[0]
        # class order: 0=hold, 1=sell, 2=buy
        idx = int(proba.argmax())
        confidence = float(proba.max())
        if confidence < ML_CONFIDENCE_THRESHOLD:
            return ("hold", confidence)
        labels = {0: "hold", 1: "sell", 2: "buy"}
        return (labels.get(idx, "hold"), confidence)

    def save(self, model, path=None):
        target = path or self.model_path
        os.makedirs(os.path.dirname(target), exist_ok=True)
        model.save_model(target)

    def is_loaded(self) -> bool:
        return self.model is not None
```

- [ ] **Step 2: Write test_ml_model.py**

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/tests/test_ml_model.py`:

```python
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))

import xgboost as xgb
import numpy as np
from ml_model import MLPredictor

def test_predict_no_model_returns_hold():
    predictor = MLPredictor(model_path="/nonexistent/model.json")
    action, conf = predictor.predict({})
    assert action == "hold"
    assert conf == 0.0

def test_predict_with_model():
    X = np.random.rand(100, 12)
    y = np.random.choice([0, 1, 2], 100)
    model = xgb.XGBClassifier(n_estimators=10, max_depth=3)
    model.fit(X, y)

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test_model.json")
        model.save_model(path)
        # Override threshold to 0 so any prediction passes
        import config
        config.ML_CONFIDENCE_THRESHOLD = 0.0
        predictor = MLPredictor(model_path=path)
        assert predictor.is_loaded()

        features = {k: 0.0 for k in ["ret_1","ret_5","ret_20","rsi","ema_ratio","macd","bb_pos","atr","high_low_range","vol_ratio","h1_trend","h4_trend"]}
        action, conf = predictor.predict(features)
        assert action in ("buy", "sell", "hold")
        assert 0.0 <= conf <= 1.0
```

- [ ] **Step 3: Run tests**

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && python -m pytest tests/test_ml_model.py -v
```

- [ ] **Step 4: Commit**

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && git add ai/ml_model.py tests/test_ml_model.py && git commit -m "feat: add XGBoost ML predictor module"
```

---

### Task 6: LLM Gate

**Files:**
- Create: `ai/llm_gate.py`
- Create: `tests/test_llm_gate.py`

- [ ] **Step 1: Write llm_gate.py**

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/ai/llm_gate.py`:

```python
import httpx
from config import LLM_API_KEY, LLM_API_BASE, LLM_MODEL, LLM_ENABLED

def build_prompt(context: dict) -> str:
    return f"""你是黄金(XAUUSD)交易顾问。当前M5时间框架。

盘面数据：
- 价格: {context.get('close', 'N/A')}，涨跌幅: {context.get('change', 'N/A')}%
- 大周期方向: H1={context.get('h1_trend', 'N/A')}, H4={context.get('h4_trend', 'N/A')}
- 技术指标: RSI={context.get('rsi', 'N/A')}, EMA20={context.get('ema20', 'N/A')}, 布林带位置={context.get('bb_pos', 'N/A')}

ML模型信号: {context.get('action', 'N/A')}，置信度: {context.get('confidence', 'N/A')}

请判断是否同意该信号。只回复 AGREE 或 REJECT，并给一句话理由。"""

def call_llm(prompt: str) -> str:
    if not LLM_ENABLED or not LLM_API_KEY:
        return "SKIPPED (LLM disabled)"

    resp = httpx.post(
        f"{LLM_API_BASE}/v1/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
        json={"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 100, "temperature": 0.3},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()

def confirm_signal(ml_action: str, ml_confidence: float, features: dict) -> tuple[bool, str]:
    context = {
        "action": ml_action,
        "confidence": f"{ml_confidence:.3f}",
        "close": features.get("close", "N/A"),
        "change": f"{features.get('ret_1', 0)*100:.2f}",
        "h1_trend": "up" if features.get("h1_trend", 0) > 0 else "down",
        "h4_trend": "up" if features.get("h4_trend", 0) > 0 else "down",
        "rsi": f"{features.get('rsi', 0):.1f}",
        "ema20": f"{features.get('ema_ratio', 0)*100:.1f}",
        "bb_pos": f"{features.get('bb_pos', 0):.2f}",
    }
    prompt = build_prompt(context)
    response = call_llm(prompt)
    approved = response.strip().upper().startswith("AGREE")
    return (approved, response)
```

- [ ] **Step 2: Write test_llm_gate.py**

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/tests/test_llm_gate.py`:

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))

from llm_gate import build_prompt

def test_build_prompt_contains_key_info():
    ctx = {"close": 2650, "change": "0.15", "h1_trend": "up", "h4_trend": "up",
           "rsi": "55.2", "ema20": "100.5", "bb_pos": "0.80",
           "action": "buy", "confidence": "0.720"}
    prompt = build_prompt(ctx)
    assert "2650" in prompt
    assert "buy" in prompt
    assert "0.720" in prompt
    assert "55.2" in prompt
```

- [ ] **Step 3: Run tests**

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && python -m pytest tests/test_llm_gate.py -v
```

- [ ] **Step 4: Commit**

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && git add ai/llm_gate.py tests/test_llm_gate.py && git commit -m "feat: add LLM gate module for signal confirmation"
```

---

### Task 7: ZeroMQ Server (Main AI Service)

**Files:**
- Create: `ai/server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write server.py**

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/ai/server.py`:

```python
import json, zmq, signal, sys
from config import ZMQ_PUB_PORT, ZMQ_REP_PORT, SYMBOL, SIGNAL_TF, SL_PIPS, TP_PIPS, SYMBOL_DIGITS
from db import insert_ohlc, get_recent_bars, insert_signal
from feature_engine import FeatureEngine
from ml_model import MLPredictor
from llm_gate import confirm_signal

running = True
fe = FeatureEngine()
predictor = MLPredictor()

def handle_ohlc(data: dict):
    row = {
        "symbol": data["symbol"], "tf": data["tf"], "time": data["time"],
        "open": data["open"], "high": data["high"], "low": data["low"],
        "close": data["close"], "volume": data.get("tick_volume", 0), "spread": data.get("spread", 0),
    }
    insert_ohlc(row)

def handle_query(data: dict) -> dict:
    symbol = data.get("symbol", SYMBOL)
    tf = data.get("tf", SIGNAL_TF)
    bars = get_recent_bars(symbol, tf, limit=60)
    if len(bars) < 51:
        return {"action": "hold", "confidence": 0.0, "entry_price": 0, "sl": 0, "tp": 0, "reason": "insufficient data"}

    features = fe.compute(bars)
    if not features:
        return {"action": "hold", "confidence": 0.0, "entry_price": 0, "sl": 0, "tp": 0, "reason": "feature computation failed"}

    close = bars[-1]["close"]
    features["close"] = close

    ml_action, ml_conf = predictor.predict(features)
    reason = f"ML: {ml_action} ({ml_conf:.3f})"

    if ml_action != "hold":
        approved, llm_resp = confirm_signal(ml_action, ml_conf, features)
        reason += f" | LLM: {llm_resp[:200]}"
        if not approved:
            ml_action = "hold"

    sl = tp = 0.0
    if ml_action == "buy":
        sl = close - SL_PIPS * (10 ** (-SYMBOL_DIGITS))
        tp = close + TP_PIPS * (10 ** (-SYMBOL_DIGITS))
    elif ml_action == "sell":
        sl = close + SL_PIPS * (10 ** (-SYMBOL_DIGITS))
        tp = close - TP_PIPS * (10 ** (-SYMBOL_DIGITS))

    insert_signal({
        "bar_time": bars[-1]["bar_time"], "symbol": symbol, "timeframe": tf,
        "action": ml_action, "confidence": ml_conf, "entry": close,
        "sl": sl, "tp": tp, "ml_model": "XGBoost", "llm_response": reason,
    })

    return {"action": ml_action, "confidence": ml_conf, "entry_price": close, "sl": sl, "tp": tp, "reason": reason}

def main():
    global running
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.connect(f"tcp://127.0.0.1:{ZMQ_PUB_PORT}")
    sub.setsockopt_string(zmq.SUBSCRIBE, "OHLC")

    rep = ctx.socket(zmq.REP)
    rep.bind(f"tcp://127.0.0.1:{ZMQ_REP_PORT}")

    poller = zmq.Poller()
    poller.register(sub, zmq.POLLIN)
    poller.register(rep, zmq.POLLIN)

    def shutdown(sig, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"[server] listening on PUB:{ZMQ_PUB_PORT} REP:{ZMQ_REP_PORT}")
    while running:
        socks = dict(poller.poll(1000))
        if sub in socks:
            msg = sub.recv_string()
            _, body = msg.split(" ", 1)
            data = json.loads(body)
            if data.get("type") == "ohlc":
                handle_ohlc(data)
        if rep in socks:
            req = rep.recv_string()
            data = json.loads(req)
            if data.get("type") == "query":
                resp = handle_query(data)
                rep.send_string(json.dumps(resp))

    sub.close()
    rep.close()
    ctx.term()
    print("[server] stopped")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write test_server.py (integration-style, mocks ZMQ)**

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/tests/test_server.py`:

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))
os.environ["ML_CONFIDENCE_THRESHOLD"] = "0.0"
os.environ["LLM_ENABLED"] = "false"

def test_handle_query_insufficient_data():
    from server import handle_query
    import importlib, ai.config
    importlib.reload(ai.config)
    from unittest.mock import patch
    with patch("server.get_recent_bars", return_value=[]):
        resp = handle_query({"symbol": "XAUUSD", "tf": "M5"})
        assert resp["action"] == "hold"
        assert "insufficient" in resp["reason"].lower()
```

- [ ] **Step 3: Run tests**

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && python -m pytest tests/test_server.py -v
```

- [ ] **Step 4: Commit**

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && git add ai/server.py tests/test_server.py && git commit -m "feat: add ZeroMQ AI server main process"
```

---

### Task 8: MQL5 EA — ZeroMQ Channel

**Files:**
- Create: `ea/Include/ZmqChannel.mqh`

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/ea/Include/ZmqChannel.mqh`:

```cpp
//+------------------------------------------------------------------+
//| ZmqChannel.mqh - ZeroMQ wrapper for MT5 EA                        |
//+------------------------------------------------------------------+
#property copyright "Trading System"

#ifndef ZMQ_CHANNEL_MQH
#define ZMQ_CHANNEL_MQH

#include <Zmq/Zmq.mqh>

class CZmqChannel
{
private:
    Context m_ctx;
    Socket  m_pub;  // PUB socket to Python
    Socket  m_req;  // REQ socket to Python

    string  m_pubEndpoint;
    string  m_reqEndpoint;

public:
    CZmqChannel()
    {
        m_pubEndpoint = "tcp://127.0.0.1:5555";
        m_reqEndpoint = "tcp://127.0.0.1:5556";
    }

    ~CZmqChannel()
    {
        m_pub.close();
        m_req.close();
        m_ctx.destroy();
    }

    bool Start()
    {
        m_ctx.create();
        if(!m_ctx.isValid()) return false;

        m_pub = m_ctx.createSocket(ZMQ_PUB);
        if(!m_pub.isValid()) return false;

        m_req = m_ctx.createSocket(ZMQ_REQ);
        if(!m_req.isValid()) return false;

        if(!m_pub.bind(m_pubEndpoint)) return false;
        if(!m_req.connect(m_reqEndpoint)) return false;

        return true;
    }

    void PublishOHLC(string symbol, string tf, datetime barTime,
                     double open, double high, double low, double close,
                     long tickVolume, int spread)
    {
        string json = StringFormat(
            "OHLC {\"type\":\"ohlc\",\"symbol\":\"%s\",\"tf\":\"%s\",\"time\":\"%s\","
            "\"open\":%.2f,\"high\":%.2f,\"low\":%.2f,\"close\":%.2f,"
            "\"tick_volume\":%d,\"spread\":%d}",
            symbol, tf, TimeToString(barTime, TIME_DATE|TIME_SECONDS),
            open, high, low, close, tickVolume, spread
        );
        ZmqMsg msg(json);
        m_pub.send(msg, false);
    }

    bool QuerySignal(string &action, double &confidence,
                     double &entryPrice, double &sl, double &tp, string &reason)
    {
        string req = "{\"type\":\"query\",\"symbol\":\"XAUUSD\",\"tf\":\"M5\"}";
        ZmqMsg reqMsg(req);
        m_req.send(reqMsg);

        ZmqMsg repMsg;
        int rc = m_req.recv(repMsg, 3000); // 3s timeout
        if(rc < 0) return false;

        string rep;
        repMsg.getString(rep);
        // Will be parsed via JSCallback or manual parsing
        // For now, stub: return the raw JSON
        return true;
    }
};

#endif
```

Commit:

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && git add ea/Include/ZmqChannel.mqh && git commit -m "feat: add MQL5 ZeroMQ channel wrapper"
```

---

### Task 9: MQL5 EA — Order Manager

**Files:**
- Create: `ea/Include/OrderManager.mqh`

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/ea/Include/OrderManager.mqh`:

```cpp
//+------------------------------------------------------------------+
//| OrderManager.mqh - Trade execution wrapper                        |
//+------------------------------------------------------------------+
#property copyright "Trading System"

#ifndef ORDER_MANAGER_MQH
#define ORDER_MANAGER_MQH

#include <Trade/Trade.mqh>

class COrderManager
{
private:
    CTrade m_trade;
    string m_symbol;
    int    m_magic;

public:
    COrderManager(string symbol, int magic = 20260528)
    {
        m_symbol = symbol;
        m_magic = magic;
        m_trade.SetExpertMagicNumber(m_magic);
    }

    ulong OpenBuy(double volume, double sl, double tp, string comment = "")
    {
        m_trade.PositionOpen(m_symbol, ORDER_TYPE_BUY, volume,
                             SymbolInfoDouble(m_symbol, SYMBOL_ASK),
                             sl, tp, comment);
        return m_trade.ResultOrder();
    }

    ulong OpenSell(double volume, double sl, double tp, string comment = "")
    {
        m_trade.PositionOpen(m_symbol, ORDER_TYPE_SELL, volume,
                             SymbolInfoDouble(m_symbol, SYMBOL_BID),
                             sl, tp, comment);
        return m_trade.ResultOrder();
    }

    bool ClosePosition(ulong ticket)
    {
        return m_trade.PositionClose(ticket);
    }

    bool HasOpenPosition()
    {
        return PositionSelect(m_symbol);
    }

    double GetLots(double riskPercent, double slPips)
    {
        double balance = AccountInfoDouble(ACCOUNT_BALANCE);
        double riskMoney = balance * riskPercent / 100.0;
        double tickValue = SymbolInfoDouble(m_symbol, SYMBOL_TRADE_TICK_VALUE);
        double point = SymbolInfoDouble(m_symbol, SYMBOL_POINT);
        double slPrice = slPips * point * 10; // 1 pip = 10 points for gold
        if(slPrice <= 0) return 0.01;
        double lots = riskMoney / (slPrice * tickValue / point);
        double minLot = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_MIN);
        double maxLot = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_MAX);
        double step = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_STEP);
        lots = MathMax(minLot, MathMin(maxLot, lots));
        lots = MathFloor(lots / step) * step;
        return lots;
    }
};

#endif
```

Commit:

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && git add ea/Include/OrderManager.mqh && git commit -m "feat: add MQL5 order manager"
```

---

### Task 10: MQL5 EA — Main GoldenBot

**Files:**
- Create: `ea/Experts/GoldenBot.mq5`

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/ea/Experts/GoldenBot.mq5`:

```cpp
//+------------------------------------------------------------------+
//| GoldenBot.mq5 - XAUUSD AI Trading EA                              |
//+------------------------------------------------------------------+
#property copyright "Trading System"
#property version   "1.00"
#property description "AI-driven XAUUSD trading bot with ZeroMQ bridge"

#include <ZmqChannel.mqh>
#include <OrderManager.mqh>

input double RiskPercent = 1.0;    // Risk per trade (%)
input int    InpMagic    = 20260528;

CZmqChannel   g_zmq;
COrderManager g_order(Symbol(), InpMagic);

int OnInit()
{
    if(!g_zmq.Start())
    {
        Print("ZeroMQ init failed");
        return INIT_FAILED;
    }
    Print("GoldenBot started on ", Symbol());
    return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
    Print("GoldenBot stopped");
}

void OnTick()
{
    static datetime lastBarTime = 0;
    datetime currentBar = iTime(Symbol(), PERIOD_M5, 0);

    // New bar closed
    if(currentBar != lastBarTime && lastBarTime != 0)
    {
        OnBarClose(PERIOD_M5);
    }
    lastBarTime = currentBar;
}

void OnBarClose(ENUM_TIMEFRAMES tf)
{
    // Publish latest closed bar
    double open  = iOpen(Symbol(), tf, 1);
    double high  = iHigh(Symbol(), tf, 1);
    double low   = iLow(Symbol(), tf, 1);
    double close = iClose(Symbol(), tf, 1);
    long   vol   = iVolume(Symbol(), tf, 1);
    int    spread = (int)SymbolInfoInteger(Symbol(), SYMBOL_SPREAD);

    string tfStr = "M5";
    datetime barTime = iTime(Symbol(), tf, 1);

    g_zmq.PublishOHLC(Symbol(), tfStr, barTime, open, high, low, close, vol, spread);

    // Query signal on M5 close
    if(tf == PERIOD_M5 && !g_order.HasOpenPosition())
    {
        string action, reason;
        double confidence, entry, sl, tp;

        if(g_zmq.QuerySignal(action, confidence, entry, sl, tp, reason))
        {
            ProcessSignal(action, confidence, entry, sl, tp, reason);
        }
    }
}

void ProcessSignal(string action, double confidence, double entry, double sl, double tp, string reason)
{
    double lots = g_order.GetLots(RiskPercent, MathAbs(entry - sl) / SymbolInfoDouble(Symbol(), SYMBOL_POINT));

    ulong ticket = 0;
    if(action == "buy")
        ticket = g_order.OpenBuy(lots, sl, tp, reason);
    else if(action == "sell")
        ticket = g_order.OpenSell(lots, sl, tp, reason);

    if(ticket > 0)
        Print("Trade opened: ", action, " ticket=", ticket, " lots=", lots, " reason=", reason);
    else
        Print("Trade failed: ", action, " error=", GetLastError());
}
```

Commit:

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && git add ea/Experts/GoldenBot.mq5 && git commit -m "feat: add GoldenBot main EA"
```

---

### Task 11: Training Script

**Files:**
- Create: `scripts/train.py`

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/scripts/train.py`:

```python
"""Train XGBoost model from PostgreSQL OHLC data."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))

import numpy as np
import pandas as pd
import xgboost as xgb
from datetime import datetime
from db import get_conn
from feature_engine import FeatureEngine
from ml_model import MLPredictor, FEATURE_ORDER

LOOKBACK = 50

def load_data(symbol="XAUUSD", tf="M5"):
    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM ohlc WHERE symbol=%s AND timeframe=%s ORDER BY bar_time ASC",
            conn, params=(symbol, tf))
    return df

def create_labels(df: pd.DataFrame, horizon: int = 5) -> np.ndarray:
    """Label each bar: 2=buy if price rises > ATR/2 in horizon bars, 1=sell if drops, 0=hold."""
    closes = df["close"].values
    labels = np.zeros(len(closes), dtype=int)
    for i in range(len(closes) - horizon):
        future_ret = (closes[i+horizon] - closes[i]) / closes[i]
        threshold = 0.001  # 0.1% as threshold
        if future_ret > threshold:
            labels[i] = 2
        elif future_ret < -threshold:
            labels[i] = 1
        else:
            labels[i] = 0
    return labels

def main():
    print("[train] loading data...")
    df = load_data()
    if len(df) < LOOKBACK + 20:
        print(f"[train] insufficient data: {len(df)} rows")
        return

    labels = create_labels(df)
    fe = FeatureEngine(lookback=LOOKBACK)

    X_list, y_list = [], []
    bars_dicts = df.to_dict("records")
    for i in range(LOOKBACK, len(bars_dicts)):
        window = bars_dicts[i-LOOKBACK:i+1]
        features = fe.compute(window)
        if features:
            X_list.append([features.get(k, 0.0) for k in FEATURE_ORDER])
            y_list.append(labels[i])

    X = np.array(X_list)
    y = np.array(y_list)
    print(f"[train] {len(X)} samples, class dist: {dict(zip(*np.unique(y, return_counts=True)))}")

    model = xgb.XGBClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.05,
        objective="multi:softprob", num_class=3, random_state=42)
    model.fit(X, y, eval_set=[(X, y)], verbose=False)

    mp = MLPredictor()
    mp.save(model)
    print(f"[train] model saved to {mp.model_path}")

if __name__ == "__main__":
    main()
```

Commit:

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && git add scripts/train.py && git commit -m "feat: add model training script"
```

---

### Task 12: Backtest Script

**Files:**
- Create: `scripts/backtest.py`

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/scripts/backtest.py`:

```python
"""Offline backtest of the ML+LLM signal pipeline using OHLC data from PostgreSQL."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))

import pandas as pd
from datetime import datetime
from db import get_conn
from feature_engine import FeatureEngine
from ml_model import MLPredictor

LOOKBACK = 50
SL_PIPS = 30
TP_PIPS = 70
SYMBOL_DIGITS = 2

def run():
    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM ohlc WHERE symbol='XAUUSD' AND timeframe='M5' ORDER BY bar_time ASC", conn)

    if len(df) < LOOKBACK + 20:
        print(f"Insufficient data: {len(df)} rows")
        return

    fe = FeatureEngine(lookback=LOOKBACK)
    predictor = MLPredictor()

    trades = []
    bars = df.to_dict("records")

    for i in range(LOOKBACK, len(bars)):
        window = bars[i-LOOKBACK:i+1]
        features = fe.compute(window)
        if not features:
            continue

        close = bars[i]["close"]
        features["close"] = close
        action, conf = predictor.predict(features)
        if action == "hold":
            continue

        pip_mult = 10 ** (-SYMBOL_DIGITS)
        sl = close - SL_PIPS * pip_mult if action == "buy" else close + SL_PIPS * pip_mult
        tp = close + TP_PIPS * pip_mult if action == "buy" else close - TP_PIPS * pip_mult

        exit_price, profit = simulate_exit(bars, i, action, sl, tp, pip_mult)
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
    print(f"Max drawdown: {drawdown(results['profit'].cumsum()):.2f}")

def simulate_exit(bars, entry_idx, action, sl, tp, pip_mult, max_bars=200):
    close = bars[entry_idx]["close"]
    end = min(entry_idx + max_bars, len(bars))
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
    last_close = bars[end-1]["close"]
    return (last_close, last_close - close if action == "buy" else close - last_close)

def drawdown(cum_pnl):
    peak = cum_pnl.cummax()
    dd = cum_pnl - peak
    return dd.min()

if __name__ == "__main__":
    run()
```

Commit:

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && git add scripts/backtest.py && git commit -m "feat: add offline backtest script"
```

---

### Task 13: Environment File Template

**Files:**
- Create: `.env.example`

Write file `C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade/.env.example`:

```bash
# PostgreSQL
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mt5_gold
DB_USER=postgres
DB_PASSWORD=

# ZeroMQ
ZMQ_PUB_PORT=5555
ZMQ_REP_PORT=5556

# Trading
TRADE_SYMBOL=XAUUSD
SL_PIPS=30
TP_PIPS=70
SYMBOL_DIGITS=2

# ML
ML_CONFIDENCE_THRESHOLD=0.6
FEATURE_LOOKBACK=50
MODEL_PATH=data/models/xgb_model.json

# LLM
LLM_ENABLED=true
LLM_API_KEY=
LLM_API_BASE=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

Commit:

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && git add .env.example && git commit -m "chore: add .env.example template"
```

---

### Task 14: Final Integration Verification

- [ ] **Step 1: Verify all Python tests pass**

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && python -m pytest tests/ -v
```

- [ ] **Step 2: Verify project structure**

```bash
find "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" -not -path "*/.git/*" -not -path "*/__pycache__/*" | sort
```

- [ ] **Step 3: Final git status and commit**

```bash
cd "C:/Users/89320/Desktop/AI_Pj/mt5_golb_day_trade" && git status && git log --oneline
```
