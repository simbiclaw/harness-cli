"""Acceptance tests for 9021 M18 — the precedent-application stage.

M18's Contract: *Deliverable* — the precedent-application stage. *Binding
constraint* — I3 (`adjust(raw, history)` is pure, and unanchored precedents are
dropped rather than applied) and I5 (anchored precedents enter the replay hash).
*Acceptance property* — empty precedents leave the score unchanged; the applied
set is recorded and replayable.

Neither codebase has a notion of precedent, so the tests below are testing a
design rather than a port. The things they pin down, in order of how much
damage getting them wrong would do:

1. Empty history is a true identity, not an approximate one. If it were not,
   every call without precedent would be quietly mis-scored.
2. A precedent overturns an *outcome*; the points are re-derived from the
   weight on the record. A precedent carrying its own delta would be a score
   with no span (I7).
3. Adjustment re-derives the total rather than patching it, so overturning the
   failure that caused a veto also lifts the veto.
4. A precedent cannot pull a deferred criterion back into the arithmetic — that
   would let history close a coverage gap D10 reserves for a human.
"""

from __future__ import annotations

import ast
import inspect
import random
from pathlib import Path

import pytest
from pydantic import ValidationError

from argus.core.adjust import (
    AdjustedScore,
    DropReason,
    Precedent,
    adjust,
)
from argus.core.score import Rubric, ScorableFact, score
from argus.types.pipeline import RubricCategory, RubricItem, VerdictResult

EPOCH = "a" * 40


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


def _fact(rubric_id: int, outcome: VerdictResult) -> ScorableFact:
    return ScorableFact(
        finding_id=f"F{rubric_id:02d}", rubric_id=rubric_id, outcome=outcome
    )


def _precedent(rubric_id: int, ruled: VerdictResult, *, pid: str = "") -> Precedent:
    return Precedent(
        precedent_id=pid or f"P{rubric_id:02d}",
        prior_evaluation_id="EVAL-2026-07-31-0042",
        rubric_id=rubric_id,
        ruled_outcome=ruled,
        intents_sha=EPOCH,
    )


# ── I3: empty history is the identity ────────────────────────────────────


def test_empty_precedents_adjusted_equals_raw():
    """The property that makes the stage safe to always run.

    Checked on every arithmetic field, not just `value`: a stage that agreed on
    the total while disagreeing on the denominator would corrupt whatever reads
    the record next.
    """
    rubric = Rubric(
        version="v1", items=(_item(1), _item(2, weight=2.0), _item(3), _item(4))
    )
    raw = score(
        [
            _fact(1, VerdictResult.PASS),
            _fact(2, VerdictResult.FAIL),
            _fact(3, VerdictResult.NEI),
            _fact(4, VerdictResult.NA),
        ],
        rubric,
    )
    adjusted = adjust(raw, [])

    assert adjusted.value == raw.value
    assert adjusted.numerator == raw.numerator
    assert adjusted.denominator == raw.denominator
    assert adjusted.veto_triggered == raw.veto_triggered
    assert adjusted.veto_criteria == raw.veto_criteria
    assert adjusted.contributions == raw.contributions
    assert adjusted.deferrals == raw.deferrals
    assert adjusted.rubric_version == raw.rubric_version
    assert adjusted.raw_value == raw.value
    assert adjusted.applied == ()
    assert adjusted.dropped == ()


def test_a_precedent_agreeing_with_the_machine_changes_nothing():
    """Agreement is not an application. Recording it would inflate the hash input."""
    rubric = Rubric(version="v1", items=(_item(1),))
    raw = score([_fact(1, VerdictResult.PASS)], rubric)
    adjusted = adjust(raw, [_precedent(1, VerdictResult.PASS)])

    assert adjusted.applied == ()
    assert adjusted.value == raw.value


def test_adjust_is_order_independent_and_replayable():
    """I5 — the stored record re-derives the identical result, in any order."""
    rubric = Rubric(version="v1", items=(_item(1), _item(2), _item(3), _item(9)))
    raw = score(
        [
            _fact(1, VerdictResult.FAIL),
            _fact(2, VerdictResult.FAIL),
            _fact(3, VerdictResult.PASS),
        ],
        rubric,
    )
    history = [
        _precedent(1, VerdictResult.PASS),
        _precedent(2, VerdictResult.PARTIAL),
        _precedent(9, VerdictResult.PASS),  # criterion not scored here
    ]
    baseline = adjust(raw, history).model_dump_json()
    for seed in range(20):
        shuffled = list(history)
        random.Random(seed).shuffle(shuffled)
        assert adjust(raw, shuffled).model_dump_json() == baseline


# ── The points are re-derived, never carried ─────────────────────────────


def test_a_precedent_carries_an_outcome_not_a_delta():
    """I7 — a digit has no span, so a precedent may not name one.

    The field set is the proof: there is nowhere to put a number of points, so
    no code path can apply one.
    """
    fields = set(Precedent.model_fields)
    assert fields == {
        "precedent_id",
        "prior_evaluation_id",
        "rubric_id",
        "ruled_outcome",
        "intents_sha",
    }
    with pytest.raises(ValidationError):
        Precedent(
            precedent_id="P01",
            prior_evaluation_id="E1",
            rubric_id=1,
            ruled_outcome=VerdictResult.PASS,
            intents_sha=EPOCH,
            delta=-3.0,
        )


def test_the_overturned_points_come_from_the_rubric_weight():
    """Overturning a weighted row must move the score by that row's weight.

    Criterion 2 carries weight 2.0. Raw is 1 of 3; overturning it is 3 of 3. A
    stage that applied a flat one-point credit would report 66.7 here and would
    have looked correct on an unweighted example.
    """
    rubric = Rubric(version="v1", items=(_item(1), _item(2, weight=2.0)))
    raw = score([_fact(1, VerdictResult.PASS), _fact(2, VerdictResult.FAIL)], rubric)
    assert raw.value == pytest.approx(33.3)

    adjusted = adjust(raw, [_precedent(2, VerdictResult.PASS)])
    assert adjusted.numerator == 3.0
    assert adjusted.denominator == 3.0
    assert adjusted.value == 100.0


def test_applied_precedents_recorded():
    """I5 — the applied set is on the record, with what it overturned."""
    rubric = Rubric(version="v1", items=(_item(1), _item(2)))
    raw = score([_fact(1, VerdictResult.FAIL), _fact(2, VerdictResult.PASS)], rubric)
    adjusted = adjust(raw, [_precedent(1, VerdictResult.PASS)])

    assert len(adjusted.applied) == 1
    entry = adjusted.applied[0]
    assert entry.precedent_id == "P01"
    assert entry.rubric_id == 1
    assert entry.finding_id == "F01"
    assert entry.from_outcome is VerdictResult.FAIL
    assert entry.to_outcome is VerdictResult.PASS
    assert adjusted.raw_value == raw.value != adjusted.value


def test_the_adjusted_record_re_derives_its_own_total():
    """The result's contributions must sum to the result's numerator.

    A record whose breakdown disagrees with its total is not replayable, and the
    disagreement would be invisible to anyone reading only the number.
    """
    rubric = Rubric(version="v1", items=(_item(1), _item(2, weight=2.0), _item(3)))
    raw = score(
        [
            _fact(1, VerdictResult.FAIL),
            _fact(2, VerdictResult.FAIL),
            _fact(3, VerdictResult.PASS),
        ],
        rubric,
    )
    adjusted = adjust(raw, [_precedent(2, VerdictResult.PASS)])

    assert sum(c.credit * c.weight for c in adjusted.contributions) == adjusted.numerator
    assert sum(c.weight for c in adjusted.contributions) == adjusted.denominator
    assert adjusted.value == round(adjusted.numerator / adjusted.denominator * 100, 1)


# ── Re-derivation, not patching ──────────────────────────────────────────


def test_overturning_the_failure_lifts_the_veto_it_caused():
    """The case a patch-the-total implementation gets wrong.

    Raw is zero because criterion 27 — the privacy veto — failed. Overturning
    that failure must restore the real score, not add points to a zero.
    """
    rubric = Rubric(version="v1", items=(_item(1), _item(27, is_veto=True)))
    raw = score([_fact(1, VerdictResult.PASS), _fact(27, VerdictResult.FAIL)], rubric)
    assert raw.veto_triggered is True
    assert raw.value == 0.0

    adjusted = adjust(raw, [_precedent(27, VerdictResult.PASS)])
    assert adjusted.veto_triggered is False
    assert adjusted.veto_criteria == ()
    assert adjusted.value == 100.0


def test_a_precedent_can_also_impose_a_veto():
    """The rule runs in both directions; precedent is not a one-way ratchet."""
    rubric = Rubric(version="v1", items=(_item(1), _item(27, is_veto=True)))
    raw = score([_fact(1, VerdictResult.PASS), _fact(27, VerdictResult.PASS)], rubric)
    assert raw.value == 100.0

    adjusted = adjust(raw, [_precedent(27, VerdictResult.FAIL)])
    assert adjusted.veto_triggered is True
    assert adjusted.veto_criteria == (27,)
    assert adjusted.value == 0.0


def test_partial_on_a_veto_criterion_is_not_a_veto():
    """`PARTIAL` earns no credit but is not a failure (`aggregator.py:76`).

    Recomputing the veto from "earned no credit" rather than from the outcome
    would zero this call, and no test that only used PASS and FAIL would notice.
    """
    rubric = Rubric(version="v1", items=(_item(27, is_veto=True),))
    raw = score([_fact(27, VerdictResult.PASS)], rubric)
    adjusted = adjust(raw, [_precedent(27, VerdictResult.PARTIAL)])

    assert adjusted.veto_triggered is False
    assert adjusted.value == 0.0  # no credit, but not a veto


# ── Unanchored and inapplicable precedents ───────────────────────────────


