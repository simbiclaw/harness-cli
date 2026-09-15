# tests/fakes.py
"""The fake LLM and fake NLI for the io/ port's acceptance tests.

Mirrors simbi's `tests/fakes.py` (9023 M4) reply-for-reply: same routes, same
payloads, same marker keying. The baseline comparison in `test_io_import.py` is
only meaningful if both sides of it are fed identical answers — a fake that
diverged would make "same output" a tautology over different inputs.

Rationale for marker keying (rather than call order) is documented in simbi's
module; short version: `question_generator` and `atomizer` dispatch through
`asyncio.gather`, so order is not stable, and a fake that guessed would answer
one call site with another's shape and fail somewhere unrelated to the code
under test.
"""

from __future__ import annotations

import json


def _entities(_prompt: str) -> str:
    return json.dumps({"products": [], "business_keywords": [], "platforms": []})


def _l1_selection(_prompt: str) -> str:
    return json.dumps({"selected": []})


def _applicability(_prompt: str) -> str:
    return json.dumps({"applicable": True})


def _atoms(_prompt: str) -> str:
    return json.dumps([
        {
            "id": "CA-01",
            "source_turn_ids": ["T02"],
            "role": "client",
            "atom_type": "明确诉求",
            "content": "你好，我想问一下CA锁未绑定怎么处理。",
            "decontextualized": "客户的CA锁显示未绑定，询问处理方式。",
        },
        {
            "id": "AA-01",
            "source_turn_ids": ["T05"],
            "role": "agent",
            "atom_type": "政策引用",
            "content": "您手上的Key不是汇信的，建议您找对应服务商处理。",
            "decontextualized": "客服引用办理要求：非汇信Key需找对应服务商处理。",
        },
    ])


def _coverage(_prompt: str) -> str:
    return json.dumps([
        {
            "client_atom_id": "CA-01",
            "agent_atom_id": "AA-01",
            "status": "ignored",
            "note": "客服未直接回应CA锁未绑定的处理方式",
        },
    ])


def _intent(_prompt: str) -> str:
    return json.dumps({
        "customer_surface_intent": "咨询CA锁未绑定",
        "customer_deep_intent": "解决未绑定问题",
        "agent_behavior_pattern": "查证后给出指引",
        "key_tension": "未直接回应处理方式",
        "intent_switches": [],
        "unresolved_intents": [],
    })


def _rubric_question(_prompt: str) -> str:
    return json.dumps({
        "applicability": "applicable",
        "question": "客服是否确认了客户身份并给出可执行的指引？",
        "hypothesis_pos": "HIGH 客服确认了身份并给出了指引",
        "hypothesis_neg": "LOW 客服没有确认身份也没有给出指引",
    })


def _accuracy_question(_prompt: str) -> str:
    return json.dumps({
        "question": "企业CA证书延期需要哪些材料？",
        "hypothesis_pos": "HIGH 客服列出的材料与企业证书延期的要求一致",
        "hypothesis_neg": "LOW 客服列出的材料与企业证书延期的要求不一致",
        "claim_type": "internal_policy",
    })


def _implied_questions(_prompt: str) -> str:
    return json.dumps([
        {
            "question": "客服是否说明了CA锁未绑定的可能原因？",
            "hypothesis_pos": "HIGH 客服说明了未绑定的原因",
            "hypothesis_neg": "LOW 客服没有说明未绑定的原因",
            "implied_q_type": "CONTEXT",
        },
    ])


def _wikichat(_prompt: str) -> str:
    return json.dumps({"verdict": "NEI", "confidence": 0.0, "reasoning": "", "key_evidence": ""})


def _report_summary(_prompt: str) -> str:
    return json.dumps({
        "summary": "本次通话客服确认了客户身份并给出指引。",
        "improvement_suggestions": ["建议一", "建议二", "建议三"],
    })


ROUTES: tuple[tuple[str, object], ...] = (
    ("从以下客服对话中提取关键业务实体", _entities),
    ("从以下L1目录中选择最相关的1-2个", _l1_selection),
    ("目录下的子目录", _l1_selection),
    ("判断以下质检规则是否适用于本通电话", _applicability),
    ("提取【客户侧】所有原子化陈述", _atoms),
    ("提取【客服侧】所有原子化陈述", _atoms),
    ("判断每个客户原子是否被客服有效响应", _coverage),
    ("推断双方的真实意图和行为模式", _intent),
    ("将以下质检规则转化为", _rubric_question),
    ("生成用于核查业务准确性的 Yes-No 子问题", _accuracy_question),
    ("生成【Implied 质检子问题】", _implied_questions),
    ("你是一个事实核查员", _wikichat),
    ("基于以下质检结果，生成简洁的质检总结", _report_summary),
)


class FakeLLM:
    """Stands in for the ported client's `complete(prompt, max_tokens=4096) -> str`."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def complete(self, prompt: str, max_tokens: int = 4096) -> str:
        self.prompts.append(prompt)
        for marker, reply in ROUTES:
            if marker in prompt:
                return reply(prompt)
        raise AssertionError(
            "FakeLLM was asked a question no route covers:\n" + prompt[:400]
        )


class FakeNLI:
    """Path A compares `best_pos > best_neg`; score the positive side higher."""

    def score(self, premise: str, hypothesis: str) -> float:
        return 0.9 if "HIGH" in hypothesis else 0.1
