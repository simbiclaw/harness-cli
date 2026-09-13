"""The raw scoring lane (9021 M10, M11) — pure, and blind to history.

I3 splits the shipped number into two stages: `raw = score(facts, rubric)`, then
`adjusted = adjust(raw, history)`. This module is the first stage. Its whole
job is to be boring: same grounded facts, same rubric version, same number,
forever.

Two things it deliberately refuses to do.

**It does not accept history.** Not as an optional argument, not through a
default, not on the fact. `score` has exactly two parameters. The runtime purity
assert in the spec's §5 rejects a raw-lane verdict citing a precedent; a
signature that cannot express one is the cheaper version of the same check, and
it fails at import time rather than at verdict time.

**It does not read a weight off a fact.** Upstream stamps the rubric's weight
onto each `Verdict` inside `core/fact_checker.py` — a module that calls the
model and is therefore bound for `io/` here — and the aggregator then sums
`v.score * v.weight` off those copies. The number that decides the score has
passed through the quarantine, where nothing re-checks it against the rubric.
So `ScorableFact` carries no `weight` field at all: the only way to get one is
to look the criterion up in the rubric that was passed in. The same is true of
`is_veto`, which upstream copies onto `Subquestion` in `question_generator.py`.

M11 — the unverifiable case. Upstream scores NEI at 0.5 and leaves it in the
denominator, so a criterion nobody could check contributes half a point to a
shipped number. This repository's rules say the opposite: a finding that
anchors to nothing real routes to a human and blocks auto-final (I2, D10). So
NEI leaves both the numerator and the denominator and is recorded as a
deferral. This changes every score the upstream has produced; that is the
intended effect, not a regression.

The `NA` case is unchanged from upstream: a criterion that does not apply to
this call is not a gap, and excluding it from both sides is already what
upstream does.

`PARTIAL` counts as a failure, scoring zero against its full weight. That is
inherited, not decided: upstream's `1.0 if PASS else 0.5 if NEI else 0.0`
already gives it zero. It is called out here because it is the one outcome
whose treatment nobody has argued for.
"""

from __future__ import annotations

import inspect
from collections.abc import Sequence
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from argus.types.pipeline import RubricItem, VerdictResult


class DeferReason(str, Enum):
    """Why a criterion left the arithmetic instead of scoring.

    Only the reasons this stage can observe. `finding_thin` and
    `criterion_below_tau` are decided downstream (M17, M19) and are not this
    function's to assign — it cannot see corroboration or κ.
    """

    UNVERIFIABLE = "unverifiable"
    HUMAN_REVIEW = "human_review"


# What each outcome contributes: (credit, counts_toward_denominator).
# `None` means the outcome does not score at all; the deferral map below says
# whether that absence is a gap or simply an inapplicable row.
_CREDIT: dict[VerdictResult, float | None] = {
    VerdictResult.PASS: 1.0,
    VerdictResult.FAIL: 0.0,
    VerdictResult.PARTIAL: 0.0,
    VerdictResult.NA: None,
    VerdictResult.NEI: None,
    VerdictResult.HUMAN_REVIEW: None,
}

# An outcome that does not score and *is* a gap. `NA` is absent on purpose: it
# does not score and is not a gap.
_DEFERRALS: dict[VerdictResult, DeferReason] = {
    VerdictResult.NEI: DeferReason.UNVERIFIABLE,
    VerdictResult.HUMAN_REVIEW: DeferReason.HUMAN_REVIEW,
}


def credit_for(outcome: VerdictResult) -> float | None:
    """The credit one outcome earns, or `None` if it does not score at all.

    Public because M18 needs it to re-derive an overturned row's credit, and a
    downstream stage reaching into `_CREDIT` would be a second place where the
    outcome-to-credit mapping lives.
    """
    return _CREDIT[outcome]


