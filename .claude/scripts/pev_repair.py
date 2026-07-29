"""DEPRECATED — Replaced by pev_tmux_adversarial.sh (plan 9006).

This Python repair library is superseded by the tmux arbiter architecture
defined in docs/exec-plans/active/9006-pev-tmux-convergence.md. Hardcoded
if/else failure classification is replaced by Claude reasoning in the
arbiter session.

This file is kept as a reference implementation for the failure classification
taxonomy. It will be moved to .claude/scripts/archived/ at M7.

Do not use for new ExecPlans. Use pev_tmux_adversarial.sh instead.

--- Original docstring below ---

Autonomous repair loop for PEV REJECTED verdicts.

On REJECTED from subagent B: reads the milestone's implementation notes,
classifies the failure, and decides the next action.

Failure classes:
- mechanical → auto-repair (fix test, adjust assertion, retry)
- semantic → needs-human-judgment → add human-todo entry, pause milestone
- constraint-violation → auto-repair + update milestone constraints

See docs/conventions/implementation-notes.md and docs/conventions/pev-loop.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACTIVE_DIR = REPO_ROOT / "docs" / "exec-plans" / "active"


class FailureClass(Enum):
    MECHANICAL = "mechanical"
    SEMANTIC = "semantic"
    CONSTRAINT_VIOLATION = "constraint-violation"


class Action(Enum):
    RETRY = "retry"
    HUMAN_TODO = "human-todo"
    UPDATE_CONSTRAINTS = "update-constraints"


@dataclass
class RepairDecision:
    """Result of the repair loop's diagnosis."""

    action: Action
    failure_class: FailureClass
    milestone: int
    reason: str
    notes_entry: str | None = None


def _read_notes(plan_stem: str, milestone: int) -> str | None:
    """Read implementation notes for a milestone."""
    notes_file = ACTIVE_DIR / f"{plan_stem}-notes" / f"M{milestone}.md"
    if not notes_file.exists():
        return None
    return notes_file.read_text()


def _extract_deviations(notes_text: str) -> list[str]:
    """Extract deviation entries from notes text."""
    entries = re.split(r"^### ", notes_text, flags=re.MULTILINE)
    return [e for e in entries if e.startswith("[deviation]")]


def _extract_human_todos(notes_text: str) -> list[str]:
    """Extract human-todo entries from notes text."""
    entries = re.split(r"^### ", notes_text, flags=re.MULTILINE)
    return [e for e in entries if e.startswith("[human-todo]")]


def diagnose_failure(
    verify_findings: str,
    failure_class_hint: str | None,
    plan_stem: str,
    milestone: int,
) -> FailureClass:
    """Classify the failure based on B's findings and implementation notes.

    Args:
        verify_findings: B's structured findings text.
        failure_class_hint: B's own classification (if provided).
        plan_stem: ExecPlan filename stem (e.g., "9005-pev-loop-evolution").
        milestone: Milestone number.

    Returns:
        FailureClass classification.
    """
    # If B provided a classification, trust it
    if failure_class_hint:
        try:
            return FailureClass(failure_class_hint)
        except ValueError:
            pass

    # Check for unresolved human-todos in notes — semantic signal
    notes = _read_notes(plan_stem, milestone)
    if notes:
        todos = _extract_human_todos(notes)
        if todos:
            return FailureClass.SEMANTIC

    # Analyze findings text for classification signals
    findings_lower = verify_findings.lower()

    # Constraint violation signals
    constraint_signals = [
        "outside the allowed writes",
        "constraint",
        "scope",
        "exceeds declared",
        "not in allowed",
    ]
    if any(s in findings_lower for s in constraint_signals):
        return FailureClass.CONSTRAINT_VIOLATION

    # Semantic signals (subjective quality, design judgment)
    semantic_signals = [
        "design",
        "subjective",
        "quality",
        "judgment",
        "preference",
        "taste",
        "feel",
    ]
    if any(s in findings_lower for s in semantic_signals):
        return FailureClass.SEMANTIC

    # Default: mechanical (test failures, assertion errors, missing imports)
    return FailureClass.MECHANICAL


def decide_action(
    failure_class: FailureClass,
    milestone: int,
    findings: str,
) -> RepairDecision:
    """Decide the next action based on failure classification.

    Args:
        failure_class: The diagnosed failure class.
        milestone: Milestone number.
        findings: B's findings text.

    Returns:
        RepairDecision with action and metadata.
    """
    if failure_class == FailureClass.SEMANTIC:
        return RepairDecision(
            action=Action.HUMAN_TODO,
            failure_class=failure_class,
            milestone=milestone,
            reason=findings,
            notes_entry=(
                f"### [human-todo] — Semantic failure in M{milestone}\n\n"
                f"B's findings require human judgment:\n\n{findings}\n"
            ),
        )

    if failure_class == FailureClass.CONSTRAINT_VIOLATION:
        return RepairDecision(
            action=Action.UPDATE_CONSTRAINTS,
            failure_class=failure_class,
            milestone=milestone,
            reason=findings,
            notes_entry=(
                f"### [deviation] — Constraint violation in M{milestone}\n\n"
                f"- **What the plan said:** Constraints declared in milestone.\n"
                f"- **What the code revealed:** Implementation exceeded scope.\n"
                f"- **Conservative choice:** Update constraints to match actual "
                f"scope, with Decision Log entry.\n"
                f"- **Revisit:** Verify updated constraints are minimal.\n"
            ),
        )

    # Mechanical: auto-repair
    return RepairDecision(
        action=Action.RETRY,
        failure_class=failure_class,
        milestone=milestone,
        reason=findings,
    )


def write_notes_entry(plan_stem: str, decision: RepairDecision) -> bool:
    """Write the repair decision's notes_entry to the milestone's notes file.

    Creates the notes directory and file if they don't exist. Appends
    the entry if the file already exists. Deduplicates: if the exact
    notes_entry text already appears, the write is skipped.

    Args:
        plan_stem: ExecPlan filename stem (e.g., "9005-pev-loop-evolution").
        decision: The RepairDecision from decide_action().

    Returns:
        True if written, False if no entry needed (mechanical or already present).
    """
    if decision.notes_entry is None:
        return False

    notes_dir = ACTIVE_DIR / f"{plan_stem}-notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    notes_file = notes_dir / f"M{decision.milestone}.md"

    if notes_file.exists():
        existing = notes_file.read_text()
        if decision.notes_entry.strip() in existing:
            return True  # already written — idempotent
        text = existing.rstrip("\n") + "\n\n" + decision.notes_entry + "\n"
    else:
        text = f"# M{decision.milestone}\n\n" + decision.notes_entry + "\n"

    notes_file.write_text(text)
    return True
