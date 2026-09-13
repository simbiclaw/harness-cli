"""Acceptance tests for 9021 M17 — independence-weighted corroboration.

M17's Contract: *Deliverable* — the independence-weighted corroboration
aggregator. *Binding constraint* — I6 (all three weight classes, W_C
provisional with its debt logged) and D4 (corroboration clears `finding_thin`,
never `criterion_below_tau`). *Acceptance property* — redundant signals
manufacture no confidence; a correlated signal weighs as neither independent
nor redundant; the two deferral axes stay orthogonal.

The upstream behaviour this replaces, for the record:
`/home/user/sim/core/aggregator.py:52-56` sums `v.score * v.weight` over every
verdict in a dimension with no notion of where a verdict's error came from, so
a model-authored verdict and the local NLI path
(`/home/user/sim/utils/nli.py:26-36`, reached from
`/home/user/sim/core/fact_checker.py:49-58`) are added up identically. There is
no correlated class upstream to port.
"""

from __future__ import annotations

import ast
import inspect
import random
from pathlib import Path

import pytest

from argus.core.corroboration import (
    CLEAR_THRESHOLD,
    W_C,
    W_INDEPENDENT,
    W_REDUNDANT,
    ClearableDeferral,
    Corroboration,
    CorroborationSignal,
    FindingClaim,
    IndependenceClass,
    Instrument,
    UnclearableDeferral,
    clears,
    corroborate,
)
from argus.core.score import Rubric, ScorableFact, score
from argus.types.anchored import Span
from argus.types.pipeline import RubricCategory, RubricItem, VerdictResult

FINDING = FindingClaim(finding_id="F01", span=Span(start=100, end=200))


def _signal(
    instrument: Instrument,
    *,
    start: int = 100,
    end: int = 200,
    signal_id: str = "",
) -> CorroborationSignal:
    return CorroborationSignal(
        signal_id=signal_id or f"{instrument.value}-{start}-{end}",
        instrument=instrument,
        span=Span(start=start, end=end),
    )


MODEL_TEXT = Instrument.MODEL_TEXT_JUDGMENT
REFERENT = Instrument.MODEL_REFERENT_MATCH
ACOUSTIC = Instrument.ACOUSTIC_MEASUREMENT
LEXICAL = Instrument.LEXICAL_MATCH


# ── I6 / D5: redundant signals manufacture no confidence ─────────────────


def test_redundant_signals_aggregate_zero():
    """soft⊕soft = 0 (D5). A second model read of the same span adds nothing."""
    result = corroborate(FINDING, [_signal(MODEL_TEXT)])

    assert result.strength == 0.0
    assert result.redundant_signals == 1
    assert result.independent_channels == 0
    assert result.clears_finding_thin is False


def test_ten_redundant_signals_still_aggregate_zero():
    """The adversarial form: confidence by re-reading is the §6.4 vote.

    Ten model-judged text criteria on the finding's own span — the exact shape
    of N model samples voting — must aggregate to the same zero as one.
    """
    signals = [_signal(MODEL_TEXT, signal_id=f"S{i:02d}") for i in range(10)]
    result = corroborate(FINDING, signals)

    assert result.strength == 0.0
    assert result.redundant_signals == 10
    assert clears(result, ClearableDeferral.FINDING_THIN) is False


def test_shifting_a_redundant_span_buys_nothing():
    """Escaping "the same span" by a character must not reclassify a signal.

    A model-judged text signal that still overlaps stays redundant; one moved
    clear of the finding is off-span and is not a corroborator at all. Both
    paths are zero, so the span is not a loophole.
    """
    overlapping = corroborate(FINDING, [_signal(MODEL_TEXT, start=199, end=260)])
    assert overlapping.strength == 0.0
    assert overlapping.redundant_signals == 1

    elsewhere = corroborate(FINDING, [_signal(MODEL_TEXT, start=200, end=260)])
    assert elsewhere.strength == 0.0
    assert elsewhere.off_span_signals == 1
    assert elsewhere.redundant_signals == 0


def test_there_is_no_per_signal_judgment_source_to_lie_about():
    """What makes soft⊕soft enforceable: the source is derived, not declared.

    A caller cannot dress two model reads up as two sources, because there is
    no field in which to name a source and the model cannot be added to one.
    """
    assert "judgment_source" not in CorroborationSignal.model_fields
    assert set(CorroborationSignal.model_fields) == {"signal_id", "instrument", "span"}
    with pytest.raises(Exception):
        CorroborationSignal(
            signal_id="S1",
            instrument=MODEL_TEXT,
            span=Span(start=100, end=200),
            judgment_source="some-other-model",
        )


# ── I6: the correlated class is neither of the other two ─────────────────


def test_correlated_signal_weighs_w_c():
    """A model-judged match to a confirmed referent: neither 1.0 nor 0.0.

    Asserted against both neighbours as well as against the value, so that
    reclassifying an independent instrument down to 0.4 — or the correlated
    class up to a full anchor — fails here rather than passing unnoticed.
    """
    result = corroborate(FINDING, [_signal(REFERENT)])

    assert result.strength == pytest.approx(0.4)
    assert result.strength != W_INDEPENDENT
    assert result.strength != W_REDUNDANT
    assert 0.0 < result.strength < 1.0
    assert result.correlated_signals == 1

    independent = corroborate(FINDING, [_signal(ACOUSTIC)])
    assert independent.strength != result.strength

    redundant = corroborate(FINDING, [_signal(MODEL_TEXT)])
    assert redundant.strength != result.strength


