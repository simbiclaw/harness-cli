#!/usr/bin/env python3
"""
Pre-execution constraint gate for PEV loop.

Reads the active ExecPlan's milestone constraints (Allowed Writes) and blocks
Edit/Write operations that target paths outside the declared scope.

Hook contract: read JSON event from stdin. Print JSON to stdout.
Exit 0 with {"continue": true} to allow.
Exit 0 with {"continue": false, "reason": "..."} to block.

Constraint format in ExecPlan milestones:
    Allowed Writes: src/argus/core/**, tests/test_core.py

If no Allowed Writes field exists for the current milestone, all writes
are allowed (backward-compatible).

See: docs/conventions/pev-loop.md § Milestone constraint fields
"""

from __future__ import annotations

import fnmatch
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACTIVE_PLANS_DIR = REPO_ROOT / "docs" / "exec-plans" / "active"

MILESTONE_RE = re.compile(r"^### M(\d+)[\s—–-]", re.MULTILINE)
ALLOWED_WRITES_RE = re.compile(r"^Allowed Writes:\s*(.+)$", re.MULTILINE)
CHECKBOX_RE = re.compile(r"^- \[([ x])\] M(\d+)", re.MULTILINE)


def _find_current_milestone(plan_text: str) -> int | None:
    """Find the first unflipped milestone in the plan."""
    for match in CHECKBOX_RE.finditer(plan_text):
        state, m_num = match.group(1), int(match.group(2))
        if state == " ":
            return m_num
    return None


def _parse_allowed_writes(plan_text: str, milestone_num: int) -> list[str]:
    """Extract Allowed Writes patterns for a specific milestone."""
    parts = MILESTONE_RE.split(plan_text)
    for i in range(1, len(parts) - 1, 2):
        if int(parts[i]) == milestone_num:
            body = parts[i + 1]
            next_m = MILESTONE_RE.search(body)
            if next_m:
                body = body[: next_m.start()]
            m = ALLOWED_WRITES_RE.search(body)
            if m:
                return [p.strip() for p in m.group(1).split(",") if p.strip()]
            break
    return []


def _path_matches_any(path: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(path, f"./{pat}"):
            return True
    return False


def main() -> int:
    event = json.load(sys.stdin)
    tool = event.get("tool_name", "")
    params = event.get("tool_input", {})

    if tool not in ("Edit", "Write", "MultiEdit", "Create"):
        print(json.dumps({"continue": True}))
        return 0

    target = params.get("file_path") or params.get("path") or ""
    if not target:
        print(json.dumps({"continue": True}))
        return 0

    try:
        rel = str(Path(target).resolve().relative_to(REPO_ROOT))
    except (ValueError, OSError):
        print(json.dumps({"continue": True}))
        return 0

    # Skip edits to exec-plan files themselves
    try:
        Path(target).resolve().relative_to(ACTIVE_PLANS_DIR)
        print(json.dumps({"continue": True}))
        return 0
    except (ValueError, OSError):
        pass

    if not ACTIVE_PLANS_DIR.exists():
        print(json.dumps({"continue": True}))
        return 0

    plans = sorted(
        ACTIVE_PLANS_DIR.glob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not plans:
        print(json.dumps({"continue": True}))
        return 0

    plan_text = plans[0].read_text()
    plan_rel = plans[0].relative_to(REPO_ROOT)
    current_m = _find_current_milestone(plan_text)

    if current_m is None:
        print(json.dumps({"continue": True}))
        return 0

    allowed = _parse_allowed_writes(plan_text, current_m)

    if not allowed:
        print(json.dumps({"continue": True}))
        return 0

    if _path_matches_any(rel, allowed):
        print(json.dumps({"continue": True}))
        return 0

    patterns_str = ", ".join(f"`{p}`" for p in allowed)
    print(json.dumps({
        "continue": False,
        "reason": (
            f"Path '{rel}' is outside the Allowed Writes for M{current_m} "
            f"in {plan_rel}. Declared patterns: {patterns_str}. "
            f"Either update the milestone's Allowed Writes in the ExecPlan "
            f"(with a Decision Log entry), or revert this edit. "
            f"See docs/conventions/pev-loop.md § Milestone constraint fields."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
