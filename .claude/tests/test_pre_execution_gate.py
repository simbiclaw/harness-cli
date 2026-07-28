"""Structural tests for the pre-execution constraint gate.

Validates that the gate correctly blocks Edit/Write outside Allowed Writes
and allows edits within scope or when no constraints are declared.

See docs/conventions/pev-loop.md § Milestone constraint fields.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GATE_SCRIPT = REPO_ROOT / ".claude" / "hooks" / "pre_execution_gate.py"


def _run_gate(tool_name: str, file_path: str) -> dict:
    """Run the gate hook with a simulated tool event."""
    event = {
        "session_id": "test",
        "tool_name": tool_name,
        "tool_input": {"file_path": str(file_path)},
    }
    result = subprocess.run(
        [sys.executable, str(GATE_SCRIPT)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return json.loads(result.stdout)


def test_gate_allows_non_edit_tools():
    """Gate allows non-Edit/Write tools."""
    result = _run_gate("Read", "/some/path")
    assert result["continue"] is True


def test_gate_allows_when_no_plans():
    """Gate allows when no active plans exist."""
    # With no active plans dir, gate should allow
    result = _run_gate("Edit", REPO_ROOT / "src" / "argus" / "core" / "test.py")
    assert result["continue"] is True


def test_gate_allows_exec_plan_edits():
    """Gate allows edits to exec-plan files themselves."""
    plan_file = REPO_ROOT / "docs" / "exec-plans" / "active" / "9005-pev-loop-evolution.md"
    result = _run_gate("Edit", plan_file)
    assert result["continue"] is True


def test_gate_allows_when_no_constraints():
    """Gate allows when current milestone has no Allowed Writes."""
    # 9005 has no Allowed Writes fields — should allow everything
    result = _run_gate("Edit", REPO_ROOT / "src" / "argus" / "core" / "anything.py")
    assert result["continue"] is True


def test_gate_blocks_overreach():
    """Gate blocks edits outside Allowed Writes patterns."""
    # Create a temporary plan with constraints
    import tempfile
    import os

    plan_content = """# Test Plan

## 3. Milestones

### M1 — Test milestone

Acceptance Test: tests/test_X.py::test_name
Allowed Writes: src/argus/core/routing.py, tests/test_routing.py

## 4. Progress

- [ ] M1: Test milestone
"""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False,
        dir=REPO_ROOT / "docs" / "exec-plans" / "active",
    ) as f:
        f.write(plan_content)
        tmp_plan = f.name

    try:
        # Should block: outside Allowed Writes
        result = _run_gate("Edit", REPO_ROOT / "src" / "argus" / "io" / "client.py")
        assert result["continue"] is False
        assert "outside the Allowed Writes" in result["reason"]

        # Should allow: inside Allowed Writes
        result = _run_gate("Edit", REPO_ROOT / "src" / "argus" / "core" / "routing.py")
        assert result["continue"] is True

        result = _run_gate("Edit", REPO_ROOT / "tests" / "test_routing.py")
        assert result["continue"] is True
    finally:
        os.unlink(tmp_plan)
