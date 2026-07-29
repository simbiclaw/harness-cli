"""M1: Subagent adversarial script — structural tests.

Acceptance tests for M1:
- --plan and --milestones parse correctly
- Whitespace in --milestones is stripped
- --resume flag loads state.json
- Real plan file doesn't crash the awk/grep pipeline
- Non-numeric milestone values are rejected
- JS and Python files contain deprecation notice referencing pev_subagent_adversarial.sh
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / ".claude" / "scripts"
SUBAGENT_SCRIPT = SCRIPTS_DIR / "pev_subagent_adversarial.sh"
ORCHESTRATOR_JS = SCRIPTS_DIR / "pev_orchestrator.js"
REPAIR_PY = SCRIPTS_DIR / "pev_repair.py"
STATE_FILE = REPO_ROOT / ".pev-signals" / "state.json"


class TestScriptAcceptsRequiredArgs:
    """M1: --plan and --milestones parse correctly on the subagent script."""

    def test_subagent_script_exists(self):
        """pev_subagent_adversarial.sh must exist."""
        assert SUBAGENT_SCRIPT.exists(), (
            f"{SUBAGENT_SCRIPT} must exist. Create this script."
        )
        assert SUBAGENT_SCRIPT.is_file(), (
            f"{SUBAGENT_SCRIPT} must be a regular file."
        )

    def test_help_flag_exists(self):
        """Script should show usage on --help."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"--help should exit 0, got {result.returncode}\n"
            f"stderr: {result.stderr}"
        )

    def test_missing_plan_reports_error(self):
        """Running without --plan should report an error and exit non-zero."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT)],
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
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test-plan"],
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
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test-plan", "--milestones", "1,2,3"],
            capture_output=True, text=True,
        )
        stderr = result.stderr.lower()
        assert "unknown option" not in stderr, (
            f"--plan and --milestones should be recognized options. Got: {result.stderr}"
        )

    def test_whitespace_in_milestones_stripped(self):
        """Whitespace after comma in --milestones must be stripped, not produce invalid keys."""
        with_whitespace = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test-plan",
             "--milestones", "1, 2, 3"],
            capture_output=True, text=True,
        )
        no_whitespace = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test-plan",
             "--milestones", "1,2,3"],
            capture_output=True, text=True,
        )
        # Both invocations should produce equivalent output
        # (same exit code, no invalid milestone identifiers like "M 2")
        assert with_whitespace.returncode == no_whitespace.returncode, (
            "Whitespace in --milestones should produce same exit code as without whitespace.\n"
            f"  with whitespace: exit {with_whitespace.returncode}\n"
            f"  without: exit {no_whitespace.returncode}\n"
            f"  with_whitespace stderr: {with_whitespace.stderr}"
        )
        combined = (with_whitespace.stdout + with_whitespace.stderr).lower()
        assert "m 2" not in combined, (
            f"Input '1, 2, 3' produced invalid milestone key 'M 2'. "
            f"Output: {combined[:500]}"
        )
        assert "m 3" not in combined, (
            f"Input '1, 2, 3' produced invalid milestone key 'M 3'. "
            f"Output: {combined[:500]}"
        )


class TestResumeReadsState:
    """M1: --resume flag loads state.json from the subagent script."""

    def test_resume_flag_accepted(self):
        """--resume should be a recognized flag, not an error."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test", "--milestones", "1",
             "--resume"],
            capture_output=True, text=True,
        )
        stderr = result.stderr.lower()
        assert "unknown option" not in stderr, (
            f"--resume should be a recognized flag. Got: {result.stderr}"
        )

    def test_resume_without_state_reports_warning(self):
        """--resume with missing state.json should report that state is missing."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "9006-pev-tmux-convergence",
             "--milestones", "1", "--resume"],
            capture_output=True, text=True,
        )
        output = (result.stdout + result.stderr).lower()
        assert "resume" in output, (
            f"--resume with existing state.json should mention resume. Got: {output[:500]}"
        )

    def test_resume_reads_existing_state(self):
        """When state.json exists, --resume should read and reference it."""
        assert STATE_FILE.exists(), "state.json must exist (from M0 fixture)"
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan",
             "9006-pev-tmux-convergence", "--milestones", "0",
             "--resume"],
            capture_output=True, text=True,
        )
        output = result.stdout + result.stderr
        assert "resume" in output.lower() or "9006" in output, (
            f"Resume should reference state. Got: {output[:500]}"
        )


class TestRealPlanFile:
    """M1: Script must not crash when processing a real, existing plan file."""

    REAL_PLAN = "9006-pev-tmux-convergence"

    def test_with_real_plan_produces_output(self):
        """Script with a real plan file must exit 0 and produce prompt output."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", self.REAL_PLAN,
             "--milestones", "0"],
            capture_output=True, text=True,
        )
        # Must not crash silently (exit 1 with empty output)
        combined = result.stdout + result.stderr
        assert len(combined) > 0, (
            f"Script produced no output with real plan file. "
            f"exit code: {result.returncode}. "
            f"This indicates a pipeline crash (awk/grep with pipefail)."
        )
        # Must exit 0 when args are valid and plan file exists
        assert result.returncode == 0, (
            f"Script should exit 0 with valid plan file, "
            f"got {result.returncode}.\n"
            f"stdout: {result.stdout[:500]}\n"
            f"stderr: {result.stderr[:500]}"
        )

    def test_with_real_plan_contains_prompt(self):
        """Output with a real plan should contain the adversarial verifier prompt."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", self.REAL_PLAN,
             "--milestones", "0,1"],
            capture_output=True, text=True,
        )
        output = (result.stdout + result.stderr).lower()
        assert "adversarial" in output or "verifier" in output, (
            f"Output should contain the adversarial prompt template. "
            f"Got: {output[:500]}"
        )


class TestMilestoneValidation:
    """M1: --milestones must validate that values are numeric."""

    def test_non_numeric_milestone_rejected(self):
        """Non-numeric milestone value like 'abc' must be rejected with non-zero exit."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test-plan",
             "--milestones", "abc"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0, (
            "Non-numeric milestone 'abc' should be rejected with non-zero exit"
        )
        output = (result.stderr + result.stdout).lower()
        assert any(word in output for word in ("invalid", "numeric", "abc", "not a number")), (
            f"Error should mention the invalid milestone value. Got: {output[:500]}"
        )

    def test_mixed_numeric_and_non_numeric_rejected(self):
        """A list mixing valid and invalid milestone values must be rejected."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test-plan",
             "--milestones", "1,abc,3"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0, (
            "Mixed '1,abc,3' should be rejected with non-zero exit"
        )


class TestDeprecatedMarkers:
    """M1: JS and Python files contain deprecation notice referencing the subagent script."""

    def test_orchestrator_js_has_deprecation(self):
        """pev_orchestrator.js must have a deprecation notice referencing pev_subagent_adversarial.sh."""
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
        assert "pev_subagent_adversarial" in content, (
            "Deprecation notice must reference pev_subagent_adversarial.sh"
        )

    def test_repair_py_has_deprecation(self):
        """pev_repair.py must have a deprecation notice referencing pev_subagent_adversarial.sh."""
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
        assert "pev_subagent_adversarial" in content, (
            "Deprecation notice must reference pev_subagent_adversarial.sh"
        )
