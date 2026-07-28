"""Structural tests for implementation notes.

Validates that:
- Notes files exist for milestones with recorded deviations
- Entries carry valid type badges (plan-confirmed/discovery/deviation/human-todo)
- Deviation entries have all four devgrid fields

See docs/conventions/implementation-notes.md.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACTIVE_DIR = REPO_ROOT / "docs" / "exec-plans" / "active"

# Entry type badge pattern: ### [type] timestamp — title
ENTRY_RE = re.compile(
    r"^### \[(plan-confirmed|discovery|deviation|human-todo)\]",
    re.MULTILINE,
)

# Devgrid fields required in deviation entries
DEVGRID_FIELDS = [
    "What the plan said",
    "What the code revealed",
    "Conservative choice",
    "Revisit",
]

# Deviation mention in plan's Surprises section (signals notes must exist)
PLAN_DEVIATION_RE = re.compile(r"\bdeviation\b", re.IGNORECASE)


def _notes_dir_for(plan_path: Path) -> Path:
    """Return the notes directory for a plan file."""
    return plan_path.parent / f"{plan_path.stem}-notes"


def _validate_notes_file(notes_file: Path, rel: Path) -> list[str]:
    """Validate a single notes file. Returns list of failures."""
    failures: list[str] = []
    text = notes_file.read_text()

    # Every entry must have a valid type badge
    headings = re.findall(r"^### .+$", text, re.MULTILINE)
    for h in headings:
        if not ENTRY_RE.match(h):
            failures.append(
                f"{rel}: entry heading lacks valid type badge: {h!r}. "
                f"Must start with [plan-confirmed], [discovery], "
                f"[deviation], or [human-todo]."
            )

    # Deviation entries must have all devgrid fields
    # Split text into entries
    entries = re.split(r"^### ", text, flags=re.MULTILINE)
    for entry in entries:
        if entry.startswith("[deviation]"):
            for field in DEVGRID_FIELDS:
                if field not in entry:
                    failures.append(
                        f"{rel}: deviation entry missing devgrid field "
                        f"'{field}': {entry[:80]!r}..."
                    )

    return failures


def test_notes_valid_when_deviations_exist():
    """Milestones with deviations have valid implementation notes files."""
    if not ACTIVE_DIR.exists():
        return

    failures: list[str] = []

    for plan_path in sorted(ACTIVE_DIR.glob("*.md")):
        text = plan_path.read_text()
        rel = plan_path.relative_to(REPO_ROOT)

        # Check if the plan's Surprises & Discoveries mentions deviations
        surprises_match = re.search(
            r"^## 6\. Surprises & Discoveries(.*?)(?=^## |\Z)",
            text,
            re.MULTILINE | re.DOTALL,
        )
        has_deviations = (
            surprises_match and PLAN_DEVIATION_RE.search(surprises_match.group(1))
        )

        notes_dir = _notes_dir_for(plan_path)

        if has_deviations:
            if not notes_dir.exists():
                failures.append(
                    f"{rel}: Surprises & Discoveries records deviations but "
                    f"notes directory {notes_dir.relative_to(REPO_ROOT)} "
                    f"does not exist. See docs/conventions/implementation-notes.md."
                )
                continue

            # Validate every notes file in the directory
            for notes_file in sorted(notes_dir.glob("M*.md")):
                notes_rel = notes_file.relative_to(REPO_ROOT)
                failures.extend(_validate_notes_file(notes_file, notes_rel))

        # If notes dir exists (even without plan deviations), validate format
        elif notes_dir.exists():
            for notes_file in sorted(notes_dir.glob("M*.md")):
                notes_rel = notes_file.relative_to(REPO_ROOT)
                failures.extend(_validate_notes_file(notes_file, notes_rel))

    assert not failures, "Implementation notes violations:\n" + "\n".join(
        f"  - {f}" for f in failures
    )


def test_notes_files_wellformed_if_present():
    """Any existing notes files are well-formed regardless of deviations."""
    if not ACTIVE_DIR.exists():
        return

    failures: list[str] = []

    for notes_dir in sorted(ACTIVE_DIR.glob("*-notes")):
        if not notes_dir.is_dir():
            continue
        for notes_file in sorted(notes_dir.glob("M*.md")):
            notes_rel = notes_file.relative_to(REPO_ROOT)
            failures.extend(_validate_notes_file(notes_file, notes_rel))

    assert not failures, "Malformed notes files:\n" + "\n".join(
        f"  - {f}" for f in failures
    )
