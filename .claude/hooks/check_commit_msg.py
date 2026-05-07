#!/usr/bin/env python3
"""commit-msg hook: enforce trailer format from commit-hygiene.md.

Invoked by pre-commit framework via .pre-commit-config.yaml.
Argv[1] is the path to the commit message file.
Exit 0 to accept; non-zero to reject.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TEMPLATE = """
Commit message must follow the format:

  <type>(<scope>): <subject>

  Plan: docs/exec-plans/active/NNNN-<slug>.md#milestone-N
  Decision: <one-line rationale, or "implementation only">

Where <type> is one of: feat fix refactor test docs chore harness
"""

SUBJECT_RE = re.compile(
    r"^(feat|fix|refactor|test|docs|chore|harness)(\([\w\-]+\))?:\s+(.{12,72})$"
)
TRAILER_PLAN = re.compile(r"^Plan:\s*docs/exec-plans/", re.MULTILINE)
TRAILER_DECISION = re.compile(r"^Decision:\s*\S", re.MULTILINE)
USELESS_SUBJECT = re.compile(
    r"^(update files|fix issues|various changes|wip|misc|stuff|tweaks?|"
    r"cleanup|polish|nits)\.?$",
    re.IGNORECASE,
)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("commit-msg: missing message file argument", file=sys.stderr)
        return 1

    msg_file = Path(argv[1])
    msg = msg_file.read_text()

    first_line = msg.splitlines()[0] if msg.splitlines() else ""
    if first_line.startswith(("Merge ", "Revert ", "fixup!", "squash!")):
        return 0

    errs: list[str] = []
    m = SUBJECT_RE.match(first_line)
    if not m:
        errs.append(
            "Subject line does not match "
            "'<type>(<scope>): <12-72 char subject>'."
        )
    else:
        subject = m.group(3).strip()
        if USELESS_SUBJECT.match(subject):
            errs.append(f"Subject is too vague: {subject!r}")
    if not TRAILER_PLAN.search(msg):
        errs.append("Missing 'Plan: docs/exec-plans/...' trailer.")
    if not TRAILER_DECISION.search(msg):
        errs.append("Missing 'Decision: ...' trailer.")

    if errs:
        print("Commit rejected:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        print(TEMPLATE, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
