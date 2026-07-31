"""Structural test: QUALITY_SCORE.md regrade schedule.

M0 of 9007-doc-garden-2026-07-31.

QUALITY_SCORE.md must have:
  - Last graded date within the last 14 days
  - Next regrade date in the future
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
QUALITY_SCORE = REPO_ROOT / "docs" / "QUALITY_SCORE.md"

LAST_GRADED_RE = re.compile(r"Last graded:\s*(\d{4}-\d{2}-\d{2})")
NEXT_REGRADE_RE = re.compile(r"Next regrade:\s*(\d{4}-\d{2}-\d{2})")


def test_quality_score_exists():
    assert QUALITY_SCORE.exists(), "QUALITY_SCORE.md must exist"


def test_has_last_graded_and_next_regrade():
    text = QUALITY_SCORE.read_text()
    assert LAST_GRADED_RE.search(text), (
        "QUALITY_SCORE.md missing 'Last graded: YYYY-MM-DD'"
    )
    assert NEXT_REGRADE_RE.search(text), (
        "QUALITY_SCORE.md missing 'Next regrade: YYYY-MM-DD'"
    )


def test_last_graded_is_recent():
    text = QUALITY_SCORE.read_text()
    m = LAST_GRADED_RE.search(text)
    assert m, "Missing Last graded date"
    last_graded = datetime.strptime(m.group(1), "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )
    days_ago = (datetime.now(timezone.utc) - last_graded).days
    assert days_ago <= 14, (
        f"Last graded is {days_ago} days ago (max 14). "
        f"Run the grader subagent or update the date."
    )


def test_next_regrade_is_future():
    text = QUALITY_SCORE.read_text()
    m = NEXT_REGRADE_RE.search(text)
    assert m, "Missing Next regrade date"
    next_regrade = datetime.strptime(m.group(1), "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )
    days_until = (next_regrade - datetime.now(timezone.utc)).days
    assert days_until >= 0, (
        f"Next regrade is {-days_until} days past due. "
        f"Update to a future date."
    )
