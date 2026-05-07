#!/usr/bin/env python3
"""hermes-action-tier-required: enforce ActionDescriptor has explicit tier.

Usage: python3 tools/lint/hermes_action_tier_required.py file ...

Every ActionDescriptor constructor call must include an explicit 'tier'
keyword argument. Calls without tier are violations.

Exit 0 if clean; exit 1 and print violations to stderr otherwise.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def check_file(file_path: Path) -> list[str]:
    violations: list[str] = []
    source = file_path.read_text()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Check for ActionDescriptor(...) calls
        func_name: str | None = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name != "ActionDescriptor":
            continue

        # Check if 'tier' is among the keyword arguments
        has_tier = False
        for kw in node.keywords:
            if kw.arg == "tier":
                has_tier = True
                break

        if not has_tier:
            violations.append(
                f"{file_path}:{node.lineno}: ActionDescriptor constructed "
                f"without explicit 'tier' keyword — tier is required"
            )

    return violations


def main(argv: list[str]) -> int:
    files = argv[1:]
    if not files:
        print("hermes-action-tier-required: no files specified", file=sys.stderr)
        return 2

    all_violations: list[str] = []
    for f in files:
        all_violations.extend(check_file(Path(f)))

    for v in all_violations:
        print(v, file=sys.stderr)
    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
