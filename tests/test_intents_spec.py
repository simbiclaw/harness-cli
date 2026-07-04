"""Acceptance Test for M5 of 0000-upgrade-spine-to-v6.md.

Asserts the INTENTS semantic-layer spec is coherent (names _rubric/ shelf
with three modules, states anchor level = scope, places history at L3),
and ARCHITECTURE.md references ADR-0002.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

INTENTS_SPEC = REPO_ROOT / "docs" / "product-specs" / "shared" / "intents-semantic-layer.md"
ARCHITECTURE = REPO_ROOT / "ARCHITECTURE.md"


def _canonical(text: str) -> str:
    return text.lower().replace(" ", "")


def test_semantic_layer_spec_coherent() -> None:
    """M5 Acceptance Test: the INTENTS spec names the _rubric/ shelf with three
    modules, states anchor level = scope, places history at L3, and
    ARCHITECTURE.md references ADR-0002."""
    assert INTENTS_SPEC.exists(), (
        "intents-semantic-layer.md must exist"
    )

    spec = INTENTS_SPEC.read_text()
    spec_c = _canonical(spec)

    # Names the _rubric/ shelf with three modules
    assert "_rubric" in spec, (
        "intents-semantic-layer.md must name the _rubric/ shelf"
    )
    rubric_modules = ["rules", "acoustic", "phrase"]
    for mod in rubric_modules:
        assert mod in spec_c, (
            f"intents-semantic-layer.md must reference the '{mod}' rubric module"
        )

    # States anchor level = scope (facts are anchored by scope/domain)
    anchor_indicators = ["anchor level", "anchorlevel", "scope"]
    has_anchor = any(indicator in spec_c for indicator in anchor_indicators)
    assert has_anchor, (
        "intents-semantic-layer.md must describe the anchor level (scope)"
    )

    # Places history at L3 (case level)
    history_at_l3 = (
        ("l3" in spec_c or "level 3" in spec_c or "level3" in spec_c)
        and ("history" in spec_c or "cookbook" in spec_c or "errors" in spec_c)
    )
    assert history_at_l3, (
        "intents-semantic-layer.md must place history at L3 (case level)"
    )

    # ARCHITECTURE.md references ADR-0002
    arch_text = ARCHITECTURE.read_text()
    arch_c = _canonical(arch_text)
    # ADR references may appear as "adr/0002" or "adr-0002"
    assert "adr/0002" in arch_c or "adr-0002" in arch_c or "adr0002" in arch_c.replace("/", ""), (
        "ARCHITECTURE.md must reference ADR-0002"
    )
