"""Acceptance tests for M3 — Corroborator classifier + residue declarer (9003).

RED phase: these tests fail until `src/argus/core/compiler/classify.py` is
implemented (module import error = the documented RED state; committed only
when green).

Pure functions per the plan's M3 contract: A3 classify_corroborators, A4
declare_residue, rev.4 classify_gap, assign_escape_tier.
"""

from __future__ import annotations

from argus.core.compiler.classify import (
    assign_escape_tier,
    classify_corroborators,
    classify_gap,
    declare_residue,
)


def make_item(**overrides) -> dict:
    item = {
        "id": "22",
        "text": "情绪安抚：客户情绪激动时先安抚再处理",
        "values": {"named_phrases": ["您别着急", "我理解"], "numeric_thresholds": []},
        "na_condition": None,
        "pass_standard": "情绪激动场景先表达理解再进入处理",
        "fail_standard": "无视客户情绪直接进入流程",
        "depends_on": [],
    }
    item.update(overrides)
    return item


def make_signals(**overrides) -> dict:
    signals = {
        "fail": [
            {"id": "22-S01", "description": "transcript contains one of the named phrases: 您别着急",
             "severity": "high", "checkable": True, "audit_result": "pass"}
        ],
        "excellence": [],
        "rejected": [],
    }
    signals.update(overrides)
    return signals


# ── A3: corroborator classification by error-source disjointness ─────────────


class TestClassifyCorroborators:
    def test_acoustic_measurement_is_independent(self):
        """Acoustic measurement → independent (weight 1.0)."""
        result = classify_corroborators(
            {"id": "C22"},
            [{"signal_type": "acoustic_measurement", "node_ref": "call-42/acoustic/f0-range"}],
        )
        assert result == [
            {"signal_type": "acoustic_measurement", "node_ref": "call-42/acoustic/f0-range",
             "independence_class": "independent"}
        ]

    def test_error_case_match_is_correlated(self):
        """Exemplar/case match → correlated (W_C 0.4)."""
        result = classify_corroborators(
            {"id": "C22"},
            [{"signal_type": "error_case_match", "node_ref": "INTENTS/errors.case-0042.yaml"}],
        )
        assert result[0]["independence_class"] == "correlated"

    def test_soft_plus_soft_is_redundant(self):
        """Another model-judged text criterion → redundant (0.0), rejected by AUTH-4."""
        result = classify_corroborators(
            {"id": "C22"},
            [{"signal_type": "soft_text", "node_ref": "item-26-S01"}],
        )
        assert result[0]["independence_class"] == "redundant"

    def test_d16_framework_not_corroborator(self):
        """The acoustic framework / phrase lexicon are rubric, NOT corroborators (D16)."""
        for ref in ("_rubric/evidence/acoustic/indicators.yaml", "_rubric/evidence/phrase-keyword/lexicon.yaml"):
            result = classify_corroborators(
                {"id": "C22"},
                [{"signal_type": "acoustic_framework", "node_ref": ref}],
            )
            assert result == [], f"framework ref {ref} must be excluded, not classified (D16)"

    def test_mixed_signals_classified(self):
        result = classify_corroborators(
            {"id": "C22"},
            [
                {"signal_type": "acoustic_measurement", "node_ref": "call-42/f0"},
                {"signal_type": "error_case_match", "node_ref": "errors.case-9.yaml"},
                {"signal_type": "soft_text", "node_ref": "item-26-S01"},
            ],
        )
        classes = [c["independence_class"] for c in result]
        assert classes == ["independent", "correlated", "redundant"]


# ── B-verification fix round (2026-08-12): F1/F2/F3 ─────────────────────────


class TestBFixRound:
    """Adversarial findings F1-F3 closed with red tests. RED phase."""

    # F1: programmatic/instrument families are INDEPENDENT (I6 weight table)
    def test_f1_programmatic_types_independent(self):
        for signal_type in ("lexical_match", "ordered_match", "lookup", "duration", "turn_count"):
            result = classify_corroborators(
                {"id": "C22"},
                [{"signal_type": signal_type, "node_ref": f"call-42/{signal_type}/span-7"}],
            )
            assert result and result[0]["independence_class"] == "independent", (
                f"{signal_type} must be independent (weight 1.0), got {result}"
            )

    # F2: D16 signal-type exclusion must strip + casefold
    def test_f2_d16_type_padding_excluded(self):
        for signal_type in (" phrase_lexicon ", "Acoustic Framework", "phrase_lexicon\t"):
            result = classify_corroborators(
                {"id": "C22"},
                [{"signal_type": signal_type, "node_ref": "call-42/f0"}],
            )
            assert result == [], f"padded/cased framework type {signal_type!r} must be excluded (D16)"

    # F3: mixed checkable+model_based must not be coverage with a false rationale
    def test_f3_mixed_signals_not_coverage(self):
        item = make_item(values={"named_phrases": [], "numeric_thresholds": []})
        signals = {
            "fail": [
                {"id": "22-S01", "description": "temporal proximity of recommendation", "severity": "high",
                 "checkable": True, "audit_result": "split"},
                {"id": "22-S02", "description": "context adaptation quality", "severity": "high",
                 "checkable": False, "audit_result": "split"},
            ],
            "excellence": [],
            "rejected": [],
        }
        gap = classify_gap(item, "empathy_and_tone", signals)
        assert gap["gap_type"] != "coverage", "mixed gate-checkable coverage must not be classified coverage"
        assert "no compiled signals" not in gap.get("rationale", ""), "rationale must not claim empty coverage"


# ── B2 re-verification fix round (2026-08-12): type normalization ───────────


