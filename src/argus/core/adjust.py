"""The adjusted lane (9021 M18) — precedent applied to a re-derived total.

I3 splits the shipped number in two: `raw = score(facts, rubric)`, then
`adjusted = adjust(raw, history)`. M10 built the first. This is the second, and
it exists so that the raw lane can stay blind: precedent is real — a human who
ruled on a near-identical call last month should bind this one — but a
precedent reaching `score()` would make the raw number unreproducible from its
grounded inputs, which is the whole property I3 protects.

Neither codebase has any notion of a precedent, so what one *is* was designed
here rather than ported. Three decisions, each of which could have gone the
other way:

**A precedent carries an outcome, not a delta.** The tempting shape is a signed
number of points. It is also the shape I7 exists to forbid: a digit has no
span, and a free-floating `-3.0` cannot be traced to anything. So a precedent
says what a human ruled about one criterion — `PASS` where the machine said
`FAIL` — and the points are re-derived from the weight already on the record,
which came from the rubric inside `core/`. Nothing here invents an arithmetic
of its own; `tally()` is the same function `score()` used.

**Adjustment re-derives; it does not patch the total.** `adjust` rebuilds the
contribution set with the overturned rows replaced and re-runs `tally`, rather
than adding and subtracting from `raw.value`. Patching a rounded aggregate
accumulates error and, worse, cannot lift a veto — the zero would survive a
precedent that overturned the very failure that caused it.

**A precedent cannot resurrect a deferred row.** A criterion that deferred has
no contribution to adjust, and letting history pull it back into the arithmetic
would let precedent close a coverage gap. D10 gives that decision to a human,
not to the record of what a human once decided about a different call.

I5: the applied set is on the result, in sorted order, so the replay hash can
take grounded inputs *and anchored precedents* and nothing else. The dropped
set is there too — not for the hash, but because "we ignored four of your
precedents" is exactly the kind of silence that makes a number untrustworthy.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from argus.core.score import Contribution, Deferral, RawScore, credit_for, tally
from argus.types.pipeline import VerdictResult

# Same shape M6 requires of an evidence epoch, for the same reason: a pin that
# is not a commit is not a pin (I4).
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class DropReason(str, Enum):
    """Why an otherwise well-formed precedent was not applied.

    Both are conditions of *this* evaluation rather than of the precedent, which
    is why they are decided here and not at construction: the same precedent is
    applicable to one call and inapplicable to the next.
    """

    NO_SUCH_CRITERION = "no_such_criterion"
    CRITERION_DEFERRED = "criterion_deferred"


class Precedent(BaseModel):
    """A prior human ruling on one criterion, anchored to where it was made.

    The anchors are not decoration. `prior_evaluation_id` is what lets someone
    read the case this ruling came from, and `intents_sha` is the epoch it was
    decided against (I4) — a ruling made when the criterion's INTENTS node said
    something else is not a ruling about this criterion.

    Malformedness is rejected here rather than tolerated and dropped later, so
    that the drop reasons on the result mean "inapplicable to this call" rather
    than "we could not read it".
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    precedent_id: str = Field(min_length=1)
    prior_evaluation_id: str = Field(min_length=1)
    rubric_id: int
    ruled_outcome: VerdictResult
    intents_sha: str

    @model_validator(mode="after")
    def _anchored(self) -> Precedent:
        if not SHA_RE.match(self.intents_sha):
            raise ValueError(
                f"intents_sha {self.intents_sha!r} is not a 40-character git object "
                f"name; an unanchored precedent cannot be applied (I4)"
            )
        if credit_for(self.ruled_outcome) is None:
            raise ValueError(
                f"a precedent cannot rule {self.ruled_outcome.value}: that outcome "
                f"does not score, so there is nothing for it to overturn"
            )
        return self


class AppliedPrecedent(BaseModel):
    """What changed, and what it was before. The `from` half is the audit trail."""

    model_config = ConfigDict(frozen=True)

    precedent_id: str
    rubric_id: int
    finding_id: str
    from_outcome: VerdictResult
    to_outcome: VerdictResult


