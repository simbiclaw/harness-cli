"""Independence-weighted corroboration (9021 M17) — pure, and blind to the score.

I6: multi-anchor confidence is a pure, independence-weighted function of the
signals. Redundant signals contribute zero — no number of correlated re-reads
manufactures confidence. This module is that function, and nothing else: it
decides *routing*, never a deduction.

Three weight classes, from the I6 table in CLAUDE.md:

| class | instruments | weight |
|---|---|---|
| independent | acoustic measurement, lexical / lookup / ordered match | 1.0 |
| correlated | a model-judged match to a confirmed referent (Error Case, Best Practice) | W_C = 0.4 PROVISIONAL |
| redundant | another model-judged text criterion on the same span | 0.0 |

**W_C is provisional and the debt is here because there is nowhere else to put
it.** The repository keeps no technical-debt register (`docs/` has no such
file; the nearest thing is a per-plan inheritance table). So, stated plainly:
0.4 is not measured. The correct value is `1 - corr(matcher_error,
proposer_error)` on a human-labelled sample of referent matches, and until that
sample exists every number this module returns for a correlated-only finding is
a placeholder that happens to be conservative. `Confidence: low`. Revisit when
the agreement sample of `core/compiler/agreement.py:36-46` — which holds the
same constant for the authoring side, and which this module deliberately does
*not* import, because a 9003-compiler private is not a runtime contract —
produces labelled matcher errors. The two copies must collapse into one config
key at M22, whose binding constraint is that no value altering a verdict lives
as a hardcoded constant; `CLEAR_THRESHOLD` is the other candidate.

Four decisions, each made deliberately.

**The judgment source is derived, never declared.** There is no per-signal
"which model judged this" field, and no way to add one from the outside:
`_MODEL_JUDGED` is a property of the instrument. That is what makes soft⊕soft
= 0 enforceable rather than aspirational. A caller cannot present two
model-judged reads of the same span as two sources, which is precisely the
Argus-vs-Argus vote §6.4 forbids — agreement is Argus-vs-human, never N model
samples voting. Upstream has no such class to port: its aggregator sums
`v.score * v.weight` over verdicts (`/home/user/sim/core/aggregator.py:52-56`)
with no notion of where a verdict's error came from, and the one genuinely
model-free instrument it owns — the local NLI path, which scores entailment
with a `transformers` text-classification pipeline
(`/home/user/sim/utils/nli.py:26-36`, reached from
`/home/user/sim/core/fact_checker.py:49-58`) rather than through the LLM client
that paths B and C use (`/home/user/sim/core/fact_checker.py:100`) — is never
distinguished from them when the numbers are added up.

**Off-span signals are not corroborators at all.** A corroborating instrument
must co-locate with the finding it corroborates — the grounding fence's job is
to verify that the proposer's signals "resolve and co-locate" (D3). An
instrument pointed at an unrelated stretch of the transcript is evidence about
something else, so it is discarded rather than weighed. This closes the cheap
manufacture: aim ten measurements anywhere in the call and claim ten anchors.

**A model-judged text signal weighs zero wherever it points.** The I6 table
scopes the redundant class to "the same span". Overlapping the finding's own
span, that is exactly D5 and the rule applies literally. Not overlapping, the
signal is off-span and is discarded. Both paths are zero, so shifting a span by
one character to escape the redundant class buys nothing — which is the only
reason the two rules are stated as one class here. Spans are compared by
*overlap*, not equality, for the same reason: exact equality would make
"widen the span by a character" a way out.

**The correlated class contributes W_C once.** Correlated signals share an
error source with the proposer by definition, so combining several of them as
though they were conditionally independent is the arithmetic I6 exists to
forbid. Ten Error-Case matches on one finding are worth one. Independent
channels, in contrast, each contribute a full term — which at weight 1.0 means
the first one saturates, and that is a consequence of the table rather than a
policy of this module.

What is *not* here: no score, no deduction, no weight off a rubric. A
violation's deduction is the rubric's weight for its anchor regardless of how
many instruments saw it (I6), and `core/score.py:172` already owns that
arithmetic and takes no corroboration argument. Nothing in this module returns
a number that belongs in a verdict.

`aggregate ✗ model_client`: stdlib and `types/` only. No model, no clock, no
RNG.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import Enum

from pydantic import BaseModel, ConfigDict

from argus.types.anchored import Span


class Instrument(str, Enum):
    """What produced a signal — and therefore whose errors it inherits.

    The four model-free members are instruments: their failure modes are
    disjoint from a text judgment's. The two model members are not, and are
    kept apart from each other only because a match to a *confirmed referent*
    rests on something a human authored, while a soft text criterion rests on
    nothing but the read.
    """

    ACOUSTIC_MEASUREMENT = "acoustic_measurement"
    LEXICAL_MATCH = "lexical_match"
    LOOKUP_MATCH = "lookup_match"
    ORDERED_MATCH = "ordered_match"
    MODEL_REFERENT_MATCH = "model_referent_match"
    MODEL_TEXT_JUDGMENT = "model_text_judgment"


# The finding's own claim is a model text judgment. Any signal from this set is
# therefore the same instrument reading again, whatever it is aimed at.
_MODEL_JUDGED = frozenset(
    {Instrument.MODEL_REFERENT_MATCH, Instrument.MODEL_TEXT_JUDGMENT}
)


class IndependenceClass(str, Enum):
    INDEPENDENT = "independent"
    CORRELATED = "correlated"
    REDUNDANT = "redundant"


_CLASS_OF: dict[Instrument, IndependenceClass] = {
    Instrument.ACOUSTIC_MEASUREMENT: IndependenceClass.INDEPENDENT,
    Instrument.LEXICAL_MATCH: IndependenceClass.INDEPENDENT,
    Instrument.LOOKUP_MATCH: IndependenceClass.INDEPENDENT,
    Instrument.ORDERED_MATCH: IndependenceClass.INDEPENDENT,
    Instrument.MODEL_REFERENT_MATCH: IndependenceClass.CORRELATED,
    Instrument.MODEL_TEXT_JUDGMENT: IndependenceClass.REDUNDANT,
}

W_INDEPENDENT = 1.0
W_C = 0.4  # PROVISIONAL — see the module docstring. Confidence: low.
W_REDUNDANT = 0.0

_WEIGHT: dict[IndependenceClass, float] = {
    IndependenceClass.INDEPENDENT: W_INDEPENDENT,
    IndependenceClass.CORRELATED: W_C,
    IndependenceClass.REDUNDANT: W_REDUNDANT,
}

# One full independent anchor's worth of corroboration clears `finding_thin`.
# This is a transcription of the deferral rule rather than a tuned number: the
# rule says "an independent corroborating anchor can clear this", and I6 prices
# an independent anchor at 1.0. Whether anything *below* a full anchor should
# ever clear a thin finding is unmeasured — it cannot be settled before W_C is,
# because the only sub-anchor strength this module can produce is W_C itself.
# `Confidence: low`. Revisit with W_C, and move both to config at M22.
CLEAR_THRESHOLD = 1.0


class UnclearableDeferral(ValueError):
    """A deferral reason corroboration has no authority over (D4).

    The two axes are orthogonal: corroboration speaks to whether *this
    finding's* evidence is thin, and says nothing about whether the criterion
    it cites is trusted. `criterion_below_tau` is a property of the criterion's
    κ (M19), and no quantity of corroborating anchors moves it.
    """


class ClearableDeferral(str, Enum):
    """Every deferral reason corroboration is competent to clear. There is one.

    A closed set, rather than a check inside `clears`, is what makes D4
    structural: `criterion_below_tau` is not a value this module can be handed.
    `core/score.py:54` holds the two reasons the raw lane can observe and says
    `finding_thin` is decided downstream; downstream is here.
    """

    FINDING_THIN = "finding_thin"


class CorroborationSignal(BaseModel):
    """One verified signal, reduced to what the weighting needs.

    Note what is absent. No score and no confidence: I7 grounds evidence, not
    numbers, and a signal that carried a number would invite someone to average
    it into a verdict. No judgment-source field: see the module docstring. No
    `intents_sha` either — M12's gate has already anchored these; what reaches
    the aggregator is a verified signal's *instrument* and *place*.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    signal_id: str
    instrument: Instrument
    span: Span


