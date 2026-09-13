"""Acceptance tests for 9021 M5 — the pipeline's data contracts live in types/.

The first attempt at M5 was rejected. Every defect was an *invention*: two enums
were silently rewritten with members that exist nowhere upstream, three required
fields were relaxed, and a mechanism was added that nothing sets and nothing
reads. The acceptance test could not see any of it, because it constructed
instances with keyword arguments and compared a JSON round-trip — and pydantic
ignores keyword arguments naming fields a model no longer has, so a model with a
field deleted round-trips trivially. Eight of ten planted deletions passed.

So these tests assert on the *shape* of each contract, not on its behaviour
under a round-trip. `model_fields` is compared against an explicit expected set
transcribed from `simbiclaw/sim@0c2cccd` `models/schemas.py`, and enum members
are compared name-and-value. A deleted field fails immediately and loudly;
`test_the_checks_can_fail` proves that rather than asserting it.

Per the milestone's Contract block, the binding constraint is I5 — the
replay-bearing record stays separable from diagnostics.
"""

from __future__ import annotations

import enum

import pytest

from argus.types import pipeline as p

# Transcribed field-for-field from simbiclaw/sim@0c2cccd models/schemas.py.
# This is the frozen shape of the upstream contract; drift from it is the
# defect the first attempt shipped.
EXPECTED_FIELDS: dict[str, set[str]] = {
    "CleanTurn": {
        "id", "role", "text", "flags", "reliability",
        "timestamp_start", "timestamp_end",
    },
    "CleanTranscript": {
        "session_id", "turns", "asr_quality", "role_swap_detected",
        "low_reliability_turn_ids",
    },
    "RubricItem": {
        "id", "category", "name", "pass_criteria", "fail_criteria",
        "na_criteria", "is_weighted", "weight", "always_check",
        "requires_domain_kb", "trigger_keywords", "is_veto",
    },
    "KBContent": {"path", "content", "level", "node_type"},
    "SessionKBContext": {
        "primary_intent_path", "secondary_intent_paths", "kb_contents",
        "domain_knowledge_summary", "all_rubric_items", "applicable_rubrics",
        "coverage_score", "low_coverage_warning", "unmatched_entities",
    },
    "Turn": {"id", "role", "text", "reliability", "flags"},
    "Session": {"session_id", "agent_id", "duration_sec", "turns", "metadata"},
    "Atom": {
        "id", "source_turn_ids", "role", "atom_type", "content",
        "decontextualized", "reliability", "intent_group",
    },
    "CoverageRelation": {"client_atom_id", "agent_atom_id", "status", "note"},
    "IntentSwitch": {"turn_id", "from_intent", "to_intent", "agent_recognized"},
    "IntentInference": {
        "customer_surface_intent", "customer_deep_intent",
        "agent_behavior_pattern", "key_tension", "intent_switches",
        "unresolved_intents",
    },
    "Subquestion": {
        "id", "question", "q_type", "source", "claim_type", "rubric_id",
        "source_atom_ids", "hypothesis_pos", "hypothesis_neg", "dimension",
        "is_veto", "implied_q_type", "applicability", "na_reason",
    },
    "EvidenceItem": {"turn_id", "doc_path", "text", "score", "supports"},
    "Verdict": {
        "question_id", "rubric_id", "result", "confidence", "score", "weight",
        "evidence", "requires_human_review", "review_reason", "checking_path",
    },
    "DimensionScore": {
        "name", "applicable_count", "passed_count", "weighted_score",
        "total_weight",
    },
    "QAReport": {
        "session_id", "agent_id", "overall_score", "grade", "veto_triggered",
        "veto_items", "dimension_scores", "verdicts", "questions",
        "requires_human_review", "human_review_items", "asr_quality_warning",
        "role_swap_detected", "multi_intent_detected", "unresolved_intents",
        "low_kb_coverage_warning", "summary", "improvement_suggestions",
    },
}

