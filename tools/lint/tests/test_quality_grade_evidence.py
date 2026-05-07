"""M2 acceptance test for the quality-grade-evidence lint."""

import subprocess
import sys
from pathlib import Path

LINT_SCRIPT = Path(__file__).resolve().parent.parent / "quality_grade_evidence.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "quality_grade_evidence"


def test_ungrounded_grade_change_fails():
    """A non-F grade without parenthetical evidence should fail the lint."""
    fixture = FIXTURES / "ungraded.md"
    result = subprocess.run(
        [sys.executable, str(LINT_SCRIPT), str(fixture)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}"
    assert "grade 'A'" in result.stderr
    assert "without inline evidence" in result.stderr


def test_all_f_grades_passes():
    """The real QUALITY_SCORE.md at bootstrap (all F) should pass."""
    result = subprocess.run(
        [sys.executable, str(LINT_SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}\nstderr: {result.stderr}"
    )
