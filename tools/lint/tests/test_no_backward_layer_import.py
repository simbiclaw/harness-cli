"""M3 acceptance tests for the no-backward-layer-import lint."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

LINT_SCRIPT = Path(__file__).resolve().parent.parent / "no_backward_layer_import.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "no_backward_layer_import"


def _run_lint(fixture_file: Path, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LINT_SCRIPT), "--root", str(root), str(fixture_file)],
        capture_output=True,
        text=True,
    )


def test_forward_import_passes():
    """Service → Types is forward (higher rank → lower rank), must pass."""
    root = FIXTURES / "passes"
    fixture = root / "argus" / "audio_intake" / "service" / "ok_forward.py"
    result = _run_lint(fixture, root)
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}\nstderr: {result.stderr}"
    )


def test_backward_import_fails():
    """Types → Service is backward (lower rank → higher rank), must fail."""
    root = FIXTURES / "fails"
    fixture = root / "argus" / "audio_intake" / "types" / "bad_backward.py"
    result = _run_lint(fixture, root)
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}"
    assert "backward layer import" in result.stderr
