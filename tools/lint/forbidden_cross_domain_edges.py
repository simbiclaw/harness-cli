#!/usr/bin/env python3
"""forbidden-cross-domain-edges: enforce the dependency matrix from ARCHITECTURE.md.

Usage: python3 tools/lint/forbidden_cross_domain_edges.py [--root ROOT] file ...

Cross-domain imports are checked against the dependency matrix in _arch_utils.py.
An edge marked 'none' in the matrix is a violation.

Exit 0 if clean; exit 1 and print violations to stderr otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path

from _arch_utils import CROSS_DOMAIN_MATRIX, DOMAINS, iter_imports, resolve_domain_and_layer

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


def check_file(file_path: Path, root: Path) -> list[str]:
    violations: list[str] = []
    src_info = resolve_domain_and_layer(file_path, root)
    if src_info is None:
        return violations
    src_domain, _src_layer = src_info
    if src_domain not in CROSS_DOMAIN_MATRIX:
        return violations

    source = file_path.read_text()
    imports = iter_imports(source)

    for lineno, module, _name in imports:
        if not module.startswith("argus."):
            continue
        parts = module.split(".")
        if len(parts) < 2:
            continue
        tgt_domain = parts[1]
        if tgt_domain not in DOMAINS:
            continue
        if tgt_domain == src_domain:
            continue  # within-domain edges handled by no-backward-layer-import

        allowed = CROSS_DOMAIN_MATRIX.get(src_domain, {}).get(tgt_domain, "none")
        if allowed == "none":
            violations.append(
                f"{file_path}:{lineno}: forbidden cross-domain edge: "
                f"{src_domain} → {tgt_domain} is 'none' in the dependency matrix — "
                f"import of {module}"
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
        print("forbidden-cross-domain-edges: no files specified", file=sys.stderr)
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
