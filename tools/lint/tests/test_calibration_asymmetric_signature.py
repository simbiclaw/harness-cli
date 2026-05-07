"""M4 acceptance test for calibration-asymmetric-signature lint."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

LINT_SCRIPT = Path(__file__).resolve().parent.parent / "calibration_asymmetric_signature.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "calibration_asymmetric_signature"


def test_asymmetric_calibrate_passes():
    fixture = FIXTURES / "passes" / "ok_asymmetric.py"
    result = subprocess.run(
        [sys.executable, str(LINT_SCRIPT), str(fixture)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}\nstderr: {result.stderr}"
    )


def test_symmetric_reconcile_fails():
    fixture = FIXTURES / "fails" / "bad_symmetric.py"
    result = subprocess.run(
        [sys.executable, str(LINT_SCRIPT), str(fixture)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}"
    assert "symmetric" in result.stderr
