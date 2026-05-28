import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai"))


def test_build_prompt_contains_key_info():
    from llm_gate import build_prompt
    ctx = {
        "close": 2650, "change": "0.15",
        "h1_trend": "up", "h4_trend": "up",
        "rsi": "55.2", "ema20": "100.5", "bb_pos": "0.80",
        "action": "buy", "confidence": "0.720",
    }
    prompt = build_prompt(ctx)
    assert "2650" in prompt
    assert "buy" in prompt
    assert "0.720" in prompt
    assert "55.2" in prompt


def test_confirm_signal_llm_disabled():
    import config
    config.LLM_ENABLED = False
    from llm_gate import confirm_signal
    features = {
        "close": 2650, "ret_1": 0.0015,
        "h1_trend": 1, "h4_trend": 1,
        "rsi": 55.0, "ema_ratio": 1.005, "bb_pos": 0.8,
    }
    approved, response = confirm_signal("buy", 0.72, features)
    assert not approved
    assert "SKIPPED" in response


def test_call_llm_returns_skipped_when_no_key():
    import config
    config.LLM_API_KEY = ""
    config.LLM_ENABLED = True
    from llm_gate import call_llm
    result = call_llm("test prompt")
    assert "SKIPPED" in result
