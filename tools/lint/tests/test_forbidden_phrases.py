"""M2 acceptance tests for the forbidden-phrases lint."""

import subprocess
import sys
from pathlib import Path

LINT_SCRIPT = Path(__file__).resolve().parent.parent / "forbidden_phrases.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "forbidden_phrases"


def _run_lint(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LINT_SCRIPT), str(path)],
        capture_output=True,
        text=True,
    )


def test_phrase_without_citation_fails():
    fixture = FIXTURES / "fails" / "ungrounded.md"
    result = _run_lint(fixture)
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}"
    assert "forbidden phrase" in result.stderr


def test_phrase_with_citation_passes():
    fixture = FIXTURES / "passes" / "cited.md"
    result = _run_lint(fixture)
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}\nstderr: {result.stderr}"
    )
