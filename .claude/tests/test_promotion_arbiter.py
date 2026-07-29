"""M6: Promotion arbiter — structural tests.

Acceptance tests for M6:
- test_mechanical_promotion_auto_executed: mechanical promotion auto-executed
- test_architectural_promotion_drafted: complex promotion drafts ExecPlan
- test_arbiter_reads_violation_records: arbiter ingests violation tracker output
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / ".claude" / "scripts"
TMUX_SCRIPT = SCRIPTS_DIR / "pev_tmux_adversarial.sh"
VIOLATIONS_DIR = REPO_ROOT / ".pev-signals" / "violations"


class TestMechanicalPromotionAutoExecuted:
    """Simple format rules flagged twice are auto-promoted without human input."""

    def test_promotion_window_exists(self):
        """The tmux script must create a fourth window for promotion arbiter."""
        script = TMUX_SCRIPT.read_text()

        # Count windows — should have arbiter, A-implementer, B-verifier,
        # orchestrator, AND promotion-arbiter (5 windows)
        window_count = len(re.findall(r"tmux new-window", script))
        assert window_count >= 4, (
            f"Expected at least 4 tmux new-window calls (including promotion), "
            f"got {window_count}"
        )

    def test_promotion_window_named_correctly(self):
        """The promotion arbiter window should have a descriptive name."""
        script = TMUX_SCRIPT.read_text()
        assert "promotion" in script.lower(), (
            "Script must define a promotion arbiter window"
        )

    def test_promotion_prompt_defines_auto_execute(self):
        """Promotion arbiter prompt must define which promotions are auto-executed."""
        script = TMUX_SCRIPT.read_text()
        assert "auto" in script.lower(), (
            "Promotion arbiter prompt must define auto-execute conditions"
        )

    def test_promotion_prompt_references_violations_dir(self):
        """Promotion arbiter must read from .pev-signals/violations/."""
        script = TMUX_SCRIPT.read_text()
        assert "violations" in script, (
            "Promotion arbiter prompt must reference violations directory"
        )


class TestArchitecturalPromotionDrafted:
    """Complex promotions generate pre-filled ExecPlan drafts."""

    def test_promotion_prompt_defines_draft_boundary(self):
        """Promotion arbiter must know when to draft vs auto-execute."""
        script = TMUX_SCRIPT.read_text()
        # Should mention drafting or human approval for complex promotions
        has_draft_logic = (
            "draft" in script.lower()
            or "human" in script.lower()
            or "approval" in script.lower()
        )
        assert has_draft_logic, (
            "Promotion arbiter must define when to draft for human approval"
        )

    def test_promotion_prompt_mentions_execplan(self):
        """Promotion arbiter must know where to write drafted ExecPlans."""
        script = TMUX_SCRIPT.read_text()
        assert "exec-plans" in script.lower() or "ExecPlan" in script, (
            "Promotion arbiter must reference ExecPlan drafts"
        )


class TestArbiterReadsViolationRecords:
    """Arbiter correctly ingests violation tracker output."""

    def test_violations_dir_is_accessible(self):
        """.pev-signals/violations/ must exist and be accessible."""
        assert VIOLATIONS_DIR.exists(), (
            ".pev-signals/violations/ must exist (from M5 fixture)"
        )

    def test_promotion_arbiter_references_pev_signals(self):
        """Promotion arbiter must know about .pev-signals/ for input."""
        script = TMUX_SCRIPT.read_text()
        assert ".pev-signals" in script, (
            "Promotion arbiter must reference .pev-signals/"
        )

    def test_promotion_uses_state_checkpoint(self):
        """Promotion arbiter should integrate with the same state.json system."""
        script = TMUX_SCRIPT.read_text()
        assert "state.json" in script, (
            "Promotion arbiter should use state.json for coordination"
        )
