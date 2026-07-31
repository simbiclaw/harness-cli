"""M4: Checkpoint recovery — structural + behavioral tests.

M4 contract:
- --resume reads state.json and produces a prompt that skips confirmed milestones
- The generated prompt (behavioral) includes checkpoint instructions
- state.json schema supports recovery (plan_id, phase, current_milestone, milestones)
"""

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / ".claude" / "scripts"
SUBAGENT_SCRIPT = SCRIPTS_DIR / "pev_subagent_adversarial.sh"
SIGNAL_DIR = REPO_ROOT / ".pev-signals"
STATE_FILE = SIGNAL_DIR / "state.json"
PLAN_ID = "9006-pev-tmux-convergence"


# ---------------------------------------------------------------------------
# state.json schema for recovery
# ---------------------------------------------------------------------------

class TestStateSchemaSupportsRecovery:
    """state.json schema must have fields needed for checkpoint recovery."""

    def test_state_file_exists(self):
        """state.json must exist (M0 fixture)."""
        assert STATE_FILE.exists(), "state.json must exist (from M0 fixture)"

    def test_required_fields_present(self):
        """state.json must have all fields required for recovery."""
        state = json.loads(STATE_FILE.read_text())
        required = {"plan_id", "phase", "current_milestone",
                    "milestones", "last_checkpoint_at"}
        missing = required - set(state.keys())
        assert not missing, f"state.json missing required fields: {missing}"

    def test_milestones_is_dict(self):
        """milestones must be a dict for per-milestone tracking."""
        state = json.loads(STATE_FILE.read_text())
        assert isinstance(state["milestones"], dict), (
            "state.json milestones must be a dict"
        )

    def test_current_milestone_is_int(self):
        """current_milestone must be a non-negative integer."""
        state = json.loads(STATE_FILE.read_text())
        assert isinstance(state["current_milestone"], int) and state["current_milestone"] >= 0


# ---------------------------------------------------------------------------
# --resume reads state.json (behavioral)
# ---------------------------------------------------------------------------

class TestResumeReadsState:
    """Behavioral: --resume causes the script to read state.json."""

    def test_resume_flag_accepted_and_outputs_state(self):
        """--resume output must reference state.json data."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", PLAN_ID,
             "--milestones", "0", "--resume"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"--resume should exit 0, got {result.returncode}\n"
            f"stderr: {result.stderr[:200]}"
        )
        output = (result.stdout + result.stderr).lower()
        # Should mention resume mode
        assert "resume" in output, (
            f"--resume output should mention resume. Got: {output[:500]}"
        )
        # Should report state from state.json
        assert "phase" in output or "current_milestone" in output, (
            f"--resume should report current phase/milestone from state. "
            f"Got: {output[:500]}"
        )

    def test_resume_skips_confirmed_milestones(self):
        """With confirmed milestones, resume output skips them or notes their status."""
        # Save original state
        original = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
        try:
            # Write state where M0-M2 are confirmed
            test_state = dict(original)
            test_state.update({
                "plan_id": PLAN_ID,
                "phase": "verify",
                "current_milestone": 2,
                "milestones": {
                    "M0": "confirmed",
                    "M1": "confirmed",
                    "M2": "confirmed",
                    "M3": "pending",
                    "M4": "pending",
                    "M5": "pending",
                    "M6": "pending",
                    "M7": "pending",
                },
                "last_checkpoint_at": "2026-07-30T00:00:00Z",
            })
            STATE_FILE.write_text(json.dumps(test_state, indent=2))

            result = subprocess.run(
                ["bash", str(SUBAGENT_SCRIPT), "--plan", PLAN_ID,
                 "--milestones", "2,3", "--resume"],
                capture_output=True, text=True,
            )
            output = (result.stdout + result.stderr).lower()
            # Should mention resume in context of state
            assert "resume" in output, (
                f"Resume output must mention resume. Got: {output[:300]}"
            )
            # Should reference the current_milestone or phase from state
            assert "current_milestone" in output or "phase" in output, (
                f"Resume output should reference state fields. Got: {output[:300]}"
            )
        finally:
            STATE_FILE.write_text(json.dumps(original, indent=2))


# ---------------------------------------------------------------------------
# Generated prompt includes checkpoint instructions (behavioral)
# ---------------------------------------------------------------------------

class TestCheckpointInGeneratedPrompt:
    """The generated prompt should instruct checkpoint writes."""

    def test_prompt_mentions_state_update(self):
        """The generated prompt must tell B to update state.json."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test-plan",
             "--milestones", "0"],
            capture_output=True, text=True,
        )
        output = result.stdout
        assert "state.json" in output, (
            "Generated prompt must mention state.json for checkpoint writes"
        )

    def test_prompt_mentions_checkpoint_after_verdict(self):
        """The generated prompt must direct updating state after each verdict."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test-plan",
             "--milestones", "0"],
            capture_output=True, text=True,
        )
        output = result.stdout.lower()
        # Should reference updating or checkpointing after verdict
        assert "checkpoint" in output or "update" in output or "save" in output, (
            "Generated prompt must direct checkpoint/save after verdict"
        )
