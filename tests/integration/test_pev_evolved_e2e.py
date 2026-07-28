"""End-to-end integration test for the evolved PEV loop.

Validates that all PEV components work together:
- Milestone constraints parse and validate
- Pre-execution gate blocks/allows correctly
- Implementation notes format validates
- Test-first gate analyzes git history
- Adversarial verification gate checks Decision Log
- Worktree utilities create/isolate/merge/cleanup
- Orchestrator script has correct structure
- Repair loop classifies and routes correctly

This is the final gate before the plan archives.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_pytest(test_path: str) -> tuple[bool, str]:
    """Run a pytest file and return (passed, output)."""
    result = subprocess.run(
        ["uv", "run", "pytest", test_path, "-v", "--no-header", "-x"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=120,
    )
    return result.returncode == 0, result.stdout + result.stderr


class TestPEVComponentsExist:
    """All PEV component files exist."""

    def test_constraint_test_exists(self):
        assert (REPO_ROOT / ".claude/tests/test_milestone_constraints.py").exists()

    def test_gate_hook_exists(self):
        assert (REPO_ROOT / ".claude/hooks/pre_execution_gate.py").exists()

    def test_gate_test_exists(self):
        assert (REPO_ROOT / ".claude/tests/test_pre_execution_gate.py").exists()

    def test_notes_convention_exists(self):
        assert (REPO_ROOT / "docs/conventions/implementation-notes.md").exists()

    def test_notes_test_exists(self):
        assert (REPO_ROOT / ".claude/tests/test_implementation_notes.py").exists()

    def test_test_first_gate_exists(self):
        assert (REPO_ROOT / ".claude/tests/test_test_first_gate.py").exists()

    def test_adv_verify_gate_exists(self):
        assert (REPO_ROOT / ".claude/tests/test_adversarial_verification_gate.py").exists()

    def test_worktree_utils_exist(self):
        assert (REPO_ROOT / ".claude/scripts/pev_worktree.py").exists()

    def test_orchestrator_exists(self):
        assert (REPO_ROOT / ".claude/scripts/pev_orchestrator.js").exists()

    def test_repair_loop_exists(self):
        assert (REPO_ROOT / ".claude/scripts/pev_repair.py").exists()


class TestPEVStructuralTests:
    """All new structural tests pass."""

    def test_milestone_constraints(self):
        passed, out = _run_pytest(".claude/tests/test_milestone_constraints.py")
        assert passed, f"Constraint test failed:\n{out}"

    def test_pre_execution_gate(self):
        passed, out = _run_pytest(".claude/tests/test_pre_execution_gate.py")
        assert passed, f"Gate test failed:\n{out}"

    def test_implementation_notes(self):
        passed, out = _run_pytest(".claude/tests/test_implementation_notes.py")
        assert passed, f"Notes test failed:\n{out}"

    def test_test_first_gate(self):
        passed, out = _run_pytest(".claude/tests/test_test_first_gate.py")
        assert passed, f"Test-first gate failed:\n{out}"

    def test_adversarial_verification_gate(self):
        passed, out = _run_pytest(".claude/tests/test_adversarial_verification_gate.py")
        assert passed, f"Adv-verify gate failed:\n{out}"

    def test_worktree(self):
        passed, out = _run_pytest(".claude/tests/test_pev_worktree.py")
        assert passed, f"Worktree test failed:\n{out}"

    def test_orchestrator(self):
        passed, out = _run_pytest(".claude/tests/test_pev_orchestrator.py")
        assert passed, f"Orchestrator test failed:\n{out}"

    def test_repair_loop(self):
        passed, out = _run_pytest(".claude/tests/test_pev_repair.py")
        assert passed, f"Repair loop test failed:\n{out}"


class TestPEVBackwardCompatibility:
    """Existing structural tests still pass (backward compatibility)."""

    def test_execplan_structure(self):
        passed, out = _run_pytest(".claude/tests/test_execplan_structure.py")
        assert passed, f"ExecPlan structure test failed:\n{out}"

    def test_decision_log_evidence(self):
        passed, out = _run_pytest(".claude/tests/test_decision_log_evidence.py")
        assert passed, f"Decision log test failed:\n{out}"

    def test_no_forbidden_phrases(self):
        passed, out = _run_pytest(".claude/tests/test_no_forbidden_phrases.py")
        assert passed, f"Forbidden phrases test failed:\n{out}"

    def test_conventions_exist(self):
        passed, out = _run_pytest("tests/test_conventions_exist.py")
        assert passed, f"Conventions exist test failed:\n{out}"


class TestPEVConventionDocs:
    """Convention docs reference the new components."""

    def test_pev_loop_has_constraint_spec(self):
        text = (REPO_ROOT / "docs/conventions/pev-loop.md").read_text()
        assert "Allowed Reads" in text
        assert "Allowed Writes" in text
        assert "Requires" in text
        assert "Risk Tier" in text

    def test_verification_floor_has_enforcement(self):
        text = (REPO_ROOT / "docs/conventions/verification-floor.md").read_text()
        assert "test_test_first_gate.py" in text
        assert "test_adversarial_verification_gate.py" in text

    def test_implementation_notes_convention(self):
        text = (REPO_ROOT / "docs/conventions/implementation-notes.md").read_text()
        for entry_type in ["plan-confirmed", "discovery", "deviation", "human-todo"]:
            assert entry_type in text
        for field in ["What the plan said", "What the code revealed", "Conservative choice", "Revisit"]:
            assert field in text
