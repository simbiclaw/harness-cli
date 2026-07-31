"""M3: Arbiter autonomy and hook exemptions — structural + behavioral tests.

M3 contract:
- pre_tool_use.py has PEV_ARBITER detection (_is_arbiter()) for Guards 0, 0.5, 1, 2.5, 6
- Behavioral: PEV_ARBITER=true bypasses guards that would block arbiter actions
- Guards 2.5 (PEV agent gate) and 6 (commit authority) also check _is_arbiter()
- pev-loop.md documents arbiter autonomy scope
"""

import importlib
import io
import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
HOOK_PATH = HOOKS_DIR / "pre_tool_use.py"
SCRIPTS_DIR = REPO_ROOT / ".claude" / "scripts"
SUBAGENT_SCRIPT = SCRIPTS_DIR / "pev_subagent_adversarial.sh"

# Add hooks dir to path to import hook modules
sys.path.insert(0, str(HOOKS_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reimport_hook():
    """Force-reimport pre_tool_use to clear cached state."""
    for mod in list(sys.modules.keys()):
        if mod.startswith("pre_tool_use"):
            del sys.modules[mod]
    import pre_tool_use as m
    return m


def _run_hook_main(tool_name: str, tool_input: dict) -> dict:
    """Run pre_tool_use.main() with a simulated event and return the JSON output."""
    hook = _reimport_hook()
    event = json.dumps({
        "tool_name": tool_name,
        "tool_input": tool_input,
    })
    old_stdin = sys.stdin
    old_stdout = sys.stdout
    try:
        sys.stdin = io.StringIO(event)
        sys.stdout = io.StringIO()
        hook.main()
        output = sys.stdout.getvalue()
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout
    return json.loads(output.strip())


# ---------------------------------------------------------------------------
# Arbiter detection
# ---------------------------------------------------------------------------

class TestArbiterDetection:
    """Behavioral: _is_arbiter() correctly detects PEV_ARBITER env var."""

    def test_arbiter_detected_when_env_true(self):
        """PEV_ARBITER=true makes _is_arbiter() return True."""
        hook = _reimport_hook()
        os.environ["PEV_ARBITER"] = "true"
        try:
            assert hook._is_arbiter() is True
        finally:
            del os.environ["PEV_ARBITER"]

    def test_not_arbiter_when_env_false(self):
        """PEV_ARBITER=false makes _is_arbiter() return False."""
        hook = _reimport_hook()
        os.environ["PEV_ARBITER"] = "false"
        try:
            assert hook._is_arbiter() is False
        finally:
            del os.environ["PEV_ARBITER"]

    def test_not_arbiter_when_env_unset(self):
        """No PEV_ARBITER makes _is_arbiter() return False."""
        hook = _reimport_hook()
        os.environ.pop("PEV_ARBITER", None)
        assert hook._is_arbiter() is False

    def test_arbiter_case_insensitive_check(self):
        """PEV_ARBITER=True (mixed case) is also detected."""
        hook = _reimport_hook()
        os.environ["PEV_ARBITER"] = "True"
        try:
            assert hook._is_arbiter() is True
        finally:
            del os.environ["PEV_ARBITER"]


# ---------------------------------------------------------------------------
# Guard 0: single checkbox flip
# ---------------------------------------------------------------------------

class TestGuard0CheckboxFlip:
    """Guard 0: single checkbox flip enforced for non-arbiter, skipped for arbiter."""

    def test_guard0_arbiter_can_flip(self):
        """PEV_ARBITER=true: arbiter flipping checkboxes is not blocked."""
        os.environ["PEV_ARBITER"] = "true"
        try:
            # Edit to active plan — would normally trigger Guard 0
            result = _run_hook_main("Edit", {
                "file_path": str(REPO_ROOT / "docs" / "exec-plans" / "active"
                                 / "9006-pev-tmux-convergence.md"),
                "old_string": "- [ ] M0",
                "new_string": "- [x] M0",
            })
            assert result.get("continue") is True, (
                f"Arbiter checkbox flip should be allowed. Got: {result}"
            )
        finally:
            os.environ.pop("PEV_ARBITER", None)


class TestGuard05VerificationGate:
    """Guard 0.5: PEV verification gate skipped for arbiter."""

    def test_guard05_has_arbiter_exemption(self):
        """Guard 0.5 source code shows _is_arbiter() check."""
        content = HOOK_PATH.read_text()
        assert "Guard 0.5" in content
        assert "_is_arbiter()" in content


# ---------------------------------------------------------------------------
# Guard 1: uncommitted flip blocks code edits
# ---------------------------------------------------------------------------

class TestGuard1UncommittedFlip:
    """Guard 1: uncommitted flip blocks code edits for non-arbiter."""

    def test_guard1_has_arbiter_exemption(self):
        """Guard 1 source code shows _is_arbiter() check."""
        content = HOOK_PATH.read_text()
        assert "Guard 1" in content
        assert "_is_arbiter()" in content


# ---------------------------------------------------------------------------
# Guard 2.5: PEV agent gate
# ---------------------------------------------------------------------------

class TestGuard25AgentGate:
    """Guard 2.5: PEV agent gate blocks code edits unless agents spawned."""

    def test_guard25_exists_in_hook(self):
        """Guard 2.5 is present in pre_tool_use.py with an _is_arbiter() check."""
        content = HOOK_PATH.read_text()
        assert "Guard 2.5" in content, "Guard 2.5 section must exist"
        assert "_is_arbiter_safe_path" in content, (
            "Guard 2.5 must use _is_arbiter_safe_path"
        )
        assert "_pev_agents_spawned" in content, (
            "Guard 2.5 must check _pev_agents_spawned"
        )

    def test_is_arbiter_safe_path_active_plan(self):
        """_is_arbiter_safe_path returns True for active plan files."""
        hook = _reimport_hook()
        plan_path = str(REPO_ROOT / "docs" / "exec-plans" / "active"
                        / "9006-pev-tmux-convergence.md")
        assert hook._is_arbiter_safe_path(plan_path) is True

    def test_is_arbiter_safe_path_notes(self):
        """_is_arbiter_safe_path returns True for notes files."""
        hook = _reimport_hook()
        notes_path = str(REPO_ROOT / "docs" / "exec-plans" / "active"
                         / "9006-pev-tmux-convergence-notes" / "M0.md")
        assert hook._is_arbiter_safe_path(notes_path) is True

    def test_is_arbiter_safe_path_signals(self):
        """_is_arbiter_safe_path returns True for .pev-signals/ paths."""
        hook = _reimport_hook()
        sig_path = str(REPO_ROOT / ".pev-signals" / "state.json")
        assert hook._is_arbiter_safe_path(sig_path) is True

    def test_is_arbiter_safe_path_src_not_safe(self):
        """_is_arbiter_safe_path returns False for src/ paths."""
        hook = _reimport_hook()
        src_path = str(REPO_ROOT / "src" / "argus" / "cli" / "main.py")
        assert hook._is_arbiter_safe_path(src_path) is False


# ---------------------------------------------------------------------------
# Guard 6: commit authority
# ---------------------------------------------------------------------------

class TestGuard6CommitAuthority:
    """Guard 6: only arbiter may commit."""

    def test_guard6_exists_in_hook(self):
        """Guard 6 section is present in pre_tool_use.py."""
        content = HOOK_PATH.read_text()
        assert "Guard 6" in content, "Guard 6 section must exist"
        assert "_is_arbiter()" in content, (
            "Guard 6 must use _is_arbiter()"
        )

    def test_arbiter_can_commit(self):
        """PEV_ARBITER=true: arbiter can commit."""
        os.environ["PEV_ARBITER"] = "true"
        try:
            result = _run_hook_main("Bash", {
                "command": "git commit -m 'test: arbiter commit'",
            })
            assert result.get("continue") is True, (
                f"Arbiter commit should be allowed. Got: {result}"
            )
        finally:
            os.environ.pop("PEV_ARBITER", None)

    def test_non_arbiter_commit_blocked(self):
        """Without PEV_ARBITER, git commit is blocked."""
        os.environ.pop("PEV_ARBITER", None)
        result = _run_hook_main("Bash", {
            "command": "git commit -m 'test: non-arbiter commit'",
        })
        assert result.get("continue") is False, (
            f"Non-arbiter commit should be blocked. Got: {result}"
        )
        assert "commit" in result.get("reason", "").lower(), (
            f"Block reason must mention 'commit'. Got: {result}"
        )


# ---------------------------------------------------------------------------
# Guard 2: sensitive path (regression — must still work)
# ---------------------------------------------------------------------------

class TestSensitivePathGuard:
    """Guard 2: sensitive path guard must still be present and functional."""

    def test_sensitive_path_check_exists(self):
        """Sensitive path checking logic still present."""
        content = HOOK_PATH.read_text()
        assert "Guard 2" in content
        assert "has_resolved_steering_for" in content

    def test_sensitive_path_patterns_loaded(self):
        """Sensitive path patterns load from .claude/sensitive-paths.txt."""
        hook = _reimport_hook()
        patterns = hook.load_sensitive_patterns()
        assert len(patterns) > 0
        assert any("hooks" in p for p in patterns)


# ---------------------------------------------------------------------------
# pev-loop.md documentation
# ---------------------------------------------------------------------------

class TestPevLoopDocs:
    """pev-loop.md documents arbiter autonomy scope."""

    def test_pev_loop_mentions_arbiter(self):
        """pev-loop.md must reference arbiter and its autonomy."""
        pev_loop = REPO_ROOT / "docs" / "conventions" / "pev-loop.md"
        assert pev_loop.exists(), "pev-loop.md must exist"
        content = pev_loop.read_text()
        assert "arbiter" in content.lower(), (
            "pev-loop.md must mention the arbiter"
        )
        assert "PEV_ARBITER" in content, (
            "pev-loop.md must document the PEV_ARBITER env var"
        )

    def test_pev_loop_documents_guard_exemptions(self):
        """pev-loop.md must describe which guards the arbiter bypasses."""
        pev_loop = REPO_ROOT / "docs" / "conventions" / "pev-loop.md"
        content = pev_loop.read_text()
        assert "checkbox" in content.lower() or "commit" in content.lower(), (
            "pev-loop.md must document arbiter's guard exemptions"
        )
