"""M3 acceptance tests for the parse-at-boundary lint."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

LINT_SCRIPT = Path(__file__).resolve().parent.parent / "parse_at_boundary.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "parse_at_boundary"


def _run(fixture_file: Path, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LINT_SCRIPT), "--root", str(root), str(fixture_file)],
        capture_output=True,
        text=True,
    )


def test_parsed_argument_passes():
    """Cross-domain call with pydantic model_validate must pass."""
    root = FIXTURES / "passes"
    fixture = root / "argus" / "audio_intake" / "service" / "ok_parsed.py"
    result = _run(fixture, root)
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}\nstderr: {result.stderr}"
    )


def test_raw_dict_argument_fails():
    """Cross-domain call with raw dict must fail."""
    root = FIXTURES / "fails"
    fixture = root / "argus" / "audio_intake" / "service" / "bad_raw_dict.py"
    result = _run(fixture, root)
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}"
    assert "unparsed cross-domain argument" in result.stderr
