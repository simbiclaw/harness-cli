"""Structural test: Commit authority — only the Arbiter commits.

Promoted from documentation to structural test on 2026-07-30.

Per docs/conventions/pev-loop.md § Commit authority:
  - Only the Arbiter commits. P, E, V never commit.
  - One milestone, two commits: the Arbiter's RED commit (failing
    test) then GREEN commit (implementation + verdict + flip).
  - Every commit must have Plan: and Decision: trailers.

This test verifies:
  1. pev-loop.md documents the commit authority rule
  2. The hook blocks git commit from non-Arbiter sessions (Guard 6)
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PEV_LOOP_MD = REPO_ROOT / "docs" / "conventions" / "pev-loop.md"
HOOK_FILE = REPO_ROOT / ".claude" / "hooks" / "pre_tool_use.py"


def test_commit_authority_documented():
    """pev-loop.md must document that only the Arbiter commits."""
    text = PEV_LOOP_MD.read_text()

    required = [
        "only the arbiter commits",
        "commit authority",
        "p, e, and v never commit",
        "two commits",
    ]

    missing = [p for p in required if p not in text.lower()]

    assert not missing, (
        "pev-loop.md § Commit authority missing required statements:\n"
        + "\n".join(f"  - '{m}'" for m in missing)
    )


def test_commit_authority_hook_guard_exists():
    """pre_tool_use.py must block git commit from non-Arbiter sessions."""
    text = HOOK_FILE.read_text()

    # Guard 6 must exist
    assert "Guard 6" in text, (
        "pre_tool_use.py missing Guard 6 (commit authority)"
    )

    # Must check _is_arbiter() before allowing commits
    assert "COMMIT_LIKE_RE" in text, (
        "Guard 6 must detect commit-like commands"
    )
    assert "_is_arbiter()" in text, (
        "Guard 6 must check _is_arbiter() before blocking commits"
    )

    # The guard must reference the documentation
    assert "commit authority" in text.lower(), (
        "Guard 6 must reference 'commit authority' from pev-loop.md"
    )


def test_commit_authority_applies_to_all_agents():
    """The commit block applies to all non-Arbiter sessions, including
    subagents spawned via the Agent tool.
    """
    text = HOOK_FILE.read_text()

    # The guard message should mention P, E, V explicitly
    has_agent_mention = (
        "p, e, and v" in text.lower()
        or "subagent" in text.lower()
        or "subagents" in text.lower()
        or "pev" in text.lower()
    )
    assert has_agent_mention, (
        "Guard 6 rejection message must reference P/E/V subagents "
        "so the blocked agent knows why its commit was rejected"
    )
