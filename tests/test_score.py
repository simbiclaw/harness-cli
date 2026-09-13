"""Acceptance tests for 9021 M10 and M11 — the raw scoring lane.

M10's Contract: *Deliverable* — a pure scoring function taking grounded facts
and the rubric. *Binding constraint* — I3 (`raw = score(facts, rubric)`, and
`score` never receives history) and I1 (`core/` imports no model client).
*Acceptance property* — identical grounded findings and rubric version produce
an identical raw score, and the rubric's weight reaches the arithmetic from
`core/` rather than from inside the quarantine.

M11's Contract: *Deliverable* — a scoring policy for unverifiable items
consistent with the deferral rules. *Binding constraint* — I2 and D10.
*Acceptance property* — an unverifiable item cannot silently contribute to a
shipped score.

The upstream behaviour these replace, for the record:
`core/aggregator.py:56-60` sums `v.score * v.weight` off verdicts whose weight
was stamped in `core/fact_checker.py:187` and whose veto flag was copied in
`core/question_generator.py:110`, both inside model-calling modules;
`core/fact_checker.py:184-185` scores NEI at 0.5 and leaves it in `applicable`,
so it lands in the denominator.
"""

from __future__ import annotations

import ast
import inspect
import random
from pathlib import Path

import pytest
from pydantic import ValidationError

from argus.core.score import (
    Contribution,
    DeferReason,
    Rubric,
    ScorableFact,
    UnknownCriterion,
    auto_final_eligible,
    score,
)
from argus.types.pipeline import RubricCategory, RubricItem, VerdictResult


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


def _rubric(*items: RubricItem, version: str = "v1") -> Rubric:
    return Rubric(version=version, items=tuple(items))


def _fact(rubric_id: int, outcome: VerdictResult, *, finding_id: str = "") -> ScorableFact:
    return ScorableFact(
        finding_id=finding_id or f"F{rubric_id:02d}",
        rubric_id=rubric_id,
        outcome=outcome,
    )


# ── I3: determinism ──────────────────────────────────────────────────────


def test_i3_determinism_canary():
    """Same facts, same rubric version, byte-identical record — in any order.

    Not just the same float: the whole result serialized. A record that agrees
    on `value` but reorders its deferrals is not replayable, and I5 hashes the
    record rather than the number.
    """
    rubric = _rubric(
        _item(1), _item(2, weight=2.0), _item(3), _item(4), _item(5, weight=2.0)
    )
    facts = [
        _fact(1, VerdictResult.PASS),
        _fact(2, VerdictResult.FAIL),
        _fact(3, VerdictResult.NEI),
        _fact(4, VerdictResult.NA),
        _fact(5, VerdictResult.PASS),
        _fact(3, VerdictResult.HUMAN_REVIEW, finding_id="F03b"),
    ]

    baseline = score(facts, rubric).model_dump_json()
    for seed in range(20):
        shuffled = list(facts)
        random.Random(seed).shuffle(shuffled)
        assert score(shuffled, rubric).model_dump_json() == baseline


def test_score_receives_no_history():
    """I3 in its structural form: the raw lane cannot be handed a precedent.

    The spec's §5 runtime assert rejects a raw-lane verdict that cites one.
    A signature that cannot express a precedent fails earlier and cannot be
    forgotten.
    """
    params = inspect.signature(score).parameters
    assert tuple(params) == ("facts", "rubric")
    for name, param in params.items():
        assert param.default is inspect.Parameter.empty, f"{name} has a default"
        assert param.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD

    # And nothing history-shaped smuggled onto the fact itself.
    forbidden = ("history", "precedent", "prior", "adjust", "past")
    for field in ScorableFact.model_fields:
        assert not any(word in field for word in forbidden), field


def test_the_rubric_version_is_on_the_record():
    """Determinism is scoped to a version; a record without one cannot claim it."""
    assert score([_fact(1, VerdictResult.PASS)], _rubric(_item(1), version="v7")).rubric_version == "v7"


# ── I3 / I1: the weight comes from the rubric ────────────────────────────


