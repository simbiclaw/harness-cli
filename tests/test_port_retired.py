"""9031 M2 red/green: the simbi port is retired, the kept types are re-homed.

The port's evidence types could not carry the spec's anchored finding (span +
quote + epoch), the fidelity floor forbade extending them, and B itself never
executed — the ruling of 2026-09-16 ("no simbi at all") retires the whole port
as the proposal mechanism. These two tests are the floor that keeps it gone:
one proves no simbi lineage survives in `src/`, the other proves the kept
types live in their Argus-side homes and the ported contract module is gone.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src" / "argus"

DELETED = [
    "io/qa_agent.py",
    "io/fact_checker.py",
    "io/nli.py",
    "io/question_generator.py",
    "io/atomizer.py",
    "io/prompts.py",
    "io/llm_client.py",
    "types/pipeline.py",
]

LINEAGE_TOKENS = ("simbi", "929d5a7", "ported from")


def test_no_ported_provenance_strings():
    hits = []
    for py in sorted(SRC.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        text = py.read_text(encoding="utf-8").lower()
        for token in LINEAGE_TOKENS:
            if token in text:
                hits.append(f"{py.relative_to(REPO_ROOT)}: contains {token!r}")
    for rel in DELETED:
        path = SRC / rel
        if path.exists():
            hits.append(f"{rel}: still exists")
    assert not hits, "port lineage survives:\n" + "\n".join(hits)


def test_rehomed_types_import():
    from argus.types.session import Session, Turn
    from argus.types.verdict import RubricCategory, RubricItem, VerdictResult

    assert VerdictResult.HUMAN_REVIEW.value == "human_review"
    assert RubricItem is not None and RubricCategory is not None
    assert Session is not None and Turn is not None
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("argus.types.pipeline")
