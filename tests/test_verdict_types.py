"""The re-homed verdict/session types, plus the replay-hash exclusions that
survive the port's retirement (9031 M2).

Two of these tests came from `tests/test_schemas.py`, whose port-fidelity
floor died with the port. Their subjects are core invariants (I5: a
model-produced number never enters the replay-bearing payload), so they were
moved here, re-pointed at the Argus-owned types, and — where a binding named
the ported `Verdict` — re-grounded onto `AnchoredEvidence.score`, the surviving
model-produced surface the replay module's own docstring names.
"""

from __future__ import annotations

import types

import pytest

from argus.types.session import Session, Turn
from argus.types.verdict import RubricCategory, RubricItem, VerdictResult


def test_verdict_result_values_roundtrip():
    assert [v.value for v in VerdictResult] == [
        "pass",
        "fail",
        "partial",
        "NEI",
        "NA",
        "human_review",
    ]
    for v in VerdictResult:
        assert VerdictResult(v.value) is v


def test_rubric_item_roundtrips():
    item = RubricItem(
        id=1,
        category=RubricCategory.PROCESS,
        name="有起接语且完整/外呼明确身份",
        pass_criteria='有起接语 标准起接 "您好。"',
        fail_criteria="",
        weight=2.0,
        is_weighted=True,
    )
    assert RubricItem.model_validate_json(item.model_dump_json()) == item
    assert RubricItem(**item.model_dump()) == item


def test_two_rubric_item_classes_remain_distinct():
    """`compiler_schemas.RubricItem` (a compiled judgment node, str id) and
    `verdict.RubricItem` (a scoring-sheet row, int id) share a name and must
    not converge — nor leak into the package namespace as a coin flip.

    Re-homed from `test_schemas.py:1244`, whose subject survived the port's
    retirement: it compares two Argus-side classes, not the port. Dropped in
    the first pass of M2 and restored on review round 1 (B-verify, 2026-09-20)
    — the worst moment to lose it was exactly when M2 relocated one of the two
    classes into a new module.
    """
    import argus.types as pkg
    from argus.types import compiler_schemas, verdict

    assert compiler_schemas.RubricItem.model_fields["id"].annotation is str
    assert verdict.RubricItem.model_fields["id"].annotation is int
    assert not hasattr(pkg, "RubricItem"), (
        "argus.types must not re-export either RubricItem — the two are "
        "distinguished by module, and a package-level name makes it a coin flip"
    )


def test_session_and_turn_roundtrip():
    session = Session(
        turns=[
            Turn(id="T01", role="agent", text="您好"),
            Turn(id="T02", role="customer", text="我广西这边的"),
        ]
    )
    loaded = Session.model_validate(session.model_dump())
    assert loaded.turns == session.turns
    assert loaded.session_id == session.session_id


