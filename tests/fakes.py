# tests/fakes.py
"""The fake LLM and fake NLI for the io/ port's acceptance tests.

**A verbatim copy of simbi's `tests/fakes.py` @ 929d5a7** (9023 M4), payloads
included — atom ids, contents, coverage rows, intent strings, implied
questions. An earlier draft here mirrored the routes and then improvised its
own payloads; the golden `tests/fixtures/io_import_baseline.json` was captured
with these, so a fake that diverged made "same output as the M4 baseline"
a tautology over different inputs. The mirror promise in this docstring is
now true: both sides of the baseline comparison are fed identical answers.

Marker keying is kept rather than call order for the reason simbi's module
documents: `question_generator` and `atomizer` dispatch through
`asyncio.gather`, so order is not stable, and a fake that guessed would answer
one call site with another's shape and fail somewhere unrelated to the code
under test. File citations in the comments name simbi's modules — they are
the payloads' provenance, kept as shipped.
"""

from __future__ import annotations

import json

# ── replies, one per LLM call site reachable from `QAAgent.run` ────────────────


def _entities(_prompt: str) -> str:
    """`knowledge/intent_retriever.py:66` — `.get` on the parsed object, so it must be an object.

    Non-empty, so the L1 classifier is reached: an empty entity list short-circuits `_classify_l1`
    and the route below never fires."""
    return json.dumps(
        {
            "products": ["CA证书"],
            "business_keywords": ["延期", "过期"],
            "platforms": ["金华市公共资源交易中心"],
        }
    )


def _l1_selection(_prompt: str) -> str:
    """`knowledge/intent_retriever.py:149` — `json.loads(raw).get("selected", [])`."""
    return json.dumps({"selected": []})


def _applicability(_prompt: str) -> str:
    """`core/kb_context_builder.py:158` — read as a boolean; the caller is exception-tolerant."""
    return json.dumps({"applicable": True})


def _atoms(_prompt: str) -> str:
    """`core/atomizer.py:36,41` — a JSON array of `Atom`s.

    The same reply serves the client and the agent call; both prompts ask for the same schema and
    the field that distinguishes them (`role`) is one the pipeline overwrites nothing of, so a
    fixed value here is a statement about the fake, not about the transcript."""
    return json.dumps(
        [
            {
                "id": "AT-01",
                "source_turn_ids": ["T02"],
                "role": "client",
                "atom_type": "明确诉求",
                "content": "我们的CA证书好像过期了",
                "decontextualized": "客户的企业CA证书已过期",
            },
            {
                "id": "AT-02",
                "source_turn_ids": ["T09"],
                "role": "agent",
                # `政策引用`, not `操作指引`: the accuracy-question path selects only atoms whose
                # `atom_type` is one of 政策引用/故障定性/业务判断/事实陈述, and an earlier version of
                # this fake used 操作指引 — so the stage was never reached and the assertion in
                # `test_e2e.py` is what caught it.
                "atom_type": "政策引用",
                "content": "企业证书延期需要提供营业执照副本、经办人身份证，还有原CA证书",
                "decontextualized": "客服引用办理要求：企业证书延期所需材料",
            },
        ]
    )


def _coverage(_prompt: str) -> str:
    """`core/atomizer.py:76` — an array of `CoverageRelation`s.

    One row is `ignored`, which is what makes the implied-question path reachable at all: it
    returns early on an empty unresponded set."""
    return json.dumps(
        [
            {
                "client_atom_id": "AT-01",
                "agent_atom_id": "AT-02",
                "status": "ignored",
                "note": "客服未直接回应证书过期的原因",
            },
        ]
    )


def _intent(_prompt: str) -> str:
    """`core/intent_inferrer.py:42` — `.get` on the object; `[]` raises `AttributeError` here."""
    return json.dumps(
        {
            "customer_surface_intent": "咨询CA证书过期的处理方式",
            "customer_deep_intent": "完成证书延期",
            "agent_behavior_pattern": "查证后给出材料清单与办理指引",
            "key_tension": "未说明过期的原因",
            "intent_switches": [],
            "unresolved_intents": [],
        }
    )


