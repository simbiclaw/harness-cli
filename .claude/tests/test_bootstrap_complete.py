"""Verify the bootstrap plan has been archived.

Asserts the bootstrap plan no longer lives under docs/plans/active/
and does live under docs/plans/completed/.

See docs/plans/active/0001-bootstrap-harness.md milestone M6.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACTIVE = REPO_ROOT / "docs" / "plans" / "active"
COMPLETED = REPO_ROOT / "docs" / "plans" / "completed"


def test_bootstrap_archived() -> None:
    active_path = ACTIVE / "0001-bootstrap-harness.md"
    completed_path = COMPLETED / "0001-bootstrap-harness.md"

    assert not active_path.exists(), (
        f"Bootstrap plan still active at {active_path}"
    )
    assert completed_path.exists(), (
        f"Bootstrap plan not found at {completed_path}"
    )