class UnknownCriterion(LookupError):
    """A fact cites a criterion the rubric does not contain.

    Upstream's `_get_weight` returns 1.0 for an unknown `rubric_id`, so a
    typo'd or stale reference scores at full unweighted strength and nothing
    says so. Under I2 a finding that anchors to nothing real is not scored at
    a default; it is refused here and routed by the caller.
    """


class ScorableFact(BaseModel):
    """A grounded finding, reduced to what the arithmetic needs.

    Note what is *not* here: no weight, no veto flag, no confidence, no prose,
    no precedent. Weight and veto come from the rubric. The rest cannot reach
    a pure function that does not accept them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    rubric_id: int
    outcome: VerdictResult


class Rubric(BaseModel):
    """The scoring sheet at one version, with the version carried along.

    I3's determinism claim is scoped to a rubric *version* — without it on the
    record, two runs that differ only in which sheet they used are
    indistinguishable after the fact.
    """

    model_config = ConfigDict(frozen=True)

    version: str
    items: tuple[RubricItem, ...]

    def item(self, rubric_id: int) -> RubricItem:
        for candidate in self.items:
            if candidate.id == rubric_id:
                return candidate
        raise UnknownCriterion(
            f"rubric {self.version} has no criterion {rubric_id}; a fact citing "
            f"a criterion that does not exist cannot be scored"
        )


class Contribution(BaseModel):
    """One scored row, kept so the total can be re-derived rather than trusted.

    I5 requires the stored record to re-derive the identical result forever. A
    record carrying only a numerator and a denominator cannot: nothing in it
    says which criterion contributed what, so a later stage that needs to
    revisit one row — M18 applying a precedent — would have to re-run the whole
    pipeline or invent the arithmetic a second time.

    `weight` and `is_veto` are copied from the rubric *here*, inside `core/`,
    at the moment the rubric was consulted. That is the opposite of upstream,
    where the copy is made inside a model-calling module and the arithmetic
    never sees the sheet.
    """

    model_config = ConfigDict(frozen=True)

    finding_id: str
    rubric_id: int
    outcome: VerdictResult
    credit: float
    weight: float
    is_veto: bool

    @model_validator(mode="after")
    def _credit_matches_outcome(self) -> Contribution:
        """The credit is a function of the outcome, so it cannot disagree with it.

        Without this a caller — M18 applying a precedent, most plausibly — could
        record `outcome=FAIL` with `credit=1.0`, and the row would score as a
        pass while the veto rule still read it as a failure. The two fields are
        stored separately because the arithmetic needs one and the veto rule
        needs the other; keeping them consistent is this check's whole job.
        """
        expected = _CREDIT[self.outcome]
        if expected is None or self.credit != expected:
            raise ValueError(
                f"outcome {self.outcome.value} scores {expected}, not {self.credit}"
            )
        return self


class Deferral(BaseModel):
    model_config = ConfigDict(frozen=True)

    finding_id: str
    rubric_id: int
    reason: DeferReason


class RawScore(BaseModel):
    """The output of the raw lane. Re-derivable from `(facts, rubric)` alone.

    `coverage_clear` is *one* of the two axes D10 requires for auto-final, and
    is deliberately not named `auto_final_eligible`: the criterion-health axis
    is invisible from here, and a boolean with that name computed from one axis
    is exactly the substitution D10 forbids. Use `auto_final_eligible()`.
    """

    model_config = ConfigDict(frozen=True)

    rubric_version: str
    value: float
    numerator: float
    denominator: float
    veto_triggered: bool
    veto_criteria: tuple[int, ...] = Field(default_factory=tuple)
    contributions: tuple[Contribution, ...] = Field(default_factory=tuple)
    deferrals: tuple[Deferral, ...] = Field(default_factory=tuple)

    @property
    def coverage_clear(self) -> bool:
        """No gaps, and something was actually scored.

        A denominator of zero is not a clean sheet — it is a call where every
        criterion was inapplicable, which is a result nobody should ship
        automatically.
        """
        return not self.deferrals and self.denominator > 0


def tally(contributions: Sequence[Contribution]) -> tuple[float, float, float, tuple[int, ...]]:
    """Sum a set of contributions into `(value, numerator, denominator, vetoes)`.

    Separated from `score` so that M18 re-derives the adjusted total through
    the same arithmetic rather than writing a second copy of it. Two copies is
    how `raw` and `adjusted` drift apart while both look correct.

    A veto is a *failure* on a criterion the rubric marks as one, matching
    upstream (`core/aggregator.py:76`). Not merely a row that earned no credit:
    `PARTIAL` also earns none, and treating it as a veto would zero a call for
    a partially-met criterion — a change nobody asked for and which would be
    invisible behind a passing test suite.

    Recomputed from the contributions rather than carried over, so a precedent
    that overturns the failure also lifts the veto it caused.
    """
    numerator = sum(c.credit * c.weight for c in contributions)
    denominator = sum(c.weight for c in contributions)
    vetoes = tuple(
        sorted(
            {
                c.rubric_id
                for c in contributions
                if c.is_veto and c.outcome is VerdictResult.FAIL
            }
        )
    )

    value = round(numerator / denominator * 100, 1) if denominator > 0 else 0.0
    if vetoes:
        value = 0.0
    return value, numerator, denominator, vetoes


def score(facts: Sequence[ScorableFact], rubric: Rubric) -> RawScore:
    """Derive the raw score. Pure: no clock, no RNG, no history, no model.

    Order-independent by construction — the arithmetic is a sum, and every
    sequence on the result is sorted before it is returned — so a caller that
    shuffles its findings gets a byte-identical record.
    """
    contributions: list[Contribution] = []
    deferrals: list[Deferral] = []

    for fact in facts:
        item = rubric.item(fact.rubric_id)  # raises on an unknown criterion
        credit = _CREDIT[fact.outcome]

        if credit is None:
            reason = _DEFERRALS.get(fact.outcome)
            if reason is not None:
                deferrals.append(
                    Deferral(
                        finding_id=fact.finding_id,
                        rubric_id=fact.rubric_id,
                        reason=reason,
                    )
                )
            continue

        contributions.append(
            Contribution(
                finding_id=fact.finding_id,
                rubric_id=fact.rubric_id,
                outcome=fact.outcome,
                credit=credit,
                weight=item.weight,
                is_veto=item.is_veto,
            )
        )

    value, numerator, denominator, vetoes = tally(contributions)

    return RawScore(
        rubric_version=rubric.version,
        value=value,
        numerator=numerator,
        denominator=denominator,
        veto_triggered=bool(vetoes),
        veto_criteria=vetoes,
        contributions=tuple(
            sorted(contributions, key=lambda c: (c.rubric_id, c.finding_id))
        ),
        deferrals=tuple(sorted(deferrals, key=lambda d: (d.rubric_id, d.finding_id))),
    )


def auto_final_eligible(raw: RawScore, *, criteria_trusted: bool) -> bool:
    """D10's two gates, conjoined — and neither with a default.

    `criteria_trusted` is keyword-only and has no default precisely so that a
    caller cannot obtain an auto-final answer while knowing only the coverage
    axis. Whoever wants the answer must supply the health axis (M19), even if
    the value they supply is `False` because they have not measured κ yet.
    """
    return raw.coverage_clear and criteria_trusted


# The signature is load-bearing, so it is asserted at import rather than left
# to a test that a future edit might not run. I3: `score` never sees history.
_PARAMS = tuple(inspect.signature(score).parameters)
if _PARAMS != ("facts", "rubric"):  # pragma: no cover - structural guard
    raise AssertionError(
        f"score() must take exactly (facts, rubric); found {_PARAMS}. I3 splits "
        f"the shipped number into raw and adjusted lanes, and the raw lane "
        f"never receives history."
    )
