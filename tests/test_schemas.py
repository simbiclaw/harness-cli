"""Acceptance tests for 9021 M5 — the pipeline's data contracts live in types/.

Two properties, per the milestone's Contract block:

- Every contract round-trips: construct, serialize, deserialize, compare equal.
  A contract that cannot survive a JSON round-trip cannot be persisted, and I5
  requires the grounded record to be persisted.
- A proposed score cannot enter the replay-bearing payload (I5). The port must
  not have widened what the replay hash sees.

See docs/exec-plans/active/9021-relayer-argus-eval-pipeline.md
"""

from __future__ import annotations

import pytest

from argus.types.evaluation import (
    Atom,
    ClaimType,
    CoverageRelation,
    CoverageStatus,
    EvidenceItem,
    QuestionSource,
    Subquestion,
    Verdict,
    VerdictResult,
)
from argus.types.rubric import RubricCategory, RubricItem
from argus.types.transcript import (
    ASRQuality,
    CleanTranscript,
    CleanTurn,
    TurnFlag,
)

# Each entry is a real instance of a contract the pipeline passes between
# stages. Explicit rather than generated: the point is to exercise the field
# set an implementer would actually populate, not a synthetic minimum.
CONTRACTS = [
    CleanTurn(
        id="T01",
        role="customer",
        text="您好，我在登录时显示CA锁未绑定。",
        flags=[TurnFlag.UNCERTAIN] if hasattr(TurnFlag, "UNCERTAIN") else [],
        reliability="high",
        timestamp_start=1,
        timestamp_end=20,
    ),
    CleanTranscript(
        session_id="S-0001",
        turns=[CleanTurn(id="T01", role="agent", text="您好，很高兴为您服务。")],
        asr_quality=ASRQuality.GOOD,
        role_swap_detected=False,
        low_reliability_turn_ids=[],
    ),
    RubricItem(
        id=27,
        category=RubricCategory.ACCURACY,
        name="保证用户信息受到保护，不私自泄漏或公布用户隐私",
        pass_criteria="未泄漏用户隐私信息",
        fail_criteria="向第三方透露用户信息",
        is_veto=True,
    ),
    Atom(
        id="CA-01",
        source_turn_ids=["T01"],
        role="client",
        atom_type="故障描述",
        content="登录时显示CA锁未绑定",
        decontextualized="客户在登录系统时遇到CA锁未绑定的提示",
        reliability="high",
    ),
    CoverageRelation(
        client_atom_id="CA-01",
        agent_atom_id="AA-01",
        status=CoverageStatus.COVERED
        if hasattr(CoverageStatus, "COVERED")
        else list(CoverageStatus)[0],
    ),
    Subquestion(
        id="RQ-01",
        question="客服是否保护了用户隐私信息？",
        q_type="literal",
        source=QuestionSource.RUBRIC_DRIVEN,
        claim_type=ClaimType.DIALOGUE_CONSISTENCY,
        rubric_id=27,
        hypothesis_pos="客服未泄漏用户隐私信息。",
        hypothesis_neg="客服泄漏了用户隐私信息。",
        dimension="准确性",
        is_veto=True,
    ),
    EvidenceItem(
        turn_id="T01",
        text="您好，我在登录时显示CA锁未绑定。",
        score=0.91,
        supports=True,
    ),
    Verdict(
        question_id="RQ-01",
        rubric_id=27,
        result=VerdictResult.PASS,
        confidence=0.91,
        score=1.0,
        weight=1.0,
        evidence=[EvidenceItem(turn_id="T01", text="片段", score=0.9, supports=True)],
        checking_path="A",
    ),
]


@pytest.mark.parametrize("instance", CONTRACTS, ids=lambda i: type(i).__name__)
def test_all_schemas_roundtrip(instance):
    """Every contract survives serialize -> deserialize unchanged."""
    model = type(instance)
    restored = model.model_validate_json(instance.model_dump_json())
    assert restored == instance


def test_evidence_item_requires_a_provenance_arm():
    """Evidence names where it came from — a turn or a document, not neither.

    I2 requires a finding to reference something real. An evidence item with
    neither arm populated cannot be anchored by any later gate, so the contract
    rejects it at construction rather than letting it reach S3.
    """
    with pytest.raises(ValueError):
        EvidenceItem(text="从哪来的都不知道", score=0.5, supports=True)


def test_replay_payload_excludes_proposed_score():
    """I5 — the port did not widen what the replay hash sees.

    Two graphs identical in their grounded findings but differing in the
    quarantined block must hash identically. If the port let a proposed score
    into the payload, proposer nondeterminism would infect the replay contract.
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
