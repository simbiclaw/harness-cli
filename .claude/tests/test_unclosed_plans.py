"""Structural test: no active ExecPlan with all milestones checked but no
Outcomes & Retrospective written.  A fully-checked plan that is still in
active/ without a retrospective is an unclosed plan — the agent forgot the
final step.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACTIVE_DIR = REPO_ROOT / "docs" / "exec-plans" / "active"

CHECKED = re.compile(r"^- \[x\]", re.MULTILINE)
UNCHECKED = re.compile(r"^- \[ \]", re.MULTILINE)
OUTCOMES_HEADER = re.compile(r"^##+\s+\d+\.\s+Outcomes & Retrospective", re.MULTILINE)

PLACEHOLDER = "(written at completion)"


def test_no_unclosed_plans():
    if not ACTIVE_DIR.exists():
        return  # nothing to check

    failures: list[str] = []
    for plan in sorted(ACTIVE_DIR.glob("*.md")):
        text = plan.read_text()

        has_unchecked = bool(UNCHECKED.search(text))
        has_checked = bool(CHECKED.search(text))

        if not has_checked:
            continue  # no progress yet — fine

        if has_unchecked:
            continue  # still in progress — fine

        # All milestones are flipped.  Must have a real retrospective.
        m = OUTCOMES_HEADER.search(text)
        if not m:
            failures.append(
                f"{plan.relative_to(REPO_ROOT)}: all milestones checked "
                f"but no 'Outcomes & Retrospective' section. Write the "
                f"retrospective and move the plan to completed/."
            )
            continue

        # Section exists — but is it just the empty placeholder?
        after_header = text[m.end():]
        # Grab text until the next heading or EOF.
        next_h = re.search(r"^##+\s+", after_header, re.MULTILINE)
        body = after_header[:next_h.start()] if next_h else after_header
        stripped = body.strip()

        if not stripped or stripped == PLACEHOLDER:
            failures.append(
                f"{plan.relative_to(REPO_ROOT)}: Outcomes & Retrospective "
                f"is empty or still the placeholder. Write the actual "
                f"retrospective and move the plan to completed/."
            )

    assert not failures, "\n  ".join([""] + failures)
