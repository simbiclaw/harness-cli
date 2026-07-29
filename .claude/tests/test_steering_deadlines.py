"""Structural test: Awaiting Steering and human-todo deadlines.

Improvement #4 from the 2026-07-30 PEV harness evaluation:
  Awaiting Steering entries and [human-todo] notes entries must have
  deadlines and must be resolved before the deadline expires.

  Expired unresolved entries fail this test — the fix is either to
  resolve the entry or to update the deadline with a Decision Log
  entry explaining the extension.

Schema:
  Awaiting Steering entries in ExecPlans:
    - **Q<n>: <question>** — Deadline: YYYY-MM-DD. <status>. <rationale>.

  [human-todo] entries in implementation notes:
    ### [human-todo] YYYY-MM-DDThh:mm:ssZ — M<N> requires human judgment
    Deadline: YYYY-MM-DD
    <findings>
    Status: unresolved | resolved
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACTIVE_DIR = REPO_ROOT / "docs" / "exec-plans" / "active"

# Patterns
DEADLINE_RE = re.compile(
    r"Deadline:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE
)
HUMAN_TODO_RE = re.compile(
    r"###\s+\[human-todo\]\s+([\dT:\.\-Z]+).*?\n(.*?)(?=\n###|\n---|\Z)",
    re.DOTALL,
)
STATUS_RE = re.compile(r"Status:\s*(unresolved|resolved)", re.IGNORECASE)
AWAITING_SECTION_RE = re.compile(
    r"## \d+\.\s*Awaiting Steering\s*\n(.*?)(?=\n## \d+\.|\Z)",
    re.DOTALL,
)
STEERING_Q_RE = re.compile(
    r"\*\*Q\d+:\s*(.+?)\*\*\s*—\s*Deadline:\s*(\d{4}-\d{2}-\d{2})\.?\s*(.+?)(?=\n\*\*Q\d+|\n>\s|\Z)",
    re.DOTALL,
)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def test_steering_deadlines_not_expired():
    """Awaiting Steering entries must not have expired deadlines.

    An expired deadline means a Tier C question was parked but never
    resolved. The plan is blocking indefinitely.
    """
    if not ACTIVE_DIR.exists():
        return

    today = _today()
    failures: list[str] = []

    for plan_path in sorted(ACTIVE_DIR.glob("*.md")):
        text = plan_path.read_text()
        rel = plan_path.relative_to(REPO_ROOT)

        # Find Awaiting Steering section
        section_match = AWAITING_SECTION_RE.search(text)
        if not section_match:
            continue

        section_body = section_match.group(1).strip()

        # Skip "None" sections
        if section_body.lower().startswith("*none"):
            continue

        # Look for entries with deadlines
        for deadline_match in DEADLINE_RE.finditer(section_body):
            deadline = deadline_match.group(1)
            if deadline < today:
                # Check if resolved
                context_start = max(0, deadline_match.start() - 200)
                context = section_body[context_start : deadline_match.end() + 200]
                if "resolved" not in context.lower():
                    failures.append(
                        f"{rel}: Awaiting Steering deadline {deadline} "
                        f"has expired and the question does not appear "
                        f"to be resolved"
                    )

    assert not failures, (
        "Expired Awaiting Steering deadlines — these Tier C questions "
        "are blocking their plans indefinitely:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )


def test_human_todo_deadlines_not_expired():
    """[human-todo] entries in implementation notes must have deadlines
    and must not have expired unresolved deadlines.
    """
    today = _today()
    failures: list[str] = []

    for notes_dir in sorted(ACTIVE_DIR.glob("*-notes")):
        if not notes_dir.is_dir():
            continue

        for notes_file in sorted(notes_dir.glob("M*.md")):
            text = notes_file.read_text()
            rel = notes_file.relative_to(REPO_ROOT)

            for todo_match in HUMAN_TODO_RE.finditer(text):
                header = todo_match.group(0)

                # Check for resolution
                status_match = STATUS_RE.search(header)
                if status_match and status_match.group(1).lower() == "resolved":
                    continue

                # Check for deadline
                deadline_match = DEADLINE_RE.search(header)
                if not deadline_match:
                    failures.append(
                        f"{rel}: [human-todo] entry without a Deadline: "
                        f"field — add 'Deadline: YYYY-MM-DD' or mark as "
                        f"'Status: resolved'"
                    )
                    continue

                deadline = deadline_match.group(1)
                if deadline < today:
                    failures.append(
                        f"{rel}: [human-todo] deadline {deadline} "
                        f"has expired without resolution. Resolve or "
                        f"extend the deadline with a reason."
                    )

    assert not failures, (
        "Expired or deadline-less [human-todo] entries — these human "
        "decisions are blocking milestones indefinitely:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )
