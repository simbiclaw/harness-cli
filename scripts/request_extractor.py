"""Request extraction: parse LLM response into a validated Request object.

M1 — Skill prototype. Claude does the extraction; this module validates the output.
"""

MAX_LENGTH = 80
MIN_LENGTH = 8


def parse_request_response(response_text: str, audio_id: str) -> tuple[bool, dict]:
    """Parse and validate an LLM-extracted Request from a call transcript.

    Args:
        response_text: The raw LLM output (one Chinese sentence or UNCLEAR).
        audio_id: The call identifier.

    Returns:
        (valid, request_dict) — valid is True if the request passes all checks.
        request_dict always has audio_id and request_text (null if UNCLEAR).
    """
    text = response_text.strip()

    # UNCLEAR marker: preserve but reject
    if text.upper() == "UNCLEAR" or text == "":
        return False, {
            "audio_id": audio_id,
            "request_text": None,
            "confidence": 0.0,
        }

    # Reject if too short
    if len(text) < MIN_LENGTH:
        return False, {"audio_id": audio_id, "request_text": text, "confidence": 0.0}

    # Reject if too long
    if len(text) > MAX_LENGTH:
        return False, {"audio_id": audio_id, "request_text": text, "confidence": 0.0}

    # Reject if contains agent dialogue markers (Claude described the agent, not the customer)
    agent_markers = ["坐席", "客服", "agent", "Agent"]
    if any(marker in text for marker in agent_markers):
        return False, {"audio_id": audio_id, "request_text": text, "confidence": 0.0}

    return True, {
        "audio_id": audio_id,
        "request_text": text,
        "confidence": 0.9,  # provisional; Claude's actual confidence is captured at extraction time
    }


def build_extraction_prompt(turns: list[dict], call_context: str = "") -> str:
    """Build the prompt for Claude to extract a Request from customer turns.

    Args:
        turns: Customer turns only (already filtered by speaker).
        call_context: Optional L1/L2 context for the call.

    Returns:
        A prompt string ready for Claude.
    """
    customer_text = "\n".join(t["text"] for t in turns)

    prompt = f"""你是客服意图分析助手。阅读以下客服通话中客户的发言，用一句中文提取客户的核心诉求。

<通话背景>
{call_context or "未知业务场景"}
</通话背景>

<客户发言>
{customer_text}
</客户发言>

要求:
- 一句中文，8-80字
- 描述客户想要什么，而非客户情绪
- 包含关键实体（产品名、业务名、操作名）
- 如果客户发言无法判断明确诉求，输出 UNCLEAR

客户诉求（一句中文）:"""

    return prompt