# Member name -> wire value. The wire value is what lands on disk, so a changed
# value is an on-disk format change even when the member name survives.
EXPECTED_ENUMS: dict[str, dict[str, str]] = {
    "ASRQuality": {"GOOD": "good", "FAIR": "fair", "POOR": "poor"},
    "TurnFlag": {
        "INCOMPLETE": "INCOMPLETE", "ASR_ERROR": "ASR_ERROR",
        "ROLE_SWAPPED": "ROLE_SWAPPED", "NORMAL": "NORMAL",
    },
    "RubricCategory": {
        "PROCESS": "流程遵守", "ATTITUDE": "态度规范", "SKILL": "技能技巧",
        "SPECIAL": "特殊项", "ACCURACY": "准确性",
    },
    "ClientAtomType": {
        "FACT_CLAIM": "事实声明", "FAULT_DESCRIPTION": "故障描述",
        "EXPLICIT_REQUEST": "明确诉求", "HISTORICAL_CLAIM": "历史声称",
        "INFERRED_CLAIM": "推断声称", "OBJECTION": "异议",
    },
    "AgentAtomType": {
        "BUSINESS_JUDGMENT": "业务判断", "FACT_STATEMENT": "事实陈述",
        "POLICY_CITATION": "政策引用", "FAULT_DIAGNOSIS": "故障定性",
        "SOLUTION_OFFER": "解决方案", "OPERATION_GUIDE": "操作指引",
        "SERVICE_PROMISE": "服务承诺", "CLOSING_ACTION": "结案行为",
        "SERVICE_ACTION": "服务行为",
    },
    "CoverageStatus": {
        "RESPONDED": "responded", "PARTIAL": "partial", "IGNORED": "ignored",
    },
    "ClaimType": {
        "DIALOGUE_CONSISTENCY": "dialogue_consistency",
        "EXTERNAL_FACT": "external_fact",
        "INTERNAL_POLICY": "internal_policy",
        "ASR_UNCERTAIN": "asr_uncertain",
    },
    "ImpliedQType": {
        "DOMAIN_KNOWLEDGE": "DOMAIN_KNOWLEDGE", "CONTEXT": "CONTEXT",
        "IMPLICIT_MEANING": "IMPLICIT_MEANING",
        "STATISTICAL_RIGOR": "STATISTICAL_RIGOR",
    },
    "QuestionSource": {
        "RUBRIC_DRIVEN": "rubric_driven", "ATOM_LITERAL": "atom_literal",
        "ATOM_IMPLIED": "atom_implied",
    },
    "VerdictResult": {
        "PASS": "pass", "FAIL": "fail", "PARTIAL": "partial", "NEI": "NEI",
        "NA": "NA", "HUMAN_REVIEW": "human_review",
    },
}

# Fields upstream declares without a default. Relaxing one turns missing
# information into a confident claim — `asr_quality` defaulting to GOOD would
# assert a transcript is trustworthy when it was never assessed.
EXPECTED_REQUIRED: dict[str, set[str]] = {
    "CleanTranscript": {"session_id", "turns", "asr_quality"},
    "Atom": {"id", "source_turn_ids", "role", "atom_type", "content",
             "decontextualized"},
    "CoverageRelation": {"client_atom_id", "status"},
    "Verdict": {"question_id", "result", "confidence", "score"},
    "EvidenceItem": {"text", "score", "supports"},
}


def _fields(name: str) -> set[str]:
    return set(getattr(p, name).model_fields)


@pytest.mark.parametrize("name", sorted(EXPECTED_FIELDS))
def test_model_field_sets_match_upstream(name):
    """Every ported model carries exactly the upstream field set.

    Not 'round-trips cleanly' — a model missing a field round-trips perfectly.
    """
    assert _fields(name) == EXPECTED_FIELDS[name]


@pytest.mark.parametrize("name", sorted(EXPECTED_ENUMS))
def test_enum_members_and_values_match_upstream(name):
    """Members and wire values both, since the value is what lands on disk."""
    member = getattr(p, name)
    assert issubclass(member, enum.Enum)
    actual = {m.name: m.value for m in member}
    assert actual == EXPECTED_ENUMS[name]


@pytest.mark.parametrize("name", sorted(EXPECTED_REQUIRED))
def test_required_fields_stay_required(name):
    """A field upstream demands is not quietly given a default here."""
    model = getattr(p, name)
    required = {f for f, info in model.model_fields.items() if info.is_required()}
    assert EXPECTED_REQUIRED[name] <= required


def test_the_checks_can_fail():
    """The shape checks fire on a planted defect.

    Without this the suite asserts its own competence. A structural check that
    has never been shown to fail is not evidence — the rejected first attempt
    passed ten planted mutations.
    """
    from pydantic import BaseModel

    class Truncated(BaseModel):
        id: str  # upstream CleanTurn has seven fields

    assert set(Truncated.model_fields) != EXPECTED_FIELDS["CleanTurn"]

    class WrongWire(str, enum.Enum):
        INCOMPLETE = "incomplete"  # upstream value is "INCOMPLETE"

    assert {m.name: m.value for m in WrongWire} != EXPECTED_ENUMS["TurnFlag"]


