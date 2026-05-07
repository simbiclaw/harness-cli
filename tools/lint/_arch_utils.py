"""Shared utilities for the architectural-edge linters.

Determines domain and layer from module paths, parses imports from AST,
and provides the dependency matrix for cross-domain edge checking.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Layer ranks: higher = later layer, can depend on lower; lower cannot depend on higher.
LAYER_RANK: dict[str, int] = {
    "types": 0,
    "config": 1,
    "repo": 2,
    "service": 3,
    "runtime": 4,
    "ui": 5,
}

DOMAINS: set[str] = {
    "audio_intake",
    "doc_ingestion",
    "conv_distillation",
    "calibration",
    "expertise",
    "argus",
    "metis",
    "hermes",
    "providers",
    "utils",
}

# Layer name aliases (repo directory names → canonical layer).
LAYER_ALIASES: dict[str, str] = {
    "types": "types",
    "config": "config",
    "repo": "repo",
    "service": "service",
    "runtime": "runtime",
    "ui": "ui",
    "providers": "providers",
    "utils": "utils",
}

# Domain name aliases (package directory → canonical domain).
DOMAIN_ALIASES: dict[str, str] = {
    "audio_intake": "audio_intake",
    "doc_ingestion": "doc_ingestion",
    "conv_distillation": "conv_distillation",
    "calibration": "calibration",
    "expertise": "expertise",
    "argus": "argus",
    "metis": "metis",
    "hermes": "hermes",
    "audiointake": "audio_intake",
    "docingestion": "doc_ingestion",
    "convdistillation": "conv_distillation",
}

# Cross-domain dependency matrix: rows depend on columns.
# "none" = forbidden edge, "via providers" = must route through providers,
# interface name = permitted direct edge.
CROSS_DOMAIN_MATRIX: dict[str, dict[str, str]] = {}


def _init_matrix() -> None:
    domains = sorted(DOMAINS)
    for d in domains:
        CROSS_DOMAIN_MATRIX[d] = dict.fromkeys(domains, "none")

    def allow(row: str, col: str, kind: str) -> None:
        CROSS_DOMAIN_MATRIX[row][col] = kind

    # 1. Audio Intake — only depends on providers and utils
    allow("audio_intake", "providers", "via providers")
    allow("audio_intake", "utils", "yes")
    # 2. Doc Ingestion
    allow("doc_ingestion", "providers", "via providers")
    allow("doc_ingestion", "utils", "yes")
    # 3. Conv Distillation — depends on Audio Intake (transcription stream)
    allow("conv_distillation", "audio_intake", "ITranscriptionStream")
    allow("conv_distillation", "providers", "via providers")
    allow("conv_distillation", "utils", "yes")
    # 4. Calibration — depends on Doc Ingestion and Conv Distillation
    allow("calibration", "doc_ingestion", "IComputeGraphSource")
    allow("calibration", "conv_distillation", "IIntentTreeSource")
    allow("calibration", "providers", "via providers")
    allow("calibration", "utils", "yes")
    # 5. Expertise Lib — depends on Calibration
    allow("expertise", "calibration", "ICalibratedGraphReader")
    allow("expertise", "providers", "via providers")
    allow("expertise", "utils", "yes")
    # 6. Argus — depends on Conv Distillation, Calibration, Expertise
    allow("argus", "conv_distillation", "IIntentTreeReader")
    allow("argus", "calibration", "ICalibratedGraphReader")
    allow("argus", "expertise", "IExpertiseReader")
    allow("argus", "providers", "via providers")
    allow("argus", "utils", "yes")
    # 7. Metis — depends on Conv Distillation, Calibration, Expertise, Argus
    allow("metis", "conv_distillation", "IIntentTreeReader")
    allow("metis", "calibration", "ICalibratedGraphReader")
    allow("metis", "expertise", "IExpertiseReader")
    allow("metis", "argus", "IArgusFindingFeed")
    allow("metis", "providers", "via providers")
    allow("metis", "utils", "yes")
    # 8. Hermes — depends on Calibration, Expertise
    allow("hermes", "calibration", "ICalibratedGraphReader")
    allow("hermes", "expertise", "IExpertiseReader")
    allow("hermes", "providers", "via providers")
    allow("hermes", "utils", "yes")
    # 9. Providers — can use utils
    allow("providers", "utils", "yes")
    # 10. Utils — no dependencies on other domains
    # self-references
    for d in domains:
        CROSS_DOMAIN_MATRIX[d][d] = "—"


_init_matrix()


def resolve_domain_and_layer(file_path: Path, root: Path) -> tuple[str, str] | None:
    """Return (domain, layer) for a Python file, or None if unresolvable.

    Expects package structure: root/<domain>/<layer>/module.py
    Providers and Utils domains may omit the layer component
    (e.g., root/providers/module.py → domain=providers, layer=providers).
    """
    try:
        rel = file_path.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 2:
        return None
    if parts[0] in ("providers", "utils"):
        domain = DOMAIN_ALIASES.get(parts[0], parts[0])
        return domain, domain
    if len(parts) < 3:
        return None
    domain = DOMAIN_ALIASES.get(parts[1], parts[1])
    layer = LAYER_ALIASES.get(parts[2], parts[2])
    if domain in DOMAINS and layer in LAYER_RANK:
        return domain, layer
    return None


def get_layer_rank(layer: str) -> int:
    return LAYER_RANK.get(layer, -1)


_STDLIB_MODULES: set[str] | None = None


def _stdlib_set() -> set[str]:
    global _STDLIB_MODULES
    if _STDLIB_MODULES is None:
        _STDLIB_MODULES = (
            set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()
        )
    return _STDLIB_MODULES


def is_external_import(module_name: str) -> bool:
    """True if module_name is a third-party dependency (not stdlib, not argus.*)."""
    top = module_name.split(".")[0]
    return top != "argus" and top not in _stdlib_set()


def iter_imports(source: str) -> list[tuple[int, str, str | None]]:
    """Parse *source* and return list of (lineno, module, name) for each import.

    For `import foo.bar` → (lineno, "foo.bar", None)
    For `from foo.bar import Baz` → (lineno, "foo.bar", "Baz")
    """
    results: list[tuple[int, str, str | None]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return results
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                results.append((node.lineno, alias.name, None))
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            for alias in node.names:
                results.append((node.lineno, node.module, alias.name))
    return results
