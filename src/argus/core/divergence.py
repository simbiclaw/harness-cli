"""Divergence diagnostic (9010 M3, core, pure).

`|proposed_score − derived_score|` per dimension per call, aggregated over the
same windows as κ — one drift clock, two instruments (D20). Divergence enters
the existing §6 drift detector as an additional INPUT, not a separate channel:
there is exactly one demotion pathway, and it is κ's. Divergence's only effect
is to raise a human-side calibration-injection flag (schedule manifest
minting); per I8 it touches no routing, coverage, auto-final right, or
score()/adjust() input. That prohibition is enforced structurally here — the
`DriftAssessment` type carries no disposer field for divergence to write.

This is the one place a logit-derived quantity (the proposed_score) is read at
all; M5's I8 fixture proves it is the only one.

Purity: no model client, no clock, no RNG. Same inputs, byte-identical output.

Provisional: 9002 M5.5 lands the real §6 drift detector and CriterionHealth.
`assess_drift` here is a minimal stand-in that models the single property M3
must guarantee — divergence is an input that flags, never a second demoter.
9002 replaces it; the divergence math (`per_call_divergence`,
`window_divergence`, `divergence_trend`) is the durable part.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DriftAssessment:
    """The drift detector's verdict for one criterion over its windows.

    Deliberately only three fields. `demote` is the single demotion pathway,
    driven by κ. `calibration_injection` is the human-side flag a widening
    divergence raises. There is no routing, coverage, or auto_final field —
    divergence has nothing here it could use to touch a disposer decision (I8).
    """

    demote: bool
    calibration_injection: bool
    reason: str


def per_call_divergence(
    proposed: dict[str, float], derived: dict[str, float]
) -> dict[str, float]:
    """`|proposed − derived|` per dimension, over dimensions present on both sides.

    A dimension present on only one side is skipped, never diffed against a
    fabricated zero — an absent comparison is honest.
    """
    return {
        dim: abs(proposed[dim] - derived[dim])
        for dim in proposed
        if dim in derived
    }


def window_divergence(per_call: list[dict[str, float]]) -> dict[str, float]:
    """Mean divergence per dimension over a window of calls — κ's windowing."""
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for call in per_call:
        for dim, value in call.items():
            totals[dim] = totals.get(dim, 0.0) + value
            counts[dim] = counts.get(dim, 0) + 1
    return {dim: totals[dim] / counts[dim] for dim in totals}


def divergence_trend(window_values: list[float]) -> str:
    """"widening", "narrowing", or "flat" across successive windows.

    Compares the last window against the first; equal endpoints (or fewer than
    two windows) read as flat. Deterministic — no tolerance band beyond exact
    comparison, so the result is byte-stable on replay.
    """
    if len(window_values) < 2:
        return "flat"
    first, last = window_values[0], window_values[-1]
    if last > first:
        return "widening"
    if last < first:
        return "narrowing"
    return "flat"


def assess_drift(
    kappa_windows: list[float], divergence_windows: list[float], tau: float
) -> DriftAssessment:
    """Combine the two instruments into one assessment (provisional detector).

    κ is the ONLY demoter: a most-recent κ below τ demotes the criterion. A
    widening divergence raises the calibration-injection flag and nothing else —
    it never sets `demote`, so it opens no second demotion pathway. Both
    instruments share this one detector; that is "one drift clock, two
    instruments".
    """
    demote = bool(kappa_windows) and kappa_windows[-1] < tau
    calibration_injection = divergence_trend(divergence_windows) == "widening"

    if demote and calibration_injection:
        reason = "kappa_below_tau; divergence_widening"
    elif demote:
        reason = "kappa_below_tau"
    elif calibration_injection:
        reason = "divergence_widening"
    else:
        reason = "stable"

    return DriftAssessment(
        demote=demote,
        calibration_injection=calibration_injection,
        reason=reason,
    )
