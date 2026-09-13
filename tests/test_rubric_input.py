"""Acceptance tests for 9021 M15 — the human rubric as compiler input.

The rubric is a real operational QA standard for a Chinese government-services
call centre, transcribed from an internal scoring sheet. Rebuilding it needs the
client's QA team, not engineering time, so the one thing that must not happen
here is a lossy hand-copy.

It is therefore generated mechanically from `simbiclaw/sim@0c2cccd`
`config/rubric_items.py` rather than retyped — see `scripts/build_rubric_yaml.py`.
M5 was rejected for exactly the failure a hand transcription invites: two enums
were rewritten from memory and the acceptance test could not see it.

These tests assert the sheet's own structural invariants, which were established
by reading the source and are independent of how the YAML was produced. A
transcription error that changed a count, dropped an item, or moved the veto
would fail here.

The scored set is 25 of the 27 rows: items 6 and 7 need a service-record store
and a workflow system this evaluator cannot read. They stay in the sheet with
their reason recorded — deleting them would make the exclusion unauditable and
irreversible.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

RUBRIC = Path(__file__).resolve().parent.parent / "docs" / "rubric" / "specific-rubric-27.yaml"

# Counts read off the source sheet. Ids run 1-27 in category order.
EXPECTED_CATEGORY_COUNTS = {
    "流程遵守": 7,
    "态度规范": 7,
    "技能技巧": 7,
    "特殊项": 1,
    "准确性": 5,
}
DATA_DEPENDENT_IDS = {6, 7}
VETO_IDS = {27}
WEIGHTED_IDS = {6, 7}
REQUIRED_KEYS = {"id", "category", "name", "pass_criteria", "fail_criteria"}


@pytest.fixture(scope="module")
def rubric() -> dict:
    assert RUBRIC.exists(), f"rubric input missing at {RUBRIC}"
    return yaml.safe_load(RUBRIC.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def items(rubric) -> list[dict]:
    return rubric["items"]


def test_twenty_seven_rows_with_contiguous_ids(items):
    """All 27 rows survive. Ids are contiguous 1-27 with no gaps or repeats."""
    assert len(items) == 27
    assert sorted(i["id"] for i in items) == list(range(1, 28))


def test_category_counts_match_the_sheet(items):
    """7/7/7/1/5. A dropped or miscategorised row moves one of these."""
    counts: dict[str, int] = {}
    for i in items:
        counts[i["category"]] = counts.get(i["category"], 0) + 1
    assert counts == EXPECTED_CATEGORY_COUNTS


def test_every_row_carries_the_required_keys(items):
    """No row is half-transcribed."""
    missing = {
        i["id"]: sorted(REQUIRED_KEYS - set(i))
        for i in items
        if not REQUIRED_KEYS <= set(i)
    }
    assert not missing, f"rows missing required keys: {missing}"


def test_no_row_has_empty_criteria_text(items):
    """Empty criteria are fed verbatim into a prompt and silently produce nothing.

    Item 1 carries an empty `fail_criteria` upstream. That is a real defect in
    the source sheet, not a transcription slip, so it is recorded rather than
    silently filled: the YAML carries `fail_criteria_missing: true` and this
    test allows exactly the ids that declare it.
    """
    offenders = []
    for i in items:
        for key in ("pass_criteria", "fail_criteria"):
            if not str(i.get(key, "")).strip() and not i.get(f"{key}_missing"):
                offenders.append(f"item {i['id']}: {key} empty and undeclared")
    assert not offenders, "\n  ".join([""] + offenders)


def test_the_veto_item_is_the_privacy_criterion(items):
    """Exactly one veto, and it is the privacy boundary.

    Under the Q3 mapping this item routes to Procedural Accuracy as a fully
    checkable structural boundary, so it does not depend on the judgment gates.
    A second veto appearing here would change the shape of that decision.
    """
    veto = {i["id"] for i in items if i.get("is_veto")}
    assert veto == VETO_IDS
    privacy = next(i for i in items if i["id"] == 27)
    assert "隐私" in privacy["name"] or "信息" in privacy["name"]


def test_weighted_items_are_six_and_seven(items):
    """The only two double-weighted rows.

    These are also the two excluded for data dependency, so once the scored set
    is 25 every scored row weighs 1.0 and the weighted path has no non-trivial
    case left. M10's weight test needs a synthetic fixture or it passes
    vacuously — recorded in the plan's Decision Log.
    """
    weighted = {i["id"] for i in items if float(i.get("weight", 1.0)) != 1.0}
    assert weighted == WEIGHTED_IDS


def test_data_dependent_items_are_declared_not_deleted(items):
    """Items 6 and 7 stay in the sheet, each naming the system it needs."""
    declared = {i["id"] for i in items if i.get("data_dependency")}
    assert declared == DATA_DEPENDENT_IDS
    for i in items:
        if i["id"] in DATA_DEPENDENT_IDS:
            assert str(i["data_dependency"]).strip(), f"item {i['id']}: empty reason"


def test_scored_set_is_twenty_five(items):
    """The operational scope: 27 rows, 25 scored."""
    scored = [i for i in items if not i.get("data_dependency")]
    assert len(scored) == 25
    assert DATA_DEPENDENT_IDS.isdisjoint({i["id"] for i in scored})


def test_provenance_is_recorded(rubric):
    """The document says where it came from and how it was produced.

    A rubric with no provenance cannot be re-verified against its source, and
    this one was generated rather than typed precisely so that it can be.
    """
    assert rubric["source"]["repo"] == "simbiclaw/sim"
    assert rubric["source"]["commit"].startswith("0c2cccd")
    assert "config/rubric_items.py" in rubric["source"]["path"]
    assert rubric["generated_by"].endswith("build_rubric_yaml.py")
