"""Structural tests for the pre-execution constraint gate.

Validates that the gate correctly blocks Edit/Write outside Allowed Writes
and allows edits within scope or when no constraints are declared.

See docs/conventions/pev-loop.md § Milestone constraint fields.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GATE_SCRIPT = REPO_ROOT / ".claude" / "hooks" / "pre_execution_gate.py"


def _run_gate(tool_name: str, file_path: str, env: dict | None = None) -> dict:
    """Run the gate hook with a simulated tool event.

    `env` overrides the subprocess environment — tests set
    `PEV_ACTIVE_PLANS_DIR` to a hermetic temp dir instead of depending on
    the live repo's newest active plan.
    """
    event = {
        "session_id": "test",
        "tool_name": tool_name,
        "tool_input": {"file_path": str(file_path)},
    }
    run_env = dict(os.environ)
    if env:
        run_env.update(env)
    result = subprocess.run(
        [sys.executable, str(GATE_SCRIPT)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=10,
        env=run_env,
    )
    return json.loads(result.stdout)


def test_gate_allows_non_edit_tools():
    """Gate allows non-Edit/Write tools."""
    result = _run_gate("Read", "/some/path")
    assert result["continue"] is True


def test_gate_allows_when_no_plans(tmp_path):
    """Gate allows when no active plans exist."""
    env = {"PEV_ACTIVE_PLANS_DIR": str(tmp_path)}  # empty dir → no plans
    result = _run_gate("Edit", REPO_ROOT / "src" / "argus" / "core" / "test.py", env=env)
    assert result["continue"] is True


def test_gate_allows_exec_plan_edits():
    """Gate allows edits to exec-plan files themselves."""
    plan_file = REPO_ROOT / "docs" / "exec-plans" / "active" / "9003-implement-soft-criteria-compiler.md"
    result = _run_gate("Edit", plan_file)
    assert result["continue"] is True


def test_gate_allows_when_no_constraints(tmp_path):
    """Gate allows when current milestone has no Allowed Writes."""
    (tmp_path / "no-constraints-plan.md").write_text(
        "# Test Plan\n\n## 3. Milestones\n\n### M1 — Test milestone\n\n"
        "Acceptance Test: tests/test_X.py::test_name\n\n"
        "## 4. Progress\n\n- [ ] M1: Test milestone\n"
    )
    env = {"PEV_ACTIVE_PLANS_DIR": str(tmp_path)}
    result = _run_gate("Edit", REPO_ROOT / "src" / "argus" / "core" / "anything.py", env=env)
    assert result["continue"] is True


def test_gate_blocks_overreach(tmp_path):
    """Gate blocks edits outside Allowed Writes patterns."""
    (tmp_path / "constrained-plan.md").write_text(
        "# Test Plan\n\n## 3. Milestones\n\n### M1 — Test milestone\n\n"
        "Acceptance Test: tests/test_X.py::test_name\n"
        "Allowed Writes: src/argus/core/routing.py, tests/test_routing.py\n\n"
        "## 4. Progress\n\n- [ ] M1: Test milestone\n"
    )
    env = {"PEV_ACTIVE_PLANS_DIR": str(tmp_path)}

    # Should block: outside Allowed Writes
    result = _run_gate("Edit", REPO_ROOT / "src" / "argus" / "io" / "client.py", env=env)
    assert result["continue"] is False
    assert "outside the Allowed Writes" in result["reason"]

    # Should allow: inside Allowed Writes
    result = _run_gate("Edit", REPO_ROOT / "src" / "argus" / "core" / "routing.py", env=env)
    assert result["continue"] is True

    result = _run_gate("Edit", REPO_ROOT / "tests" / "test_routing.py", env=env)
    assert result["continue"] is True
