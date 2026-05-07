"""Verify pre-commit hooks fire correctly.

Tests the commit-msg format hook with both valid and invalid messages
by invoking pre-commit's run mode with a synthetic commit message file.

See docs/exec-plans/active/0001-bootstrap-harness.md milestone M4.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_pre_commit_commit_msg(msg: str) -> subprocess.CompletedProcess:
    """Run the commit-msg pre-commit hook on a temp file with *msg*."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(msg)
        tmp = f.name
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pre_commit",
                "run",
                "commit-msg-format",
                "--hook-stage",
                "commit-msg",
                "--commit-msg-file",
                tmp,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=REPO_ROOT,
        )
    finally:
        Path(tmp).unlink(missing_ok=True)
    return result


def test_commit_msg_rejects_bad_format() -> None:
    """A commit message without Plan:/Decision: trailers should be rejected."""
    bad_msg = "wip"
    result = _run_pre_commit_commit_msg(bad_msg)
    assert result.returncode != 0, (
        f"Expected non-zero exit for bad message, got stdout:\n{result.stdout}"
    )


def test_commit_msg_accepts_good_format() -> None:
    """A commit message with proper trailers should be accepted."""
    good_msg = """\
feat(scaffold): add initial project structure

Plan: docs/exec-plans/active/0001-bootstrap-harness.md#milestone-4
Decision: verify pre-commit hook
"""
    result = _run_pre_commit_commit_msg(good_msg)
    assert result.returncode == 0, (
        f"Expected zero exit for good message, got stderr:\n{result.stderr}"
    )
