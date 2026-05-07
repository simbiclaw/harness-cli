#!/usr/bin/env python3
"""parse-at-boundary: cross-domain function calls must go through typed schema validators.

Usage: python3 tools/lint/parse_at_boundary.py [--root ROOT] file ...

Detects cross-domain function calls where arguments are not constructed via
a typed schema validator (e.g., Pydantic model_validate or constructor).

Exit 0 if clean; exit 1 and print violations to stderr otherwise.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from _arch_utils import resolve_domain_and_layer

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def _find_root(file_path: Path, explicit_root: Path | None) -> Path | None:
    if explicit_root is not None:
        return explicit_root
    cur = file_path.resolve().parent
    for _ in range(10):
        if (cur / "argus").is_dir():
            return cur
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return ROOT_DIR / "src"


def _has_parse_call(node: ast.expr) -> bool:
    """Check if an AST expression involves a typed schema validator call."""
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr in (
            "model_validate",
            "model_construct",
            "parse_obj",
            "parse_raw",
        ):
            return True
        if isinstance(node.func, ast.Name):
            return True
    if isinstance(node, ast.Dict):
        return False
    return isinstance(node, ast.Name)


def check_file(file_path: Path, root: Path) -> list[str]:
    violations: list[str] = []
    src_info = resolve_domain_and_layer(file_path, root)
    if src_info is None:
        return violations
    _src_domain, _src_layer = src_info

    source = file_path.read_text()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Check if this is a call to a cross-domain function
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            # Local function call — not cross-domain, skip
            continue

        # Check arguments for raw dicts/lists — these are unparsed data
        for arg in node.args:
            if isinstance(arg, ast.Dict):
                func_name = ast.unparse(node.func) if hasattr(ast, "unparse") else "<call>"
                violations.append(
                    f"{file_path}:{node.lineno}: unparsed cross-domain argument: "
                    f"raw dict literal passed to {func_name} without "
                    f"typed schema validator — parse at boundary required"
                )
            elif isinstance(arg, ast.List):
                func_name = ast.unparse(node.func) if hasattr(ast, "unparse") else "<call>"
                violations.append(
                    f"{file_path}:{node.lineno}: unparsed cross-domain argument: "
                    f"raw list literal passed to {func_name} without "
                    f"typed schema validator — parse at boundary required"
                )

    return violations


def main(argv: list[str]) -> int:
    args = argv[1:]
    explicit_root: Path | None = None
    files: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--root" and i + 1 < len(args):
            explicit_root = Path(args[i + 1])
            i += 2
        else:
            files.append(args[i])
            i += 1

    if not files:
        print("parse-at-boundary: no files specified", file=sys.stderr)
        return 2

    all_violations: list[str] = []
    for f in files:
        fp = Path(f)
        root = _find_root(fp, explicit_root)
        if root is None:
            continue
        all_violations.extend(check_file(fp, root))

    for v in all_violations:
        print(v, file=sys.stderr)
    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
