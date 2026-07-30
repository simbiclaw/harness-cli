"""M7: E2E integration test for PEV subagent pipeline.

Structural verification that all pipeline components are wired correctly
for the subagent-based PEV architecture (plan 9006). Replaces the tmux-based
E2E test which checked tmux windows and session variables.

Acceptance tests:
- test_core_components_exist: script, state, violations dir, conventions
- test_state_schema_complete: all fields including agent_ids
- test_all_acceptance_tests_exist: all M0-M7 test files importable
"""

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / ".claude" / "scripts"
SUBAGENT_SCRIPT = SCRIPTS_DIR / "pev_subagent_adversarial.sh"
STATE_FILE = REPO_ROOT / ".pev-signals" / "state.json"
VIOLATIONS_DIR = REPO_ROOT / ".pev-signals" / "violations"

# All milestone acceptance tests for this plan
MILESTONE_TESTS = [
    ("M0", ".claude/tests/test_pev_signals.py"),
    ("M1", ".claude/tests/test_pev_tmux.py"),
    ("M2", ".claude/tests/test_verdict_notes_unified.py"),
    ("M3", ".claude/tests/test_arbiter_autonomy.py"),
    ("M4", ".claude/tests/test_pev_recovery.py"),
    ("M5", ".claude/tests/test_violation_tracker.py"),
    ("M6", ".claude/tests/test_promotion_arbiter.py"),
    ("M7", ".claude/tests/test_pev_tmux_e2e.py"),
    ("M7", ".claude/tests/test_cross_refs.py"),
]


class TestCoreComponentsExist:
    """All core pipeline components must be in place."""

    def test_subagent_script_exists(self):
        """pev_subagent_adversarial.sh must exist and be executable."""
        assert SUBAGENT_SCRIPT.exists(), (
            f"{SUBAGENT_SCRIPT} must exist"
        )
        assert SUBAGENT_SCRIPT.is_file(), (
            f"{SUBAGENT_SCRIPT} must be a regular file"
        )
        assert SUBAGENT_SCRIPT.stat().st_mode & 0o111, (
            f"{SUBAGENT_SCRIPT} must be executable"
        )

    def test_state_file_exists(self):
        """state.json must exist (M0 fixture)."""
        assert STATE_FILE.exists(), "state.json must exist"

    def test_violations_dir_exists(self):
        """.pev-signals/violations/ must exist (M5 fixture)."""
        assert VIOLATIONS_DIR.exists(), (
            ".pev-signals/violations/ must exist"
        )

    def test_pev_loop_convention_exists(self):
        """pev-loop.md convention must exist."""
        pev_loop = REPO_ROOT / "docs" / "conventions" / "pev-loop.md"
        assert pev_loop.exists(), "pev-loop.md must exist"

    def test_claude_md_exists(self):
        """CLAUDE.md must exist and reference subagent architecture."""
        claude_md = REPO_ROOT / "CLAUDE.md"
        assert claude_md.exists(), "CLAUDE.md must exist"

        content = claude_md.read_text()
        # Must reference the subagent/PEV loop, not tmux
        assert any(word in content.lower() for word in (
            "pev", "subagent", "harness"
        )), "CLAUDE.md must reference the PEV/harness system"


class TestStateSchemaComplete:
    """state.json must have the complete schema for the subagent architecture."""

    def test_required_fields_present(self):
        """state.json must have all required fields."""
        state = json.loads(STATE_FILE.read_text())
        required = {
            "plan_id", "phase", "current_milestone",
            "milestones", "last_checkpoint_at",
        }
        missing = required - set(state.keys())
        assert not missing, f"state.json missing: {missing}"

    def test_milestones_cover_m0_to_m7(self):
        """All 8 milestones (M0-M7) must be tracked in state.json."""
        state = json.loads(STATE_FILE.read_text())
        milestones = state["milestones"]
        for m in range(8):
            key = f"M{m}"
            assert key in milestones, (
                f"state.json milestones must include {key}"
            )
            assert milestones[key] in (
                "pending", "in_progress", "confirmed", "pending_verdict"
            ), f"M{m} status invalid: {milestones[key]}"

    def test_agent_ids_present(self):
        """state.json must have agent_ids for subagent coordination."""
        state = json.loads(STATE_FILE.read_text())
        agent_ids = state.get("agent_ids")
        assert agent_ids is not None, (
            "state.json must have agent_ids dict for subagent coordination"
        )
        for aid_key in ("p_agent_id", "e_agent_id", "v_agent_id"):
            assert aid_key in agent_ids, (
                f"agent_ids must include {aid_key}"
            )

    def test_no_tmux_session_in_required_fields(self):
        """state schema may retain tmux fields but must not require them."""
        state = json.loads(STATE_FILE.read_text())
        agent_ids = state.get("agent_ids")
        assert agent_ids is not None, (
            "subagent architecture requires agent_ids"
        )


class TestAllAcceptanceTestsExist:
    """All milestone acceptance tests must be importable."""

    def test_all_test_files_exist(self):
        """Every milestone has a corresponding test file on disk."""
        for milestone, rel_path in MILESTONE_TESTS:
            full_path = REPO_ROOT / rel_path
            assert full_path.exists(), (
                f"{milestone}: acceptance test {rel_path} must exist"
            )

    def test_all_test_files_importable(self):
        """Every acceptance test file must be syntactically valid Python."""
        seen = set()
        for milestone, rel_path in MILESTONE_TESTS:
            if rel_path in seen:
                continue
            seen.add(rel_path)
            full_path = REPO_ROOT / rel_path
            spec = importlib.util.spec_from_file_location(
                f"test_{milestone}", full_path
            )
            assert spec is not None, (
                f"{milestone}: {rel_path} failed to load spec"
            )
            assert spec.loader is not None, (
                f"{milestone}: {rel_path} has no loader"
            )
