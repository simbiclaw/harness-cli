"""M5 acceptance test for hermes-action-tier-required lint."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

LINT_SCRIPT = Path(__file__).resolve().parent.parent / "hermes_action_tier_required.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "hermes_action_tier_required"


def test_explicit_tier_passes():
    fixture = FIXTURES / "passes" / "ok_explicit_tier.py"
    result = subprocess.run(
        [sys.executable, str(LINT_SCRIPT), str(fixture)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}\nstderr: {result.stderr}"
    )


def test_missing_tier_fails():
    fixture = FIXTURES / "fails" / "bad_no_tier.py"
    result = subprocess.run(
        [sys.executable, str(LINT_SCRIPT), str(fixture)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}"
    assert "without explicit 'tier'" in result.stderr
