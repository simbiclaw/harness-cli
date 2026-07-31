"""Worktree utilities for PEV Execute-phase sandboxing.

Provides isolated git worktrees for milestone implementation. The implementer
works in /tmp/impl-<sha>/, and verified state merges back after subagent B
returns CONFIRMED.

Usage:
    from pev_worktree import create_worktree, run_tests_in_worktree, merge_worktree, remove_worktree

    wt = create_worktree("abc123")
    result = run_tests_in_worktree(wt, "tests/test_X.py::test_name")
    if result.passed:
        merge_worktree(wt, "main")
    remove_worktree(wt)
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORKTREE_PREFIX = "/tmp/impl-"


@dataclass
class TestResult:
    """Result of running tests in a worktree."""

    passed: bool
    exit_code: int
    stdout: str
    stderr: str


def create_worktree(commit_sha: str) -> Path:
    """Create an isolated git worktree at /tmp/impl-<short-sha>/.

    Args:
        commit_sha: Full or short commit SHA to base the worktree on.

    Returns:
        Path to the created worktree directory.

    Raises:
        RuntimeError: If worktree creation fails.
    """
    short = commit_sha[:8]
    worktree_path = Path(f"{WORKTREE_PREFIX}{short}")

    if worktree_path.exists():
        remove_worktree(worktree_path)

    result = subprocess.run(
        ["git", "worktree", "add", str(worktree_path), commit_sha],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to create worktree at {worktree_path}: {result.stderr}"
        )

    return worktree_path


def run_tests_in_worktree(
    worktree_path: Path, test_id: str, timeout: int = 120
) -> TestResult:
    """Run a specific test in the worktree.

    Args:
        worktree_path: Path to the worktree.
        test_id: Pytest test ID (e.g., "tests/test_X.py::test_name").
        timeout: Timeout in seconds.

    Returns:
        TestResult with pass/fail, exit code, stdout, stderr.
    """
    # Sync dependencies first
    sync = subprocess.run(
        ["uv", "sync", "--dev"],
        capture_output=True,
        text=True,
        cwd=worktree_path,
        timeout=timeout,
    )
    if sync.returncode != 0:
        return TestResult(
            passed=False,
            exit_code=sync.returncode,
            stdout=sync.stdout,
            stderr=f"uv sync failed: {sync.stderr}",
        )

    result = subprocess.run(
        ["uv", "run", "pytest", test_id, "-v", "--no-header", "-x"],
        capture_output=True,
        text=True,
        cwd=worktree_path,
        timeout=timeout,
    )

    return TestResult(
        passed=result.returncode == 0,
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def merge_worktree(worktree_path: Path, target_branch: str) -> bool:
    """Merge the worktree's changes back into the target branch.

    Args:
        worktree_path: Path to the worktree.
        target_branch: Branch to merge into.

    Returns:
        True if merge succeeded, False otherwise.
    """
    # Get the worktree's current branch/commit
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=worktree_path,
        timeout=10,
    )
    if result.returncode != 0:
        return False

    wt_head = result.stdout.strip()

    # Merge into target branch from the main repo
    result = subprocess.run(
        ["git", "merge", "--no-ff", "-m", f"merge worktree {worktree_path.name}", wt_head],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=30,
    )
    return result.returncode == 0


def remove_worktree(worktree_path: Path) -> None:
    """Remove a worktree and its administrative files.

    Args:
        worktree_path: Path to the worktree to remove.
    """
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree_path)],
        capture_output=True,
        cwd=REPO_ROOT,
        timeout=15,
    )
    # Fallback: force-remove if git worktree remove fails
    if worktree_path.exists():
        shutil.rmtree(worktree_path, ignore_errors=True)


def list_worktrees() -> list[Path]:
    """List all active PEV worktrees under /tmp/impl-*."""
    tmp = Path("/tmp")
    return sorted(tmp.glob("impl-*"))


def cleanup_stale_worktrees() -> list[Path]:
    """Remove any PEV worktrees not registered with git.

    Returns:
        List of removed worktree paths.
    """
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=10,
    )
    registered = set()
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            registered.add(Path(line.split(" ", 1)[1]))

    removed = []
    for wt in list_worktrees():
        if wt not in registered:
            remove_worktree(wt)
            removed.append(wt)
    return removed
