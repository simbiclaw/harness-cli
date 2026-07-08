"""Acceptance Test for M3 of 0000-upgrade-spine-to-v6.md.

Asserts expertise-library.md classifies Acoustic Feature and Phrase & Keyword
under the Versioned-rubric epistemic class, not under Facts, and names the
three category readers.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SPEC = REPO_ROOT / "docs" / "product-specs" / "shared" / "expertise-library.md"


def test_acoustic_and_phrase_are_rubric() -> None:
    """M3 Acceptance Test: Acoustic Feature and Phrase & Keyword are classified
    as Versioned-rubric, not Facts, and the three category readers exist."""
    text = SPEC.read_text()

    # 1. The spec must have an epistemic-class table or section header
    #    naming "Versioned rubric" or "Versioned-rubric" as a class.
    rubric_markers = [
        "versioned rubric",
        "Versioned rubric",
        "versioned-rubric",
        "Versioned-rubric",
    ]
    has_rubric_class = any(m in text for m in rubric_markers)
    assert has_rubric_class, "expertise-library.md must define a 'Versioned rubric' epistemic class"

    # 2. Acoustic Feature must appear in the rubric class, not in facts
    #    We check by looking for the module name in proximity to the class label.
    #    The spec should place "Acoustic Feature" under the rubric section,
    #    not under a "Descriptive facts" or plain "Facts" section.
    desc_fact_markers = [
        "descriptive facts",
        "Descriptive facts",
        "descriptive-facts",
        "Descriptive-facts",
    ]

    # Find where Acoustic Feature appears and check which section it's in
    lines = text.splitlines()
    current_section: str | None = None
    acoustic_section: str | None = None
    phrase_section: str | None = None

    for line in lines:
        stripped = line.strip().lower()
        # Track which epistemic-class section we're in
        if any(m.lower() in stripped for m in rubric_markers) and (
            stripped.startswith("#") or stripped.startswith("|") or "class" in stripped
        ):
            current_section = "rubric"
        elif any(m.lower() in stripped for m in desc_fact_markers) and (
            stripped.startswith("#") or stripped.startswith("|") or "class" in stripped
        ):
            current_section = "facts"
        elif "history" in stripped and ("accumulated" in stripped or "class" in stripped):
            current_section = "history"

        # Record which section Acoustic and Phrase appear in
        if "acoustic feature" in stripped:
            acoustic_section = current_section
        if "phrase" in stripped and "keyword" in stripped:
            phrase_section = current_section

    assert acoustic_section == "rubric", (
        f"Acoustic Feature must be under the Versioned-rubric class, "
        f"but found under: {acoustic_section}"
    )
    assert phrase_section == "rubric", (
        f"Phrase & Keyword must be under the Versioned-rubric class, "
        f"but found under: {phrase_section}"
    )

    # 3. The three category readers must be named
    #    The spec should describe readers grouped by epistemic class:
    #    rubric reader, facts reader, history reader (or equivalent names)
    reader_indicators = [
        ("rubric", ["rubricreader", "rubric reader", "rubric provider", "versioned rubric reader"]),
        ("facts", ["factsreader", "facts reader", "fact reader", "descriptive facts reader"]),
        (
            "history",
            ["historyreader", "history reader", "history provider", "accumulated history reader"],
        ),
    ]

    # Remove spaces for camelCase matching
    text_no_spaces = text.lower().replace(" ", "")
    for category, patterns in reader_indicators:
        found = any(p.lower().replace(" ", "") in text_no_spaces for p in patterns)
        assert found, (
            f"expertise-library.md must name a {category} category reader. "
            f"Looked for one of: {patterns}"
        )
