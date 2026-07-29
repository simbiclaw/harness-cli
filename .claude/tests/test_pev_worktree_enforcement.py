"""Structural test: Worktree isolation enforcement + Tier C rollback.

Improvement #6 from the 2026-07-30 PEV harness evaluation:
  Worktree isolation is documentation-only — agents may or may not
  use /tmp/impl-<sha>/ during Execute. This test checks that
  active milestones have a recorded worktree_path in state.json.

Improvement #7 from the 2026-07-30 PEV harness evaluation:
  When a Tier C question is parked in Awaiting Steering, there's no
  automated mechanism to revert commits made before the escalation.
  This test checks that Awaiting Steering entries record a
  pre_steering_sha for potential rollback.

Schema extensions to state.json:
  {
    "plan_id": "...",
    "phase": "execute",
    "current_milestone": 0,
    "milestones": {
      "M0": {
        "status": "in_progress",
        "worktree_path": "/tmp/impl-abc123/"
      }
    },
    "pre_steering_sha": null
  }

Schema extensions to Awaiting Steering entries:
  **Q<n>: <question>** — Deadline: YYYY-MM-DD. pre_steering_sha: <sha>. <status>.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_FILE = REPO_ROOT / ".pev-signals" / "state.json"
ACTIVE_DIR = REPO_ROOT / "docs" / "exec-plans" / "active"

# Active milestone statuses that imply implementation is in progress
ACTIVE_IMPL_STATUSES = {"in_progress", "pending_verdict"}

# Awaiting Steering patterns
AWAITING_SECTION_RE = re.compile(
    r"## \d+\.\s*Awaiting Steering\s*\n(.*?)(?=\n## \d+\.|\Z)",
    re.DOTALL,
)
PRE_STEERING_SHA_RE = re.compile(
    r"pre_steering_sha:\s*([a-f0-9]{7,40})",
    re.IGNORECASE,
)
STEERING_RESOLVED_RE = re.compile(
    r"(?:resolved|none\b)",
    re.IGNORECASE,
)


def _status_for(milestone_value) -> str:
    if isinstance(milestone_value, dict):
        return milestone_value.get("status", "pending")
    return milestone_value


def _worktree_for(milestone_value) -> str | None:
    if isinstance(milestone_value, dict):
        return milestone_value.get("worktree_path")
    return None


def _load_state():
    if not STATE_FILE.exists():
        return None
    return json.loads(STATE_FILE.read_text())


# ── Improvement #6: Worktree enforcement ──────────────────────────────────

def test_active_milestones_have_worktree():
    """Milestones in {in_progress, pending_verdict} should record a
    worktree_path in state.json, proving isolation was used.

    Only checks milestones using the extended dict form.
    Simple string form ("M0": "pending") is grandfathered until the
    arbiter is updated to write the new schema.
    """
    state = _load_state()
    if state is None:
        return

    milestones = state.get("milestones", {})
    failures: list[str] = []

    for key, value in milestones.items():
        # Skip milestones using the simple string form
        if not isinstance(value, dict):
            continue

        status = _status_for(value)
        if status not in ACTIVE_IMPL_STATUSES:
            continue

        worktree = _worktree_for(value)
        if not worktree:
            failures.append(
                f"{key}: status is '{status}' but no worktree_path "
                f"recorded — agent may not be using worktree isolation"
            )

    assert not failures, (
        "Worktree isolation violations — active milestones without "
        "recorded worktree_path:\n" + "\n".join(f"  - {f}" for f in failures)
    )


def test_state_json_has_worktree_field():
    """state.json schema should support worktree_path at the top level
    (for the current active implementation) and per-milestone.
    """
    state = _load_state()
    if state is None:
        return

    top_worktree = state.get("worktree_path")
    if top_worktree is not None:
        assert isinstance(top_worktree, str), (
            "Top-level worktree_path must be a string if present"
        )


# ── Improvement #7: Tier C rollback ───────────────────────────────────────

def test_steering_entries_have_pre_steering_sha():
    """Awaiting Steering entries should record a pre_steering_sha
    for potential rollback if the Tier C decision is rejected.

    An entry without a pre_steering_sha can't be rolled back —
    the agent can't determine which commits to revert.
    """
    if not ACTIVE_DIR.exists():
        return

    failures: list[str] = []

    for plan_path in sorted(ACTIVE_DIR.glob("*.md")):
        text = plan_path.read_text()
        rel = plan_path.relative_to(REPO_ROOT)

        section_match = AWAITING_SECTION_RE.search(text)
        if not section_match:
            continue

        section_body = section_match.group(1).strip()

        # Skip empty/None sections
        if not section_body or section_body.lower().startswith("*none"):
            continue

        # Check if section has unresolved entries
        if STEERING_RESOLVED_RE.search(section_body.lower()):
            continue  # All resolved — no rollback needed

        # Unresolved entries should have a pre_steering_sha
        if not PRE_STEERING_SHA_RE.search(section_body):
            failures.append(
                f"{rel}: Awaiting Steering has unresolved entries "
                f"but no pre_steering_sha recorded. Add "
                f"'pre_steering_sha: <sha>' to enable rollback if "
                f"the Tier C decision is rejected."
            )

    assert not failures, (
        "Tier C rollback violations — unresolved Awaiting Steering "
        "entries without pre_steering_sha:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )
