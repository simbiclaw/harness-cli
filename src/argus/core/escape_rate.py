"""The escape-rate estimator (9021 M19) — and the floor it needs to mean anything.

9020 landed the tranche split and a "compatible estimator" in
`core/escape_sampler.py`, with its docstring deferring the real one to a
milestone that never ran. This module is that estimator. The sampler keeps the
split; the estimate lives here, which is the reconciliation M19 asks for.

Two things the 9020 version got wrong, both invisible while nothing called it.

**An empty tranche returned `0.0`.** A rate of zero is the most reassuring
number this function can produce, and it was what you got for reviewing nobody.
An estimate and the absence of one are different facts and must not share a
representation, so the result is a record carrying `reportable` rather than a
bare float.

**The floor had no declared value.** 9020 shipped `absolute_floor: int = 0` and
every test passed its own number, so the floor existed as a parameter and
nowhere as a commitment. `ESCAPE_RATE_FLOOR` below is that commitment.

**Where 60 comes from.** The escape ceiling already declared in this repository
is 0.05 — `core/compiler/agreement.py:49`, the fraction of escapes a criterion
may tolerate before its gate is re-examined. The question the estimate has to
answer is therefore "is the true rate below 0.05?", and the hardest version of
it is a sample in which a human found nothing: by the rule of three, zero events
in n trials puts the 95% upper bound at about 3/n, so 3/0.05 = 60 reviews is the
smallest clean sample that can distinguish "below the ceiling" from "too few
looks to tell". Below that, a clean sample is silence, not evidence.

`Confidence: low` — on the 0.05 ceiling, not on the arithmetic. 60 follows from
0.05 by a standard bound; whether 0.05 is the right ceiling for customer-service
QA is unmeasured, inherited from patch-1's AUTH-6, and moves this number
inversely if it changes. What would settle it: the first human-labelled review
period, which also produces the `corr(matcher_error, proposer_error)` sample
W_C is waiting on.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from argus.core.escape_sampler import RandomTranche

# See the module docstring: 3 / 0.05, the rule of three against the escape
# ceiling at core/compiler/agreement.py:49.
ESCAPE_RATE_FLOOR = 60


class EscapeRate(BaseModel):
    """An escape-rate estimate, or the explicit absence of one.

    `value` is meaningless unless `reportable` is true. It is still carried when
    it is not — a caller triaging a short review period wants to see the two
    misses it did find, and hiding them would be its own kind of silence.
    """

    model_config = ConfigDict(frozen=True)

    value: float
    reviewed: int
    misses: int
    floor: int
    reportable: bool


def compute_escape_rate(
    sample: RandomTranche, *, floor: int = ESCAPE_RATE_FLOOR
) -> EscapeRate:
    """Human-caught misses over reviewed auto-passes, on the random tranche only.

    Type-enforced, as 9020 built it: a `PrioritizedTranche` or a raw list raises
    `TypeError`. The prioritized tranche is ordered by the proposer signal, so
    feeding it here would estimate the rate among the calls most suspected of
    being misses — the bias D22 exists to prevent, and a `float` return could
    not have made that failure visible after the fact.

    A sample below the floor is computed but not reportable. It is not an error:
    review periods start short, and the honest answer to "what is the escape
    rate" after eleven reviews is "we do not know yet", which is a value this
    function must be able to return.
    """
    if not isinstance(sample, RandomTranche):
        raise TypeError(
            f"compute_escape_rate consumes only the random tranche; got "
            f"{type(sample).__name__}. The prioritized tranche is excluded by "
            f"D22 — feeding it here would bias the estimate."
        )
    if floor < 1:
        raise ValueError(
            f"floor {floor} is not a floor; 9020 shipped a default of 0 and the "
            f"result was that no call site had one (see the module docstring)"
        )

    reviewed = len(sample.calls)
    misses = sum(1 for c in sample.calls if c.missed)
    return EscapeRate(
        value=misses / reviewed if reviewed else 0.0,
        reviewed=reviewed,
        misses=misses,
        floor=floor,
        reportable=reviewed >= floor,
    )
