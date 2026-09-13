"""The four layer fences, enforced by an artifact that can fail.

M8's binding constraint names four fences from CLAUDE.md:

    core ✗ model_client        — no module in core/ imports an LLM client
    grounding ✗ proposer       — the grounding gate never imports the proposer
    grounding ✗ matching_model — the exemplar/case match happens in the
                                 proposer, never in the gate
    aggregate ✗ model_client   — the corroboration aggregator is pure

Three of the four have been satisfied only because the code they guard does not
exist yet. That is not enforcement, and this module refuses to pretend
otherwise: `test_fence_coverage_is_visible` names every guarded path that is
still absent, so vacuity is a reported fact rather than a silent green tick. As
each file lands, the live scan picks it up with no change here.

M8 also specifies `forbidden` contracts in `.importlinter`. Those are written,
but `import-linter` cannot be installed in this environment, so they cannot be
shown to fail — and a contract that has never failed is not enforcement. This
module is the runnable half, and it is strictly stronger than the lint would be
on one axis: import-linter's `layers` contract cannot see a third-party import
at all, which is why `from anthropic import Anthropic` inside `core/` passes
`lint-imports` today.

Supersedes the three-name denylist at `tests/test_local_proposer.py:187-202`,
which accepts `openai`, `cohere`, `mlx_lm` and every other client by omission.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE = REPO_ROOT / "src" / "argus" / "core"

# Roots that constitute "a model client". Deliberately broader than the three
# names the superseded check knew about: the fence is about the *category*, and
# a denylist that has to be edited for each new vendor fails open.
MODEL_CLIENT_ROOTS = {
    "anthropic",
    "openai",
    "cohere",
    "mistralai",
    "google",
    "vertexai",
    "ollama",
    "llama_cpp",
    "mlx",
    "mlx_lm",
    "mlx_vlm",
    "transformers",
    "torch",
    "sentence_transformers",
    "litellm",
    "boto3",
}

# core/ is a pure layer: no network, no clock, no randomness. These are not
# model clients, but a core module reaching for one is the same defect class —
# an impure input smuggled into a stage whose whole value is reproducibility.
IMPURE_ROOTS = {"httpx", "requests", "urllib", "urllib3", "aiohttp", "socket"}

# argus-internal modules that ARE the proposer. core/ importing one of these
# crosses the quarantine from the inside.
PROPOSER_MODULES = {"local_proposer", "logprob_scoring", "proposer", "llm_client"}

# Modules that perform a model-judged match — the exemplar/case matching the
# grounding gate must never do itself (D3).
MATCHING_MODEL_ROOTS = {
    "sentence_transformers",
    "chromadb",
    "faiss",
    "sklearn",
    "annoy",
    "hnswlib",
}

# Files each fence guards, relative to src/argus/. Absent ones are reported.
FENCE_TARGETS = {
    "grounding ✗ proposer": "core/grounding.py",
    "grounding ✗ matching_model": "core/grounding.py",
    "aggregate ✗ model_client": "core/corroboration.py",
}


def imported_roots(code: str) -> list[tuple[int, str]]:
    """Every imported module, as (lineno, dotted name)."""
    out: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.Import):
            out.extend((node.lineno, a.name) for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.append((node.lineno, node.module))
    return out


def fence_violations(code: str, forbidden_roots: set[str], forbidden_substrings: set[str]) -> list[str]:
    """Return imports that cross a fence.

    Matches on the *root* package so `torch.nn.functional` is caught by `torch`,
    and on substrings for argus-internal module names, which appear as
    `argus.io.local_proposer` or a bare relative import.
    """
    violations: list[str] = []
    for lineno, name in imported_roots(code):
        root = name.split(".")[0]
        if root in forbidden_roots:
            violations.append(f"line {lineno}: imports {name}")
        elif any(s in name for s in forbidden_substrings):
            violations.append(f"line {lineno}: imports {name}")
    return violations


def _core_files() -> list[Path]:
    return [p for p in sorted(CORE.rglob("*.py")) if p.name != "__init__.py"]


# --- Red samples: each must be caught ---------------------------------------

RED_MODEL_CLIENT = "from anthropic import Anthropic\n"
RED_OPENAI = "import openai\n"
RED_MLX = "from mlx_lm import load\n"
RED_PROPOSER = "from argus.io.local_proposer import LocalProposer\n"
RED_IMPURE = "import httpx\n"
RED_MATCHER = "from sentence_transformers import SentenceTransformer\n"

GREEN_PURE = "import math\nimport re\nfrom argus.types import pipeline\n"


def test_the_checker_catches_every_fence_crossing():
    """The checker fires on each shape the fences forbid.

    Written first and asserted here because three of the four fences currently
    guard files that do not exist: without this, the whole module would be
    green while checking nothing.
    """
    banned = MODEL_CLIENT_ROOTS | IMPURE_ROOTS
    for label, sample in [
        ("anthropic", RED_MODEL_CLIENT),
        ("openai", RED_OPENAI),
        ("mlx_lm", RED_MLX),
        ("httpx", RED_IMPURE),
    ]:
        assert fence_violations(sample, banned, PROPOSER_MODULES), f"missed {label}"

    assert fence_violations(RED_PROPOSER, set(), PROPOSER_MODULES), "missed the proposer import"
    assert fence_violations(RED_MATCHER, MATCHING_MODEL_ROOTS, set()), "missed the matching model"
    assert not fence_violations(GREEN_PURE, banned, PROPOSER_MODULES), "false positive on pure code"


def test_core_imports_no_model_client():
    """Fence 1 — `core ✗ model_client`, over the whole live core tree.

    This is the fence import-linter structurally cannot express: its `layers`
    contract constrains only inter-layer `argus.*` edges, so a third-party
    client import inside `core/` is invisible to it.
    """
    assert CORE.exists(), f"core tree missing at {CORE}"
    banned = MODEL_CLIENT_ROOTS | IMPURE_ROOTS
    failures: list[str] = []
    for py in _core_files():
        for v in fence_violations(py.read_text(), banned, PROPOSER_MODULES):
            failures.append(f"{py.relative_to(REPO_ROOT)}: {v}")
    assert not failures, "core ✗ model_client:\n  " + "\n  ".join(failures)


def test_grounding_imports_neither_proposer_nor_matching_model():
    """Fences 2 and 3 — both guard `core/grounding.py` (S3).

    S3 verifies that the proposer's signals resolve and co-locate. It does not
    re-judge them, and it does not perform the match itself: an exemplar match
    is a correlated signal produced in the proposer, and a gate that produced
    its own would be corroborating itself.
    """
    grounding = CORE / "grounding.py"
    if not grounding.exists():
        return  # reported by test_fence_coverage_is_visible
    code = grounding.read_text()
    proposer_hits = fence_violations(code, set(), PROPOSER_MODULES)
    matcher_hits = fence_violations(code, MATCHING_MODEL_ROOTS | MODEL_CLIENT_ROOTS, set())
    assert not proposer_hits, "grounding ✗ proposer:\n  " + "\n  ".join(proposer_hits)
    assert not matcher_hits, "grounding ✗ matching_model:\n  " + "\n  ".join(matcher_hits)


def test_aggregate_imports_no_model_client():
    """Fence 4 — the corroboration aggregator is pure: no model, no clock, no RNG."""
    aggregate = CORE / "corroboration.py"
    if not aggregate.exists():
        return  # reported by test_fence_coverage_is_visible
    banned = MODEL_CLIENT_ROOTS | IMPURE_ROOTS | {"random", "secrets", "time", "datetime"}
    hits = fence_violations(aggregate.read_text(), banned, PROPOSER_MODULES)
    assert not hits, "aggregate ✗ model_client:\n  " + "\n  ".join(hits)


def test_fence_coverage_is_visible():
    """Name every fence whose guarded file does not exist yet.

    The plan records that three of four fences were satisfied only by the
    absence of the code they guard. This test makes that absence *visible*
    instead of letting it read as compliance. It does not fail on absence —
    the milestones that create those files are not done — but it prints what is
    unguarded, so no one mistakes this module for full coverage.

    When `core/grounding.py` and `core/corroboration.py` land, the two tests
    above begin checking them with no edit here.
    """
    absent = {
        fence: target
        for fence, target in FENCE_TARGETS.items()
        if not (REPO_ROOT / "src" / "argus" / target).exists()
    }
    covered = len(FENCE_TARGETS) - len(absent)
    print(
        f"\nfence coverage: 1 live (core ✗ model_client) + {covered} of "
        f"{len(FENCE_TARGETS)} file-specific fences"
    )
    for fence, target in sorted(absent.items()):
        print(f"  VACUOUS: {fence} — {target} does not exist yet")
    # The live fence must always be real; the others are milestone-gated.
    assert CORE.exists()