def test_the_three_classes_hold_three_distinct_weights():
    """I6's table, stated once. Two classes sharing a weight is the failure."""
    assert (W_INDEPENDENT, W_C, W_REDUNDANT) == (1.0, 0.4, 0.0)
    assert len({W_INDEPENDENT, W_C, W_REDUNDANT}) == 3
    assert len(set(IndependenceClass)) == 3


def test_correlated_signals_do_not_compound():
    """"No number of correlated re-reads manufactures confidence" (I6).

    Ten Error-Case matches share the proposer's error source, so they are worth
    one — and in particular they never reach the threshold a real anchor does.
    """
    spread = [
        _signal(REFERENT, start=100 + 10 * i, end=110 + 10 * i, signal_id=f"C{i}")
        for i in range(10)
    ]
    result = corroborate(FINDING, spread)

    assert result.strength == pytest.approx(W_C)
    assert result.correlated_signals == 10
    assert result.clears_finding_thin is False


def test_a_correlated_signal_cannot_clear_finding_thin_alone():
    """The provisional W_C sits below the threshold; it must stay below it."""
    assert W_C < CLEAR_THRESHOLD
    assert clears(corroborate(FINDING, [_signal(REFERENT)]), "finding_thin") is False


# ── D4 axis one: an independent anchor clears `finding_thin` ─────────────


def test_independent_signal_clears_finding_thin():
    """One real anchor is what the deferral rule says clears a thin finding."""
    result = corroborate(FINDING, [_signal(ACOUSTIC)])

    assert result.strength == pytest.approx(W_INDEPENDENT)
    assert result.independent_channels == 1
    assert result.clears_finding_thin is True
    assert clears(result, ClearableDeferral.FINDING_THIN) is True


def test_every_independent_instrument_clears_it():
    """The I6 table lists four; none of them is a special case."""
    for instrument in (
        Instrument.ACOUSTIC_MEASUREMENT,
        Instrument.LEXICAL_MATCH,
        Instrument.LOOKUP_MATCH,
        Instrument.ORDERED_MATCH,
    ):
        assert corroborate(FINDING, [_signal(instrument)]).clears_finding_thin is True


def test_a_bare_finding_clears_nothing():
    """With no signals there is no corroboration — and no default that clears."""
    result = corroborate(FINDING, [])
    assert result.strength == 0.0
    assert result.clears_finding_thin is False


def test_an_off_span_instrument_does_not_corroborate():
    """Co-location (D3): an instrument aimed elsewhere is evidence of something else."""
    result = corroborate(FINDING, [_signal(ACOUSTIC, start=900, end=950)])
    assert result.strength == 0.0
    assert result.off_span_signals == 1
    assert result.independent_channels == 0
    assert result.clears_finding_thin is False


def test_the_same_instrument_read_twice_is_one_channel():
    """Two measurements over one stretch are one measurement made twice."""
    result = corroborate(
        FINDING,
        [
            _signal(ACOUSTIC, start=100, end=200, signal_id="A1"),
            _signal(ACOUSTIC, start=120, end=180, signal_id="A2"),
        ],
    )
    assert result.independent_channels == 1

    two = corroborate(
        FINDING,
        [
            _signal(ACOUSTIC, start=100, end=140, signal_id="A1"),
            _signal(LEXICAL, start=100, end=140, signal_id="L1"),
        ],
    )
    assert two.independent_channels == 2


def test_strength_is_bounded_and_order_independent():
    """A confidence outside [0, 1] is not one, and shuffling is not evidence."""
    signals = [
        _signal(ACOUSTIC, start=100, end=140, signal_id="A1"),
        _signal(LEXICAL, start=150, end=190, signal_id="L1"),
        _signal(REFERENT, start=110, end=130, signal_id="C1"),
        _signal(MODEL_TEXT, start=100, end=200, signal_id="R1"),
        _signal(ACOUSTIC, start=900, end=950, signal_id="A2"),
    ]
    baseline = corroborate(FINDING, signals).model_dump_json()
    for seed in range(20):
        shuffled = list(signals)
        random.Random(seed).shuffle(shuffled)
        assert corroborate(FINDING, shuffled).model_dump_json() == baseline

    assert 0.0 <= corroborate(FINDING, signals).strength <= 1.0


# ── D4 axis two: nothing clears `criterion_below_tau` ────────────────────


def test_corroboration_never_clears_criterion_below_tau():
    """The two axes are orthogonal, and the second one is not addressable.

    Not "returns False": refused. A caller that wires criterion health into
    this call finds out at the call site rather than reading a plausible
    negative that would silently become a positive if the rule ever loosened.
    """
    with pytest.raises(UnclearableDeferral):
        clears(corroborate(FINDING, [_signal(ACOUSTIC)]), "criterion_below_tau")

    assert "criterion_below_tau" not in {member.value for member in ClearableDeferral}
    with pytest.raises(ValueError):
        ClearableDeferral("criterion_below_tau")


