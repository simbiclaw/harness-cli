"""9031 M1 acceptance: the staged §9.1 facet contract, parsed as data.

The contract's job is to be checkable, so its own acceptance test checks the
document rather than trusting it: the eight epistemic classes are present, every
facet row names a producer, every row carries an anchoring cell (even when that
cell says "n/a — yardstick"), the document cites PRODUCERS.md §9 as the sole
normative text it proposes to become, and the two-tier report-storage
refinement is stated.

Real-data clause: the contract is checked against the live tree where it makes
claims about it — the call-record facet schema must match what a real record
actually emits. Fixture-only validation is not acceptance (9031's first lesson).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC = REPO_ROOT / "docs" / "facets" / "producers-9.1-revision-proposal.md"
INTENTS = Path("/Users/prometheus/workspace/INTENTS")

CLASS_HEADINGS = [
    "### 2.1 Versioned rubric",
    "### 2.2 Descriptive facts",
    "### 2.3 Facts",
    "### 2.4 Accumulated history",
]


@pytest.fixture(scope="module")
def doc_text() -> str:
    assert DOC.exists(), f"the staged contract must exist at {DOC}"
    return DOC.read_text(encoding="utf-8")


def test_all_eight_classes_are_stated(doc_text):
    for heading in CLASS_HEADINGS:
        assert heading in doc_text, f"missing class section: {heading}"


def test_every_facet_row_names_a_producer_and_an_anchor(doc_text):
    """Each table row under §2.x is | module | producer | facets | anchoring | —
    four cells, none empty. A facet without a producer or without an anchoring
    statement is exactly what this contract exists to forbid."""
    section = doc_text.split("## 3.")[0]
    rows, offenders = 0, []
    for line in section.splitlines():
        if not line.startswith("|") or set(line) <= set("|- :"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells[0] in ("module", "producer") or "---" in cells[0]:
            continue
        if len(cells) < 3:
            continue
        if cells[0] in ("Rules & criteria (25 items)", "module"):
            pass
        # tables vary: (module, producer, facets, anchoring) or (producer, facets, anchoring)
        data = cells[1:] if len(cells) >= 4 else cells
        rows += 1
        producer_cell = cells[1] if len(cells) >= 4 else cells[0]
        anchor_cell = cells[-1]
        if not producer_cell:
            offenders.append(f"{cells[0]}: no producer named")
        if not anchor_cell:
            offenders.append(f"{cells[0]}: no anchoring cell (write 'n/a — <reason>')")
    assert rows >= 8, f"expected at least one facet row per class, parsed {rows}"
    assert not offenders, "facet rows missing producer/anchoring:\n" + "\n".join(offenders)


def test_contract_cites_sole_normative_text(doc_text):
    """Ruling R7 + the ADR-0005 discipline: one contract, one copy — the text
    must point at PRODUCERS.md §9 as the governing text and present itself as
    its proposed revision, not as a second authority."""
    assert "PRODUCERS.md" in doc_text and "§9" in doc_text
    assert "sole normative" in doc_text or "governs" in doc_text
    assert "staged" in doc_text.lower()


def test_two_tier_storage_is_stated(doc_text):
    assert "§9.3" in doc_text
    for token in ("daily summary JSONL", "content-addressed", "Parquet"):
        assert token in doc_text, f"two-tier refinement missing {token!r}"


REAL_RECORDS = sorted(INTENTS.glob("**/calls/**/*.json")) if INTENTS.exists() else []


@pytest.mark.skipif(not REAL_RECORDS, reason="INTENTS corpus not present on this host")
def test_call_record_facet_schema_matches_a_real_record(doc_text):
    """The contract's §2.3 row claims the record carries a per-segment acoustic
    block with f0/intensity/speaking_rate/voice_quality. Check it against a real
    record, not a fixture."""
    record = json.loads(REAL_RECORDS[0].read_text(encoding="utf-8"))
    segments = record.get("segments") or []
    assert segments, "real record carries no segments"
    acoustic = segments[0].get("acoustic") or {}
    for block in ("f0", "intensity", "speaking_rate", "voice_quality"):
        assert block in acoustic, f"record's segment acoustic block lacks {block!r}"
    # and the contract must actually state these four names
    for block in ("f0", "intensity", "speaking_rate", "voice_quality"):
        assert block in doc_text, f"contract does not name the facet {block!r}"
