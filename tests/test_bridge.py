"""Acceptance tests for M5 — Binary→continuous bridge (9003).

RED phase: these tests fail until `src/argus/core/compiler/bridge.py` is
implemented (module import error = the documented RED state; committed only
when green).

Pure functions per the plan's M5 contract: B-A bind_item_to_dimension, B-B
compile_applicability_gate, B-C synthesize_hard_fail, B-D extract_values,
check_dimension_coverage.
"""

from __future__ import annotations

from argus.core.compiler.bridge import (
    bind_item_to_dimension,
    check_dimension_coverage,
    compile_applicability_gate,
    extract_values,
    synthesize_hard_fail,
)
from argus.core.compiler.validator import check_applicability_gate, check_no_forced_mapping


def make_item(**overrides) -> dict:
    item = {
        "id": "22",
        "text": "情绪安抚：客户情绪激动时先安抚再处理",
        "values": {"named_phrases": ["您别着急", "我理解"], "numeric_thresholds": []},
        "na_condition": None,
        "deduction_weight": None,
        "pass_standard": "情绪激动场景先表达理解再进入处理",
        "fail_standard": "无视客户情绪直接进入流程",
    }
    item.update(overrides)
    return item


def make_align(**overrides) -> dict:
    align = {"22": "empathy_and_tone", "20": "commercial_guidance", "21": "commercial_guidance"}
    align.update(overrides)
    return align


# ── B-A: bind item to dimension ──────────────────────────────────────────────


class TestBindItemToDimension:
    def test_bind_item_via_align(self):
        """Item routes to its align.md dimension with deduction + severity_map."""
        binding = bind_item_to_dimension(
            make_item(deduction_weight=2.0),
            make_align(),
            manifest_epoch="2026-08-12-0123456789abcdef0123456789abcdef01234567",
        )
        assert binding["item_id"] == "22"
        assert binding["dimension"] == "empathy_and_tone"
        assert binding["deduction"] == 2.0
        assert binding["severity_map"] == (
            "calibration://manifest/2026-08-12-0123456789abcdef0123456789abcdef01234567/severity/22"
        )
        assert binding["auto_final_allowed"] is True

    def test_uncalibrated_surface_form_no_auto_final(self):
        """No manifest epoch yet → surface-form-sensitive criteria get auto_final: false (AUTH-9)."""
        binding = bind_item_to_dimension(make_item(), make_align(), manifest_epoch=None)
        assert binding["auto_final_allowed"] is False
        assert binding["severity_map"] is None

    def test_unmapped_item_binding_dimension_none(self):
        binding = bind_item_to_dimension(
            make_item(id="24"), make_align(**{"24": None}), manifest_epoch=None
        )
        assert binding["dimension"] is None, "unmapped item binds to no dimension"


# ── B-B: applicability gate ──────────────────────────────────────────────────


class TestCompileApplicabilityGate:
    def test_na_condition_compiles_to_gate(self):
        item = make_item(na_condition="Item 20 为 NA（无营销机会）")
        gate = compile_applicability_gate(item)
        assert gate is not None
        assert "Item 20" in gate["spec"], "gate spec must carry the NA condition"

    def test_no_na_condition_returns_none(self):
        assert compile_applicability_gate(make_item()) is None

    def test_missing_applicability_gate_rejected(self):
        """NA-bearing item without a gate → AUTH-7 rejects (M1 validator cross-check)."""
        node = {
            "node_id": "item-21",
            "human_version": {
                "item_number": 21,
                "text": "积极灵活营销",
                "na_condition": "无营销机会",
            },
            "applicability_gate": None,
        }
        errors = check_applicability_gate(node)
        assert errors, "NA-bearing item without gate must be rejected (AUTH-7)"


# ── B-C: hard-fail synthesis ─────────────────────────────────────────────────


class TestSynthesizeHardFail:
    def test_hard_fail_synthesized_not_copied(self):
        """Many-to-one routing rule, synthesized — never a copied threshold."""
        items = [make_item(id="01"), make_item(id="02"), make_item(id="09")]
        rule = synthesize_hard_fail(items, "procedural_accuracy")
        assert rule is not None
        assert rule["dimension"] == "procedural_accuracy"
        assert set(rule["trigger"]["items"]) == {"item-01", "item-02", "item-09"}, "many-to-one"
        assert rule["synthesized"] is True
        assert "threshold" not in rule, "no copied threshold"

    def test_single_item_no_collective_fail(self):
        assert synthesize_hard_fail([make_item(id="01")], "procedural_accuracy") is None

    def test_empty_items_none(self):
        assert synthesize_hard_fail([], "procedural_accuracy") is None


