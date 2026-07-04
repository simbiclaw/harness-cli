"""Acceptance Test for M2 of 0000-upgrade-spine-to-v6.md.

Asserts all four foundational ADRs exist, are well-formed, and
docs/adr/ is no longer empty.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

ADR_DIR = REPO_ROOT / "docs" / "adr"

REQUIRED_ADRS = [
    "0001-expertise-epistemic-classes-and-argus-eval-function.md",
    "0002-intents-path-as-ontology.md",
    "0003-knowledge-calibration-dissolves-to-write-time-ownership.md",
    "0004-expertise-library-is-a-runtime-artifact.md",
]


def test_four_foundational_adrs_exist_and_are_wellformed() -> None:
    """M2 Acceptance Test: all four ADRs exist, each has Status and Decision,
    and docs/adr/ is not empty."""
    assert ADR_DIR.exists(), (
        f"docs/adr/ directory must exist"
    )
    assert ADR_DIR.is_dir(), (
        f"docs/adr/ must be a directory"
    )

    adr_files = list(ADR_DIR.glob("*.md"))
    assert adr_files, "docs/adr/ must not be empty"

    failures: list[str] = []

    for filename in REQUIRED_ADRS:
        path = ADR_DIR / filename
        if not path.exists():
            failures.append(f"Missing ADR: {filename}")
            continue

        text = path.read_text()

        # Each ADR must have a Status line (bold)
        if "**Status**:" not in text and "**Status:**" not in text:
            failures.append(f"{filename}: missing '**Status**:' line")

        # Each ADR must have a ## Decision section
        if "## Decision" not in text:
            failures.append(f"{filename}: missing '## Decision' section")

    assert not failures, "\n  ".join([""] + failures)

    # Also assert no unexpected ADRs (exactly these four)
    adr_names = {p.name for p in adr_files}
    expected = set(REQUIRED_ADRS)
    extra = adr_names - expected
    assert not extra, (
        f"Unexpected files in docs/adr/ (only the four foundational ADRs "
        f"should exist at this milestone): {extra}"
    )