def test_unanchored_precedent_dropped():
    """I4 — a precedent whose epoch is not a commit cannot be constructed.

    Rejected at construction rather than tolerated and skipped, so that a drop
    on the result always means "inapplicable to this call" rather than
    "unreadable".
    """
    for bad in ("", "latest", "a" * 39, "z" * 40, "A" * 40):
        with pytest.raises(ValidationError):
            Precedent(
                precedent_id="P01",
                prior_evaluation_id="E1",
                rubric_id=1,
                ruled_outcome=VerdictResult.PASS,
                intents_sha=bad,
            )
    # An anchor that is present but empty is the same failure with better manners.
    for blank in ("precedent_id", "prior_evaluation_id"):
        payload = _precedent(1, VerdictResult.PASS).model_dump()
        payload[blank] = ""
        with pytest.raises(ValidationError):
            Precedent(**payload)


def test_a_precedent_ruling_a_non_scoring_outcome_is_refused():
    """`NEI`, `NA` and `HUMAN_REVIEW` do not score, so they cannot overturn.

    Allowing one would let a precedent delete a row from the denominator, which
    is a coverage change wearing a scoring change's clothes.
    """
    for outcome in (VerdictResult.NEI, VerdictResult.NA, VerdictResult.HUMAN_REVIEW):
        with pytest.raises(ValidationError, match="does not score"):
            _precedent(1, outcome)


def test_a_precedent_for_an_unscored_criterion_is_dropped_and_recorded():
    """Silence about an ignored precedent is what makes a number untrustworthy."""
    rubric = Rubric(version="v1", items=(_item(1),))
    raw = score([_fact(1, VerdictResult.PASS)], rubric)
    adjusted = adjust(raw, [_precedent(99, VerdictResult.FAIL)])

    assert adjusted.value == raw.value
    assert adjusted.applied == ()
    assert len(adjusted.dropped) == 1
    assert adjusted.dropped[0].rubric_id == 99
    assert adjusted.dropped[0].reason is DropReason.NO_SUCH_CRITERION


def test_a_precedent_cannot_resurrect_a_deferred_criterion():
    """D10 — history may not close a coverage gap.

    The deferral survives adjustment untouched, and the criterion stays out of
    the denominator. Whether the call can auto-finalise is still decided by the
    coverage and criterion-health gates, on the deferrals this record carries.
    """
    rubric = Rubric(version="v1", items=(_item(1), _item(2)))
    raw = score([_fact(1, VerdictResult.PASS), _fact(2, VerdictResult.NEI)], rubric)
    adjusted = adjust(raw, [_precedent(2, VerdictResult.PASS)])

    assert adjusted.denominator == 1.0
    assert adjusted.deferrals == raw.deferrals
    assert adjusted.applied == ()
    assert adjusted.dropped[0].reason is DropReason.CRITERION_DEFERRED


def test_two_precedents_on_one_criterion_is_an_error_not_a_last_writer_win():
    """Which of two conflicting rulings binds is a human's call.

    Picking one silently — first or last — would make the shipped number depend
    on the order history happened to be read in, which I5 forbids.
    """
    rubric = Rubric(version="v1", items=(_item(1),))
    raw = score([_fact(1, VerdictResult.FAIL)], rubric)
    history = [
        _precedent(1, VerdictResult.PASS, pid="P-A"),
        _precedent(1, VerdictResult.PARTIAL, pid="P-B"),
    ]
    with pytest.raises(ValueError, match="two precedents rule on criterion 1"):
        adjust(raw, history)


def test_a_precedent_applies_to_every_finding_on_its_criterion():
    """One criterion can carry several findings; a ruling binds the criterion.

    Applying it to only the first would make the result depend on which finding
    happened to be enumerated first.
    """
    rubric = Rubric(version="v1", items=(_item(1),))
    raw = score(
        [
            ScorableFact(finding_id="F-a", rubric_id=1, outcome=VerdictResult.FAIL),
            ScorableFact(finding_id="F-b", rubric_id=1, outcome=VerdictResult.FAIL),
        ],
        rubric,
    )
    adjusted = adjust(raw, [_precedent(1, VerdictResult.PASS)])

    assert len(adjusted.applied) == 2
    assert {a.finding_id for a in adjusted.applied} == {"F-a", "F-b"}
    assert adjusted.value == 100.0


# ── I3 / I1: purity and the fence ────────────────────────────────────────


def test_adjust_takes_raw_and_history_and_nothing_else():
    """I3's second stage, in its structural form."""
    params = inspect.signature(adjust).parameters
    assert tuple(params) == ("raw", "history")
    for param in params.values():
        assert param.default is inspect.Parameter.empty


def test_adjust_no_model_client_and_no_impurity():
    """I1 and purity — no model, no clock, no RNG in the adjusted lane."""
    source = Path(__file__).resolve().parent.parent / "src" / "argus" / "core" / "adjust.py"
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
    assert forbidden.isdisjoint(roots), f"impurity reached the adjusted lane: {roots & forbidden}"

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("argus."):
            assert node.module.split(".")[1] in {"types", "config", "core"}, node.module


def test_the_adjusted_record_does_not_carry_a_proposed_score():
    """I5 — the replay hash takes grounded inputs and anchored precedents only.

    A `proposed_score` field on this record would be one edit away from entering
    the hash. There is none, and this states why.
    """
    for field in AdjustedScore.model_fields:
        assert "proposed" not in field
