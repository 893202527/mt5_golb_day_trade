import httpx
import config


def build_prompt(context: dict) -> str:
    return (
        f"你是黄金(XAUUSD)交易顾问。当前M5时间框架。\n\n"
        f"盘面数据：\n"
        f"- 价格: {context.get('close', 'N/A')}，涨跌幅: {context.get('change', 'N/A')}%\n"
        f"- 大周期方向: H1={context.get('h1_trend', 'N/A')}, H4={context.get('h4_trend', 'N/A')}\n"
        f"- 技术指标: RSI={context.get('rsi', 'N/A')}, EMA20={context.get('ema20', 'N/A')}, "
        f"布林带位置={context.get('bb_pos', 'N/A')}\n\n"
        f"ML模型信号: {context.get('action', 'N/A')}，置信度: {context.get('confidence', 'N/A')}\n\n"
        f"请判断是否同意该信号。只回复 AGREE 或 REJECT，并给一句话理由。"
    )


def call_llm(prompt: str) -> str:
    if not config.LLM_ENABLED or not config.LLM_API_KEY:
        return "SKIPPED (LLM disabled)"

    resp = httpx.post(
        f"{config.LLM_API_BASE}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {config.LLM_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": config.LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 100,
            "temperature": 0.3,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def confirm_signal(ml_action: str, ml_confidence: float, features: dict) -> tuple:
    context = {
        "action": ml_action,
        "confidence": f"{ml_confidence:.3f}",
        "close": features.get("close", "N/A"),
        "change": f"{features.get('ret_1', 0) * 100:.2f}",
        "h1_trend": "up" if features.get("h1_trend", 0) > 0 else "down",
        "h4_trend": "up" if features.get("h4_trend", 0) > 0 else "down",
        "rsi": f"{features.get('rsi', 0):.1f}",
        "ema20": f"{features.get('ema_ratio', 0) * 100:.1f}",
        "bb_pos": f"{features.get('bb_pos', 0):.2f}",
    }
    prompt = build_prompt(context)
    response = call_llm(prompt)
    approved = response.strip().upper().startswith("AGREE")
    return (approved, response)