class DroppedPrecedent(BaseModel):
    model_config = ConfigDict(frozen=True)

    precedent_id: str
    rubric_id: int
    reason: DropReason


class AdjustedScore(BaseModel):
    """The shipped number, and the record of how it differs from the raw one."""

    model_config = ConfigDict(frozen=True)

    rubric_version: str
    value: float
    numerator: float
    denominator: float
    veto_triggered: bool
    veto_criteria: tuple[int, ...] = Field(default_factory=tuple)
    contributions: tuple[Contribution, ...] = Field(default_factory=tuple)
    deferrals: tuple[Deferral, ...] = Field(default_factory=tuple)

    raw_value: float
    applied: tuple[AppliedPrecedent, ...] = Field(default_factory=tuple)
    dropped: tuple[DroppedPrecedent, ...] = Field(default_factory=tuple)


def adjust(raw: RawScore, history: Sequence[Precedent]) -> AdjustedScore:
    """Apply anchored precedent to a raw score. Pure: no clock, no RNG, no model.

    With empty history the result is the raw score verbatim — same value, same
    numerator, same denominator, same vetoes. That is asserted rather than
    assumed: it is the property that makes "we applied no precedent" and "we
    have no precedent stage" indistinguishable in the output, which is what a
    reviewer needs in order to trust the stage at all.
    """
    deferred_criteria = {d.rubric_id for d in raw.deferrals}
    scored_criteria = {c.rubric_id for c in raw.contributions}

    rulings: dict[int, Precedent] = {}
    dropped: list[DroppedPrecedent] = []

    for precedent in history:
        if precedent.rubric_id in deferred_criteria and precedent.rubric_id not in scored_criteria:
            # Checked before the membership test so a deferred criterion reports
            # why it was skipped rather than the less specific "not scored".
            dropped.append(
                DroppedPrecedent(
                    precedent_id=precedent.precedent_id,
                    rubric_id=precedent.rubric_id,
                    reason=DropReason.CRITERION_DEFERRED,
                )
            )
            continue
        if precedent.rubric_id not in scored_criteria:
            dropped.append(
                DroppedPrecedent(
                    precedent_id=precedent.precedent_id,
                    rubric_id=precedent.rubric_id,
                    reason=DropReason.NO_SUCH_CRITERION,
                )
            )
            continue
        if precedent.rubric_id in rulings:
            raise ValueError(
                f"two precedents rule on criterion {precedent.rubric_id} "
                f"({rulings[precedent.rubric_id].precedent_id} and "
                f"{precedent.precedent_id}); which one binds is a human's call, "
                f"not this function's"
            )
        rulings[precedent.rubric_id] = precedent

    contributions: list[Contribution] = []
    applied: list[AppliedPrecedent] = []

    for contribution in raw.contributions:
        precedent = rulings.get(contribution.rubric_id)
        if precedent is None or precedent.ruled_outcome is contribution.outcome:
            contributions.append(contribution)
            continue

        contributions.append(
            contribution.model_copy(
                update={
                    "outcome": precedent.ruled_outcome,
                    "credit": credit_for(precedent.ruled_outcome),
                }
            )
        )
        applied.append(
            AppliedPrecedent(
                precedent_id=precedent.precedent_id,
                rubric_id=contribution.rubric_id,
                finding_id=contribution.finding_id,
                from_outcome=contribution.outcome,
                to_outcome=precedent.ruled_outcome,
            )
        )

    value, numerator, denominator, vetoes = tally(contributions)

    return AdjustedScore(
        rubric_version=raw.rubric_version,
        value=value,
        numerator=numerator,
        denominator=denominator,
        veto_triggered=bool(vetoes),
        veto_criteria=vetoes,
        contributions=tuple(sorted(contributions, key=lambda c: (c.rubric_id, c.finding_id))),
        deferrals=raw.deferrals,
        raw_value=raw.value,
        applied=tuple(sorted(applied, key=lambda a: (a.rubric_id, a.finding_id))),
        dropped=tuple(sorted(dropped, key=lambda d: (d.rubric_id, d.precedent_id))),
    )