# ── B-D: value extraction ────────────────────────────────────────────────────


class TestExtractValues:
    def test_values_extracted_from_checklist(self):
        """Named phrases → lexical; numbers → threshold; both at confidence 1.0."""
        item = make_item(
            values={
                "named_phrases": ["您好", "请问有什么可以帮您"],
                "numeric_thresholds": [{"name": "speaking_rate", "threshold": 120, "unit": "wpm"}],
            }
        )
        extractions = extract_values(item)
        lexical = [e for e in extractions if e["kind"] == "lexical"]
        threshold = [e for e in extractions if e["kind"] == "threshold"]
        assert lexical and threshold, "both extraction kinds must be produced"
        assert lexical[0]["confidence"] == 1.0 and threshold[0]["confidence"] == 1.0
        assert "您好" in lexical[0]["spec"]["phrases"]
        assert threshold[0]["spec"]["name"] == "speaking_rate"

    def test_empty_values_no_extractions(self):
        assert (
            extract_values(make_item(values={"named_phrases": [], "numeric_thresholds": []})) == []
        )


# ── coverage check ───────────────────────────────────────────────────────────


class TestCheckDimensionCoverage:
    def test_unmapped_item_not_force_fit(self):
        """Item 24: no adequate dimension → coverage gap row, defer disposition."""
        verdict = check_dimension_coverage(
            make_item(id="24"),
            make_align(**{"24": None}),
            dimensions=["empathy_and_tone", "commercial_guidance", "procedural_accuracy"],
        )
        assert verdict["covered"] is False
        assert verdict["data_dependency"]["connected"] is False
        assert verdict["data_dependency"]["disposition"] == "defer_until_source_connected"
        assert verdict["manifest_row"]["kind"] == "dimension_coverage_gap"
        assert "24" in verdict["manifest_row"]["source_items"]

    def test_mapped_item_covered(self):
        verdict = check_dimension_coverage(
            make_item(id="22"),
            make_align(),
            dimensions=["empathy_and_tone", "commercial_guidance", "procedural_accuracy"],
        )
        assert verdict["covered"] is True
        assert verdict["manifest_row"] is None

    def test_forced_mapping_rejected(self):
        """A node claiming a dimension for an unmapped item → AUTH-10 rejects."""
        node = {
            "node_id": "item-24",
            "dimension": "problem_resolution",
            "source_binary_items": ["24"],
        }
        errors = check_no_forced_mapping(node, align_map={"24": None})
        assert errors, "forced mapping must be rejected (AUTH-10)"


# ── B-verification fix round (2026-08-12): W1/W3/W4 ─────────────────────────


class TestBFixRound:
    """Findings W1/W3/W4 closed with red tests. RED phase."""

    # W1: empty/whitespace epoch must degrade to the no-manifest behavior
    def test_w1_empty_epoch_no_auto_final(self):
        for epoch in ("", "   "):
            binding = bind_item_to_dimension(make_item(), make_align(), manifest_epoch=epoch)
            assert binding["auto_final_allowed"] is False, (
                f"epoch {epoch!r} must not grant auto-final"
            )
            assert binding["severity_map"] is None, (
                f"epoch {epoch!r} must not produce a dangling ref"
            )

    # W3: keyless threshold entries must not fabricate signals
    def test_w3_keyless_threshold_skipped(self):
        item = make_item(values={"named_phrases": [], "numeric_thresholds": [{"name": "x"}, {}]})
        extractions = extract_values(item)
        assert extractions == [], "keyless threshold entries must not fabricate threshold signals"

    # W4: duplicate item ids dedupe in the hard-fail trigger
    def test_w4_duplicate_ids_deduped(self):
        rule = synthesize_hard_fail([make_item(id="01"), make_item(id="01")], "procedural_accuracy")
        assert rule is not None
        assert rule["trigger"]["items"] == ["item-01"], "duplicate ids must dedupe"


# ── no-crash contract (M1/M2/M3/M4 precedent) ────────────────────────────────


class TestNoCrash:
    def test_garbage_inputs_no_crash(self):
        assert bind_item_to_dimension(None, make_align(), None)["item_id"] is None
        assert compile_applicability_gate(None) is None
        assert synthesize_hard_fail(None, "d") is None
        assert extract_values(None) == []
        assert check_dimension_coverage(None, make_align(), [])["covered"] is False
