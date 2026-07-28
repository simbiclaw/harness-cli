"""Structural test: detect file-scope collisions between active ExecPlans.

Replaces the frozen COLLISION-REPORT.md (a one-off v6-spine upgrade artifact)
with a living detector. Every plan declares its file-scope in a machine-readable
`**File Scope:**` block; this test checks that no two active plans claim
overlapping files.

A collision forces the plans to negotiate before either proceeds — the same
principle as the per-milestone Allowed Writes gate, lifted to the plan level.

See docs/PLANS.md §2 (Big Picture — File Scope block).
"""

from __future__ import annotations

import re
from collections import defaultdict
from fnmatch import fnmatch
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACTIVE_DIR = REPO_ROOT / "docs" / "exec-plans" / "active"

# Match a **File Scope:** block. The block ends at a blank line or next
# markdown heading/styled text.
FILE_SCOPE_HEADER = re.compile(r"^\*\*File Scope:\*\*\s*$", re.MULTILINE)
SCOPE_LINE = re.compile(r"^[-*]\s+`([^`]+)`", re.MULTILINE)


def _parse_file_scope(plan_text: str) -> list[str] | None:
    """Extract file-scope paths from a plan's **File Scope:** block.

    Returns None if the plan has no File Scope block (advisory — plan
    needs one). Returns a list of repo-relative path patterns otherwise.
    """
    header = FILE_SCOPE_HEADER.search(plan_text)
    if not header:
        return None

    # Find the end of the block: blank line or next markdown heading.
    # Don't use ** as terminator — scope paths like `src/argus/**`
    # contain literal ** inside backticks.
    start = header.end()
    block_end = re.search(r"\n\s*\n|^#{1,3}\s", plan_text[start:], re.MULTILINE)
    if block_end:
        block = plan_text[start:start + block_end.start()]
    else:
        block = plan_text[start:]

    paths: list[str] = []
    for m in SCOPE_LINE.finditer(block):
        paths.append(m.group(1))

    return paths


def _paths_overlap(a: str, b: str) -> bool:
    """Check whether two file path patterns intersect.

    Handles exact matches, glob matches, and prefix matches.
    """
    # Exact match
    if a == b:
        return True

    # Glob match in either direction
    if fnmatch(a, b) or fnmatch(b, a):
        return True

    # If one is a glob like `foo/**`, a concrete path under foo/ collides
    # fnmatch('src/argus/types/compiler_schemas.py', 'src/argus/types/**') == True
    if fnmatch(b, a) or fnmatch(a, b):
        return True

    # Prefix overlap: 'src/argus/types/' is a prefix of 'src/argus/types/foo.py'
    if a.endswith("/**"):
        prefix_a = a[:-3]
        if b.startswith(prefix_a):
            return True
    if b.endswith("/**"):
        prefix_b = b[:-3]
        if a.startswith(prefix_b):
            return True

    return False


def _plan_name(plan_path: Path) -> str:
    """Extract the plan number-slug name."""
    return plan_path.stem


def test_no_file_scope_collisions():
    """No two active plans claim overlapping file-scope paths."""
    if not ACTIVE_DIR.exists():
        return

    failures: list[str] = []
    advisory: list[str] = []

    # Collect all plans with their scopes
    plans: dict[str, list[str]] = {}
    plans_missing: list[str] = []

    for plan_path in sorted(ACTIVE_DIR.glob("*.md")):
        name = _plan_name(plan_path)
        text = plan_path.read_text()
        scope = _parse_file_scope(text)

        if scope is None:
            plans_missing.append(name)
            continue

        plans[name] = scope

    # Advisory: plans without File Scope
    for name in sorted(plans_missing):
        advisory.append(
            f"{name}: no **File Scope:** block — "
            f"add one per docs/PLANS.md §2"
        )

    # Check pairwise collisions
    names = sorted(plans.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a_name, a_paths = names[i], plans[names[i]]
            b_name, b_paths = names[j], plans[names[j]]

            for pa in a_paths:
                for pb in b_paths:
                    if _paths_overlap(pa, pb):
                        failures.append(
                            f"Collision: {a_name} and {b_name} both "
                            f"declare `{pa}` vs `{pb}`. "
                            f"Negotiate before either proceeds."
                        )

    # Build the error message
    msg_parts: list[str] = []

    if advisory:
        msg_parts.append(
            f"Plans missing **File Scope:** block ({len(advisory)}):\n"
            + "\n".join(f"  - {a}" for a in advisory)
        )

    if failures:
        msg_parts.append(
            f"File-scope collisions ({len(failures)}):\n"
            + "\n".join(f"  - {f}" for f in failures)
        )

    if msg_parts:
        assert not failures, (
            "Cross-plan file-scope issues:\n\n"
            + "\n\n".join(msg_parts)
            + "\n\nSee docs/PLANS.md §2."
        )

    # Advisory-only: don't fail, but report
    if advisory:
        import warnings
        warnings.warn(
            "\n" + "\n".join(f"  - {a}" for a in advisory),
            stacklevel=2,
        )
