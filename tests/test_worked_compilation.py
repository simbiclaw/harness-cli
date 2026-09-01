"""M8 acceptance tests — worked compilation over the real 27-item rubric (9003).

Drives the runner's deterministic loop headlessly over the REAL inputs
(docs/exec-plans/active/9003-m8-worked-compilation/) into a pytest tmp_path —
never through the INTENTS symlink. The B-E-refined signals are an
authoring-time layer on top of this deterministic contract and are not
exercised here; these tests pin the §3.6b worked-compilation contract:
27 = 25 compiled nodes + 2 dimension_coverage_gap rows, no invented values,
synthesized per-dimension hard-fail gates, and manifest coverage of every
lossy item.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

pytest.importorskip("argus.core.compiler")  # Requires: M5 — skip until core lands

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER = REPO_ROOT / ".claude" / "skills" / "rubric-compiler" / "scripts" / "run_compile.py"
INPUTS = REPO_ROOT / "docs" / "exec-plans" / "active" / "9003-m8-worked-compilation"

DEFERRED_ITEMS = {"6", "7"}  # marked * in the rubric — external system data
OPERATIONAL_COUNT = 25

# The deterministic chain's structural completeness markers — everything else
# that is checkable: false is genuine residue the manifest must name.
FALLBACK_EXACT = "quality of the agent's handling as judged against the pass standard"


@pytest.fixture(scope="module")
def staged_run(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("m8") / "out"
    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "loop",
            "--inputs",
            str(INPUTS),
            "--out",
            str(out),
            "--evaluator",
            "mock",
            "--no-epoch-commit",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return out


def _manifest(out: Path) -> dict:
    return json.loads((out / "tree" / "_meta" / "residue-manifest.yaml").read_text())


def test_all_items_compiled(staged_run):
    """Every rubric item produces a node or a manifest row: 25 nodes; items
    6/7 produce dimension_coverage_gap rows (defer_until_source_connected)."""
    rubric = yaml.safe_load((INPUTS / "specific-rubric.yaml").read_text())
    assert len(rubric["items"]) == 27
    nodes = sorted((staged_run / "nodes").glob("item-*.json"))
    node_ids = {p.stem.removeprefix("item-") for p in nodes}
    assert len(nodes) == OPERATIONAL_COUNT
    assert node_ids == {it["id"] for it in rubric["items"]} - DEFERRED_ITEMS
    gap_rows = [
        r for r in _manifest(staged_run)["rows"] if r.get("kind") == "dimension_coverage_gap"
    ]
    gap_items = {i for r in gap_rows for i in (r.get("source_items") or [])}
    assert gap_items == DEFERRED_ITEMS
    for row in gap_rows:
        assert row.get("data_dependency"), row
        assert row.get("disposition") == "defer_until_source_connected", row


def test_no_invented_values(staged_run):
    """Every extracted lexical phrase traces to the item's own rubric text
    (text / standards / NA condition) — nothing invented (M8 rule)."""
    rubric = yaml.safe_load((INPUTS / "specific-rubric.yaml").read_text())
    by_id = {it["id"]: it for it in rubric["items"]}
    for path in sorted((staged_run / "nodes").glob("item-*.json")):
        node = json.loads(path.read_text())
        item = by_id[node["node_id"].removeprefix("item-")]
        corpus = "".join(
            str(item.get(key) or "")
            for key in ("text", "pass_standard", "fail_standard", "na_condition")
        )
        for extraction in node.get("values_extracted") or []:
            if extraction.get("kind") != "lexical":
                continue
            for phrase in extraction["spec"]["phrases"]:
                assert phrase in corpus, f"{node['node_id']}: {phrase!r} not in rubric text"


def test_hard_fail_rules_per_dimension(staged_run):
    """Each dimension with an IMMEDIATE-FAIL threshold in the generic skill
    has a synthesized (never copied) hard-fail gate in gates/{dimension}.yaml."""
    skill = yaml.safe_load((INPUTS / "generic-skill.yaml").read_text())
    gated = {rule["dimension"] for rule in skill["hard_threshold_mechanism"]["rules"]}
    for dimension in gated:
        gate_path = staged_run / "tree" / "_rubric" / "gates" / f"{dimension}.yaml"
        assert gate_path.exists(), f"missing gate for {dimension}"
        gate = yaml.safe_load(gate_path.read_text())
        rule = gate["hard_fail_rule"]
        assert rule.get("synthesized") is True
        assert len(rule["trigger"]["items"]) >= 2  # many-to-one, not a copied threshold


def test_manifest_covers_all_lossy_items(staged_run):
    """Every item whose node carries genuine model-quarantined residue (a
    checkable:false signal beyond the declared fallbacks) has a
    within_dimension manifest row naming what was left behind."""
    covered = {
        i
        for r in _manifest(staged_run)["rows"]
        if r.get("kind") == "within_dimension"
        for i in (r.get("source_items") or [])
    }
    for path in sorted((staged_run / "nodes").glob("item-*.json")):
        node = json.loads(path.read_text())
        lossy = any(
            not s.get("checkable")
            and not str(s.get("description") or "").startswith("model-judged")
            and str(s.get("description") or "") != FALLBACK_EXACT
            for lane in ("fail", "excellence")
            for s in (node.get("signals") or {}).get(lane) or []
        )
        item_id = node["node_id"].removeprefix("item-")
        if lossy:
            assert item_id in covered, f"lossy item {item_id} missing manifest row"
            row = next(
                r
                for r in _manifest(staged_run)["rows"]
                if r.get("kind") == "within_dimension" and item_id in (r.get("source_items") or [])
            )
            assert row.get("left_behind"), row
