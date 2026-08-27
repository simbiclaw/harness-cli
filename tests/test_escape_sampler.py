"""Acceptance tests for 9010 M4 — escape sampler tranche split (D22).

The escape-rate estimator needs an unbiased sample of auto-passed calls. The
continuous proposed score lets us prioritize which auto-passed calls humans
review (low score, no grounded finding), but prioritizing the whole sample
would bias the very number the estimator depends on. So the sampler splits:

- a RANDOM tranche (>= a declared absolute floor), decorrelated from proposer
  signal, the only input compute_escape_rate() may consume;
- a PRIORITIZED tranche, ordered by proposer signal, excluded from the rate.

The random-tranche-only rule is enforced by TYPE, not convention:
compute_escape_rate() rejects anything that is not a RandomTranche.

See docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation.md
"""

from __future__ import annotations

import pytest

from argus.core.escape_sampler import (
    AutoPassedCall,
    PrioritizedTranche,
    RandomTranche,
    compute_escape_rate,
    split_tranches,
)


def _stream(n: int, miss_every: int = 10) -> list[AutoPassedCall]:
    """A synthetic auto-passed stream with a known miss rate (1/miss_every).

    `missed` is assigned by position, independent of call_id and proposed_score,
    so the true stream miss rate is exactly 1/miss_every.
    """
    calls = []
    for i in range(n):
        calls.append(
            AutoPassedCall(
                call_id=f"call-{i:05d}",
                proposed_score=float(i % 20),
                has_grounded_finding=(i % 3 == 0),
                missed=(i % miss_every == 0),
            )
        )
    return calls


def test_d22_red():
    """compute_escape_rate() fed a non-random tranche is rejected."""
    calls = _stream(100)
    _, prioritized = split_tranches(calls, random_fraction=0.5, absolute_floor=10)
    assert isinstance(prioritized, PrioritizedTranche)

    with pytest.raises(TypeError):
        compute_escape_rate(prioritized)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        compute_escape_rate(calls)  # a raw list is not a RandomTranche either


def test_d22_green():
    """Random tranche only; the estimator is unbiased over a known miss rate."""
    calls = _stream(1000, miss_every=10)  # true rate = 0.10
    random_tranche, _ = split_tranches(calls, random_fraction=0.5, absolute_floor=20)
    assert isinstance(random_tranche, RandomTranche)

    rate = compute_escape_rate(random_tranche)
    # Unbiased: the decorrelated random tranche recovers the stream rate.
    assert abs(rate - 0.10) < 0.03, f"rate {rate} strayed from the true 0.10"


def test_random_tranche_floor_holds():
    """The random tranche never falls below the declared absolute minimum."""
    calls = _stream(200)
    # A tiny fraction would give ~2 calls, but the floor is 30.
    random_tranche, _ = split_tranches(calls, random_fraction=0.01, absolute_floor=30)
    assert len(random_tranche) >= 30

    # With fewer calls than the floor, the tranche is all of them (cannot invent).
    few = _stream(12)
    rt, pt = split_tranches(few, random_fraction=0.5, absolute_floor=30)
    assert len(rt) == 12 and len(pt) == 0


def test_prioritized_tranche_excluded_from_rate():
    """A prioritized case entering the pool leaves the computed rate unchanged."""
    calls = _stream(400, miss_every=8)
    random_tranche, prioritized = split_tranches(
        calls, random_fraction=0.5, absolute_floor=20
    )
    before = compute_escape_rate(random_tranche)

    # A newly prioritized case — even a missed one — is not in the random tranche,
    # so the estimator cannot see it and the rate is unchanged.
    extra = AutoPassedCall("call-EXTRA", proposed_score=0.0,
                           has_grounded_finding=False, missed=True)
    prioritized2 = PrioritizedTranche(list(prioritized.calls) + [extra])
    after = compute_escape_rate(random_tranche)
    assert before == after
    assert extra not in random_tranche.calls


def test_partition_is_decorrelated_from_proposer_signal():
    """The random tranche is chosen independently of proposed_score.

    If selection tracked the proposer signal, the random tranche's mean score
    would differ systematically from the stream's — the bias D22 forbids.
    """
    calls = _stream(1000)
    random_tranche, _ = split_tranches(calls, random_fraction=0.5, absolute_floor=20)
    stream_mean = sum(c.proposed_score for c in calls) / len(calls)
    tranche_mean = sum(c.proposed_score for c in random_tranche.calls) / len(random_tranche)
    assert abs(stream_mean - tranche_mean) < 1.0, (
        "random tranche mean score tracks the stream — selection must not "
        "correlate with the proposer signal"
    )
