"""Structural test: .pev-signals/ directory and state.json schema.

M0 of 9006-pev-tmux-convergence.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
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
    assert type(data["current_milestone"]) is int and data["current_milestone"] >= 0, (
        f"current_milestone must be a non-negative integer, got {data['current_milestone']!r}"
    )

    # milestones must be a dict mapping string keys to valid statuses
    assert isinstance(data["milestones"], dict), "milestones must be a dict"
    for key, value in data["milestones"].items():
        assert re.fullmatch(r"M\d+", key), f"milestone key must match M<digits>, got {key!r}"
        assert value in VALID_MILESTONE_STATUSES, (
            f"milestone status for {key} must be one of {VALID_MILESTONE_STATUSES}, got {value!r}"
        )

    assert len(data["milestones"]) > 0, "milestones must not be empty"

    # last_checkpoint_at must be an ISO-8601 string
    assert isinstance(data["last_checkpoint_at"], str) and data["last_checkpoint_at"], (
        "last_checkpoint_at must be a non-empty ISO-8601 string"
    )

    # agent_ids is optional but must be valid if present
    # (docs/conventions/pev-loop.md § The three agents)
    agent_ids = data.get("agent_ids")
    if agent_ids is not None:
        assert isinstance(agent_ids, dict), (
            "agent_ids must be a dict if present"
        )
        for aid_key in ("p_agent_id", "e_agent_id", "v_agent_id"):
            if aid_key in agent_ids:
                val = agent_ids[aid_key]
                assert val is None or isinstance(val, str), (
                    f"agent_ids.{aid_key} must be null or a string, "
                    f"got {type(val).__name__}"
                )
