"""Structural test: layered architecture for src/argus/.

Backstop for import-linter. Both must pass.

Layer order: types -> config -> io -> core -> cli.
A module in layer N may import from layers <= N. Imports flowing the other
direction fail this test.
"""

from __future__ import annotations

import ast
from pathlib import Path

LAYERS = ["types", "config", "io", "core", "cli"]
LAYER_RANK = {name: i for i, name in enumerate(LAYERS)}

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC = REPO_ROOT / "src" / "argus"


def layer_of_module(mod: str) -> str | None:
    parts = mod.split(".")
    if len(parts) >= 2 and parts[0] == "argus" and parts[1] in LAYER_RANK:
        return parts[1]
    return None


def layer_of_file(path: Path) -> str | None:
    try:
        rel = path.relative_to(SRC)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) >= 1 and parts[0] in LAYER_RANK:
        return parts[0]
    return None


def imports_in(path: Path) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            out.append((node.lineno, node.module))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                out.append((node.lineno, alias.name))
    return out


def test_layer_imports_flow_upward():
    if not SRC.exists():
        return  # Bootstrap: source tree may be empty.

    violations: list[str] = []
    for py in SRC.rglob("*.py"):
        src_layer = layer_of_file(py)
        if src_layer is None:
            continue  # not in any layer (e.g. argus/__init__.py)
        for lineno, imp in imports_in(py):
            tgt_layer = layer_of_module(imp)
            if tgt_layer is None:
                continue  # third-party or stdlib
            if LAYER_RANK[tgt_layer] > LAYER_RANK[src_layer]:
                violations.append(
                    f"{py.relative_to(REPO_ROOT)}:{lineno}: "
                    f"layer '{src_layer}' imports from higher layer "
                    f"'{tgt_layer}' ({imp}). Imports must flow downward "
                    f"toward '{LAYERS[0]}'. Move the imported symbol to "
                    f"a layer <= {src_layer}, or invert the dependency. "
                    f"See docs/conventions/layering.md."
                )
    assert not violations, "Layer violations:\n  " + "\n  ".join(violations)
