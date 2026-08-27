"""Escape sampler tranche split (9020 M4, core, pure).

The escape-rate estimator (D11) needs an unbiased sample of auto-passed calls.
The continuous proposed score (M2) lets us prioritize which auto-passed calls a
human reviews — low proposed score, no grounded finding, the recall problem
wearing a flag. But prioritizing the *whole* sample would bias the very number
the estimator depends on. So the sampler splits (D22):

- a RANDOM tranche — >= a declared absolute floor, chosen decorrelated from the
  proposer signal, the only decorrelated window into auto-passed calls and the
  only input `compute_escape_rate()` may consume;
- a PRIORITIZED tranche — ordered by proposer signal, feeding recall recovery
  and calibration minting, and excluded from the escape-rate computation.

The random-tranche-only rule is enforced by TYPE: `compute_escape_rate()`
accepts a `RandomTranche` and nothing else. A `PrioritizedTranche` or a raw
list is a `TypeError`, so the bias cannot enter by a careless call site.

Decorrelation without RNG: the partition is a stable hash of `call_id`, which
is independent of `proposed_score`, so the random tranche is decorrelated from
the proposer signal AND deterministic (replayable) — no clock, no RNG.

Provisional: 9002 M5.5 owns the real `compute_escape_rate()`; this module lands
the tranche split and a compatible estimator. The split ratio and floor are
config (Q3); they are function arguments with documented defaults until the
config layer lands. `escape-random` provenance is the scarce, load-bearing
input to manifest curation (companion patch 3), so the random tranche is the
value this milestone protects.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class AutoPassedCall:
    """One auto-finalized call eligible for escape sampling.

    `proposed_score` is the quarantined M2 signal used only to ORDER the
    prioritized tranche — never to select the random tranche. `missed` is the
    review outcome: did a human find an escape the pipeline auto-passed.
    """

    call_id: str
    proposed_score: float
    has_grounded_finding: bool
    missed: bool


@dataclass(frozen=True)
class RandomTranche:
    """The decorrelated sample. The ONLY type compute_escape_rate() accepts."""

    calls: list[AutoPassedCall]

    def __len__(self) -> int:
        return len(self.calls)


@dataclass(frozen=True)
class PrioritizedTranche:
    """Ordered by proposer signal. Excluded from the escape-rate computation."""

    calls: list[AutoPassedCall]

    def __len__(self) -> int:
        return len(self.calls)


def _partition_key(call_id: str) -> int:
    """A stable, uniform key from call_id — independent of the proposer signal."""
    digest = hashlib.sha256(call_id.encode()).hexdigest()
    return int(digest[:16], 16)


def _priority_key(call: AutoPassedCall) -> tuple:
    """Order the prioritized tranche: lowest proposed score, ungrounded first.

    These are the auto-passes most likely to be silent misses (the C6 recall
    problem). `call_id` breaks ties deterministically.
    """
    return (call.has_grounded_finding, call.proposed_score, call.call_id)


def split_tranches(
    calls: list[AutoPassedCall],
    random_fraction: float = 0.5,
    absolute_floor: int = 0,
) -> tuple[RandomTranche, PrioritizedTranche]:
    """Split auto-passed calls into a random tranche and a prioritized tranche.

    The random tranche size is `max(absolute_floor, round(random_fraction * n))`,
    capped at n — the floor can never manufacture calls that do not exist. Its
    members are the calls with the smallest partition key, a hash of call_id
    that is decorrelated from `proposed_score`. Everything else is prioritized,
    ordered by proposer signal.

    Defaults (0.5, 0) are provisional; the real values are config (Q3).
    """
    if not 0.0 <= random_fraction <= 1.0:
        raise ValueError("random_fraction must be in [0, 1]")
    n = len(calls)
    target = max(absolute_floor, round(random_fraction * n))
    target = min(target, n)

    by_key = sorted(calls, key=lambda c: _partition_key(c.call_id))
    random_calls = by_key[:target]
    random_ids = {c.call_id for c in random_calls}
    prioritized_calls = sorted(
        (c for c in calls if c.call_id not in random_ids), key=_priority_key
    )
    return RandomTranche(random_calls), PrioritizedTranche(prioritized_calls)


def compute_escape_rate(sample: RandomTranche) -> float:
    """Human-caught misses / reviewed auto-passes, over the random tranche only.

    Type-enforced: a `PrioritizedTranche` or a raw list raises `TypeError`, so a
    biased sample cannot reach the estimator. An empty tranche is a rate of 0.0.
    """
    if not isinstance(sample, RandomTranche):
        raise TypeError(
            f"compute_escape_rate consumes only the random tranche; got "
            f"{type(sample).__name__}. The prioritized tranche is excluded by "
            f"D22 — feeding it here would bias the estimate."
        )
    if not sample.calls:
        return 0.0
    misses = sum(1 for c in sample.calls if c.missed)
    return misses / len(sample.calls)
