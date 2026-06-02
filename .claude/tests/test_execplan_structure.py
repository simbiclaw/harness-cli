"""Structural tests for ExecPlan form.

- test_execplan_has_required_sections: active plans have the 8 required
  section headers, and each section has content or an italic placeholder.
- test_execplan_filenames_have_slugs: plan filenames follow NNNN-slug.md.

See docs/PLANS.md.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACTIVE_DIR = REPO_ROOT / "docs" / "exec-plans" / "active"
PLANS_DIRS = [
    REPO_ROOT / "docs" / "exec-plans" / d for d in ("active", "completed", "archived")
]

REQUIRED_SECTIONS = [
    (1, "Purpose"),
    (2, "Big Picture"),
    (3, "Milestones"),
    (4, "Progress"),
    (5, "Decision Log"),
    (6, "Surprises & Discoveries"),
    (7, "Awaiting Steering"),
    (8, "Outcomes & Retrospective"),
]

# Matches exactly "## N. Name" — section headers, not ### subheadings.
SECTION_HEADER = re.compile(r"^##\s+(\d+)\.\s+(.+)$", re.MULTILINE)
NEXT_SECTION_RE = re.compile(r"^##\s+\d+\.\s+", re.MULTILINE)
FILENAME_RE = re.compile(r"^\d{4}-[\w\-]+\.md$")


def test_execplan_has_required_sections():
    if not ACTIVE_DIR.exists():
        return

    failures: list[str] = []
    for plan in sorted(ACTIVE_DIR.glob("*.md")):
        text = plan.read_text()
        rel = plan.relative_to(REPO_ROOT)

        found: list[tuple[int, str, int]] = []  # (num, name, start_pos)
        for m in SECTION_HEADER.finditer(text):
            num = int(m.group(1))
            name = m.group(2).strip()
            found.append((num, name, m.start()))

        section_starts = {num: (name, pos) for num, name, pos in found}

        for req_num, req_name in REQUIRED_SECTIONS:
            if req_num not in section_starts:
                failures.append(
                    f"{rel}: missing section '{req_num}. {req_name}'. "
                    f"See docs/PLANS.md for required sections."
                )
                continue

            _, start_pos = section_starts[req_num]
            # Find next section header after this one (exactly ##, not ###)
            after_header = text.find("\n", start_pos) + 1
            nxt = NEXT_SECTION_RE.search(text[after_header:])
            end_pos = (after_header + nxt.start()) if nxt else len(text)
            body = text[start_pos:end_pos]

            body_lines = body.splitlines()
            content_lines = [
                l for l in body_lines[1:] if l.strip()
            ]
            if not content_lines:
                failures.append(
                    f"{rel}: section '{req_num}. {req_name}' is empty. "
                    f"Add content or an italic placeholder note. "
                    f"See docs/PLANS.md."
                )

    assert not failures, "\n  ".join([""] + failures)


def test_execplan_filenames_have_slugs():
    failures: list[str] = []
    for plans_dir in PLANS_DIRS:
        if not plans_dir.exists():
            continue
        for plan in plans_dir.glob("*.md"):
            name = plan.name
            rel = plan.relative_to(REPO_ROOT)
            if not FILENAME_RE.match(name):
                failures.append(
                    f"{rel}: filename does not match 'NNNN-slug.md' "
                    f"pattern. Expected four digits, hyphen, descriptive "
                    f"slug. See docs/PLANS.md."
                )

    assert not failures, "\n  ".join([""] + failures)