def test_weight_comes_from_rubric_not_verdict():
    """The arithmetic reads weight from the sheet, and there is no other source.

    Two halves. First: a fact has no weight field and refuses one, so a value
    stamped inside the quarantine has no way in. Second: changing only the
    rubric's weight changes the number, which proves the rubric is what the
    arithmetic actually consults rather than a constant that happens to agree.
    """
    assert "weight" not in ScorableFact.model_fields
    assert "is_veto" not in ScorableFact.model_fields
    with pytest.raises(ValidationError):
        ScorableFact(
            finding_id="F01", rubric_id=1, outcome=VerdictResult.PASS, weight=9.0
        )

    facts = [_fact(1, VerdictResult.PASS), _fact(2, VerdictResult.FAIL)]
    unweighted = score(facts, _rubric(_item(1), _item(2)))
    weighted = score(facts, _rubric(_item(1), _item(2, weight=2.0)))

    assert unweighted.value == 50.0  # 1 of 2
    assert weighted.value == pytest.approx(33.3)  # 1 of 3
    assert weighted.denominator == 3.0


def test_the_veto_flag_comes_from_the_rubric_too():
    """Upstream copies `is_veto` onto a question inside a model-calling module.

    Item 27 — the privacy veto — is the row this protects. A run whose veto flag
    was dropped or flipped in the quarantine would ship a passing score for a
    call that must score zero.
    """
    facts = [_fact(1, VerdictResult.PASS), _fact(27, VerdictResult.FAIL)]
    without = score(facts, _rubric(_item(1), _item(27)))
    with_veto = score(facts, _rubric(_item(1), _item(27, is_veto=True)))

    assert without.veto_triggered is False
    assert without.value == 50.0
    assert with_veto.veto_triggered is True
    assert with_veto.veto_criteria == (27,)
    assert with_veto.value == 0.0


def test_a_veto_criterion_that_passes_does_not_trigger():
    """The veto is a failure on a veto row, not the presence of one."""
    raw = score([_fact(27, VerdictResult.PASS)], _rubric(_item(27, is_veto=True)))
    assert raw.veto_triggered is False
    assert raw.value == 100.0


def test_a_fact_citing_an_unknown_criterion_is_refused():
    """Upstream defaults an unknown `rubric_id` to weight 1.0 and says nothing.

    A stale or typo'd reference then scores at full unweighted strength. Under
    I2 a finding that anchors to nothing real is not scored at a default.
    """
    with pytest.raises(UnknownCriterion, match="no criterion 99"):
        score([_fact(99, VerdictResult.PASS)], _rubric(_item(1)))


# ── M11: the unverifiable case ───────────────────────────────────────────


def test_nei_excluded_from_denominator():
    """An unverifiable item neither scores nor counts — upstream gave it 0.5.

    The facts are chosen so the two policies cannot agree by coincidence:
    upstream reports (1.0 + 1.0 + 0.5) / 3 = 83.3, this reports 2 of 2 = 100.0.
    A one-pass-one-fail-one-NEI case would have given 50.0 under both and
    proved nothing.
    """
    rubric = _rubric(_item(1), _item(2), _item(3))
    facts = [
        _fact(1, VerdictResult.PASS),
        _fact(2, VerdictResult.PASS),
        _fact(3, VerdictResult.NEI),
    ]
    raw = score(facts, rubric)

    upstream_value = round((1.0 + 1.0 + 0.5) / 3 * 100, 1)
    assert upstream_value == 83.3
    assert raw.value != upstream_value

    assert raw.denominator == 2.0, "the unverifiable row must leave the denominator"
    assert raw.numerator == 2.0
    assert raw.value == 100.0

    assert len(raw.deferrals) == 1
    assert raw.deferrals[0].rubric_id == 3
    assert raw.deferrals[0].finding_id == "F03"
    assert raw.deferrals[0].reason is DeferReason.UNVERIFIABLE


def test_an_unverifiable_row_cannot_contribute_at_any_weight():
    """The exclusion is of the row, not of a half-point.

    A weighted unverifiable row is where a surviving 0.5 would do the most
    damage, so it is checked at weight 2.0 rather than 1.0.
    """
    rubric = _rubric(_item(1), _item(2, weight=2.0))
    raw = score([_fact(1, VerdictResult.PASS), _fact(2, VerdictResult.NEI)], rubric)
    assert (raw.numerator, raw.denominator, raw.value) == (1.0, 1.0, 100.0)


def test_nei_blocks_auto_final():
    """D10's coverage gate. A gap is a gap however trusted the criteria are."""
    rubric = _rubric(_item(1), _item(2))
    clean = score([_fact(1, VerdictResult.PASS), _fact(2, VerdictResult.PASS)], rubric)
    gapped = score([_fact(1, VerdictResult.PASS), _fact(2, VerdictResult.NEI)], rubric)

    assert auto_final_eligible(clean, criteria_trusted=True) is True
    assert auto_final_eligible(gapped, criteria_trusted=True) is False


