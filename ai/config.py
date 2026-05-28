import os
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
