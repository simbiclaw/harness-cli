"""Structural tests for the PEV autonomous repair loop.

Validates failure classification, action routing, and notes generation.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / ".claude" / "scripts"))

from pev_repair import (
    Action,
    FailureClass,
    RepairDecision,
    decide_action,
    diagnose_failure,
)


class TestFailureClassification:
    def test_mechanical_default(self):
        fc = diagnose_failure("test assertion failed on line 42", None, "test", 1)
        assert fc == FailureClass.MECHANICAL

    def test_mechanical_hint(self):
        fc = diagnose_failure("some failure", "mechanical", "test", 1)
        assert fc == FailureClass.MECHANICAL

    def test_semantic_hint(self):
        fc = diagnose_failure("design quality issue", "semantic", "test", 1)
        assert fc == FailureClass.SEMANTIC

    def test_constraint_violation_hint(self):
        fc = diagnose_failure("exceeded scope", "constraint-violation", "test", 1)
        assert fc == FailureClass.CONSTRAINT_VIOLATION

    def test_constraint_signals_in_text(self):
        fc = diagnose_failure(
            "path src/argus/io/client.py is outside the Allowed Writes",
            None, "test", 1,
        )
        assert fc == FailureClass.CONSTRAINT_VIOLATION

    def test_semantic_signals_in_text(self):
        fc = diagnose_failure(
            "the design quality is subjective and needs judgment",
            None, "test", 1,
        )
        assert fc == FailureClass.SEMANTIC


class TestActionRouting:
    def test_mechanical_retries(self):
        d = decide_action(FailureClass.MECHANICAL, 1, "test failed")
        assert d.action == Action.RETRY
        assert d.milestone == 1

    def test_semantic_creates_human_todo(self):
        d = decide_action(FailureClass.SEMANTIC, 3, "design needs review")
        assert d.action == Action.HUMAN_TODO
        assert d.notes_entry is not None
        assert "[human-todo]" in d.notes_entry

    def test_constraint_violation_updates_constraints(self):
        d = decide_action(FailureClass.CONSTRAINT_VIOLATION, 2, "exceeded scope")
        assert d.action == Action.UPDATE_CONSTRAINTS
        assert d.notes_entry is not None
        assert "[deviation]" in d.notes_entry
        assert "What the plan said" in d.notes_entry
        assert "What the code revealed" in d.notes_entry
        assert "Conservative choice" in d.notes_entry
        assert "Revisit" in d.notes_entry


class TestRepairDecision:
    def test_decision_has_required_fields(self):
        d = decide_action(FailureClass.MECHANICAL, 5, "some reason")
        assert isinstance(d, RepairDecision)
        assert d.action is not None
        assert d.failure_class is not None
        assert d.milestone == 5
        assert d.reason == "some reason"

    def test_repair_classifies_and_routes(self):
        """Combined test: classify then route for all three classes."""
        # Mechanical
        fc = diagnose_failure("assertion error", None, "test", 1)
        d = decide_action(fc, 1, "assertion error")
        assert d.action == Action.RETRY

        # Semantic
        fc = diagnose_failure("subjective design quality", None, "test", 2)
        d = decide_action(fc, 2, "subjective design quality")
        assert d.action == Action.HUMAN_TODO

        # Constraint violation
        fc = diagnose_failure("outside the allowed writes", None, "test", 3)
        d = decide_action(fc, 3, "outside the allowed writes")
        assert d.action == Action.UPDATE_CONSTRAINTS
