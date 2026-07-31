"""Structural test: Two-commit model per milestone (RED → GREEN).

Promoted from documentation to structural test on 2026-07-30.

Per docs/conventions/pev-loop.md § Commit authority:
  - Each milestone produces exactly two commits by the Arbiter.
  - RED commit: failing test only, committed after Plan phase.
  - GREEN commit: implementation + verdict + checkbox flip, after CONFIRMED.
  - RED must precede GREEN. No other commit pattern is valid.

This test scans git history for commits with Plan: trailers,
groups by (plan, milestone), and enforces the two-commit pattern.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Commit subject patterns
RED_SUBJECT_RE = re.compile(
    r"^test\(m(\d+)\):", re.IGNORECASE
)
GREEN_SUBJECT_RE = re.compile(
    r"^flip\(m(\d+)\):", re.IGNORECASE
)
PLAN_TRAILER_RE = re.compile(
    r"^Plan:\s*docs/exec-plans/\S+?(?:#milestone-(\d+))?", re.MULTILINE
)
DECISION_TRAILER_RE = re.compile(
    r"^Decision:\s*", re.MULTILINE
)

# Files that a RED commit may touch (test-only)
TEST_FILE_PATTERNS = [
    "tests/",
    ".claude/tests/",
    "conftest.py",
    "pyproject.toml",  # test config
]

GIT_LOG_SINCE = "90 days ago"


def _git_log_commits() -> list[dict]:
    """Return parsed commits with Plan: trailers."""
    try:
        result = subprocess.run(
            [
                "git", "log",
                f"--since={GIT_LOG_SINCE}",
                "--name-only",
                "--pretty=tformat:%x00%H%x00%aI%x00%s%x00%an%x00%B%x00",
                "--",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    commits = []
    for chunk in result.stdout.split("\x00"):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        parts = chunk.split("\n")
        if len(parts) < 5:
            continue

        sha = parts[0].strip()
        date = parts[1].strip()
        subject = parts[2].strip()
        author = parts[3].strip()
        # The rest is body + file list
        body_lines = []
        file_lines = []
        in_files = False
        for line in parts[4:]:
            if not in_files and "Plan:" in line:
                body_lines.append(line)
            elif line.strip() == "" and body_lines:
                in_files = True
            elif in_files:
                if line.strip():
                    file_lines.append(line.strip())
            else:
                body_lines.append(line)

        body = "\n".join(body_lines)

        # Only include commits with Plan: trailers
        plan_m = PLAN_TRAILER_RE.search(body)
        if not plan_m:
            continue

        milestone_str = plan_m.group(1)
        milestone = int(milestone_str) if milestone_str else None
        plan_ref = plan_m.group(0).replace("Plan: ", "").strip()
        plan_id = plan_ref.split("#")[0] if "#" in plan_ref else plan_ref

        has_decision = bool(DECISION_TRAILER_RE.search(body))

        commits.append({
            "sha": sha,
            "date": date,
            "subject": subject,
            "author": author,
            "plan_ref": plan_ref,
            "plan_id": plan_id.rstrip("/"),
            "milestone": milestone,
            "has_decision": has_decision,
            "files": file_lines,
            "body": body,
        })

    return commits


def _is_test_only(files: list[str]) -> bool:
    """Check whether all changed files are test files."""
    for f in files:
        if not any(f.startswith(p) for p in TEST_FILE_PATTERNS):
            return False
    return True


def _has_checkbox_flip(files: list[str]) -> bool:
    """Check whether the commit includes a plan file with checkbox changes."""
    return any("docs/exec-plans/" in f for f in files)


def _has_implementation(files: list[str]) -> bool:
    """Check whether the commit includes non-test, non-plan files."""
    for f in files:
        if (f.startswith("src/") or f.startswith(".claude/scripts/")
                or f.startswith(".claude/hooks/")):
            return True
    return False


def _has_verdict_notes(files: list[str]) -> bool:
    """Check whether the commit includes implementation notes."""
    return any("-notes/" in f for f in files)


def test_red_green_two_commit_pattern():
    """Each milestone must follow the RED→GREEN two-commit model.

    RED commit (test before implementation):
      - Subject: test(m<N>): ... — RED
      - Files: test files only (tests/, .claude/tests/)
      - Plan: and Decision: trailers present

    GREEN commit (implementation + verdict + flip):
      - Subject: flip(m<N>): ...
      - Files: implementation + notes + plan checkbox
      - Plan: and Decision: trailers present

    RED must precede GREEN for the same milestone.
    """
    commits = _git_log_commits()
    if not commits:
        return  # No Plan:-trailered commits to check

    # Group by (plan_id, milestone)
    from collections import defaultdict
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for c in commits:
        if c["milestone"] is not None:
            key = (c["plan_id"], c["milestone"])
            groups[key].append(c)

    failures: list[str] = []

    for (plan_id, m_num), group in sorted(groups.items()):
        # Check for RED commit
        reds = [c for c in group if RED_SUBJECT_RE.search(c["subject"])]
        greens = [c for c in group if GREEN_SUBJECT_RE.search(c["subject"])]
        others = [
            c for c in group
            if not RED_SUBJECT_RE.search(c["subject"])
            and not GREEN_SUBJECT_RE.search(c["subject"])
        ]

        # A milestone should have either 0 commits (not started),
        # or 2 commits (RED + GREEN). Other counts are violations.
        if len(group) == 0:
            continue  # Not started

        if len(group) == 1 and len(reds) == 1 and len(greens) == 0:
            # RED commit exists but no GREEN yet — mark in progress
            # This is valid if the milestone is currently being executed.
            # Check that RED commit is test-only.
            red = reds[0]
            if not _is_test_only(red["files"]):
                failures.append(
                    f"{red['sha'][:8]}: RED commit for M{m_num} in "
                    f"{plan_id} touches non-test files: {red['files']}. "
                    f"RED commits must only change test files."
                )
            if not red["has_decision"]:
                failures.append(
                    f"{red['sha'][:8]}: RED commit for M{m_num} missing "
                    f"Decision: trailer."
                )
            continue  # Valid in-progress state

        if len(group) == 2 and len(reds) == 1 and len(greens) == 1:
            # Full two-commit pattern
            red = reds[0]
            green = greens[0]

            # RED must precede GREEN
            if red["date"] >= green["date"]:
                failures.append(
                    f"M{m_num} in {plan_id}: RED commit "
                    f"({red['sha'][:8]}, {red['date']}) does not precede "
                    f"GREEN commit ({green['sha'][:8]}, {green['date']})"
                )

            # RED must be test-only
            if not _is_test_only(red["files"]):
                failures.append(
                    f"{red['sha'][:8]}: RED commit for M{m_num} touches "
                    f"non-test files: {red['files']}"
                )

            # RED must have Decision: test-first
            if not red["has_decision"]:
                failures.append(
                    f"{red['sha'][:8]}: RED commit missing Decision: trailer"
                )

            # GREEN must include checkbox flip
            if not _has_checkbox_flip(green["files"]):
                failures.append(
                    f"{green['sha'][:8]}: GREEN commit for M{m_num} does "
                    f"not include plan file (checkbox flip missing)"
                )

            # GREEN should include implementation or notes
            if not (_has_implementation(green["files"])
                    or _has_verdict_notes(green["files"])):
                failures.append(
                    f"{green['sha'][:8]}: GREEN commit for M{m_num} has "
                    f"neither implementation files nor verdict notes"
                )

            # GREEN must have Decision: trailer
            if not green["has_decision"]:
                failures.append(
                    f"{green['sha'][:8]}: GREEN commit missing "
                    f"Decision: trailer"
                )

            continue  # Valid pattern

        # Any other pattern is a violation
        if others:
            other_shas = ", ".join(c["sha"][:8] for c in others)
            failures.append(
                f"M{m_num} in {plan_id}: {len(others)} commit(s) with "
                f"unrecognized subject pattern "
                f"({other_shas}). Only RED (test(m<N>): ... — RED) "
                f"and GREEN (flip(m<N>): ...) commits are allowed."
            )

        if len(reds) > 1:
            failures.append(
                f"M{m_num} in {plan_id}: {len(reds)} RED commits "
                f"— expected at most 1"
            )

        if len(greens) > 1:
            failures.append(
                f"M{m_num} in {plan_id}: {len(greens)} GREEN commits "
                f"— expected at most 1"
            )

        if len(group) > 2:
            failures.append(
                f"M{m_num} in {plan_id}: {len(group)} total commits "
                f"— expected exactly 2 (RED + GREEN)"
            )

    assert not failures, (
        "Commit model violations — each milestone must follow the "
        "RED→GREEN two-commit pattern:\n\n" + "\n\n".join(failures)
    )