class TestB2FixRound:
    """B2 findings closed: signal_type normalization shared by framework
    exclusion AND classification. RED phase."""

    def test_b2_order_match_independent(self):
        result = classify_corroborators(
            {"id": "C22"},
            [{"signal_type": "order_match", "node_ref": "call-42/span-7"}],
        )
        assert result[0]["independence_class"] == "independent", "order_match must be independent (1.0)"

    def test_b2_phrase_keyword_type_excluded(self):
        for signal_type in ("phrase-keyword", "Phrase-Keyword"):
            result = classify_corroborators(
                {"id": "C22"},
                [{"signal_type": signal_type, "node_ref": "call-42/f0"}],
            )
            assert result == [], f"{signal_type!r} must be D16-excluded"

    def test_b2_spaced_acoustic_measurement_independent(self):
        for signal_type in ("acoustic measurement", "Acoustic Measurement"):
            result = classify_corroborators(
                {"id": "C22"},
                [{"signal_type": signal_type, "node_ref": "call-42/f0"}],
            )
            assert result and result[0]["independence_class"] == "independent", (
                f"{signal_type!r} must be independent, not framework, not correlated"
            )


# ── B3 re-verification fix round (2026-08-12): camelCase normalization ──────


class TestB3FixRound:
    """B3 findings closed: camelCase forms must normalize to their families."""

    def test_b3_camel_case_independent(self):
        for signal_type in ("OrderMatch", "AcousticMeasurement", "LexicalMatch", "LookupValue", "DurationMs"):
            result = classify_corroborators(
                {"id": "C22"},
                [{"signal_type": signal_type, "node_ref": "call-42/f0"}],
            )
            assert result and result[0]["independence_class"] == "independent", (
                f"camelCase {signal_type!r} must be independent"
            )

    def test_b3_camel_case_redundant(self):
        result = classify_corroborators(
            {"id": "C22"},
            [{"signal_type": "SoftText", "node_ref": "item-26-S01"}],
        )
        assert result and result[0]["independence_class"] == "redundant", "SoftText must be redundant"

    def test_b3_camel_case_framework_excluded(self):
        for signal_type in ("PhraseLexicon", "PhraseKeyword", "AcousticFramework"):
            result = classify_corroborators(
                {"id": "C22"},
                [{"signal_type": signal_type, "node_ref": "call-42/f0"}],
            )
            assert result == [], f"camelCase framework type {signal_type!r} must be D16-excluded"


# ── A4: residue declaration ──────────────────────────────────────────────────


class TestDeclareResidue:
    def test_residue_names_rejected_standards(self):
        signals = make_signals(
            rejected=[{"standard": "坐席应表现灵活主动", "reason": "adjective without concrete referent"}]
        )
        residue = declare_residue(signals, "empathy_and_tone")
        assert residue, "residue must never be empty"
        assert "灵活" in residue, "residue must name the rejected standard"

    def test_residue_never_empty(self):
        """Empty residue → fails AUTH-2; declare_residue must always return non-empty."""
        assert declare_residue(make_signals(), "empathy_and_tone")
        assert declare_residue(
            {"fail": [], "excellence": [], "rejected": []}, "commercial_guidance"
        ), "even a fully-rejected criterion declares residue"

    def test_residue_names_dimension_holistic_aspects(self):
        residue = declare_residue(make_signals(), "empathy_and_tone")
        assert "empathy_and_tone" in residue or "语气" in residue or "维度" in residue


# ── rev.4: gap classification ────────────────────────────────────────────────


class TestClassifyGap:
    def test_values_gap_from_lexical(self):
        gap = classify_gap(make_item(), "empathy_and_tone", make_signals())
        assert gap["gap_type"] == "values"

    def test_perceiver_gap_from_model_based(self):
        item = make_item(values={"named_phrases": [], "numeric_thresholds": []})
        signals = make_signals(
            fail=[{"id": "22-S01", "description": "emotional handling quality",
                   "severity": "high", "checkable": False, "audit_result": "model_only"}]
        )
        assert classify_gap(item, "empathy_and_tone", signals)["gap_type"] == "perceiver"

    def test_calibration_surface_form_from_gated_model_based(self):
        item = make_item(
            id="21",
            values={"named_phrases": [], "numeric_thresholds": []},
            depends_on=["20"],
        )
        signals = make_signals(
            fail=[{"id": "21-S01", "description": "context adaptation quality",
                   "severity": "high", "checkable": False, "audit_result": "model_only"}]
        )
        assert classify_gap(item, "commercial_guidance", signals)["gap_type"] == "calibration_surface_form"

    def test_proxy_gap_from_numeric_threshold(self):
        item = make_item(
            values={"named_phrases": [], "numeric_thresholds": [{"name": "speaking_rate", "threshold": 120}]}
        )
        assert classify_gap(item, "procedural_accuracy", make_signals())["gap_type"] == "proxy"

    def test_coverage_gap_from_no_signals(self):
        item = make_item(values={"named_phrases": [], "numeric_thresholds": []})
        signals = make_signals(fail=[], excellence=[], rejected=[{"standard": "x", "reason": "y"}])
        assert classify_gap(item, "problem_resolution", signals)["gap_type"] == "coverage"


# ── escape tier ──────────────────────────────────────────────────────────────


class TestAssignEscapeTier:
    def test_proxy_gap_gets_aggressive_escape(self):
        assert assign_escape_tier("proxy") == "aggressive"

    def test_coverage_gap_gets_aggressive_escape(self):
        assert assign_escape_tier("coverage") == "aggressive"

    def test_standard_escapes(self):
        for gap in ("values", "perceiver", "calibration_surface_form"):
            assert assign_escape_tier(gap) == "standard", f"{gap} must be standard"
