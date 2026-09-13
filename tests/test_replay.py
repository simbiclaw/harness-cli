"""Acceptance tests for 9021 M21 — the replay record.

M21's Contract: *Deliverable* — a stored record that re-derives the verdict.
*Binding constraint* — I5, quoted rather than paraphrased: the hash is a
function of grounded inputs and anchored precedents only, never of the proposed
score. *Acceptance property* — the stored record re-derives an identical
result; changing only the precedent set changes the hash; the proposed score
never does.

The third property is the one with teeth, and it needs a real place for a
proposed score to leak in. There is one: `AnchoredEvidence.score` carries
upstream's number — the NLI entailment score on path A, the model's own
confidence on path B (`simbiclaw/sim@0c2cccd core/fact_checker.py:63,118`). It
is on the record, it is model-authored, and a hash built by dumping the record
would absorb it. So that is what these tests vary.
"""

from __future__ import annotations

import ast
import random
from pathlib import Path

import pytest
from pydantic import ValidationError

from argus.core.adjust import Precedent
from argus.core.grounding import GroundedFinding, ProposedFinding
from argus.core.replay import (
    ReplayMismatch,
    ReplayRecord,
    record_for,
    rederive,
    replay_hash,
    transcript_digest,
)
from argus.core.score import Rubric, ScorableFact, score
from argus.core.adjust import adjust
from argus.types.anchored import AnchoredEvidence, Span
from argus.types.pipeline import RubricCategory, RubricItem, VerdictResult

EPOCH = "a" * 40
OTHER_EPOCH = "b" * 40

TRANSCRIPT = (
    "[1s -> 20s]客户: 您好，我在登录时显示CA锁未绑定。\n"
    "[20s -> 25s]客服: 您好，很高兴为您服务。\n"
    "[25s -> 30s]客服: 请问您贵姓？\n"
)
QUOTE = "请问您贵姓？"
START = TRANSCRIPT.index(QUOTE)


def _item(rubric_id: int, *, weight: float = 1.0, is_veto: bool = False) -> RubricItem:
    return RubricItem(
        id=rubric_id,
        category=RubricCategory.PROCESS,
        name=f"criterion {rubric_id}",
        pass_criteria="p",
        fail_criteria="f",
        weight=weight,
        is_weighted=weight != 1.0,
        is_veto=is_veto,
    )


RUBRIC = Rubric(version="v1", items=(_item(1), _item(2, weight=2.0), _item(27, is_veto=True)))


def _evidence(*, score_value: float = 0.91, supports: bool = True) -> AnchoredEvidence:
    return AnchoredEvidence(
        turn_id="T03",
        text=QUOTE,
        score=score_value,
        supports=supports,
        span=Span(start=START, end=START + len(QUOTE)),
        quote=QUOTE,
        intents_sha=EPOCH,
    )


def _grounded(finding_id: str, rubric_id: int, **ev) -> GroundedFinding:
    return GroundedFinding(
        finding=ProposedFinding(
            finding_id=finding_id,
            rubric_id=rubric_id,
            intents_node="process/greeting",
            violation="称谓语缺失",
            checking_path="A",
            evidence=(_evidence(**ev),),
        ),
        epoch=EPOCH,
    )


def _fact(rubric_id: int, outcome: VerdictResult) -> ScorableFact:
    return ScorableFact(
        finding_id=f"F{rubric_id:02d}", rubric_id=rubric_id, outcome=outcome
    )


def _record(**overrides) -> ReplayRecord:
    kwargs = dict(
        intents_sha=EPOCH,
        rubric_version="v1",
        transcript=TRANSCRIPT,
        findings=(_grounded("F01", 1), _grounded("F02", 2)),
        facts=(_fact(1, VerdictResult.FAIL), _fact(2, VerdictResult.PASS)),
        precedents=(),
    )
    kwargs.update(overrides)
    return record_for(**kwargs)


# ── Re-derivation ────────────────────────────────────────────────────────


