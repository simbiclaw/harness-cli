"""Acceptance tests for 9010 M3 — divergence diagnostic into the §6 drift detector.

Divergence is |proposed_score − derived_score| per dimension per call,
aggregated over the same windows as κ — one drift clock, two instruments. It
enters the existing drift detector as an additional INPUT, not a separate
channel: there is exactly one demotion pathway (κ's), and divergence's only
effect is to raise a human-side calibration-injection flag. Per I8 it never
touches routing, coverage, auto-final rights, or any score()/adjust() input —
proven here structurally: the assessment type carries no such field.

Uses a provisional drift detector (9002 M5.5 is unstarted), clearly marked.

See docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation.md
"""

from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from argus.core.divergence import (
    DriftAssessment,
    assess_drift,
    per_call_divergence,
    window_divergence,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "src" / "argus" / "core" / "divergence.py"


def test_divergence_is_pure():
    """Same inputs produce byte-identical output across two calls."""
    proposed = {"procedural": 17.0, "empathy": 3.0}
    derived = {"procedural": 12.0, "empathy": 3.5}
    a = per_call_divergence(proposed, derived)
    b = per_call_divergence(proposed, derived)
    assert a == b == {"procedural": 5.0, "empathy": 0.5}

    windows = [{"procedural": 5.0}, {"procedural": 6.0}]
    assert window_divergence(windows) == window_divergence(windows)

    kappas = [0.9, 0.88, 0.87]
    divs = [1.0, 2.0, 3.0]
    assert assess_drift(kappas, divs, tau=0.8) == assess_drift(kappas, divs, tau=0.8)


def test_divergence_only_over_shared_dimensions():
    """A dimension present on one side only is skipped, not scored against zero."""
    d = per_call_divergence({"a": 5.0, "b": 1.0}, {"a": 2.0})
    assert d == {"a": 3.0}


def test_feeds_existing_detector_one_demotion_pathway():
    """Divergence is an input to the same detector; it opens no second demotion path.

    A widening divergence with healthy κ must NOT demote — demotion is κ's
    pathway alone. If divergence could demote, that is the forbidden second
    channel.
    """
    healthy_kappa = [0.9, 0.9, 0.9]
    widening_div = [1.0, 3.0, 6.0]
    a = assess_drift(healthy_kappa, widening_div, tau=0.8)
    assert a.demote is False, "widening divergence must not demote; κ is the only demoter"
    assert a.calibration_injection is True, "widening divergence must flag calibration"

    # κ falling below τ demotes — the one pathway — regardless of divergence.
    falling_kappa = [0.9, 0.82, 0.75]
    flat_div = [1.0, 1.0, 1.0]
    b = assess_drift(falling_kappa, flat_div, tau=0.8)
    assert b.demote is True
    assert b.calibration_injection is False


def test_widening_divergence_flags_calibration_only():
    """A widening series raises the calibration flag and touches no machine decision.

    Structural guarantee of I8: the assessment type exposes only demote,
    calibration_injection, and reason — no routing, coverage, or auto_final
    field exists for divergence to write.
    """
    a = assess_drift([0.9, 0.9, 0.9], [0.5, 2.0, 5.0], tau=0.8)
    assert a.calibration_injection is True
    assert a.demote is False

    field_names = {f.name for f in fields(DriftAssessment)}
    forbidden = {"routing", "coverage", "auto_final", "raw", "adjusted", "deduction", "severity"}
    assert not (field_names & forbidden), (
        f"DriftAssessment must not carry a disposer field (I8); found "
        f"{field_names & forbidden}"
    )
    assert field_names == {"demote", "calibration_injection", "reason"}


def test_core_no_model_client():
    """divergence ✗ model_client, ✗ clock, ✗ RNG — a pure drift instrument."""
    tree = ast.parse(MODULE.read_text(), filename=str(MODULE))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
    forbidden_roots = {"anthropic", "llama_cpp", "random", "time", "datetime", "secrets"}
    offenders = [m for m in imported if m.split(".")[0] in forbidden_roots]
    assert not offenders, f"divergence must be pure; forbidden imports: {offenders}"
