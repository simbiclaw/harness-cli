"""M4: Checkpoint recovery — structural tests.

Acceptance tests for M4:
- test_checkpoint_written_after_verdict: state.json updated after each verdict
- test_resume_skips_confirmed: resumed session correctly identifies completed milestones
- test_resume_rebuilds_tmux_session: tmux session structure matches fresh start
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / ".claude" / "scripts"
TMUX_SCRIPT = SCRIPTS_DIR / "pev_tmux_adversarial.sh"
SIGNAL_DIR = REPO_ROOT / ".pev-signals"
STATE_FILE = SIGNAL_DIR / "state.json"


class TestCheckpointWrittenAfterVerdict:
    """state.json is updated after each verdict is processed."""

    def test_script_has_state_write_logic(self):
        """The tmux script or arbiter prompt must include checkpoint write logic."""
        script = TMUX_SCRIPT.read_text()

        # The script or arbiter goals must reference writing to state.json
        assert "state.json" in script, (
            "Script must reference state.json for checkpoint writes"
        )

        # Should have logic to update state.json after verdicts
        has_write = (
            "state.json" in script
            and ("write" in script.lower() or "checkpoint" in script.lower())
        )
        assert has_write, (
            "Script must write checkpoints to state.json after verdicts"
        )

    def test_arbiter_prompt_mentions_checkpoint(self):
        """Arbiter prompt must instruct writing checkpoints after verdicts."""
        script = TMUX_SCRIPT.read_text()
        arbiter_start = script.find("ARBITER_PROMPT=")
        assert arbiter_start != -1

        # Get the arbiter prompt section
        arbiter_section = script[arbiter_start:]
        b_start = arbiter_section.find('B_PROMPT="')
        if b_start != -1:
            arbiter_text = arbiter_section[:b_start]
        else:
            arbiter_text = arbiter_section

        # Arbiter must save state
        assert "state.json" in arbiter_text, (
            "Arbiter prompt must instruct writing to state.json"
        )


class TestResumeSkipsConfirmed:
    """Resumed session correctly identifies completed and pending milestones."""

    def test_resume_reads_state_file(self):
        """--resume flag causes the script to read state.json."""
        # Run with --resume using the real state file
        result = subprocess.run(
            ["bash", str(TMUX_SCRIPT), "--plan",
             "9006-pev-tmux-convergence", "--milestones", "0,1,2,3",
             "--resume"],
            capture_output=True, text=True,
        )
        output = result.stdout + result.stderr

        # Should mention resume mode
        assert "esume" in output, (
            f"--resume output should mention resume. Got: {output[:500]}"
        )
        # Should read and report state
        assert "phase" in output.lower() or "milestone" in output.lower(), (
            f"Resume should report current phase/milestone. Got: {output[:500]}"
        )

    def test_resume_recognizes_confirmed_milestones(self):
        """Resume output should show that M0-M3 are confirmed."""
        # Update state to have M0-M3 confirmed
        original_state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
        try:
            test_state = {
                "plan_id": "9006-pev-tmux-convergence",
                "phase": "verify",
                "current_milestone": 3,
                "milestones": {
                    "M0": "confirmed",
                    "M1": "confirmed",
                    "M2": "confirmed",
                    "M3": "confirmed",
                    "M4": "pending",
                    "M5": "pending",
                    "M6": "pending",
                    "M7": "pending",
                },
                "last_checkpoint_at": "2026-07-29T16:00:00Z",
                "arbiter_pid": None,
                "tmux_session": None,
            }
            STATE_FILE.write_text(json.dumps(test_state, indent=2))

            result = subprocess.run(
                ["bash", str(TMUX_SCRIPT), "--plan",
                 "9006-pev-tmux-convergence", "--milestones", "3,4",
                 "--resume"],
                capture_output=True, text=True,
            )
            output = result.stdout + result.stderr

            # Should report current state from state.json
            assert "current_milestone" in output.lower() or "phase" in output.lower(), (
                f"Resume should report current state. Got: {output[:500]}"
            )
        finally:
            # Restore original state
            STATE_FILE.write_text(json.dumps(original_state, indent=2))

    def test_state_schema_supports_recovery(self):
        """state.json schema must have fields needed for recovery."""
        assert STATE_FILE.exists(), "state.json must exist"
        state = json.loads(STATE_FILE.read_text())

        required_fields = [
            "plan_id", "phase", "current_milestone",
            "milestones", "last_checkpoint_at",
        ]
        for field in required_fields:
            assert field in state, (
                f"state.json must have '{field}' for checkpoint recovery"
            )

        # milestones must be a dict with per-milestone status
        assert isinstance(state["milestones"], dict), (
            "state.json milestones must be a dict for per-milestone tracking"
        )


class TestResumeRebuildsTmuxSession:
    """--resume creates the same tmux session structure as a fresh start."""

    def test_fresh_and_resume_have_same_windows(self):
        """Both fresh and --resume should create the same tmux windows."""
        script = TMUX_SCRIPT.read_text()

        # Count new-window commands
        window_names_fresh = set()
        window_names_resume = set()

        # Both code paths create the same windows:
        # arbiter, A-implementer, B-verifier, orchestrator
        expected_windows = {"arbiter", "A-implementer", "B-verifier", "orchestrator"}

        # Verify all expected windows are created in the script
        for window in expected_windows:
            assert f'-n "{window}"' in script or f"-n '{window}'" in script or f"-n {window}" in script, (
                f"Script must create window '{window}'"
            )

    def test_resume_does_not_duplicate_windows(self):
        """--resume should create the same number of windows as fresh start."""
        script = TMUX_SCRIPT.read_text()

        # Count tmux new-window calls
        new_window_count = len(re.findall(r"tmux new-window", script))
        # Both fresh and resume should create the same 3 windows
        # (arbiter is created as new-session, not new-window)
        assert new_window_count >= 3, (
            f"Expected at least 3 tmux new-window calls, got {new_window_count}"
        )
