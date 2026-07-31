"""Verify each hook script runs without error when given mock input.

Each hook follows the contract: read JSON event from stdin (or argv for
commit-msg), exit 0 with valid JSON on stdout. This test pipes minimal
mock events and asserts clean exit.

See docs/exec-plans/active/0001-bootstrap-harness.md milestone M3.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
CLAUDE_DIR = Path(__file__).resolve().parent.parent


def run_hook(hook: str, stdin: str | None = None, args: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(HOOKS_DIR / hook), *(args or [])]
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=10)


def test_settings_json_is_valid() -> None:
    raw = (CLAUDE_DIR / "settings.json").read_text()
    doc = json.loads(raw)
    assert "hooks" in doc


def test_pre_tool_use_runs() -> None:
    # A Bash echo should pass all guards.
    event = json.dumps({"tool_name": "Bash", "tool_input": {"command": "echo hello"}})
    result = run_hook("pre_tool_use.py", stdin=event)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    output = json.loads(result.stdout)
    assert output == {"continue": True}


def test_pre_tool_use_allows_safe_edit() -> None:
    # An Edit to an arbiter-safe path (active plan file) should be allowed
    # without PEV agents spawned. Non-arbiter-safe paths require agent_ids.
    repo_root = CLAUDE_DIR.parent
    event = json.dumps({
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(
                repo_root / "docs" / "exec-plans" / "active" / "test-fake.md"
            )
        },
    })
    result = run_hook("pre_tool_use.py", stdin=event)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    output = json.loads(result.stdout)
    assert output == {"continue": True}


def test_post_tool_use_runs() -> None:
    # PostToolUse only reacts to Edit/Write — Bash should be a no-op.
    event = json.dumps({"tool_name": "Bash", "tool_input": {"command": "echo hello"}})
    result = run_hook("post_tool_use.py", stdin=event)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    # No output means no message (not a plan edit)
    assert result.stdout.strip() == ""


def test_post_tool_use_ignores_non_plan_edit() -> None:
    # An Edit to a non-plan file should produce no output.
    event = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "/tmp/foo.py"}})
    result = run_hook("post_tool_use.py", stdin=event)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.strip() == ""


def test_commit_msg_runs() -> None:
    # Write a valid commit message to a temp file.
    body = """\
docs(readme): update installation instructions

Plan: docs/exec-plans/active/0001-bootstrap-harness.md#milestone-3
Decision: test commit-msg hook
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(body)
        tmp = f.name
    try:
        result = run_hook("check_commit_msg.py", args=[tmp])
        assert result.returncode == 0, f"stderr: {result.stderr}"
    finally:
        Path(tmp).unlink(missing_ok=True)