def test_the_two_auto_final_axes_do_not_substitute_for_each_other():
    """D10 — neither gate stands in for the other.

    And the health axis is keyword-only with no default, so a caller cannot
    reach an auto-final answer while knowing only coverage.
    """
    clean = score([_fact(1, VerdictResult.PASS)], _rubric(_item(1)))
    assert auto_final_eligible(clean, criteria_trusted=False) is False

    params = inspect.signature(auto_final_eligible).parameters
    health = params["criteria_trusted"]
    assert health.kind is inspect.Parameter.KEYWORD_ONLY
    assert health.default is inspect.Parameter.empty


def test_a_human_review_outcome_is_also_a_deferral():
    """`requires_human_review` upstream is a flag beside a score that still counts.

    Here the row leaves the arithmetic for the same reason NEI does: nobody has
    decided it yet.
    """
    raw = score([_fact(1, VerdictResult.HUMAN_REVIEW)], _rubric(_item(1)))
    assert raw.denominator == 0.0
    assert raw.deferrals[0].reason is DeferReason.HUMAN_REVIEW
    assert raw.coverage_clear is False


def test_na_is_excluded_without_being_a_gap():
    """An inapplicable criterion is not a coverage failure.

    This is the one exclusion that must *not* block auto-final — conflating it
    with a gap would defer every call that skips an optional row.
    """
    rubric = _rubric(_item(1), _item(2))
    raw = score([_fact(1, VerdictResult.PASS), _fact(2, VerdictResult.NA)], rubric)
    assert raw.denominator == 1.0
    assert raw.deferrals == ()
    assert raw.coverage_clear is True


def test_an_all_na_call_is_not_a_clean_hundred_or_a_shippable_zero():
    """Nothing scored means nothing to ship, not a perfect or a failing call."""
    raw = score([_fact(1, VerdictResult.NA)], _rubric(_item(1)))
    assert raw.denominator == 0.0
    assert raw.coverage_clear is False
    assert auto_final_eligible(raw, criteria_trusted=True) is False


def test_a_contribution_cannot_disagree_with_itself():
    """`credit` is a function of `outcome`, so a row storing both must agree.

    They are stored separately because the arithmetic reads one and the veto
    rule reads the other. Without this check a caller — M18 applying a
    precedent is the realistic one — could write `outcome=FAIL, credit=1.0`,
    and the row would score as a pass while still tripping the veto.
    """
    ok = dict(finding_id="F01", rubric_id=1, weight=1.0, is_veto=False)
    assert Contribution(outcome=VerdictResult.PASS, credit=1.0, **ok).credit == 1.0

    with pytest.raises(ValidationError, match="scores 0.0, not 1.0"):
        Contribution(outcome=VerdictResult.FAIL, credit=1.0, **ok)
    with pytest.raises(ValidationError, match="scores 1.0, not 0.0"):
        Contribution(outcome=VerdictResult.PASS, credit=0.0, **ok)
    # An outcome that does not score has no credit to record at all.
    with pytest.raises(ValidationError, match="scores None"):
        Contribution(outcome=VerdictResult.NEI, credit=0.0, **ok)


def test_every_outcome_in_the_enum_is_handled():
    """A new `VerdictResult` member must not fall through to a silent default.

    The port mirrors upstream, so a member added there arrives here without
    anyone editing this module. Iterating the enum means that arrival fails
    loudly rather than scoring at whatever `.get()` returns.
    """
    rubric = _rubric(_item(1))
    for outcome in VerdictResult:
        raw = score([_fact(1, outcome)], rubric)
        assert isinstance(raw.value, float)


# ── I1: the fence ────────────────────────────────────────────────────────

MODEL_CLIENTS = {"anthropic", "openai", "transformers", "torch", "chromadb", "httpx"}


def test_core_no_model_client():
    """I1 — the raw lane is downstream of the quarantine, not inside it.

    Checked on the source rather than on `sys.modules`, so an import that is
    present but unreached still fails.
    """
    source = Path(__file__).resolve().parent.parent / "src" / "argus" / "core" / "score.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])

    assert MODEL_CLIENTS.isdisjoint(roots), f"model client reached core: {roots & MODEL_CLIENTS}"

    argus_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith("argus.")
    }
    for module in argus_imports:
        layer = module.split(".")[1]
        assert layer in {"types", "config", "core"}, f"core imports {module}"
