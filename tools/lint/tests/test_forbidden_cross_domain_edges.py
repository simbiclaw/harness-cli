"""M3 acceptance tests for the forbidden-cross-domain-edges lint."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

LINT_SCRIPT = Path(__file__).resolve().parent.parent / "forbidden_cross_domain_edges.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "forbidden_cross_domain_edges"


def _run(fixture_file: Path, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LINT_SCRIPT), "--root", str(root), str(fixture_file)],
        capture_output=True,
        text=True,
    )


def test_allowed_edge_passes():
    root = FIXTURES / "passes"
    fixture = root / "argus" / "calibration" / "service" / "allowed_edge.py"
    result = _run(fixture, root)
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}\nstderr: {result.stderr}"
    )


def test_none_edge_fails():
    root = FIXTURES / "fails"
    fixture = root / "argus" / "audio_intake" / "service" / "forbidden_edge.py"
    result = _run(fixture, root)
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}"
    assert "forbidden cross-domain edge" in result.stderr
