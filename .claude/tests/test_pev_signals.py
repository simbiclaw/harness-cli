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


def test_state_json_consistent_with_plan():
    """state.json milestone statuses must match plan file checkboxes.

    If a plan has M<N> checked ([x]), state.json must show it as
    'confirmed'. If state.json shows 'confirmed' but the plan has [ ],
    the checkbox was never flipped. Either direction is a sync gap.

    This prevents the M7 edge case where V found state.json showing
    M0=confirmed, M1-M7=pending while the plan had all 8 checked.
    """
    data = json.loads(STATE_FILE.read_text())
    milestones = data.get("milestones", {})
    plan_id = data.get("plan_id", "")

    # Find the active plan file
    active_dir = REPO_ROOT / "docs" / "exec-plans" / "active"
    plan_file = active_dir / f"{plan_id}.md"
    if not plan_file.exists():
        # Plan might be in completed or archived
        for d in ("completed", "archived"):
            alt = REPO_ROOT / "docs" / "exec-plans" / d / f"{plan_id}.md"
            if alt.exists():
                plan_file = alt
                break
        if not plan_file.exists():
            return  # Plan file not found — can't verify consistency

    plan_text = plan_file.read_text()

    checked_re = re.compile(r"^- \[x\] M(\d+)", re.MULTILINE)
    unchecked_re = re.compile(r"^- \[ \] M(\d+)", re.MULTILINE)

    checked_in_plan = {f"M{m.group(1)}" for m in checked_re.finditer(plan_text)}
    unchecked_in_plan = {f"M{m.group(1)}" for m in unchecked_re.finditer(plan_text)}

    failures: list[str] = []

    for key in checked_in_plan:
        status = milestones.get(key)
        if status != "confirmed":
            failures.append(
                f"{key}: checked [x] in plan but state.json shows "
                f"'{status}' (expected 'confirmed'). Arbiter must "
                f"update state.json after each GREEN commit."
            )

    for key in unchecked_in_plan:
        status = milestones.get(key)
        if status == "confirmed":
            failures.append(
                f"{key}: unchecked [ ] in plan but state.json shows "
                f"'confirmed'. Either the checkbox was flipped without "
                f"committing, or state.json was not reset."
            )

    assert not failures, (
        "State/plan consistency violations — state.json must match "
        "plan file checkbox state:\n" + "\n".join(f"  - {f}" for f in failures)
    )
