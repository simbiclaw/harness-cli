#!/usr/bin/env python3
"""PostToolUse hook.

Detects when an Edit/Write to a file under docs/exec-plans/active/ flips a
checkbox from `[ ]` to `[x]`, and emits a reminder to commit immediately
with the milestone reference.

Soft nudge, not a hard block. The structural test on commit messages
provides the hard enforcement.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACTIVE_PLANS_DIR = REPO_ROOT / "docs" / "exec-plans" / "active"


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    tool = event.get("tool_name", "")
    if tool not in ("Edit", "MultiEdit", "Write"):
        return 0

    params = event.get("tool_input", {})
    target = params.get("file_path") or params.get("path") or ""
    if not target:
        return 0

    target_path = Path(target).resolve()
    try:
        rel = target_path.relative_to(ACTIVE_PLANS_DIR)
    except ValueError:
        return 0

    new_text = params.get("new_str") or params.get("content") or ""
    if "[x]" not in new_text:
        return 0

    print(json.dumps({
        "message": (
            f"Milestone checkbox flipped in docs/exec-plans/active/{rel}. Per "
            f"docs/conventions/commit-hygiene.md, commit immediately with:\n\n"
            f"  <type>(<scope>): <verb-noun subject>\n\n"
            f"  Plan: docs/exec-plans/active/{rel}#milestone-N\n"
            f"  Decision: <one-line>\n"
        )
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
