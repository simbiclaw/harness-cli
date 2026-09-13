"""Acceptance tests for 9021 M19 — S5 routing and the reconciled estimator.

M19's Contract: *Deliverable* — S5 routing, and the escape estimator reconciled
with the sampler. *Binding constraint* — D10 (auto-final requires both axes
clear); the estimator consumes the random tranche only, and that tranche
respects its declared floor. *Acceptance property* — a call carrying ungrounded
findings never auto-finalises; a biased sample cannot reach the estimator; the
floor holds whatever the prioritisation asks for.

The plan's advisory: "The floor has no declared value anywhere — declare one
during execution and record its basis." It is declared in
`core/escape_rate.py` as `ESCAPE_RATE_FLOOR = 60`, from the rule of three
against the 0.05 escape ceiling at `core/compiler/agreement.py:49`. The basis
is asserted below rather than left in prose, so a later edit to either number
without the other fails.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from argus.core.adjust import adjust
from argus.core.compiler.agreement import _ESCAPE_CEILING
from argus.core.escape_rate import ESCAPE_RATE_FLOOR, compute_escape_rate
from argus.core.escape_sampler import (
    AutoPassedCall,
    PrioritizedTranche,
    RandomTranche,
    split_tranches,
)
from argus.core.grounding import ProposedFinding, UngroundedFinding, UngroundedReason
from argus.core.route import (
    DeferReason,
    Disposition,
    RoutingDecision,
    route,
)
from argus.core.score import Rubric, ScorableFact, score
from argus.types.pipeline import RubricCategory, RubricItem, VerdictResult


def _item(rubric_id: int) -> RubricItem:
    return RubricItem(
        id=rubric_id,
        category=RubricCategory.PROCESS,
        name=f"criterion {rubric_id}",
        pass_criteria="p",
        fail_criteria="f",
    )


RUBRIC = Rubric(version="v1", items=(_item(1), _item(2), _item(3)))


def _adjusted(*outcomes: tuple[int, VerdictResult]):
    facts = [
        ScorableFact(finding_id=f"F{r:02d}", rubric_id=r, outcome=o)
        for r, o in outcomes
    ]
    return adjust(score(facts, RUBRIC), [])


CLEAN = ((1, VerdictResult.PASS), (2, VerdictResult.FAIL))


def _ungrounded(finding_id: str = "F09") -> UngroundedFinding:
    return UngroundedFinding(
        finding=ProposedFinding(
            finding_id=finding_id,
            rubric_id=3,
            intents_node="process/greeting",
            violation="称谓语缺失",
            checking_path="B",
        ),
        reason=UngroundedReason.UNANCHORABLE_PATH,
        detail="path B quotes a document, not the transcript",
    )


# ── D10: the two axes ────────────────────────────────────────────────────


def test_auto_final_requires_both_axes():
    """Neither gate substitutes for the other — all four combinations.

    The table is the test. An implementation that accumulated one list of
    problems and checked it for emptiness would pass the two diagonal cases and
    fail nothing, which is why both off-diagonal cases are here.
    """
    clean = _adjusted(*CLEAN)

    both = route(clean)
    assert both.coverage_clear and both.criteria_clear
    assert both.disposition is Disposition.AUTO_FINAL

    coverage_only = route(clean, untrusted_criteria=[2])
    assert coverage_only.coverage_clear is True
    assert coverage_only.criteria_clear is False
    assert coverage_only.disposition is Disposition.HUMAN

    health_only = route(clean, ungrounded=[_ungrounded()])
    assert health_only.coverage_clear is False
    assert health_only.criteria_clear is True
    assert health_only.disposition is Disposition.HUMAN

    neither = route(clean, ungrounded=[_ungrounded()], untrusted_criteria=[2])
    assert not neither.coverage_clear and not neither.criteria_clear
    assert neither.disposition is Disposition.HUMAN


def test_ungrounded_always_routes_to_human():
    """I2 — a finding that anchors to nothing real always reaches a person.

    Checked against every ungrounded reason the gate can produce, so a new one
    cannot arrive with a quiet exemption.
    """
    clean = _adjusted(*CLEAN)
    for reason in UngroundedReason:
        finding = _ungrounded().model_copy(update={"reason": reason})
        decision = route(clean, ungrounded=[finding])
        assert decision.disposition is Disposition.HUMAN, reason
        assert decision.coverage_clear is False


def test_a_deferred_score_row_blocks_auto_final():
    """M11's unverifiable row is a coverage gap at S5, under §6's vocabulary."""
    decision = route(_adjusted((1, VerdictResult.PASS), (2, VerdictResult.NEI)))

    assert decision.disposition is Disposition.HUMAN
    assert decision.deferrals[0].reason is DeferReason.UNGROUNDED
    # The originating word survives the mapping.
    assert "unverifiable" in decision.deferrals[0].detail


def test_a_thin_finding_blocks_auto_final():
    """I6 — single-channel evidence without an independent anchor defers."""
    decision = route(_adjusted(*CLEAN), thin_findings=["F01"])

    assert decision.disposition is Disposition.HUMAN
    assert decision.coverage_clear is False
    assert decision.criteria_clear is True
    assert decision.deferrals[0].reason is DeferReason.FINDING_THIN


def test_an_all_na_call_does_not_auto_finalise():
    """Nothing scored is not a cleared gate; it is an unanswered question."""
    decision = route(_adjusted((1, VerdictResult.NA)))
    assert decision.coverage_clear is False
    assert decision.disposition is Disposition.HUMAN


# ── D4: the axes cannot be crossed ───────────────────────────────────────


def test_routing_cannot_be_handed_corroboration():
    """D4, structurally — there is no argument here that could clear κ < τ.

    Corroboration clears `finding_thin` and never `criterion_below_tau`. If this
    function accepted signals it would have to be *trusted* not to apply them to
    the health axis. It accepts the outcome instead: which findings are still
    thin. The signature is the enforcement.
    """
    params = inspect.signature(route).parameters
    assert set(params) == {"adjusted", "ungrounded", "thin_findings", "untrusted_criteria"}
    for name in ("ungrounded", "thin_findings", "untrusted_criteria"):
        assert params[name].kind is inspect.Parameter.KEYWORD_ONLY

    source = Path(__file__).resolve().parent.parent / "src" / "argus" / "core" / "route.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "argus.core.corroboration" not in imported


def test_no_quantity_of_evidence_clears_an_untrusted_criterion():
    """D4 — the two axes are orthogonal, tried adversarially.

    A call with a perfect score, no ungrounded findings, nothing thin and every
    finding on the criterion still does not auto-finalise while the criterion is
    untrusted.
    """
    perfect = _adjusted((1, VerdictResult.PASS), (2, VerdictResult.PASS), (3, VerdictResult.PASS))
    assert perfect.value == 100.0

    decision = route(perfect, untrusted_criteria=[1])
    assert decision.disposition is Disposition.HUMAN
    assert decision.coverage_clear is True, "the coverage axis really is clear"
    assert decision.criteria_clear is False


def test_the_three_defer_reasons_are_exactly_sixs_vocabulary():
    """§6 names three values. A fourth would be a spec change, not a refactor."""
    assert {r.value for r in DeferReason} == {
        "ungrounded",
        "finding_thin",
        "criterion_below_tau",
    }


def test_every_scorer_reason_maps_rather_than_defaulting():
    """A new `score.DeferReason` member must fail loudly, not route as a default."""
    from argus.core.route import _FROM_SCORER
    from argus.core.score import DeferReason as ScoreDeferReason

    assert set(_FROM_SCORER) == set(ScoreDeferReason)
    assert set(_FROM_SCORER.values()) <= set(DeferReason)


# ── Nothing is dropped ───────────────────────────────────────────────────


def test_every_objection_appears_in_the_decision():
    """A decision that omitted an objection would auto-finalise by forgetting it."""
    adjusted = _adjusted((1, VerdictResult.PASS), (2, VerdictResult.NEI))
    decision = route(
        adjusted,
        ungrounded=[_ungrounded("F07"), _ungrounded("F08")],
        thin_findings=["F01"],
        untrusted_criteria=[3, 5],
    )
    assert len(decision.deferrals) == 2 + len(adjusted.deferrals) + 1 + 2
    assert {d.subject for d in decision.deferrals} >= {"F07", "F08", "F01", "3", "5"}


def test_the_decision_is_order_independent():
    """Same objections in any order, same record."""
    adjusted = _adjusted(*CLEAN)
    a = route(adjusted, ungrounded=[_ungrounded("F07"), _ungrounded("F08")], untrusted_criteria=[3, 5])
    b = route(adjusted, ungrounded=[_ungrounded("F08"), _ungrounded("F07")], untrusted_criteria=[5, 3])
    assert a.model_dump_json() == b.model_dump_json()


# ── The estimator and its floor ──────────────────────────────────────────


def _stream(n: int, miss_every: int = 10) -> list[AutoPassedCall]:
    return [
        AutoPassedCall(
            call_id=f"call-{i:05d}",
            proposed_score=float(i % 20),
            has_grounded_finding=(i % 3 == 0),
            missed=(i % miss_every == 0),
        )
        for i in range(n)
    ]


def test_the_floor_follows_from_the_declared_escape_ceiling():
    """The basis, asserted rather than left in prose.

    60 is 3 / 0.05 — the rule of three against the escape ceiling this repo
    already declares. Changing either number alone fails here, which is the
    point: the floor is not a preference.
    """
    assert _ESCAPE_CEILING == 0.05
    assert ESCAPE_RATE_FLOOR == round(3 / _ESCAPE_CEILING)


def test_escape_rate_consumes_random_tranche_only():
    """D22 — a biased sample cannot reach the estimator, by type."""
    calls = _stream(400)
    random_tranche, prioritized = split_tranches(
        calls, random_fraction=0.5, absolute_floor=ESCAPE_RATE_FLOOR
    )
    assert isinstance(compute_escape_rate(random_tranche).value, float)

    with pytest.raises(TypeError):
        compute_escape_rate(prioritized)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        compute_escape_rate(calls)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        compute_escape_rate(RandomTranche(prioritized.calls).calls)  # type: ignore[arg-type]


def test_a_sample_below_the_floor_is_not_reportable():
    """The 9020 defect: an empty tranche returned 0.0, the most reassuring number.

    An estimate and the absence of one must not share a representation.
    """
    # Built rather than tuned for: `_stream`'s miss_every marks index 0 whatever
    # the period, so no value of it produces a spotless sample.
    spotless = [
        AutoPassedCall(
            call_id=f"clean-{i:03d}",
            proposed_score=1.0,
            has_grounded_finding=True,
            missed=False,
        )
        for i in range(11)
    ]
    result = compute_escape_rate(RandomTranche(spotless))

    assert result.reviewed == 11
    assert result.misses == 0
    assert result.reportable is False, "eleven clean reviews are silence, not evidence"

    empty = compute_escape_rate(RandomTranche([]))
    assert empty.value == 0.0 and empty.reportable is False


def test_a_sample_at_the_floor_is_reportable():
    at_floor = RandomTranche(_stream(ESCAPE_RATE_FLOOR, miss_every=10))
    assert compute_escape_rate(at_floor).reportable is True
    one_short = RandomTranche(_stream(ESCAPE_RATE_FLOOR - 1, miss_every=10))
    assert compute_escape_rate(one_short).reportable is False


def test_the_floor_holds_whatever_the_prioritisation_asks_for():
    """The acceptance property, in the case the prioritiser would starve it.

    A 1% random fraction over 400 calls is four calls. The floor overrides it.
    """
    calls = _stream(400)
    random_tranche, _ = split_tranches(
        calls, random_fraction=0.01, absolute_floor=ESCAPE_RATE_FLOOR
    )
    assert len(random_tranche) >= ESCAPE_RATE_FLOOR
    assert compute_escape_rate(random_tranche).reportable is True


def test_a_floor_cannot_be_omitted():
    """9020 shipped `absolute_floor: int = 0`, so no call site had a floor.

    Required and keyword-only now: a floor you can forget is not one.
    """
    params = inspect.signature(split_tranches).parameters
    assert params["absolute_floor"].default is inspect.Parameter.empty
    assert params["absolute_floor"].kind is inspect.Parameter.KEYWORD_ONLY
    with pytest.raises(TypeError):
        split_tranches(_stream(10))  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="is not a floor"):
        compute_escape_rate(RandomTranche(_stream(10)), floor=0)


def test_the_estimator_is_still_unbiased():
    """The reconciliation must not have changed the number it computes."""
    calls = _stream(1000, miss_every=10)  # true rate 0.10
    random_tranche, _ = split_tranches(
        calls, random_fraction=0.5, absolute_floor=ESCAPE_RATE_FLOOR
    )
    assert abs(compute_escape_rate(random_tranche).value - 0.10) < 0.03


# ── Purity ───────────────────────────────────────────────────────────────


def test_route_and_estimator_are_pure():
    """No model, no clock, no RNG in either stage."""
    root = Path(__file__).resolve().parent.parent / "src" / "argus" / "core"
    forbidden = {
        "anthropic", "openai", "transformers", "torch", "chromadb", "httpx",
        "random", "time", "datetime", "secrets",
    }
    for name in ("route.py", "escape_rate.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
        assert forbidden.isdisjoint(roots), f"{name}: {roots & forbidden}"
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("argus."):
                assert node.module.split(".")[1] in {"types", "config", "core"}, node.module


def test_the_decision_carries_no_score():
    """Routing changes disposition, never the number. I6's other half."""
    for field in RoutingDecision.model_fields:
        assert field not in {"value", "score", "raw", "adjusted", "deduction"}
