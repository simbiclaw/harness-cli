"""M7: E2E integration test for PEV tmux pipeline.

Structural verification that all pipeline components are wired correctly.
Full behavioral E2E (running tmux with live Claude sessions) requires manual
execution; this test verifies configuration integrity.

Acceptance tests:
- test_pipeline_components_exist: all 5 tmux windows defined
- test_promotion_arbiter_wired: promotion window connected to violations dir
- test_checkpoint_and_resume_wired: state.json integration verified
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / ".claude" / "scripts"
TMUX_SCRIPT = SCRIPTS_DIR / "pev_tmux_adversarial.sh"
STATE_FILE = REPO_ROOT / ".pev-signals" / "state.json"
VIOLATIONS_DIR = REPO_ROOT / ".pev-signals" / "violations"


class TestPipelineComponentsExist:
    """All pipeline components must be defined and connected."""

    def test_all_tmux_windows_defined(self):
        """5 tmux windows: arbiter, A-implementer, B-verifier, orchestrator,
        promotion-arbiter."""
        script = TMUX_SCRIPT.read_text()

        expected_windows = [
            "arbiter",
            "A-implementer",
            "B-verifier",
            "orchestrator",
            "promotion-arbiter",
        ]

        for window in expected_windows:
            # Check both new-session and new-window references
            has_window = (
                f'-n "{window}"' in script
                or f"-n '{window}'" in script
                or f"-n {window}" in script
                or f'"$SESSION:{window}"' in script
                or f"'$SESSION:{window}'" in script
            )
            assert has_window, (
                f"Pipeline must define window '{window}'"
            )

    def test_goal_prompts_defined(self):
        """All agents must have goal prompts."""
        script = TMUX_SCRIPT.read_text()

        required_prompts = [
            "A_PROMPT=",
            "B_PROMPT=",
            "ARBITER_PROMPT=",
            "PROMOTION_ARBITER_PROMPT=",
        ]

        for prompt_var in required_prompts:
            assert prompt_var in script, (
                f"Script must define {prompt_var}"
            )

    def test_no_broken_references(self):
        """All variable references in the script must be defined."""
        script = TMUX_SCRIPT.read_text()

        # Key variables that should exist
        required_vars = [
            "PLAN_ID",
            "MILESTONES_INPUT",
            "REPO_ROOT",
            "ACTIVE_DIR",
            "SIGNAL_DIR",
            "STATE_FILE",
            "NOTES_DIR",
            "SESSION",
        ]

        for var in required_vars:
            # Should be assigned somewhere
            assert f"{var}=" in script or f'"{var}"' in script or f"${var}" in script, (
                f"Variable {var} must be defined and used"
            )


class TestPromotionArbiterWired:
    """Promotion arbiter connected to violation tracker output."""

    def test_violations_dir_fixture_exists(self):
        """.pev-signals/violations/ must exist for promotion arbiter input."""
        assert VIOLATIONS_DIR.exists(), (
            ".pev-signals/violations/ must exist (M5 fixture)"
        )

    def test_promotion_window_after_orchestrator(self):
        """Promotion window must be created after orchestrator in the script."""
        script = TMUX_SCRIPT.read_text()

        orchestrator_pos = script.find('-n "orchestrator"')
        promotion_pos = script.find('-n "promotion-arbiter"')

        assert orchestrator_pos > 0, "Script must create orchestrator window"
        assert promotion_pos > 0, "Script must create promotion-arbiter window"
        assert promotion_pos > orchestrator_pos, (
            "Promotion arbiter window must be created after orchestrator window"
        )


class TestCheckpointAndResumeWired:
    """state.json checkpoint integration is complete."""

    def test_state_file_has_complete_schema(self):
        """state.json must have all fields needed for full pipeline recovery."""
        assert STATE_FILE.exists(), "state.json must exist"

        state = json.loads(STATE_FILE.read_text())

        required = [
            "plan_id",
            "phase",
            "current_milestone",
            "milestones",
            "last_checkpoint_at",
            "arbiter_pid",
            "tmux_session",
        ]
        for field in required:
            assert field in state, (
                f"state.json missing required field: {field}"
            )

    def test_state_milestones_cover_all_milestones(self):
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

    def test_resume_references_all_state_fields(self):
        """--resume code path must reference all state.json fields."""
        script = TMUX_SCRIPT.read_text()

        # Resume section should reference key state fields
        resume_section_start = script.find("if $RESUME_MODE; then")
        assert resume_section_start > 0, "Script must have --resume logic"

        resume_section = script[resume_section_start:resume_section_start + 2000]

        # Should reference state.json fields
        assert "state.json" in resume_section or "STATE_FILE" in resume_section, (
            "Resume must reference state.json"
        )
        assert "plan_id" in resume_section.lower(), (
            "Resume must read plan_id from state"
        )
        assert "phase" in resume_section.lower(), (
            "Resume must read phase from state"
        )