def test_replay_payload_still_excludes_proposed_score():
    """I5 — proposed scores never widen what the replay hash sees.

    Exercises 9020's module, which the retirement does not touch.
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


def test_model_produced_numbers_never_enter_replay_hash():
    """I5: model-produced numbers stay out of the replay hash.

    Migrated from the retired port's fidelity floor (was
    `test_m5_verdict_fields_never_enter_replay_hash`); the binding that named
    the ported `Verdict` is re-grounded on `AnchoredEvidence.score`, the
    surviving model-produced surface. Four parts, each guarding a way the
    previous one could pass vacuously:

    1. the evidence type actually declares the model-produced field — a
       rename must error here, not let the exclusion pass over an empty set;
    2. `_hashable()`'s output — the allowlist IS the contract surface —
       carries neither name as a key, at the top level or nested;
    3. real data: two records differing only in `AnchoredEvidence.score`
       hash identically;
    4. liveness: a stand-in namespace whose `_hashable` *does* carry the
       score hashes differently, so part 2 is enforced by difference and
       not by hope.
    """
    from argus.core.adjust import Precedent
    from argus.core.grounding import GroundedFinding, ProposedFinding
    from argus.core.replay import ReplayRecord, _hashable, record_for, replay_hash
    from argus.core.score import ScorableFact
    from argus.types.anchored import AnchoredEvidence, Span

    # 1. Binding: `score` is the field the replay module's docstring names as
    # a model-proposed number riding along; a rename must fail loudly here.
    # `confidence` stays in the swept set even though AnchoredEvidence does not
    # declare it today — the allowlist must keep excluding it if it ever lands.
    model_produced = {"score", "confidence"}
    assert "score" in AnchoredEvidence.model_fields, (
        "AnchoredEvidence no longer declares the model-produced field the I5 "
        "clause names; re-read the replay docstring and update this set, do "
        "not delete it"
    )

    epoch = "c" * 40
    transcript = "[25s -> 30s]客服: 请问您贵姓？"
    quote = "请问您贵姓？"
    start = transcript.index(quote)

    def record(evidence_score: float) -> ReplayRecord:
        finding = GroundedFinding(
            finding=ProposedFinding(
                finding_id="F01",
                rubric_id=1,
                intents_node="process/greeting",
                violation="称谓语缺失",
                evidence=(
                    AnchoredEvidence(
                        turn_id="T01",
                        text=quote,
                        score=evidence_score,
                        supports=True,
                        span=Span(start=start, end=start + len(quote)),
                        quote=quote,
                        intents_sha=epoch,
                    ),
                ),
            ),
            epoch=epoch,
        )
        return record_for(
            intents_sha=epoch,
            rubric_version="v1",
            transcript=transcript,
            findings=(finding,),
            facts=(
                ScorableFact(finding_id="F01", rubric_id=1, outcome=VerdictResult.FAIL),
            ),
            precedents=(
                Precedent(
                    precedent_id="P-1",
                    prior_evaluation_id="prior-eval",
                    rubric_id=1,
                    ruled_outcome=VerdictResult.PASS,
                    intents_sha=epoch,
                ),
            ),
        )

    low, high = record(0.05), record(0.95)

    # Anti-vacuity: the inputs really did differ, on the exact field the
    # replay module's docstring names as a model-proposed number riding along.
    assert low.findings[0].finding.evidence[0].score == 0.05
    assert high.findings[0].finding.evidence[0].score == 0.95

    # 2. The recursive key sweep. Shown to reach the nested dicts, so the
    # empty intersection is a finding, not a sweep that collected nothing.
    collected: set[str] = set()

    def sweep(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                collected.add(key)
                sweep(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                sweep(item)

    sweep(_hashable(low))
    assert "evidence" in collected, "the sweep never reached a nested dict"
    assert not collected & model_produced, (
        f"model-produced keys reached the allowlist: {sorted(collected & model_produced)}"
    )

    # 3. Behavior, on real data: the proposed number does not move the hash.
    assert replay_hash(low) == replay_hash(high)

    # 4. Liveness — prove the hash mechanism consumes its allowlist, so the
    # day `score` is added to it, the hash moves and part 2 has teeth. A
    # vars() copy alone is not enough: the copied replay_hash's globals stay
    # bound to the real module, so the code object is rebound onto the
    # stand-in's namespace explicitly.
    from argus.core import replay as replay_module

    stand_in = types.ModuleType("replay_with_score")
    stand_in.__dict__.update(vars(replay_module))

    def _hashable_with_score(rec: ReplayRecord) -> dict:
        payload = _hashable(rec)
        payload["score"] = rec.findings[0].finding.evidence[0].score
        return payload

    stand_in._hashable = _hashable_with_score
    stand_in_hash = types.FunctionType(
        replay_hash.__code__, stand_in.__dict__, "replay_hash"
    )
    assert stand_in_hash(low) != replay_hash(low), (
        "adding score to the allowlist did not move the hash — part 2's "
        "exclusion is not enforced by the mechanism"
    )
    assert stand_in_hash(low) != stand_in_hash(high), (
        "the stand-in hash does not actually read the score it was given"
    )
