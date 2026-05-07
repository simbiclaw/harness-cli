"""Structural test: recent commits follow the trailer format.

Walks `git log --since=30.days.ago` and asserts every commit message:
  - has a Plan: trailer pointing to a real ExecPlan path
  - has a Decision: trailer
  - has a non-trivial subject

Skips merge commits and reverts.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

TRAILER_PLAN = re.compile(
    r"^Plan:\s*(docs/exec-plans/\S+\.md)(?:#\S+)?", re.MULTILINE
)
TRAILER_DECISION = re.compile(r"^Decision:\s*\S.*$", re.MULTILINE)
SUBJECT_RE = re.compile(
    r"^[a-z]+(\([\w\-]+\))?:\s+(.{12,72})$"
)
USELESS_SUBJECTS = re.compile(
    r"^(update files|fix issues|various changes|wip|misc|stuff|tweaks?|"
    r"cleanup|polish|nits)\.?$",
    re.IGNORECASE,
)


def git_log() -> list[tuple[str, str]]:
    try:
        out = subprocess.check_output(
            [
                "git", "log", "--since=30.days.ago", "--no-merges",
                "--pretty=format:%H%x00%B%x1e",
            ],
            cwd=REPO_ROOT,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    out = out.rstrip("\x1e")
    if not out:
        return []
    entries: list[tuple[str, str]] = []
    for chunk in out.split("\x1e"):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        sha, _, msg = chunk.partition("\x00")
        entries.append((sha, msg))
    return entries


def test_commits_follow_format():
    failures: list[str] = []
    for sha, msg in git_log():
        sha_short = sha[:8]
        lines = msg.splitlines()
        subject = lines[0] if lines else ""

        # Skip first-commit conventions or merge fallout.
        if subject.startswith(("Initial commit", "fixup!", "squash!")):
            continue

        m = SUBJECT_RE.match(subject)
        if not m:
            failures.append(
                f"{sha_short}: subject does not match "
                f"'<type>(<scope>): <verb-noun>': {subject!r}"
            )
            continue
        if USELESS_SUBJECTS.match(m.group(2).strip()):
            failures.append(
                f"{sha_short}: subject is too vague: {subject!r}"
            )

        plan_match = TRAILER_PLAN.search(msg)
        if not plan_match:
            failures.append(f"{sha_short}: missing 'Plan:' trailer.")
        else:
            plan_path_str = plan_match.group(1)
            plan_path = REPO_ROOT / plan_path_str
            if not plan_path.exists():
                stem = Path(plan_path_str).name
                alt_dirs = [
                    REPO_ROOT / "docs" / "plans" / d
                    for d in ("active", "completed", "archived")
                ]
                if not any((d / stem).exists() for d in alt_dirs):
                    failures.append(
                        f"{sha_short}: Plan trailer references missing "
                        f"file '{plan_path_str}'."
                    )
        if not TRAILER_DECISION.search(msg):
            failures.append(f"{sha_short}: missing 'Decision:' trailer.")

    assert not failures, "\n  ".join([""] + failures)
