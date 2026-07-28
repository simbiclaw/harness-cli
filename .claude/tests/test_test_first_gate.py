"""Structural test: test-first gate.

Verifies that for milestone commits touching src/, the milestone's
Acceptance Test file exists in git history at or before that commit.
Enforces the red-before-green invariant from verification-floor.md rule #1.

See docs/conventions/verification-floor.md and docs/conventions/pev-loop.md.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACTIVE_DIR = REPO_ROOT / "docs" / "exec-plans" / "active"

PLAN_TRAILER_RE = re.compile(r"^Plan:\s*(docs/exec-plans/\S+?)(?:#|\s|$)", re.MULTILINE)
ACCEPTANCE_TEST_RE = re.compile(r"Acceptance Test:\s*`?([^\`\n]+?)`?\s*$", re.MULTILINE)
MILESTONE_RE = re.compile(r"^### M(\d+)[\s—–-]", re.MULTILINE)

# Look back this many days for milestone commits
GIT_LOG_SINCE = "90 days ago"


def _git_log() -> list[tuple[str, str, list[str]]]:
    """Return list of (sha, message, [changed_files]) for recent commits."""
    try:
        result = subprocess.run(
            [
                "git", "log",
                f"--since={GIT_LOG_SINCE}",
                "--name-only",
                "--pretty=tformat:%x00%H%x00%B%x00",
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
        if len(parts) < 2:
            continue
        sha = parts[0].strip()
        # Find where message ends and files begin (blank line separator)
        msg_lines = []
        files = []
        in_files = False
        for line in parts[1:]:
            if line.strip() == "" and not in_files and msg_lines:
                in_files = True
                continue
            if in_files:
                if line.strip():
                    files.append(line.strip())
            else:
                msg_lines.append(line)
        commits.append((sha, "\n".join(msg_lines), files))
    return commits


def _file_existed_at(sha: str, file_path: str) -> bool:
    """Check if a file existed at a given commit."""
    try:
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{sha}:{file_path}"],
            capture_output=True,
            cwd=REPO_ROOT,
            timeout=10,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _get_acceptance_tests(plan_path: Path) -> dict[int, str]:
    """Extract milestone number → acceptance test file from a plan."""
    if not plan_path.exists():
        return {}
    text = plan_path.read_text()
    result: dict[int, str] = {}

    parts = MILESTONE_RE.split(text)
    for i in range(1, len(parts) - 1, 2):
        m_num = int(parts[i])
        body = parts[i + 1]
        next_m = MILESTONE_RE.search(body)
        if next_m:
            body = body[: next_m.start()]

        m = ACCEPTANCE_TEST_RE.search(body)
        if m:
            test_ref = m.group(1).strip()
            # Extract file path from test reference (e.g. tests/test_X.py::test_name)
            test_file = test_ref.split("::")[0].strip("`").strip()
            result[m_num] = test_file

    return result


def _milestone_from_commit(msg: str) -> int | None:
    """Extract milestone number from commit message Plan trailer fragment."""
    m = re.search(r"#milestone-(\d+)", msg)
    if m:
        return int(m.group(1))
    m = re.search(r"\bM(\d+)\b", msg)
    if m:
        return int(m.group(1))
    return None


def test_test_first_enforced():
    """Test files committed before or with src/ changes for each milestone."""
    failures: list[str] = []

    commits = _git_log()
    if not commits:
        return  # No history to check

    # Cache: plan_path -> milestone -> test_file
    plan_tests: dict[str, dict[int, str]] = {}

    for sha, msg, files in commits:
        # Only check commits with a Plan trailer
        plan_m = PLAN_TRAILER_RE.search(msg)
        if not plan_m:
            continue

        plan_rel = plan_m.group(1).split("#")[0]
        if "ad-hoc" in plan_rel:
            continue

        # Does this commit touch src/?
        src_files = [f for f in files if f.startswith("src/")]
        if not src_files:
            continue

        # Get the milestone's acceptance test
        if plan_rel not in plan_tests:
            plan_tests[plan_rel] = _get_acceptance_tests(REPO_ROOT / plan_rel)
        tests = plan_tests[plan_rel]

        m_num = _milestone_from_commit(msg)
        if m_num is None or m_num not in tests:
            continue

        test_file = tests[m_num]

        # The test file must exist at this commit or any ancestor
        if not _file_existed_at(sha, test_file):
            failures.append(
                f"{sha[:8]}: commit touches src/ for M{m_num} but acceptance "
                f"test '{test_file}' does not exist at this commit. "
                f"Test-first violated: red commits must precede green commits "
                f"(docs/conventions/verification-floor.md rule #1)."
            )

    assert not failures, "Test-first violations:\n" + "\n".join(
        f"  - {f}" for f in failures
    )
