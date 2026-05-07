#!/usr/bin/env python3
"""no-backward-layer-import: enforce layer ordering within each domain.

Usage: python3 tools/lint/no_backward_layer_import.py [--root ROOT] file ...

A file in a later layer (higher rank) may import from an earlier layer (lower
rank) within the same domain. The reverse is a violation.

Exit 0 if clean; exit 1 and print violations to stderr otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path

from _arch_utils import (
    DOMAINS,
    get_layer_rank,
    iter_imports,
    resolve_domain_and_layer,
)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def _find_root(file_path: Path, explicit_root: Path | None) -> Path | None:
    if explicit_root is not None:
        return explicit_root
    # Walk up looking for an 'argus' package marker
    cur = file_path.resolve().parent
    for _ in range(10):
        if (cur / "argus").is_dir():
            return cur
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return ROOT_DIR / "src"


def check_file(file_path: Path, root: Path) -> list[str]:
    violations: list[str] = []
    src_info = resolve_domain_and_layer(file_path, root)
    if src_info is None:
        return violations
    src_domain, src_layer = src_info
    src_rank = get_layer_rank(src_layer)
    if src_rank < 0:
        return violations

    source = file_path.read_text()
    imports = iter_imports(source)

    for lineno, module, _name in imports:
        if not module.startswith("argus."):
            continue
        # Resolve target: argus.<domain>.<layer>...
        parts = module.split(".")
        if len(parts) < 3:
            continue
        tgt_domain = parts[1]
        tgt_layer = parts[2] if len(parts) > 2 else None
        if tgt_domain not in DOMAINS:
            continue
        if tgt_domain != src_domain:
            continue  # cross-domain edges handled by the other lint
        tgt_rank = get_layer_rank(tgt_layer) if tgt_layer else -1
        if tgt_rank < 0:
            continue

        if tgt_rank > src_rank:
            violations.append(
                f"{file_path}:{lineno}: backward layer import: "
                f"{src_layer} (rank {src_rank}) importing from "
                f"{tgt_layer} (rank {tgt_rank}) in domain {src_domain} — "
                f"module {module}"
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
        print("no-backward-layer-import: no files specified", file=sys.stderr)
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
