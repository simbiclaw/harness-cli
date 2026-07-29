"""Structural test: Feedback consumption and iteration cap enforcement.

Improvement #2 (feedback consumption) from the 2026-07-30 PEV harness evaluation:
  A REJECTED verdict must be consumed (notes_consumed_at) before the
  next milestone advances past Plan phase. Writing the notes file is
  not enough — the arbiter must read and act on it.

Improvement #3 (iteration cap):
  pev-loop.md says "split if >3 iterations." This test enforces that cap.
  Milestones exceeding 3 iterations without an iteration_waiver fail.

Schema: milestones in state.json support optional iteration tracking.

  Simple form (backward-compatible):
    "M0": "pending"

  Extended form (with iteration tracking):
    "M0": {
      "status": "pending_verdict",
      "iterations": [
        {
          "verdict": "REJECTED",
          "verdict_at": "2026-07-30T10:00:00Z",
          "notes_consumed_at": "2026-07-30T10:05:00Z"
        },
        {
          "verdict": "CONFIRMED",
          "verdict_at": "2026-07-30T11:00:00Z",
          "notes_consumed_at": "2026-07-30T11:05:00Z"
        }
      ]
    }

  Milestones with >3 iterations may add:
    "iteration_waiver": true
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_FILE = REPO_ROOT / ".pev-signals" / "state.json"
MAX_ITERATIONS = 3


def _parse_milestone_number(key: str) -> int:
    return int(key.lstrip("M"))


def _iterations_for(milestone_value) -> list[dict]:
    """Extract iterations list from a milestone value.

    Supports both simple (string) and extended (dict) forms.
    """
    if isinstance(milestone_value, dict):
        return milestone_value.get("iterations", [])
    return []


def _status_for(milestone_value) -> str:
    """Extract status from a milestone value."""
    if isinstance(milestone_value, dict):
        return milestone_value.get("status", "pending")
    return milestone_value


def _load_state():
    if not STATE_FILE.exists():
        return None
    return json.loads(STATE_FILE.read_text())


# ── Improvement #2: Feedback consumption ──────────────────────────────────

def test_rejected_verdicts_must_be_consumed():
    """Every REJECTED verdict in a milestone's iterations must have
    notes_consumed_at — proving the arbiter read the feedback before
    the next iteration began.
    """
    state = _load_state()
    if state is None:
        return

    milestones = state.get("milestones", {})
    failures: list[str] = []

    for key, value in milestones.items():
        iterations = _iterations_for(value)
        for i, iteration in enumerate(iterations):
            if iteration.get("verdict") == "REJECTED":
                if not iteration.get("notes_consumed_at"):
                    failures.append(
                        f"{key} iteration {i}: REJECTED but no "
                        f"notes_consumed_at — feedback was written but "
                        f"may not have been consumed by the arbiter"
                    )

    assert not failures, (
        "Feedback consumption violations — REJECTED verdicts without "
        "consumed_at timestamps:\n" + "\n".join(f"  - {f}" for f in failures)
    )


def test_consumption_precedes_next_milestone():
    """When a milestone has REJECTED iterations, the last consumed_at
    must precede the next milestone entering Plan phase.

    If M0's last rejected feedback was consumed at T1, but M1 entered
    in_progress at T0 (earlier), the feedback wasn't consumed before
    the next milestone advanced — a loop closure violation.
    """
    state = _load_state()
    if state is None:
        return

    milestones = state.get("milestones", {})
    if not milestones:
        return

    sorted_keys = sorted(milestones.keys(), key=_parse_milestone_number)
    failures: list[str] = []

    for i in range(len(sorted_keys) - 1):
        current_key = sorted_keys[i]
        next_key = sorted_keys[i + 1]

        current_val = milestones[current_key]
        next_val = milestones[next_key]

        iterations = _iterations_for(current_val)

        # Find the last REJECTED verdict that was consumed
        last_rejected_consumed = None
        for iteration in reversed(iterations):
            if iteration.get("verdict") == "REJECTED":
                consumed = iteration.get("notes_consumed_at")
                if consumed:
                    last_rejected_consumed = consumed
                    break

        if last_rejected_consumed is None:
            continue  # No rejected+consumed iteration — nothing to check

        # Check next milestone's first in_progress timestamp
        next_iterations = _iterations_for(next_val)
        if next_iterations:
            first_progress = next_iterations[0].get("verdict_at")
            if first_progress and first_progress < last_rejected_consumed:
                failures.append(
                    f"{next_key} first activity at {first_progress} "
                    f"precedes {current_key} last rejected feedback consumed "
                    f"at {last_rejected_consumed} — consumption happened "
                    f"after the next milestone already advanced"
                )

    assert not failures, (
        "Feedback consumption ordering violations:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )


# ── Improvement #3: Iteration cap ─────────────────────────────────────────

def test_iteration_cap_enforced():
    """No milestone may exceed 3 PEV iterations without an iteration_waiver.

    pev-loop.md § When this rubric is wrong:
      "If a milestone consistently takes more than 3 PEV iterations
       to converge, the milestone is likely too large — split it."
    """
    state = _load_state()
    if state is None:
        return

    milestones = state.get("milestones", {})
    failures: list[str] = []

    for key, value in milestones.items():
        iterations = _iterations_for(value)
        if len(iterations) <= MAX_ITERATIONS:
            continue

        # Check for waiver
        if isinstance(value, dict) and value.get("iteration_waiver"):
            continue

        # Count REJECTED vs CONFIRMED
        rejected = sum(
            1 for it in iterations if it.get("verdict") == "REJECTED"
        )
        confirmed = sum(
            1 for it in iterations if it.get("verdict") == "CONFIRMED"
        )

        failures.append(
            f"{key}: {len(iterations)} iterations "
            f"({rejected} REJECTED, {confirmed} CONFIRMED) "
            f"— exceeds cap of {MAX_ITERATIONS}. "
            f"Split this milestone or add iteration_waiver: true "
            f"with a Decision Log entry explaining why."
        )

    assert not failures, (
        f"Iteration cap violations — milestones exceeding "
        f"{MAX_ITERATIONS} PEV iterations:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )


def test_last_iteration_must_be_confirmed():
    """If a milestone has iterations, the last one must be CONFIRMED
    if the milestone status is 'confirmed'.

    A milestone with status 'confirmed' but whose last iteration is
    REJECTED signals a state inconsistency.
    """
    state = _load_state()
    if state is None:
        return

    milestones = state.get("milestones", {})
    failures: list[str] = []

    for key, value in milestones.items():
        status = _status_for(value)
        iterations = _iterations_for(value)

        if status == "confirmed" and iterations:
            last = iterations[-1]
            if last.get("verdict") != "CONFIRMED":
                failures.append(
                    f"{key}: status is 'confirmed' but last iteration "
                    f"verdict is {last.get('verdict')!r} — "
                    f"expected CONFIRMED"
                )

    assert not failures, (
        "State consistency violations — confirmed milestones with "
        "non-CONFIRMED last iteration:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )
