#!/usr/bin/env python3
"""calibration-asymmetric-signature: enforce non-symmetric calibrate() signature.

Usage: python3 tools/lint/calibration_asymmetric_signature.py file ...

The calibration function must be intentionally asymmetric. Functions named
'reconcile' (symmetric by convention) or calibrate functions with symmetric
parameter names (a/b, x/y, left/right) are violations.

Exit 0 if clean; exit 1 and print violations to stderr otherwise.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SYMMETRIC_PARAM_PAIRS = [
    {"a", "b"},
    {"x", "y"},
    {"left", "right"},
    {"lhs", "rhs"},
    {"first", "second"},
    {"input1", "input2"},
    {"arg1", "arg2"},
]


def _is_symmetric_params(params: list[ast.arg]) -> bool:
    """Check if parameter names suggest symmetry (a/b, x/y, etc.)."""
    if len(params) < 2:
        return False
    names = {p.arg for p in params if p.arg != "self"}
    return any(pair.issubset(names) for pair in SYMMETRIC_PARAM_PAIRS)


def check_file(file_path: Path) -> list[str]:
    violations: list[str] = []
    source = file_path.read_text()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name == "reconcile":
                violations.append(
                    f"{file_path}:{node.lineno}: symmetric 'reconcile' function found — "
                    f"calibration must use 'calibrate(intentTree, computeGraph)' "
                    f"with intentionally asymmetric parameters"
                )
            elif node.name == "calibrate":
                params = node.args.args
                if len(params) < 2:
                    violations.append(
                        f"{file_path}:{node.lineno}: calibrate() requires at least "
                        f"two parameters (intentTree, computeGraph)"
                    )
                elif _is_symmetric_params(params):
                    violations.append(
                        f"{file_path}:{node.lineno}: calibrate() parameters are "
                        f"symmetric — must use intentionally asymmetric names "
                        f"(e.g., intent_tree, compute_graph)"
                    )

    return violations


def main(argv: list[str]) -> int:
    files = argv[1:]
    if not files:
        print("calibration-asymmetric-signature: no files specified", file=sys.stderr)
        return 2

    all_violations: list[str] = []
    for f in files:
        all_violations.extend(check_file(Path(f)))

    for v in all_violations:
        print(v, file=sys.stderr)
    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