def test_stored_graph_rederives_identical_result():
    """The record reproduces what the live pipeline produced, field for field.

    Compared as serialized records rather than on `value` alone: a replay that
    agreed on the total while disagreeing on the breakdown is not a replay.
    """
    facts = (_fact(1, VerdictResult.FAIL), _fact(2, VerdictResult.PASS))
    precedents = (
        Precedent(
            precedent_id="P01",
            prior_evaluation_id="EVAL-0042",
            rubric_id=1,
            ruled_outcome=VerdictResult.PASS,
            intents_sha=EPOCH,
        ),
    )
    live = adjust(score(facts, RUBRIC), precedents)

    record = _record(facts=facts, precedents=precedents)
    replayed = rederive(record, RUBRIC, transcript=TRANSCRIPT)

    assert replayed.model_dump_json() == live.model_dump_json()
    assert replayed.value == 100.0  # the precedent overturned criterion 1


def test_rederivation_is_stable_across_repeats():
    """I5 says *forever*. Ten replays of one record must not drift."""
    record = _record()
    first = rederive(record, RUBRIC).model_dump_json()
    for _ in range(10):
        assert rederive(record, RUBRIC).model_dump_json() == first


def test_replaying_against_a_different_rubric_version_is_refused():
    """The same findings score differently under a different sheet.

    Refused rather than re-derived, because the result would look authoritative
    and be a different evaluation.
    """
    other = Rubric(version="v2", items=RUBRIC.items)
    with pytest.raises(ReplayMismatch, match="rubric v1"):
        rederive(_record(), other)


def test_replaying_against_a_different_transcript_is_refused():
    """The spans index into a text; a different text makes them meaningless."""
    with pytest.raises(ReplayMismatch, match="does not match"):
        rederive(_record(), RUBRIC, transcript=TRANSCRIPT + "extra")


def test_the_digest_is_of_the_transcript_not_a_copy_of_it():
    """The record carries no transcript, so it cannot drift from one."""
    record = _record()
    assert record.transcript_sha256 == transcript_digest(TRANSCRIPT)
    assert TRANSCRIPT not in record.model_dump_json()


# ── The hash: what moves it ──────────────────────────────────────────────


def test_replay_hash_includes_anchored_precedents():
    """Two records identical but for their precedent set must hash differently.

    The failure this prevents: an earlier revision of this milestone hashed
    "grounded inputs only", so two runs citing different precedents — and
    shipping different numbers — were indistinguishable by hash.
    """
    without = _record()
    with_precedent = _record(
        precedents=(
            Precedent(
                precedent_id="P01",
                prior_evaluation_id="EVAL-0042",
                rubric_id=1,
                ruled_outcome=VerdictResult.PASS,
                intents_sha=EPOCH,
            ),
        )
    )
    assert replay_hash(without) != replay_hash(with_precedent)
    # And the numbers really do differ, so the hash is tracking something real.
    assert rederive(without, RUBRIC).value != rederive(with_precedent, RUBRIC).value


def test_two_different_precedent_sets_hash_differently():
    """Not just present-vs-absent: which precedent was cited must matter."""

    def _with(pid: str, ruled: VerdictResult) -> ReplayRecord:
        return _record(
            precedents=(
                Precedent(
                    precedent_id=pid,
                    prior_evaluation_id="EVAL-0042",
                    rubric_id=1,
                    ruled_outcome=ruled,
                    intents_sha=EPOCH,
                ),
            )
        )

    assert replay_hash(_with("P-A", VerdictResult.PASS)) != replay_hash(
        _with("P-B", VerdictResult.PASS)
    )
    assert replay_hash(_with("P-A", VerdictResult.PASS)) != replay_hash(
        _with("P-A", VerdictResult.PARTIAL)
    )


def test_replay_hash_excludes_proposed_score():
    """I5 — never a function of a proposed score.

    `AnchoredEvidence.score` is a model-authored number that is genuinely on the
    record: upstream's NLI entailment score on path A, the model's own
    confidence on path B (`core/fact_checker.py:63,118`). It must not move the
    hash, and the two records below differ in nothing else.
    """
    low = _record(findings=(_grounded("F01", 1, score_value=0.10),))
    high = _record(findings=(_grounded("F01", 1, score_value=0.99),))

    assert low.findings[0].finding.evidence[0].score != high.findings[0].finding.evidence[0].score
    assert replay_hash(low) == replay_hash(high)


