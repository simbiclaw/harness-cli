"""Structural test for hook path portability.

Enforces that settings.json hook commands use repo-relative paths,
never absolute paths. Absolute paths break on any other checkout
location — CI, another machine, a container, or a git worktree — where the
hook either fails to launch or runs against the wrong repo.

See docs/conventions/verification-floor.md and the 9004 retrospective:
four worktree agents whose guard layer was pointed at a different checkout.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SETTINGS_FILE = REPO_ROOT / ".claude" / "settings.json"
SETTINGS_LOCAL_FILE = REPO_ROOT / ".claude" / "settings.local.json"


def _abs_paths_in_value(value, path: str) -> list[str]:
    """Recursively find absolute-path strings in a settings value.

    Returns a list of human-readable paths to the violating value.
    """
    findings: list[str] = []

    if isinstance(value, str):
        if value.startswith("/"):
            findings.append(f"{path} = {value!r}")
    elif isinstance(value, dict):
        for k, v in value.items():
            findings.extend(_abs_paths_in_value(v, f"{path}.{k}"))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            findings.extend(_abs_paths_in_value(v, f"{path}[{i}]"))

    return findings


def _find_absolute_paths(settings: dict, filename: str) -> list[str]:
    """Walk a settings dict and find absolute paths in hook commands."""
    failures: list[str] = []

    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return failures

    for hook_type in hooks:
        if not isinstance(hooks[hook_type], list):
            continue
        for i, matcher_block in enumerate(hooks[hook_type]):
            if not isinstance(matcher_block, dict):
                continue
            inner_hooks = matcher_block.get("hooks", [])
            if not isinstance(inner_hooks, list):
                continue
            for j, hook in enumerate(inner_hooks):
                if not isinstance(hook, dict):
                    continue
                command = hook.get("command", "")
                if isinstance(command, str) and command:
                    path = f"{filename}:hooks.{hook_type}[{i}].hooks[{j}].command"
                    findings = _abs_paths_in_value(command, path)
                    failures.extend(findings)

    return failures


def test_no_absolute_paths_in_hook_commands():
    """Every hook command uses a repo-relative path, never absolute."""
    failures: list[str] = []

    for settings_path in (SETTINGS_FILE, SETTINGS_LOCAL_FILE):
        if not settings_path.exists():
            continue

        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError as e:
            failures.append(f"{settings_path.name}: invalid JSON: {e}")
            continue

        rel = str(settings_path.relative_to(REPO_ROOT))
        failures.extend(_find_absolute_paths(settings, rel))

    assert not failures, (
        "Absolute paths in hook commands break portability "
        "(CI / worktree / container / another machine).\n"
        "Use repo-relative paths instead:\n"
        "  python3 .claude/hooks/pre_tool_use.py\n"
        "\nFound absolute paths:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )
