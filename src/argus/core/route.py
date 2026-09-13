"""S5 routing (9021 M19) — the two-axis gate, kept two.

D10: auto-final requires **both** gates clear — the coverage gate (no
ungrounded findings, no deferrals) AND the criterion health gate (every cited
criterion `trusted`). Neither substitutes for the other. That sentence is easy
to write and easy to lose: the natural implementation accumulates a list of
"problems", checks whether it is empty, and the two axes become one the moment
someone adds a reason to the list. So the axes are computed separately here,
from separately-typed inputs, and conjoined exactly once.

**Why this function does not take corroboration.** I6 lets an independent
corroborating anchor clear a per-finding `finding_thin` deferral; D4 says no
amount of corroboration clears a criterion's `criterion_below_tau`. If routing
accepted corroboration it would have to be trusted not to apply it to the
second axis. It does not accept it: `core/corroboration.py` decides which
findings are still thin, and this stage receives that outcome. The health axis
arrives as a set of untrusted criterion ids and there is no argument here that
could clear one.

**Three `defer_reason` values, and where the others went.** §6 names exactly
`ungrounded`, `finding_thin` and `criterion_below_tau`. The earlier stages have
their own vocabularies — `score.DeferReason` has `unverifiable` and
`human_review`, which are what *the scorer* can observe — and folding them in
would either lose information or grow §6's list. Neither: each incoming reason
maps to one of the three, and `detail` keeps the originating reason readable.
An `unverifiable` row is `ungrounded` because nothing about it resolved to real
evidence; a `human_review` row is `ungrounded` for the same reason, and both
carry the word they arrived with.

**A deferral is never a reason to drop a finding.** Same rule as the grounding
gate (I2): every input appears in the output. A routing decision that quietly
omitted a finding would auto-finalise a call by losing the objection to it.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from argus.core.adjust import AdjustedScore
from argus.core.grounding import UngroundedFinding
from argus.core.score import DeferReason as ScoreDeferReason


class Disposition(str, Enum):
    AUTO_FINAL = "auto_final"
    HUMAN = "human"


class DeferReason(str, Enum):
    """§6's three values. Not a superset of any earlier stage's enum."""

    UNGROUNDED = "ungrounded"
    FINDING_THIN = "finding_thin"
    CRITERION_BELOW_TAU = "criterion_below_tau"


# What each scorer-observable reason becomes at S5. Explicit rather than a
# default, so a new `score.DeferReason` member fails here instead of routing as
# whatever `.get()` returns.
_FROM_SCORER: dict[ScoreDeferReason, DeferReason] = {
    ScoreDeferReason.UNVERIFIABLE: DeferReason.UNGROUNDED,
    ScoreDeferReason.HUMAN_REVIEW: DeferReason.UNGROUNDED,
}


class RouteDeferral(BaseModel):
    """One reason this call cannot finalise itself, and what raised it."""

    model_config = ConfigDict(frozen=True)

    reason: DeferReason
    subject: str
    detail: str


class RoutingDecision(BaseModel):
    """The disposition, both axes shown separately, and every objection kept.

    `coverage_clear` and `criteria_clear` are on the record rather than folded
    into the disposition because "this call went to a human" and "this call
    went to a human *because a criterion is untrusted*" are different facts, and
    only the second one tells anybody what to fix.
    """

    model_config = ConfigDict(frozen=True)

    disposition: Disposition
    coverage_clear: bool
    criteria_clear: bool
    deferrals: tuple[RouteDeferral, ...] = Field(default_factory=tuple)

    @property
    def auto_final(self) -> bool:
        return self.disposition is Disposition.AUTO_FINAL


def route(
    adjusted: AdjustedScore,
    *,
    ungrounded: Sequence[UngroundedFinding] = (),
    thin_findings: Collection[str] = (),
    untrusted_criteria: Collection[int] = (),
) -> RoutingDecision:
    """Decide whether a call may finalise itself. Pure: no clock, no RNG, no model.

    `thin_findings` are the finding ids whose corroboration did *not* clear
    `finding_thin` — the outcome of `core/corroboration.py`, not its inputs.
    `untrusted_criteria` are the rubric ids whose κ is below τ. The two arrive
    separately and stay separate.
    """
    deferrals: list[RouteDeferral] = []

    for finding in ungrounded:
        deferrals.append(
            RouteDeferral(
                reason=DeferReason.UNGROUNDED,
                subject=finding.finding.finding_id,
                detail=f"{finding.reason.value}: {finding.detail}",
            )
        )

    for deferral in adjusted.deferrals:
        deferrals.append(
            RouteDeferral(
                reason=_FROM_SCORER[deferral.reason],
                subject=deferral.finding_id,
                detail=(
                    f"criterion {deferral.rubric_id} scored "
                    f"{deferral.reason.value}, so it reached no verified evidence"
                ),
            )
        )

    for finding_id in thin_findings:
        deferrals.append(
            RouteDeferral(
                reason=DeferReason.FINDING_THIN,
                subject=finding_id,
                detail=(
                    "single-channel evidence, uncorroborated by an independent "
                    "anchor (I6)"
                ),
            )
        )

    for rubric_id in untrusted_criteria:
        deferrals.append(
            RouteDeferral(
                reason=DeferReason.CRITERION_BELOW_TAU,
                subject=str(rubric_id),
                detail=(
                    "criterion agreement is below tau; no amount of "
                    "corroboration clears this (D4)"
                ),
            )
        )

    raised = {d.reason for d in deferrals}

    # The coverage axis: nothing unanchored, nothing thin, and something scored.
    # A call where every criterion was inapplicable has cleared no gate; it has
    # answered no question.
    coverage_clear = (
        DeferReason.UNGROUNDED not in raised
        and DeferReason.FINDING_THIN not in raised
        and adjusted.denominator > 0
    )
    # The criterion health axis, computed from its own inputs and nothing else.
    criteria_clear = DeferReason.CRITERION_BELOW_TAU not in raised

    return RoutingDecision(
        disposition=(
            Disposition.AUTO_FINAL
            if (coverage_clear and criteria_clear)
            else Disposition.HUMAN
        ),
        coverage_clear=coverage_clear,
        criteria_clear=criteria_clear,
        deferrals=tuple(sorted(deferrals, key=lambda d: (d.reason.value, d.subject))),
    )