class FindingClaim(BaseModel):
    """The finding being corroborated, as the aggregator needs to see it.

    `span` is here because co-location is what makes a signal a corroborator of
    *this* finding rather than of something else in the call. No rubric_id and
    no outcome: both belong to the deduction, which this module does not touch.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    span: Span


class Corroboration(BaseModel):
    """The aggregate. A routing input, not a score.

    Every field is a count or a strength in [0, 1]. There is deliberately no
    field a caller could mistake for a deduction, and no field that speaks to
    criterion health.
    """

    model_config = ConfigDict(frozen=True)

    finding_id: str
    strength: float
    independent_channels: int
    correlated_signals: int
    redundant_signals: int
    off_span_signals: int

    @property
    def clears_finding_thin(self) -> bool:
        return self.strength >= CLEAR_THRESHOLD


def _overlaps(a: Span, b: Span) -> bool:
    """Half-open ranges intersect. Touching end-to-start is not overlapping."""
    return a.start < b.end and b.start < a.end


def _independent_channels(signals: Sequence[CorroborationSignal]) -> int:
    """Distinct independent channels: one per instrument per place it read.

    Two acoustic measurements over the same stretch of audio are one
    measurement made twice, not two anchors. Sorting first makes the count
    independent of the order signals arrive in.
    """
    occupied: dict[Instrument, list[Span]] = {}
    channels = 0
    ordered = sorted(
        signals, key=lambda s: (s.instrument.value, s.span.start, s.span.end, s.signal_id)
    )
    for signal in ordered:
        seen = occupied.setdefault(signal.instrument, [])
        if any(_overlaps(signal.span, other) for other in seen):
            continue
        seen.append(signal.span)
        channels += 1
    return channels


def corroborate(
    finding: FindingClaim, signals: Sequence[CorroborationSignal]
) -> Corroboration:
    """Weigh the signals that corroborate `finding`. Pure: no clock, no RNG.

    Noisy-OR over the surviving terms — one per independent channel, plus at
    most one for the whole correlated class. Redundant signals supply no term,
    which is `W_REDUNDANT` doing its job rather than a special case.
    """
    on_span = [s for s in signals if _overlaps(s.span, finding.span)]
    by_class: dict[IndependenceClass, list[CorroborationSignal]] = {
        klass: [] for klass in IndependenceClass
    }
    for signal in on_span:
        by_class[_CLASS_OF[signal.instrument]].append(signal)

    channels = _independent_channels(by_class[IndependenceClass.INDEPENDENT])
    correlated = by_class[IndependenceClass.CORRELATED]
    redundant = by_class[IndependenceClass.REDUNDANT]

    terms = [_WEIGHT[IndependenceClass.INDEPENDENT]] * channels
    if correlated:
        # Once, not once each: a shared error source does not compound.
        terms.append(_WEIGHT[IndependenceClass.CORRELATED])
    # Carried as real terms rather than skipped: `W_REDUNDANT` is what makes
    # them weightless, so a future edit to the table changes behaviour here
    # instead of being quietly ignored by a filter.
    terms.extend([_WEIGHT[IndependenceClass.REDUNDANT]] * len(redundant))

    strength = round(1.0 - math.prod(1.0 - term for term in terms), 6)

    return Corroboration(
        finding_id=finding.finding_id,
        strength=strength,
        independent_channels=channels,
        correlated_signals=len(correlated),
        redundant_signals=len(redundant),
        off_span_signals=len(signals) - len(on_span),
    )


def clears(corroboration: Corroboration, deferral: ClearableDeferral | str) -> bool:
    """Does this corroboration clear that deferral? Only one deferral can ask.

    Anything but `finding_thin` is refused rather than answered `False`, so a
    caller that wires the criterion-health axis into this call finds out at the
    call site instead of receiving a plausible-looking negative (D4).
    """
    try:
        ClearableDeferral(deferral)
    except ValueError:
        raise UnclearableDeferral(
            f"corroboration cannot clear {deferral!r}; it clears only "
            f"{ClearableDeferral.FINDING_THIN.value!r}. A criterion's "
            f"'criterion_below_tau' deferral is the other axis (D4) — it is a "
            f"property of the criterion's κ, and no number of corroborating "
            f"anchors moves it."
        ) from None
    return corroboration.clears_finding_thin


# Asserted at import rather than left to a test a future edit might not run: D4
# lives in the *size* of this set, so a member added to it is the violation
# itself, not a step toward one.
_CLEARABLE = tuple(ClearableDeferral)
if _CLEARABLE != (ClearableDeferral.FINDING_THIN,):  # pragma: no cover - guard
    raise AssertionError(
        f"ClearableDeferral must hold exactly finding_thin; found {_CLEARABLE}. "
        f"Corroboration clears a per-finding evidence deferral and nothing "
        f"else; the criterion-health axis is orthogonal to it (D4)."
    )
