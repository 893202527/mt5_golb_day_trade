import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))


def test_defaults_when_no_env():
    """Test that config falls back to defaults when no env vars are set."""
    # Clear relevant env vars for this test
    for key in ["ZMQ_PUB_PORT", "ZMQ_REP_PORT", "TRADE_SYMBOL", "ML_CONFIDENCE_THRESHOLD",
                "FEATURE_LOOKBACK", "MODEL_PATH", "SL_PIPS", "TP_PIPS",
                "LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL", "LLM_ENABLED"]:
        os.environ.pop(key, None)

    # Re-import to get fresh values (load_dotenv won't find .env since there isn't one)
    import importlib
    import ai.config as cfg
    importlib.reload(cfg)

    assert cfg.ZMQ_PUB_PORT == 5555
    assert cfg.ZMQ_REP_PORT == 5556
    assert cfg.SYMBOL == "XAUUSD"
    assert cfg.SIGNAL_TF == "M5"
    assert cfg.TREND_TFS == ["H1", "H4"]
    assert cfg.ML_CONFIDENCE_THRESHOLD == 0.6
    assert cfg.FEATURE_LOOKBACK == 50
    assert cfg.SL_PIPS == 30
    assert cfg.TP_PIPS == 70
    assert cfg.SYMBOL_DIGITS == 2
    assert cfg.LLM_API_BASE == "https://api.deepseek.com"
    assert cfg.LLM_MODEL == "deepseek-chat"
    assert cfg.LLM_ENABLED is True
    assert cfg.LLM_API_KEY == ""


def test_env_override():
    """Test that environment variables override defaults."""
    os.environ["LLM_ENABLED"] = "false"
    os.environ["ML_CONFIDENCE_THRESHOLD"] = "0.75"
    os.environ["TRADE_SYMBOL"] = "XAGUSD"

    import importlib
    import ai.config as cfg
    importlib.reload(cfg)

    assert cfg.LLM_ENABLED is False
    assert cfg.ML_CONFIDENCE_THRESHOLD == 0.75
    assert cfg.SYMBOL == "XAGUSD"
