"""M3 acceptance tests for the external-imports-only-in-providers lint."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

LINT_SCRIPT = Path(__file__).resolve().parent.parent / "external_imports_only_in_providers.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "external_imports_only_in_providers"


def _run(fixture_file: Path, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LINT_SCRIPT), "--root", str(root), str(fixture_file)],
        capture_output=True,
        text=True,
    )


def test_providers_external_passes():
    """External import in providers domain must pass."""
    root = FIXTURES / "passes"
    fixture = root / "argus" / "providers" / "ok_external.py"
    result = _run(fixture, root)
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}\nstderr: {result.stderr}"
    )


def test_non_providers_external_fails():
    """External import outside providers domain must fail."""
    root = FIXTURES / "fails"
    fixture = root / "argus" / "argus" / "service" / "bad_external.py"
    result = _run(fixture, root)
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}"
    assert "external import outside providers" in result.stderr
