"""Structural test: every flipped checkbox must have a PEV verdict in notes.

Lesson 1 from postmortem 2026-07-29-pev-without-pev.md:
  "Add a test that verifies every checkbox flip has a corresponding
   notes entry in -notes/M<N>.md. A flipped checkbox without a
   [plan-confirmed] or [deviation] entry is a harness violation."

Scans all active and completed ExecPlans for flipped milestone checkboxes
(- [x] M<N>:). For each flipped milestone, checks that the corresponding
implementation notes file exists and contains a valid verdict entry badge.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACTIVE_DIR = REPO_ROOT / "docs" / "exec-plans" / "active"
COMPLETED_DIR = REPO_ROOT / "docs" / "exec-plans" / "completed"

# Match a flipped milestone checkbox: - [x] M<number>:<space><title>
FLIPPED_CHECKBOX = re.compile(r"^- \[x\] M(\d+):", re.MULTILINE)

# Valid entry type badges that constitute a PEV verdict
VERDICT_BADGES = re.compile(
    r"^### \[(plan-confirmed|deviation|human-todo|discovery)\]",
    re.MULTILINE,
)

# Match a milestone heading to extract the milestone number
MILESTONE_HEADING = re.compile(r"^### M(\d+)\b", re.MULTILINE)


def _notes_dir_for(plan_path: Path) -> Path:
    """Return the notes directory for a plan file."""
    return plan_path.parent / f"{plan_path.stem}-notes"


def _flipped_milestones(plan_text: str) -> list[int]:
    """Return milestone numbers of all flipped checkboxes in a plan."""
    return [int(m.group(1)) for m in FLIPPED_CHECKBOX.finditer(plan_text)]


def _has_verdict(notes_file: Path) -> bool:
    """Check whether a notes file contains a valid PEV verdict entry."""
    if not notes_file.exists():
        return False
    content = notes_file.read_text()
    return bool(VERDICT_BADGES.search(content))


def test_confirmed_milestones_have_notes():
    """Every flipped checkbox (- [x] M<N>:) must have notes with a verdict entry.

    Violations indicate a milestone was marked complete without adversarial
    verification — the exact failure mode identified in postmortem
    2026-07-29-pev-without-pev.md.
    """
    if not ACTIVE_DIR.exists():
        return

    failures: list[str] = []

    # Scan both active and completed plan directories
    plan_dirs = [d for d in [ACTIVE_DIR, COMPLETED_DIR] if d.exists()]
    for plan_dir in plan_dirs:
        for plan_path in sorted(plan_dir.glob("*.md")):
            text = plan_path.read_text()
            rel = str(plan_path.relative_to(REPO_ROOT))
            notes_dir = _notes_dir_for(plan_path)
            flipped = _flipped_milestones(text)

            if not flipped:
                continue

            # Backward compatibility: only enforce for plans that have
            # a notes directory. Plans without -notes/ predate the
            # implementation notes convention (established 2026-07-28).
            if not notes_dir.exists():
                continue

            for m_num in flipped:
                notes_file = notes_dir / f"M{m_num}.md"
                notes_rel = str(notes_file.relative_to(REPO_ROOT))

                if not notes_file.exists():
                    failures.append(
                        f"{rel}: M{m_num} checkbox flipped ([x]) "
                        f"but notes file missing: {notes_rel}. "
                        f"PEV requires a subagent B verdict written to this file."
                    )
                elif not _has_verdict(notes_file):
                    failures.append(
                        f"{rel}: M{m_num} checkbox flipped ([x]) "
                        f"but {notes_rel} contains no verdict entry. "
                        f"Must contain one of: [plan-confirmed], [deviation], "
                        f"[human-todo], [discovery]."
                    )

    assert not failures, (
        "PEV checkbox-flip gate violations — flipped checkboxes without "
        "corresponding notes entries (see postmortem 2026-07-29-pev-without-pev.md):\n"
        + "\n".join(f"  - {f}" for f in failures)
    )


def test_unflipped_milestones_should_not_have_confirmed_notes():
    """Guard against stale notes from previous runs.

    If a milestone is unflipped (- [ ] M<N>:), it should not have
    a notes file with a [plan-confirmed] verdict. This would indicate
    a stale notes file from a previous execution that hasn't been
    cleaned up before restart.
    """
    if not ACTIVE_DIR.exists():
        return

    warnings: list[str] = []

    for plan_path in sorted(ACTIVE_DIR.glob("*.md")):
        text = plan_path.read_text()
        rel = str(plan_path.relative_to(REPO_ROOT))
        notes_dir = _notes_dir_for(plan_path)

        # Find unflipped milestones
        unflipped = re.findall(r"^- \[ \] M(\d+):", text, re.MULTILINE)
        all_milestones = {int(m.group(1)) for m in MILESTONE_HEADING.finditer(text)}

        for m_num_str in unflipped:
            m_num = int(m_num_str)
            notes_file = notes_dir / f"M{m_num}.md"
            if notes_file.exists() and _has_verdict(notes_file):
                notes_rel = str(notes_file.relative_to(REPO_ROOT))
                warnings.append(
                    f"{rel}: M{m_num} is unflipped but {notes_rel} "
                    f"contains a verdict from a previous run. "
                    f"Delete stale notes before restarting PEV."
                )

    # This is a warning, not a hard failure — stale notes are a hygiene issue
    # but don't indicate the same severity as missing notes for flipped milestones.
    if warnings:
        raise AssertionError(
            "Stale notes files detected (unflipped milestones with verdicts):\n"
            + "\n".join(f"  - {w}" for w in warnings)
        )


def test_no_milestone_skipping():
    """Milestones must complete V verification in order.

    If M<N> is confirmed, all M<0..N-1> must be confirmed.
    E must not skip ahead before V confirms the current milestone.
    """
    STATE_FILE = REPO_ROOT / ".pev-signals" / "state.json"
    if not STATE_FILE.exists():
        return

    try:
        import json
        state = json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return

    milestones = state.get("milestones", {})
    if not milestones:
        return

    ordered = sorted(
        [(int(k[1:]), k, v) for k, v in milestones.items()],
        key=lambda x: x[0],
    )

    failures = []
    saw_unconfirmed = False
    for num, key, value in ordered:
        if value == "confirmed":
            if saw_unconfirmed:
                failures.append(f"{key}={value} but earlier milestone(s) unconfirmed")
        else:
            saw_unconfirmed = True

    current = state.get("current_milestone", 0)
    for num, key, value in ordered:
        if num < current and value != "confirmed":
            failures.append(
                f"{key}={value} but current_milestone={current} — "
                f"M{num} must be confirmed before advancing"
            )

    assert not failures, (
        "PEV sequential gate: V must confirm each milestone before E moves on:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )
