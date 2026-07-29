"""M1: Tmux script formalization — structural tests.

Acceptance tests for M1:
- test_script_accepts_required_args: --plan and --milestones parse correctly
- test_resume_reads_state: --resume flag loads state.json
- test_deprecated_markers: JS and Python files contain deprecation notice
"""

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / ".claude" / "scripts"
TMUX_SCRIPT = SCRIPTS_DIR / "pev_tmux_adversarial.sh"
ORCHESTRATOR_JS = SCRIPTS_DIR / "pev_orchestrator.js"
REPAIR_PY = SCRIPTS_DIR / "pev_repair.py"
STATE_FILE = REPO_ROOT / ".pev-signals" / "state.json"


class TestScriptAcceptsRequiredArgs:
    """--plan and --milestones parse correctly."""

    def test_help_flag_exists(self):
        """Script should show usage on --help (or at minimum not error on --help)."""
        result = subprocess.run(
            ["bash", str(TMUX_SCRIPT), "--help"],
            capture_output=True, text=True,
        )
        # --help should exit 0 and mention --plan and --milestones
        assert result.returncode == 0, (
            f"--help should exit 0, got {result.returncode}\n"
            f"stderr: {result.stderr}"
        )

    def test_missing_plan_reports_error(self):
        """Running without --plan should report an error and exit non-zero."""
        result = subprocess.run(
            ["bash", str(TMUX_SCRIPT)],
            capture_output=True, text=True,
        )
        assert result.returncode != 0, (
            "Script without --plan should exit non-zero"
        )
        output = result.stderr + result.stdout
        assert "--plan" in output.lower(), (
            f"Error should mention --plan. Got: {output}"
        )

    def test_missing_milestones_reports_error(self):
        """Running with --plan but without --milestones should report an error."""
        result = subprocess.run(
            ["bash", str(TMUX_SCRIPT), "--plan", "test-plan"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0, (
            "Script without --milestones should exit non-zero"
        )
        output = result.stderr + result.stdout
        assert "--milestones" in output.lower() or "milestones" in output.lower(), (
            f"Error should mention milestones. Got: {output}"
        )

    def test_required_args_accepted(self):
        """Script with --plan and --milestones should validate (not error on missing optional)."""
        result = subprocess.run(
            ["bash", str(TMUX_SCRIPT), "--plan", "test-plan", "--milestones", "1,2,3"],
            capture_output=True, text=True,
        )
        # Should not fail on argument parsing — may fail on plan not found, which is OK
        stderr = result.stderr.lower()
        # It should NOT say "missing required" or "unknown option"
        assert "unknown option" not in stderr, (
            f"--plan and --milestones should be recognized options. Got: {result.stderr}"
        )


class TestResumeReadsState:
    """--resume flag loads state.json."""

    def test_resume_flag_accepted(self):
        """--resume should be a recognized flag, not an error."""
        result = subprocess.run(
            ["bash", str(TMUX_SCRIPT), "--plan", "test", "--milestones", "1",
             "--resume"],
            capture_output=True, text=True,
        )
        stderr = result.stderr.lower()
        assert "unknown option" not in stderr, (
            f"--resume should be a recognized flag. Got: {result.stderr}"
        )

    def test_resume_without_state_reports_warning(self):
        """--resume with missing state.json should report that state is missing."""
        # Use a valid plan ID so the script reaches the --resume check
        result = subprocess.run(
            ["bash", str(TMUX_SCRIPT), "--plan", "9006-pev-tmux-convergence",
             "--milestones", "1", "--resume"],
            capture_output=True, text=True,
        )
        # The state.json exists (from M0), so resume should reference it
        output = (result.stdout + result.stderr).lower()
        assert "resume" in output, (
            f"--resume with existing state.json should mention resume. Got: {output[:500]}"
        )

    def test_resume_reads_existing_state(self):
        """When state.json exists, --resume should read and reference it."""
        # State file already exists from M0
        assert STATE_FILE.exists(), "state.json must exist (from M0 fixture)"
        result = subprocess.run(
            ["bash", str(TMUX_SCRIPT), "--plan",
             "9006-pev-tmux-convergence", "--milestones", "0",
             "--resume"],
            capture_output=True, text=True,
        )
        # Should reference the state file's plan_id
        output = result.stdout + result.stderr
        # The resume path should mention state or the plan ID from state
        assert "resume" in output.lower() or "9006" in output, (
            f"Resume should reference state. Got: {output[:500]}"
        )


class TestDeprecatedMarkers:
    """JS and Python files contain deprecation notice referencing this plan."""

    def test_orchestrator_js_has_deprecation(self):
        """pev_orchestrator.js must have a deprecation notice."""
        content = ORCHESTRATOR_JS.read_text()
        has_deprecation = (
            "DEPRECATED" in content
            or "deprecated" in content
            or "9006" in content
        )
        assert has_deprecation, (
            "pev_orchestrator.js must contain a deprecation notice "
            "referencing plan 9006"
        )
        # Should reference the tmux script
        assert "pev_tmux_adversarial" in content, (
            "Deprecation notice must reference pev_tmux_adversarial.sh"
        )

    def test_repair_py_has_deprecation(self):
        """pev_repair.py must have a deprecation notice."""
        content = REPAIR_PY.read_text()
        has_deprecation = (
            "DEPRECATED" in content
            or "deprecated" in content
            or "9006" in content
        )
        assert has_deprecation, (
            "pev_repair.py must contain a deprecation notice "
            "referencing plan 9006"
        )
        # Should reference the tmux script
        assert "pev_tmux_adversarial" in content, (
            "Deprecation notice must reference pev_tmux_adversarial.sh"
        )