def test_no_pile_of_anchors_clears_criterion_below_tau():
    """Try to break it: fifty maximum-strength anchors across the finding."""
    signals = [
        _signal(ACOUSTIC, start=100 + i, end=200, signal_id=f"A{i}") for i in range(25)
    ] + [_signal(LEXICAL, start=100 + i, end=200, signal_id=f"L{i}") for i in range(25)]
    result = corroborate(FINDING, signals)

    assert result.strength == pytest.approx(1.0)
    assert result.clears_finding_thin is True
    with pytest.raises(UnclearableDeferral):
        clears(result, "criterion_below_tau")
    for reason in ("criterion_below_tau", "ungrounded", "unverifiable", "human_review"):
        with pytest.raises(UnclearableDeferral):
            clears(result, reason)


def test_the_clearable_set_holds_exactly_one_reason():
    """D4 lives in the size of the set — a second member is the violation."""
    assert tuple(ClearableDeferral) == (ClearableDeferral.FINDING_THIN,)
    assert ClearableDeferral.FINDING_THIN.value == "finding_thin"


def test_nothing_here_reports_criterion_health():
    """Corroboration cannot answer the health question even by accident."""
    forbidden = ("kappa", "tau", "criterion", "trusted", "health")
    for field in Corroboration.model_fields:
        assert not any(word in field for word in forbidden), field
    for name, param in inspect.signature(corroborate).parameters.items():
        assert not any(word in name for word in forbidden), name


# ── I6: corroboration changes routing, never the deduction ───────────────


def test_corroboration_returns_no_score_or_deduction():
    """A violation's deduction is the rubric's weight, however many saw it.

    Two halves. First: no returned field could be mistaken for a deduction.
    Second: the raw lane's number is the same with and without corroboration in
    the room — `score` cannot be handed one, and the finding's arithmetic does
    not consult this module.
    """
    forbidden = ("score", "deduction", "weight", "points", "raw", "adjusted", "value")
    for field in Corroboration.model_fields:
        assert not any(word in field for word in forbidden), field
    assert "score" not in inspect.signature(corroborate).parameters
    assert "rubric" not in inspect.signature(corroborate).parameters

    rubric = Rubric(
        version="v1",
        items=(
            RubricItem(
                id=1,
                category=RubricCategory.PROCESS,
                name="criterion 1",
                pass_criteria="p",
                fail_criteria="f",
                weight=2.0,
                is_weighted=True,
                is_veto=False,
            ),
        ),
    )
    facts = [ScorableFact(finding_id="F01", rubric_id=1, outcome=VerdictResult.FAIL)]
    before = score(facts, rubric)

    thin = corroborate(FINDING, [])
    thick = corroborate(FINDING, [_signal(ACOUSTIC), _signal(LEXICAL), _signal(REFERENT)])
    assert thin.clears_finding_thin != thick.clears_finding_thin

    after = score(facts, rubric)
    assert after.model_dump_json() == before.model_dump_json()
    assert "corroboration" not in inspect.signature(score).parameters
    assert tuple(inspect.signature(score).parameters) == ("facts", "rubric")


def test_a_signal_cannot_carry_a_number_into_the_aggregate():
    """I7 — ground evidence, not numbers. A signal has no score to average."""
    assert "score" not in CorroborationSignal.model_fields
    assert "confidence" not in CorroborationSignal.model_fields
    with pytest.raises(Exception):
        CorroborationSignal(
            signal_id="S1",
            instrument=ACOUSTIC,
            span=Span(start=100, end=200),
            score=0.99,
        )


# ── The fence: aggregate ✗ model_client, and purity ──────────────────────

MODEL_CLIENTS = {"anthropic", "openai", "transformers", "torch", "chromadb", "httpx"}
IMPURE = {"random", "time", "datetime", "secrets", "uuid"}


def test_aggregate_no_model_client():
    """`aggregate ✗ model_client` — the aggregator is pure (I1, I6).

    Checked on the source rather than on `sys.modules`, so an import that is
    present but unreached still fails. Clock and RNG are checked with it: a
    corroboration strength that moved with the time of day would break I5's
    replayability as surely as a model call would.
    """
    source = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "argus"
        / "core"
        / "corroboration.py"
    )
    tree = ast.parse(source.read_text(encoding="utf-8"))

    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])

    assert MODEL_CLIENTS.isdisjoint(roots), f"model client reached core: {roots & MODEL_CLIENTS}"
    assert IMPURE.isdisjoint(roots), f"impurity reached the aggregator: {roots & IMPURE}"

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
        assert not module.startswith("argus.io"), f"aggregator imports {module}"


def test_the_same_signals_give_the_same_strength_forever():
    """I5 — replayability. The aggregate is a function of its inputs alone."""
    signals = [_signal(ACOUSTIC, start=110, end=150), _signal(REFERENT)]
    first = corroborate(FINDING, signals)
    assert [corroborate(FINDING, signals) == first for _ in range(5)] == [True] * 5