def test_the_hash_takes_an_allowlist_not_the_whole_record():
    """The structural reason the previous test keeps passing.

    A hash over `model_dump_json()` would absorb every field anyone adds later.
    This asserts the record serializes the excluded field — so the exclusion is
    a choice the hash makes, not an accident of the field being absent.
    """
    record = _record()
    assert '"score":' in record.model_dump_json()


def test_grounded_inputs_do_move_the_hash():
    """The other direction: the exclusion must not have excluded everything."""
    base = _record()
    for changed in (
        _record(findings=(_grounded("F01", 1), _grounded("F09", 2))),
        _record(facts=(_fact(1, VerdictResult.PASS), _fact(2, VerdictResult.PASS))),
        _record(rubric_version="v2"),
        _record(transcript=TRANSCRIPT + "\n[31s -> 35s]客户: 好的。\n"),
    ):
        assert replay_hash(changed) != replay_hash(base)


def test_a_changed_span_or_quote_moves_the_hash():
    """The anchor is a grounded input. Re-anchoring a finding is a new evaluation."""
    base = _record(findings=(_grounded("F01", 1),))
    moved = ProposedFinding(
        finding_id="F01",
        rubric_id=1,
        intents_node="process/greeting",
        violation="称谓语缺失",
        checking_path="A",
        evidence=(
            AnchoredEvidence(
                turn_id="T03",
                text="您好",
                score=0.91,
                supports=True,
                span=Span(start=0, end=2),
                quote="[1",
                intents_sha=EPOCH,
            ),
        ),
    )
    other = _record(findings=(GroundedFinding(finding=moved, epoch=EPOCH),))
    assert replay_hash(other) != replay_hash(base)


def test_the_hash_is_order_independent():
    """A hash that changes when a list is shuffled reports a difference that isn't one."""
    findings = [_grounded(f"F{i:02d}", 1) for i in range(5)]
    facts = [
        ScorableFact(finding_id=f"F{i:02d}", rubric_id=1, outcome=VerdictResult.FAIL)
        for i in range(5)
    ]
    baseline = replay_hash(_record(findings=tuple(findings), facts=tuple(facts)))
    for seed in range(10):
        shuffled_f, shuffled_x = list(findings), list(facts)
        random.Random(seed).shuffle(shuffled_f)
        random.Random(seed + 100).shuffle(shuffled_x)
        assert replay_hash(_record(findings=tuple(shuffled_f), facts=tuple(shuffled_x))) == baseline


def test_the_hash_is_a_sha256_hex_digest():
    assert len(replay_hash(_record())) == 64
    assert set(replay_hash(_record())) <= set("0123456789abcdef")


# ── I4: one evaluation, one epoch ────────────────────────────────────────


def test_a_record_without_a_real_epoch_is_refused():
    for bad in ("", "latest", "a" * 39, "z" * 40, "A" * 40):
        with pytest.raises(ValidationError):
            _record(intents_sha=bad)


def test_a_precedent_from_another_epoch_cannot_enter_the_record():
    """I4 — a ruling made against a different tree is not a ruling about this one."""
    foreign = Precedent(
        precedent_id="P01",
        prior_evaluation_id="EVAL-0042",
        rubric_id=1,
        ruled_outcome=VerdictResult.PASS,
        intents_sha=OTHER_EPOCH,
    )
    with pytest.raises(ValidationError, match="one evaluation, one epoch"):
        _record(precedents=(foreign,))


def test_a_malformed_transcript_digest_is_refused():
    with pytest.raises(ValidationError, match="not a SHA-256 digest"):
        ReplayRecord(
            intents_sha=EPOCH,
            rubric_version="v1",
            transcript_sha256="deadbeef",
        )


# ── Purity ───────────────────────────────────────────────────────────────


def test_replay_no_model_client_and_no_impurity():
    """I1 and purity — no model, no clock, no RNG in the replay lane."""
    source = Path(__file__).resolve().parent.parent / "src" / "argus" / "core" / "replay.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])

    forbidden = {
        "anthropic", "openai", "transformers", "torch", "chromadb", "httpx",
        "random", "time", "datetime", "secrets", "uuid",
    }
    assert forbidden.isdisjoint(roots), f"impurity reached the replay lane: {roots & forbidden}"

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("argus."):
            assert node.module.split(".")[1] in {"types", "config", "core"}, node.module