def _rubric_question(_prompt: str) -> str:
    """`core/question_generator.py:79` — one question per applicable rubric.

    Returning `{"applicability": "NA"}` here would be a smaller fake and would still reach a
    report — but with zero questions, so stages 4 and 5 would never run. The hypotheses carry a
    token the NLI fake keys on to score the positive side above the negative one."""
    return json.dumps(
        {
            "applicability": "applicable",
            "question": "客服是否确认了客户身份并给出可执行的指引？",
            "hypothesis_pos": "HIGH 客服确认了身份并给出了指引",
            "hypothesis_neg": "LOW 客服没有确认身份也没有给出指引",
        }
    )


def _accuracy_question(_prompt: str) -> str:
    """`core/question_generator.py:145` — the literal path, reached only when there are accuracy
    atoms *and* a domain summary. `claim_type` decides which fact-checking path the question takes."""
    return json.dumps(
        {
            "question": "企业CA证书延期需要哪些材料？",
            "hypothesis_pos": "HIGH 客服列出的材料与企业证书延期的要求一致",
            "hypothesis_neg": "LOW 客服列出的材料与企业证书延期的要求不一致",
            "claim_type": "internal_policy",
        }
    )


def _implied_questions(_prompt: str) -> str:
    """`core/question_generator.py:204` — an array; reached only when coverage has an unresponded
    row, which `_coverage` above provides."""
    return json.dumps(
        [
            {
                "question": "客服是否说明了证书过期的可能原因？",
                "hypothesis_pos": "HIGH 客服说明了过期原因",
                "hypothesis_neg": "LOW 客服没有说明过期原因",
                "implied_q_type": "CONTEXT",
            },
        ]
    )


def _wikichat(_prompt: str) -> str:
    """`core/fact_checker.py:97` — `verdict` and `confidence` are direct-indexed, and
    `confidence` is compared with `<`, so it must be a number."""
    return json.dumps(
        {
            "verdict": "NEI",
            "confidence": 0.0,
            "reasoning": "",
            "key_evidence": "",
        }
    )


def _report_summary(_prompt: str) -> str:
    """`agents/qa_agent.py:132` — both keys are direct-indexed and validated by `QAReport`."""
    return json.dumps(
        {
            "summary": "本次通话客服确认了客户身份并给出指引。",
            "improvement_suggestions": ["建议一", "建议二", "建议三"],
        }
    )


# (marker, reply), tried in order. Each marker is a line unique to one prompt template.
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


# The routes that must fire for a test to be exercising the pipeline rather than the fake.
#
# **What this list does and does not catch (corrected 2026-09-14 by verification).** The first
# version of this comment said that with the empty payloads an earlier revision of this fake
# returned, *none* of these fired. Measured: **three of the six fired anyway** — `atomizer` calls
# its three prompts unconditionally, with no short-circuit on empty input, so
#
#     提取【客户侧】所有原子化陈述 / 判断每个客户原子是否被客服有效响应 / 将以下质检规则转化为
#
# fire under empty payloads too. The three that actually discriminate are the implied-question
# path, the accuracy path and the fact-checker, because each has a gate the empty payloads close.
# So this is a floor for the empty-payload regression, not a discriminator for a pipeline given
# no input at all — `test_e2e.py` carries a separate assertion for that, and it is the one that
# matters.
INTERACTING_ROUTES: tuple[str, ...] = (
    "提取【客户侧】所有原子化陈述",
    "判断每个客户原子是否被客服有效响应",
    "将以下质检规则转化为",
    "生成【Implied 质检子问题】",
    "生成用于核查业务准确性的 Yes-No 子问题",
    "你是一个事实核查员",
)


class FakeLLM:
    """Stands in for `AnthropicClient.complete(prompt, max_tokens=4096) -> str`."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.markers: list[str] = []

    async def complete(self, prompt: str, max_tokens: int = 4096) -> str:
        self.prompts.append(prompt)
        for marker, reply in ROUTES:
            if marker in prompt:
                self.markers.append(marker)
                return reply(prompt)
        raise AssertionError(
            "FakeLLM was asked a question no route covers — the pipeline reached a call "
            "site this fake does not know about:\n" + prompt[:400]
        )


class FakeNLI:
    """Stands in for `NLIModel.score`, which would otherwise download a model on construction.

    Path A compares `best_pos > best_neg` per question, so an even score would fail every
    question — and rubric 27 is `is_veto`, which would pin the report to 0 and hide whether the
    rest of the pipeline worked. Scoring the positive hypothesis strictly higher makes the run a
    happy path in the ordinary sense."""

    def score(self, premise: str, hypothesis: str) -> float:
        return 0.9 if "HIGH" in hypothesis else 0.1
