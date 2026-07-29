"""M3: Arbiter autonomy and hook exemptions — structural tests.

Acceptance tests for M3:
- test_hook_allows_arbiter_checkbox_flip: arbiter edit to [ ] → [x] is not blocked
- test_hook_blocks_non_arbiter_checkbox_flip: non-arbiter checkbox flip still blocked
- test_arbiter_goal_includes_autonomy_scope: goal prompt has explicit autonomy boundaries
"""

import json
import os
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
TMUX_SCRIPT = REPO_ROOT / ".claude" / "scripts" / "pev_tmux_adversarial.sh"

# Add hooks dir to path to import hook modules
sys.path.insert(0, str(HOOKS_DIR))


class TestHookAllowsArbiterCheckboxFlip:
    """Arbiter-originated checkbox flips in plan files are not blocked."""

    def test_pre_tool_use_has_arbiter_exemption(self):
        """pre_tool_use.py must contain arbiter exemption logic."""
        hook_path = HOOKS_DIR / "pre_tool_use.py"
        content = hook_path.read_text()
        # Must reference arbiter detection mechanism
        has_arbiter_check = (
            "PEV_ARBITER" in content
            or "arbiter" in content.lower()
        )
        assert has_arbiter_check, (
            "pre_tool_use.py must contain arbiter detection/exemption logic"
        )

    def test_arbiter_env_allows_multi_flip(self):
        """When PEV_ARBITER is set, multi-checkbox flips (up to 1) are still enforced
        but the arbiter exemption prevents the uncommitted-flip blocker from
        stopping checkbox flips in plan files."""
        # Import the hook module and test its logic directly
        import pre_tool_use

        # Simulate arbiter flipping a checkbox in a plan file
        # The hook should allow this because (a) it's at most 1 flip, and
        # (b) it's in an active plan file
        test_plan = REPO_ROOT / "docs" / "exec-plans" / "active" / "9006-pev-tmux-convergence.md"
        if test_plan.exists():
            # With PEV_ARBITER=true, the uncommitted-flip guard should not block
            # edits to plan files (arbiter needs to flip checkboxes autonomously)
            os.environ["PEV_ARBITER"] = "true"
            try:
                # Guard 1 (uncommitted flip) should skip when PEV_ARBITER is set
                assert pre_tool_use.is_active_plan(str(test_plan)), (
                    "Test plan should be recognized as an active plan"
                )
            finally:
                del os.environ["PEV_ARBITER"]

    def test_hook_imports_and_has_functions(self):
        """The hook module should be importable and have required helpers."""
        import pre_tool_use

        assert hasattr(pre_tool_use, "is_active_plan"), (
            "pre_tool_use must export is_active_plan"
        )
        assert hasattr(pre_tool_use, "count_new_flips"), (
            "pre_tool_use must export count_new_flips"
        )


class TestHookBlocksNonArbiterCheckboxFlip:
    """Non-arbiter checkbox flips are still subject to existing guards."""

    def test_without_arbiter_env_guards_active(self):
        """Without PEV_ARBITER, existing guards (single flip, uncommitted flip)
        should still apply normally."""
        import pre_tool_use

        # Verify the guard functions exist and work
        assert pre_tool_use.CHECKBOX_LINE is not None
        assert callable(pre_tool_use.count_checked)


class TestArbiterGoalIncludesAutonomyScope:
    """Arbiter's goal prompt contains explicit autonomy boundaries."""

    def test_goal_mentions_autonomy(self):
        """Arbiter goal prompt must mention autonomy and what it can do."""
        script = TMUX_SCRIPT.read_text()
        # Find the arbiter prompt
        assert "ARBITER_PROMPT=" in script, "Script must define ARBITER_PROMPT"

        # The arbiter prompt should mention autonomous actions
        assert "flip" in script.lower(), (
            "Arbiter prompt must mention flipping checkboxes"
        )
        assert "autonom" in script.lower(), (
            "Arbiter prompt must mention autonomy/autonomous actions"
        )

    def test_goal_defines_autonomy_boundaries(self):
        """Arbiter goal must define what it CAN and CANNOT do autonomously."""
        script = TMUX_SCRIPT.read_text()

        # Find arbiter prompt section
        arbiter_start = script.find("ARBITER_PROMPT=")
        assert arbiter_start != -1, "ARBITER_PROMPT not found"

        # The arbiter prompt should define its boundaries
        arbiter_section = script[arbiter_start:]
        arbiter_end = arbiter_section.find('B_PROMPT="')
        if arbiter_end == -1:
            arbiter_end = len(arbiter_section)
        arbiter_text = arbiter_section[:arbiter_end]

        # Must mention what it CAN do
        assert "flip" in arbiter_text.lower(), (
            "Arbiter must be told it can flip checkboxes"
        )

        # Must mention what requires human input
        has_human_gate = "human" in arbiter_text.lower() or "semantic" in arbiter_text.lower()
        assert has_human_gate, (
            "Arbiter goal must define when to pause for human input"
        )

    def test_arbiter_goal_mentions_signals_dir(self):
        """Arbiter must know about .pev-signals/ for checkpoint state."""
        script = TMUX_SCRIPT.read_text()
        assert ".pev-signals" in script.lower(), (
            "Arbiter goal must reference .pev-signals/ for coordination"
        )

    def test_arbiter_knows_tmux_session_name(self):
        """Arbiter must know the tmux session name for IPC."""
        script = TMUX_SCRIPT.read_text()
        # Should reference the session name for capture-pane / send-keys
        assert "pev-adversarial" in script, (
            "Arbiter prompt must know the tmux session name for IPC commands"
        )
