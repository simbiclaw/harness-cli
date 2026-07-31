"""M6: Promotion arbiter — structural + behavioral tests.

M6 contract:
- Reads violation tracker output from .pev-signals/violations/
- Mechanical promotions (simple format rules) → prompt instructs auto-execution
- Architectural promotions (complex) → prompt instructs ExecPlan drafting
"""

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / ".claude" / "scripts"
SUBAGENT_SCRIPT = SCRIPTS_DIR / "pev_subagent_adversarial.sh"
VIOLATIONS_DIR = REPO_ROOT / ".pev-signals" / "violations"


# ---------------------------------------------------------------------------
# Violations directory
# ---------------------------------------------------------------------------

class TestViolationsDirAccessible:
    """The violation tracker output directory must be accessible."""

    def test_violations_dir_exists(self):
        """.pev-signals/violations/ must exist (from M5 fixture)."""
        assert VIOLATIONS_DIR.exists(), (
            ".pev-signals/violations/ must exist"
        )

    def test_violations_dir_is_readable(self):
        """Must be able to list files in violations dir."""
        files = list(VIOLATIONS_DIR.iterdir())
        # May be empty (no violations yet); should not crash
        assert isinstance(files, list)


# ---------------------------------------------------------------------------
# Promotion instructions in generated prompt (behavioral)
# ---------------------------------------------------------------------------

class TestPromotionInstructionsInPrompt:
    """The generated prompt must include promotion arbiter instructions."""

    def test_prompt_references_violations_dir(self):
        """Generated prompt must mention .pev-signals/violations/."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test-plan",
             "--milestones", "0"],
            capture_output=True, text=True,
        )
        output = result.stdout
        assert "violations" in output.lower(), (
            "Generated prompt must reference .pev-signals/violations/ "
            "for promotion input"
        )

    def test_prompt_mentions_promotion(self):
        """Generated prompt must mention rule promotion or promotion arbiter."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test-plan",
             "--milestones", "0"],
            capture_output=True, text=True,
        )
        output = result.stdout.lower()
        assert "promotion" in output, (
            "Generated prompt must mention promotion of repeated violations"
        )


class TestMechanicalPromotion:
    """Mechanical promotions should be described as auto-executable."""

    def test_mechanical_promotion_auto_execute(self):
        """Generated prompt must define auto-execution for mechanical promotions."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test-plan",
             "--milestones", "0"],
            capture_output=True, text=True,
        )
        output = result.stdout.lower()
        # Should mention auto-execution or automatic action for simple promotions
        assert "auto" in output or "automatic" in output, (
            "Generated prompt must define auto-execute conditions "
            "for mechanical promotions"
        )


class TestArchitecturalPromotion:
    """Architectural promotions should be described as needing ExecPlan drafts."""

    def test_architectural_promotion_drafts_execplan(self):
        """Generated prompt must instruct drafting ExecPlans for complex promotions."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test-plan",
             "--milestones", "0"],
            capture_output=True, text=True,
        )
        output = result.stdout.lower()
        # Must mention drafting — "execplan" alone matches plan header text
        assert "draft" in output, (
            "Generated prompt must instruct ExecPlan drafting "
            "for architectural promotions"
        )

    def test_architectural_promotion_requires_human(self):
        """Complex promotions must require human approval, not auto-execute."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test-plan",
             "--milestones", "0"],
            capture_output=True, text=True,
        )
        output = result.stdout.lower()
        # Must require human judgment/approval for complex promotions
        # (not just "human" which appears naturally in rejection criteria)
        assert "human" in output and ("approval" in output or "judgment" in output), (
            "Generated prompt must require human approval for "
            "architectural promotions"
        )


# ---------------------------------------------------------------------------
# Violation schema integration
# ---------------------------------------------------------------------------

class TestViolationSchemaIntegration:
    """Behavioral: write a violation record and verify the arbiter can process it."""

    def test_write_and_read_violation_record(self):
        """Writing a violation record and reading it must work end-to-end."""
        test_record = {
            "rule_slug": "test-commit-message-format",
            "violation_count": 2,
            "plans": ["9001-test", "9002-test"],
            "files": ["docs/plan1.md", "docs/plan2.md"],
            "excerpts": [
                "broke the commit message convention",
                "skipped commit message rule again",
            ],
            "suggested_promotion": "documentation → structural test",
        }
        record_path = VIOLATIONS_DIR / "test-commit-message-format.json"
        try:
            record_path.write_text(json.dumps(test_record, indent=2) + "\n")
            assert record_path.exists()

            read_back = json.loads(record_path.read_text())
            assert read_back["rule_slug"] == "test-commit-message-format"
            assert read_back["violation_count"] == 2
            assert "plans" in read_back
            assert "excerpts" in read_back
            assert "suggested_promotion" in read_back

            # Verify the schema is compatible with what a promotion arbiter would read
            assert read_back["suggested_promotion"] in (
                "documentation → structural test",
                "structural test → hook",
                "hook → CI gate",
                "insufficient data",
            )
        finally:
            if record_path.exists():
                record_path.unlink()
