"""Structural test: PEV loop closure — no milestone advances before
the prior milestone's PEV loop is closed (CONFIRMED).

Promoted from documentation (pev-loop.md) to structural test.
See docs/conventions/pev-loop.md § Loop boundaries.

Invariant: milestones progress sequentially through the PEV loop.
You cannot start M(N+1) until M(N) reaches confirmed. Violations
are gaps, parallel active milestones, or confirmed-after-pending.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_FILE = REPO_ROOT / ".pev-signals" / "state.json"

# Status ordering for sequential-progress invariant
STATUS_ORDER = {
    "pending": 0,
    "in_progress": 1,
    "pending_verdict": 2,
    "confirmed": 3,
}

ACTIVE_STATUSES = {"in_progress", "pending_verdict"}


def _parse_milestone_number(key: str) -> int:
    """Extract integer from milestone key like 'M3'."""
    return int(key.lstrip("M"))


def _load_state():
    """Load and return the parsed state.json, or None if absent."""
    if not STATE_FILE.exists():
        return None
    return json.loads(STATE_FILE.read_text())


def test_no_gaps_in_confirmed_prefix():
    """Confirmed milestones must form a contiguous prefix starting at M0.

    If M2 is confirmed but M1 is pending, that's a gap — M1's PEV loop
    was never closed but M2 advanced anyway.
    """
    state = _load_state()
    if state is None:
        return  # No state file — nothing to check

    milestones = state.get("milestones", {})
    if not milestones:
        return

    sorted_keys = sorted(milestones.keys(), key=_parse_milestone_number)

    seen_non_confirmed = False
    violations: list[str] = []

    for key in sorted_keys:
        status = milestones[key]
        if status == "confirmed":
            if seen_non_confirmed:
                violations.append(
                    f"{key} is confirmed but an earlier milestone "
                    f"is not confirmed (gap in confirmed prefix)"
                )
        else:
            seen_non_confirmed = True

    assert not violations, (
        "PEV loop closure violation — gaps in confirmed prefix:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


def test_at_most_one_active_milestone():
    """At most one milestone may be in_progress or pending_verdict.

    Two active milestones means the PEV loop for the first one was not
    closed before the second one began — a loop closure violation.
    """
    state = _load_state()
    if state is None:
        return

    milestones = state.get("milestones", {})
    if not milestones:
        return

    active = [
        key for key, status in milestones.items() if status in ACTIVE_STATUSES
    ]

    assert len(active) <= 1, (
        f"PEV loop closure violation — {len(active)} active milestones "
        f"(at most 1 allowed): {', '.join(active)}. "
        f"The first active milestone's PEV loop must close (CONFIRMED) "
        f"before the next milestone enters Plan phase."
    )


def test_active_milestone_follows_confirmed_prefix():
    """An active milestone must immediately follow the confirmed prefix.

    If M0 is confirmed but M2 is in_progress (with M1 pending), M2
    jumped ahead — M1's loop was skipped, or M2 started prematurely.
    """
    state = _load_state()
    if state is None:
        return

    milestones = state.get("milestones", {})
    if not milestones:
        return

    sorted_keys = sorted(milestones.keys(), key=_parse_milestone_number)

    active_key = None
    for key in sorted_keys:
        if milestones[key] in ACTIVE_STATUSES:
            active_key = key
            break

    if active_key is None:
        return  # No active milestone — nothing to check

    active_num = _parse_milestone_number(active_key)

    for key in sorted_keys:
        num = _parse_milestone_number(key)
        if num < active_num:
            assert milestones[key] == "confirmed", (
                f"PEV loop closure violation — {active_key} is active "
                f"but earlier milestone {key} is {milestones[key]!r}, "
                f"not confirmed. All milestones before an active "
                f"milestone must be confirmed."
            )
        elif num > active_num:
            assert milestones[key] == "pending", (
                f"PEV loop closure violation — {active_key} is active "
                f"but later milestone {key} is {milestones[key]!r}, "
                f"not pending. No milestone can start after the active "
                f"one until the active loop closes."
            )


def test_loop_closure_documented():
    """The loop closure rule must be documented in pev-loop.md.

    This ensures the structural test and the documentation stay in sync.
    If the documentation is removed, this test fails as a reminder that
    the structural test is enforcing a rule whose rationale must remain
    discoverable.
    """
    pev_loop_md = REPO_ROOT / "docs" / "conventions" / "pev-loop.md"
    assert pev_loop_md.exists(), "pev-loop.md must exist"

    text = pev_loop_md.read_text()

    # The documentation must contain the loop-closure concept
    assert "A milestone may take multiple PEV iterations to converge" in text, (
        "pev-loop.md must document the multi-iteration convergence rule"
    )
    assert "return to Plan with B's findings as input" in text, (
        "pev-loop.md must document that REJECTED restarts the loop"
    )
