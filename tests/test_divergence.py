"""Acceptance tests for 9020 M3 — divergence diagnostic into the §6 drift detector.

Divergence is |proposed_score − derived_score| per dimension per call,
aggregated over the same windows as κ — one drift clock, two instruments. It
enters the existing drift detector as an additional INPUT, not a separate
channel: there is exactly one demotion pathway (κ's), and divergence's only
effect is to raise a human-side calibration-injection flag. Per I8 it never
touches routing, coverage, auto-final rights, or any score()/adjust() input —
proven here structurally: the assessment type carries no such field.

Uses a provisional drift detector (9002 M5.5 is unstarted), clearly marked.

See docs/exec-plans/active/9020-continuous-proposer-and-provenance-separation.md
"""

from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

import pytest

from argus.core.divergence import (
    DriftAssessment,
    assess_drift,
    divergence_trend,
    per_call_divergence,
    probe_divergence,
    window_divergence,
)
from argus.types.pipeline import RubricCategory

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


# ── 9021 M20: the probe must be able to fail ────────────────────────────────
#
# M20 repurposes 9020's proposer as an *observable* drift probe. The two sides
# of the comparison do not speak the same language:
#
#   proposed — keys are the proposer's own dimension strings
#              (`ProposerCall.dimensions`, src/argus/io/local_proposer.py:103),
#              values are an index on the ORDERED letter scale, in [0, k-1]
#              where k = `g_used` (src/argus/io/logprob_scoring.py:25-45).
#   derived  — keys are the five `RubricCategory` values
#              (src/argus/types/pipeline.py:83-90), the number is a percentage
#              (`QAReport.overall_score`, src/argus/types/pipeline.py:326).
#
# Both mismatches are silent in the shipped 9020 code, and silence here is the
# worst possible failure mode: a monitor that cannot fail is trusted.


def test_disjoint_keys_raise():
    """Incomparable key vocabularies fail loudly instead of reporting stability.

    With a silent skip, a disjoint pair produces `{}`. The chain below is why
    that single empty dict is fatal rather than merely empty: it windows to
    `{}`, whose series trends "flat", which clears `calibration_injection` —
    for every window, forever, by construction. The probe would report a stable
    proposer without ever having compared one number to another.
    """
    # Real key vocabularies from both sides, not invented ones.
    proposed = {"empathy": 3.2, "procedural": 1.0}
    derived = {
        RubricCategory.ATTITUDE.value: 87.5,
        RubricCategory.PROCESS.value: 92.0,
    }
    assert not (proposed.keys() & derived.keys()), "fixture must be disjoint"

    with pytest.raises(ValueError, match="no shared dimension"):
        per_call_divergence(proposed, derived)

    # Nothing at all on either side is the same failure, not a quiet success.
    with pytest.raises(ValueError, match="no shared dimension"):
        per_call_divergence({}, {})

    # The stability-forever chain the raise removes, in the real functions.
    assert window_divergence([{}, {}, {}]) == {}
    assert divergence_trend([]) == "flat"
    assert assess_drift([0.9, 0.9, 0.9], [], tau=0.8).calibration_injection is False

    # A partial overlap is still a comparison, and stays one (9020's rule,
    # asserted by test_divergence_only_over_shared_dimensions above).
    assert per_call_divergence({"a": 5.0, "b": 1.0}, {"a": 2.0}) == {"a": 3.0}


def test_units_are_comparable():
    """Unifying keys is not enough — the two sides are on different scales.

    `abs(3.2 - 87.5)` over a shared key is well-formed and meaningless: an
    ordinal scale index differenced against a percentage. `probe_divergence` is
    the probe's entry point and both scale tops are keyword-only with no
    default, so a caller cannot enter the probe without declaring what its
    numbers mean.
    """
    dim = RubricCategory.ATTITUDE.value
    ordinal = {dim: 3.2}      # g_used = 5 letters -> the axis top is 4.0
    percentage = {dim: 87.5}

    # The raw difference the unfixed probe would have reported.
    assert per_call_divergence(ordinal, percentage) == {dim: abs(3.2 - 87.5)}

    # Declaring no scale is impossible, not merely discouraged.
    with pytest.raises(TypeError):
        probe_divergence(ordinal, percentage)

    d = probe_divergence(ordinal, percentage, proposed_upper=4.0, derived_upper=100.0)
    assert d == {dim: abs(3.2 / 4.0 - 87.5 / 100.0)}
    assert 0.0 <= d[dim] <= 1.0, "both sides land on the common [0, 1] axis"

    # A number that is not on the scale it was declared to be on is an
    # incomparable input too: 87.5 cannot be an index into a 5-letter scale.
    with pytest.raises(ValueError, match="outside its declared scale"):
        probe_divergence(percentage, percentage, proposed_upper=4.0, derived_upper=100.0)

    # g_used == 1 leaves no score axis at all; dividing by zero width would
    # otherwise raise ZeroDivisionError or fabricate a ratio.
    with pytest.raises(ValueError, match="degenerate scale"):
        probe_divergence({dim: 0.0}, percentage, proposed_upper=0.0, derived_upper=100.0)

    # The key check is not bypassed by going through the entry point.
    with pytest.raises(ValueError, match="no shared dimension"):
        probe_divergence(
            {"empathy": 3.2}, percentage, proposed_upper=4.0, derived_upper=100.0
        )
