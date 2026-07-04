"""Acceptance Test for M4 of 0000-upgrade-spine-to-v6.md.

Asserts fact-checking.md defines the two-stage score→adjust contract,
that history is not an argument to score, and the verdict carries
raw, adjusted, and applied_precedents.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SPEC = REPO_ROOT / "docs" / "product-specs" / "argus" / "fact-checking.md"


def _canonical(text: str) -> str:
    """Remove spaces and downcase for fuzzy matching."""
    return text.lower().replace(" ", "")


def test_two_stage_score_then_adjust() -> None:
    """M4 Acceptance Test: fact-checking.md describes score(facts, rubric)
    then adjust(raw, history), and the verdict shape records raw, adjusted,
    and applied_precedents."""
    text = SPEC.read_text()
    c = _canonical(text)

    # 1. Must contain both stage signatures
    assert _canonical("score(facts, rubric)") in c, (
        "fact-checking.md must contain the signature 'score(facts, rubric)'"
    )
    assert _canonical("adjust(raw, history)") in c, (
        "fact-checking.md must contain the signature 'adjust(raw, history)'"
    )

    # 2. score must NOT receive history as an argument
    bad_signatures = [
        "score(facts, rubric, history)",
        "score(facts, history, rubric)",
        "score(facts,history)",
    ]
    for bad in bad_signatures:
        assert _canonical(bad) not in c, (
            f"score() must not receive history as an argument; "
            f"found suspicious signature matching '{bad}'"
        )

    # 3. The verdict must carry raw, adjusted, and applied_precedents fields
    text_lower = text.lower()
    assert "raw" in text_lower, (
        "fact-checking.md must reference the 'raw' verdict field"
    )
    assert "adjusted" in text_lower, (
        "fact-checking.md must reference the 'adjusted' verdict field"
    )
    assert "applied_precedents" in c, (
        "fact-checking.md must reference 'applied_precedents' on the verdict"
    )

    # 4. Must reference ADR-0001
    assert "adr0001" in _canonical(text).replace("-", ""), (
        "fact-checking.md must reference ADR-0001"
    )
