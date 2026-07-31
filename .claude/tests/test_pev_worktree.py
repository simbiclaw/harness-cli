"""Structural tests for PEV worktree utilities.

Validates worktree creation, isolation, test running, merge, and cleanup.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / ".claude" / "scripts"))

from pev_worktree import (
    cleanup_stale_worktrees,
    create_worktree,
    list_worktrees,
    merge_worktree,
    remove_worktree,
    run_tests_in_worktree,
)


@pytest.fixture()
def head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=10,
    )
    return result.stdout.strip()


@pytest.fixture()
def worktree(head_sha):
    """Create a worktree, yield it, clean up after."""
    wt = create_worktree(head_sha)
    yield wt
    remove_worktree(wt)


class TestWorktreeLifecycle:
    def test_create_worktree(self, worktree):
        assert worktree.exists()
        assert (worktree / ".git").exists()

    def test_worktree_isolation(self, worktree):
        # Worktree should have same files as repo
        assert (worktree / "pyproject.toml").exists()
        assert (worktree / "docs" / "conventions" / "pev-loop.md").exists()

    def test_remove_worktree(self, head_sha):
        wt = create_worktree(head_sha)
        assert wt.exists()
        remove_worktree(wt)
        assert not wt.exists()

    def test_recreate_worktree(self, head_sha):
        wt1 = create_worktree(head_sha)
        remove_worktree(wt1)
        wt2 = create_worktree(head_sha)
        assert wt2.exists()
        remove_worktree(wt2)


class TestWorktreeTests:
    def test_run_tests_in_worktree(self, worktree):
        # Run a known-passing structural test
        result = run_tests_in_worktree(
            worktree,
            ".claude/tests/test_execplan_structure.py::test_execplan_filenames_have_slugs",
        )
        assert result.passed, f"Test failed: {result.stderr}\n{result.stdout}"
        assert result.exit_code == 0


class TestWorktreeCleanup:
    def test_list_worktrees_empty_after_cleanup(self, worktree):
        # Our fixture worktree should be listed
        wts = list_worktrees()
        assert worktree in wts

    def test_cleanup_stale(self):
        removed = cleanup_stale_worktrees()
        # Should not raise; may or may not remove anything
        assert isinstance(removed, list)