def test_upstream_output_loads():
    """The port reads what the upstream system actually writes.

    The rejected attempt could not: it had invented TurnFlag members and
    dropped ASR_ERROR and ROLE_SWAPPED, both emitted by live code at
    core/asr_preprocessor.py:46,54. This pins the wire format against a
    realistic payload rather than against instances this test built itself.
    """
    on_disk = (
        '{"session_id":"S-0001",'
        '"turns":[{"id":"T01","role":"customer","text":"您好，我在登录时显示CA锁未绑定。",'
        '"flags":["ASR_ERROR","ROLE_SWAPPED"],"reliability":"low",'
        '"timestamp_start":1,"timestamp_end":20}],'
        '"asr_quality":"fair","role_swap_detected":true,'
        '"low_reliability_turn_ids":["T01"]}'
    )
    t = p.CleanTranscript.model_validate_json(on_disk)
    assert t.turns[0].flags == [p.TurnFlag.ASR_ERROR, p.TurnFlag.ROLE_SWAPPED]
    assert t.turns[0].timestamp_end == 20

    coverage = '{"client_atom_id":"CA-01","agent_atom_id":"AA-01","status":"responded"}'
    assert p.CoverageRelation.model_validate_json(coverage).status is p.CoverageStatus.RESPONDED


def test_contracts_roundtrip():
    """Real instances survive serialize -> deserialize unchanged."""
    verdict = p.Verdict(
        question_id="RQ-01",
        rubric_id=27,
        result=p.VerdictResult.PASS,
        confidence=0.91,
        score=1.0,
        evidence=[p.EvidenceItem(turn_id="T01", text="片段", score=0.9, supports=True)],
    )
    assert p.Verdict.model_validate_json(verdict.model_dump_json()) == verdict

    atom = p.Atom(
        id="CA-01",
        source_turn_ids=["T01"],
        role="client",
        atom_type=p.ClientAtomType.FAULT_DESCRIPTION.value,
        content="登录时显示CA锁未绑定",
        decontextualized="客户在登录系统时遇到CA锁未绑定的提示",
    )
    assert p.Atom.model_validate_json(atom.model_dump_json()) == atom


def test_types_package_has_one_rubric_item_per_module_and_they_differ():
    """The name `RubricItem` is now used twice in argus.types, deliberately.

    `compiler_schemas.RubricItem` is a SpecificRubric row destined for the 9003
    compiler and keys on a string id. `pipeline.RubricItem` is the upstream
    scoring-sheet row and keys on an int. They model the same sheet at different
    maturities and reconciling them is M15's job, not M5's — porting a third
    shape here would have been the same invention that got M5 rejected.

    This test exists so the collision is a recorded fact rather than a trap: it
    fails the moment someone makes them silently interchangeable.
    """
    from argus.types import compiler_schemas as cs

    assert cs.RubricItem.model_fields["id"].annotation is str
    assert p.RubricItem.model_fields["id"].annotation is int
    assert set(cs.RubricItem.model_fields) != set(p.RubricItem.model_fields)


def test_replay_payload_still_excludes_proposed_score():
    """I5 — the port did not widen what the replay hash sees.

    This exercises 9020's module rather than M5's, which is a real limitation:
    it proves the mechanism is intact, not that the new contracts respect it.
    Nothing in `pipeline.py` reaches the payload yet because nothing constructs
    a FindingGraph from it. Tying the two together is M21's work, and the risk
    in the gap is `Verdict.score` — model-produced upstream, unmarked here.
    """
    from argus.types.proposer_diagnostics import (
        GroundedFinding,
        ProposedScores,
        QuarantinedFindingGraph,
        replay_hash,
    )

    grounded = [GroundedFinding(dimension="准确性", deduction=0.25)]
    bare = QuarantinedFindingGraph(
        grounded=grounded, intents_sha="a" * 40, rubric_version="v1"
    )
    with_scores = QuarantinedFindingGraph(
        grounded=grounded,
        intents_sha="a" * 40,
        rubric_version="v1",
        proposed_scores=ProposedScores(scores={"准确性": 12.03}, g_used=20),
        proposer_id="qwen3.5-27b-4bit",
    )
    assert replay_hash(bare) == replay_hash(with_scores)
