"""Structural test: .pev-signals/ directory and state.json schema.

M0 of 9006-pev-tmux-convergence.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SIGNAL_DIR = REPO_ROOT / ".pev-signals"
STATE_FILE = SIGNAL_DIR / "state.json"

REQUIRED_STATE_FIELDS = {
    "plan_id",
    "phase",
    "current_milestone",
    "milestones",
    "last_checkpoint_at",
}

VALID_PHASES = {"plan", "execute", "verify", "repair", "complete"}
VALID_MILESTONE_STATUSES = {"pending", "in_progress", "pending_verdict", "confirmed"}


def test_signal_dir_exists():
    """M0: .pev-signals/ directory must exist with a .gitkeep file."""
    assert SIGNAL_DIR.exists(), f"{SIGNAL_DIR} must exist"
    assert SIGNAL_DIR.is_dir(), f"{SIGNAL_DIR} must be a directory"

    gitkeep = SIGNAL_DIR / ".gitkeep"
    assert gitkeep.exists(), f"{gitkeep} must exist to keep the directory in git"


def test_state_schema_validates():
    """M0: state.json must have all required fields with valid values."""
    assert STATE_FILE.exists(), (
        f"{STATE_FILE} must exist. Create a valid fixture at .pev-signals/state.json."
    )

    data = json.loads(STATE_FILE.read_text())

    # Required top-level fields
    missing = REQUIRED_STATE_FIELDS - set(data.keys())
    assert not missing, f"state.json missing required fields: {missing}"

    # plan_id must be a non-empty string
    assert isinstance(data["plan_id"], str) and data["plan_id"], (
        "plan_id must be a non-empty string"
    )

    # phase must be one of the valid phases
    assert data["phase"] in VALID_PHASES, (
        f"phase must be one of {VALID_PHASES}, got {data['phase']!r}"
    )

    # current_milestone must be a positive integer
    assert isinstance(data["current_milestone"], int) and data["current_milestone"] >= 0, (
        f"current_milestone must be a non-negative integer, got {data['current_milestone']!r}"
    )

    # milestones must be a dict mapping string keys to valid statuses
    assert isinstance(data["milestones"], dict), "milestones must be a dict"
    for key, value in data["milestones"].items():
        assert key.startswith("M"), f"milestone key must start with 'M', got {key!r}"
        assert value in VALID_MILESTONE_STATUSES, (
            f"milestone status for {key} must be one of {VALID_MILESTONE_STATUSES}, got {value!r}"
        )

    # last_checkpoint_at must be an ISO-8601 string
    assert isinstance(data["last_checkpoint_at"], str) and data["last_checkpoint_at"], (
        "last_checkpoint_at must be a non-empty ISO-8601 string"
    )
