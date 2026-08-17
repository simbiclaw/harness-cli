"""Acceptance tests for M2 — Signal Decomposition + Evidence authoring (9003).

RED phase: these tests fail until `src/argus/core/compiler/signals.py` is
implemented (module import error = the documented RED state; committed only
when green).

Pure functions per the plan's M2 contract: A1 decompose_dimension, A2+B-E
decompose_signals, B-F audit_gate_checkable, D5/D9 assign_facets, A2-ac
compile_acoustic_framework, A2-ph compile_phrase_lexicon.
"""

from __future__ import annotations

from argus.core.compiler.signals import (
    assign_facets,
    audit_gate_checkable,
    compile_acoustic_framework,
    compile_phrase_lexicon,
    decompose_dimension,
    decompose_signals,
)


def make_item(**overrides) -> dict:
    item = {
        "id": "22",
        "text": "情绪安抚：客户情绪激动时先安抚再处理",
        "values": {"named_phrases": ["您别着急", "我理解"], "numeric_thresholds": []},
        "na_condition": None,
        "pass_standard": "情绪激动场景先表达理解再进入处理",
        "fail_standard": "无视客户情绪直接进入流程",
    }
    item.update(overrides)
    return item


# ── A2 + B-E: signal decomposition ───────────────────────────────────────────


class TestDecomposeSignals:
    def test_lexical_signal_decomposed(self):
        """A phrase-based criterion decomposes into a gate-checkable lexical FAIL signal."""
        signals = decompose_signals(make_item())
        fail = [s for s in signals["fail"] if s.get("checkable") and s["audit_result"] == "pass"]
        assert any("您别着急" in s["description"] for s in fail), (
            "lexical signal must reference the phrases"
        )
        assert signals["rejected"] == [], "no rejected entries for a clean item"

    def test_ordered_relation_signal_decomposed(self):
        """'acknowledge before resolve' → FAIL signal with ordered-relation evidence shape."""
        item = make_item(fail_standard="坐席应先安抚客户情绪再进入处理")
        signals = decompose_signals(item)
        ordered = [
            s
            for s in signals["fail"]
            if s.get("evidence_shape", {}).get("shape") == "ordered_relation"
        ]
        assert ordered, "ordered-relation signal must be produced"
        s = ordered[0]
        assert s["checkable"] is True
        assert s["audit_result"] == "pass"
        assert s["evidence_shape"]["first"] and s["evidence_shape"]["second"], (
            "ordered pair must be named"
        )

    def test_adjective_signal_rejected(self):
        """'agent should sound empathetic' → rejected, no concrete referent."""
        item = make_item(
            values={"named_phrases": [], "numeric_thresholds": []},
            pass_standard="坐席应表现灵活主动",
            fail_standard="坐席表现混乱",
        )
        signals = decompose_signals(item)
        assert signals["rejected"], (
            "adjective-only standards must be rejected, not silently dropped"
        )
        assert all(not s.get("checkable") for s in signals["fail"]), (
            "no gate-checkable signal from adjectives"
        )

    def test_signal_split_needed(self):
        """'context-appropriate recommendation' → B-F auto-split into programmatic + model_based siblings."""
        item = make_item(
            values={"named_phrases": [], "numeric_thresholds": []},
            pass_standard="结合客户场景给出适当的推荐",
            fail_standard="泛泛推荐或无推荐",
        )
        signals = decompose_signals(item)
        split = [s for s in signals["fail"] if s["audit_result"] == "split"]
        prog = [s for s in split if s["checkable"] is True]
        model = [s for s in split if s["checkable"] is False]
        assert prog and model, (
            "B-F split must produce both a programmatic and a model_based sibling"
        )
        assert (
            "proximity" in prog[0]["description"].lower()
            or "temporal" in prog[0]["description"].lower()
        )
        assert (
            "context" in model[0]["description"].lower()
            or "adaptation" in model[0]["description"].lower()
        )

    def test_excellence_signals_present(self):
        """Pass standards decompose into excellence signals."""
        signals = decompose_signals(make_item())
        assert signals["excellence"], "pass standard must produce at least one excellence signal"


# ── B-F: gate-checkability audit ─────────────────────────────────────────────


class TestAuditGateCheckable:
    def test_lexical_is_pass(self):
        signal = {
            "id": "22-S01",
            "description": "transcript contains one of the named phrases: 您别着急",
        }
        assert audit_gate_checkable(signal) == "pass"

    def test_conclusion_only_is_model_only(self):
        signal = {"id": "22-S02", "description": "agent's emotional handling quality"}
        assert audit_gate_checkable(signal) == "model_only"

    def test_context_appropriate_is_split(self):
        signal = {"id": "20-S03", "description": "context-appropriate recommendation"}
        assert audit_gate_checkable(signal) == "split"


# ── A1: dimension decomposition ──────────────────────────────────────────────


class TestDecomposeDimension:
    def test_dimension_splits_into_candidates_and_residue(self):
        dimension = {
            "name": "commercial_guidance",
            "description": "业务引导：识别机会、针对性推荐、避免泛泛推荐",
        }
        result = decompose_dimension(dimension)
        assert result["candidates"], "signal-decomposable parts must be named"
        assert result["residue"], "non-decomposable judgment parts must be named as residue (A1/A4)"


# ── D5/D9: signal-shaped facets ──────────────────────────────────────────────


class TestAssignFacets:
    def test_programmatic_facet_signal_shaped(self):
        signals = {
            "fail": [{"id": "22-S01", "description": "lexical phrase present", "checkable": True}]
        }
        facets = assign_facets(signals, "values")
        prog = facets["programmatic"]
        assert prog, "programmatic facet must be assigned"
        assert prog[0]["enables_signals"] == ["22-S01"]
        assert prog[0]["indicator"] and prog[0]["calculation"] and prog[0]["output_schema"]

    def test_model_based_facet_carries_prompt(self):
        signals = {
            "fail": [
                {"id": "22-S02", "description": "emotional handling quality", "checkable": False}
            ]
        }
        facets = assign_facets(signals, "perceiver")
        model = facets["model_based"]
        assert model, "model_based facet must be assigned"
        assert model[0]["enables_signals"] == ["22-S02"]
        assert model[0]["prompt"] and model[0]["output_schema"], (
            "extraction prompt authored by the compiler"
        )


# ── A2-ac: acoustic indicator framework ──────────────────────────────────────


class TestAcousticFramework:
    def test_acoustic_framework_has_12_indicators(self):
        indicators = [
            {"name": f"ind{i:02d}", "threshold": 1.0, "unit": "Hz", "description": f"indicator {i}"}
            for i in range(1, 13)
        ]
        entries = compile_acoustic_framework(indicators)
        assert len(entries) == 12
        for e in entries:
            assert e["type"] == "acoustic"
            assert e["values"]["threshold"] is not None
            assert e["values"]["unit"] and e["values"]["description"]


# ── B-verification fix round (2026-08-12): B1-B5 + W2/W3 ────────────────────


class TestBFixRound:
    """Adversarial findings B1-B5, W2, W3 closed with red tests. RED phase."""

    # B1: no-crash contract across all six functions
    def test_b1_no_crash_malformed_inputs(self):
        for bad in (None, "x", []):
            assert decompose_signals(bad)["rejected"], f"decompose_signals({bad!r}) must not crash"
        for bad in (None, "x"):
            assert isinstance(decompose_dimension(bad), dict), "decompose_dimension must not crash"
        assert assign_facets("x", "values") == {"programmatic": [], "model_based": []}
        assert compile_acoustic_framework(None) == []
        assert compile_acoustic_framework("x") == []
        assert compile_phrase_lexicon(None) == {}

    # B2: annotated RubricItem instance must work
    def test_b2_rubric_item_instance(self):
        from argus.types.compiler_schemas import RubricItem

        item = RubricItem(
            id="22",
            text="情绪安抚",
            values={"named_phrases": ["您别着急"], "numeric_thresholds": []},
            pass_standard="先安抚再处理",
            fail_standard="未安抚",
        )
        signals = decompose_signals(item)
        assert signals["fail"], "RubricItem instance must decompose"

    # B3: real ordered forms must not be silently dropped
    def test_b3_ordered_hou_form(self):
        signals = decompose_signals(make_item(fail_standard="坐席先安抚后处理"))
        assert any(
            s.get("evidence_shape", {}).get("shape") == "ordered_relation" for s in signals["fail"]
        ), "先X后Y form must produce an ordered signal"

    def test_b3_english_then_form(self):
        signals = decompose_signals(make_item(fail_standard="acknowledge THEN resolve"))
        assert any(
            s.get("evidence_shape", {}).get("shape") == "ordered_relation" for s in signals["fail"]
        ), "English 'THEN' form must produce an ordered signal"

    def test_b3_unknown_standard_not_dropped(self):
        signals = decompose_signals(make_item(fail_standard="坐席未使用道歉用语"))
        assert signals["fail"], "an unmatched fail standard must never silently vanish"
        assert any(not s["checkable"] for s in signals["fail"]), (
            "unmatched standard becomes model_based"
        )

    # B4: decompose ↔ audit consistency
    def test_b4_audit_consistency_battery(self):
        items = [
            make_item(),
            make_item(fail_standard="坐席先安抚后处理"),
            make_item(
                values={"named_phrases": ["适当回应"], "numeric_thresholds": []},
                pass_standard="坐席应耐心倾听",
                fail_standard="坐席急躁挂断",
            ),
            make_item(
                values={"named_phrases": [], "numeric_thresholds": []},
                pass_standard="结合客户场景给出适当的推荐",
                fail_standard="泛泛推荐或无推荐",
            ),
        ]
        for item in items:
            signals = decompose_signals(item)
            for lane in ("fail", "excellence"):
                for s in signals[lane]:
                    assert audit_gate_checkable(s) == s["audit_result"], (
                        f"mismatch on {s['id']}: stored {s['audit_result']} vs audited {audit_gate_checkable(s)}"
                    )

    # B5: adjective + concrete referent → model_based, not flat-rejected
    def test_b5_adjective_with_referent_model_based(self):
        signals = decompose_signals(
            make_item(
                values={"named_phrases": [], "numeric_thresholds": []},
                pass_standard="坐席应灵活处理客户投诉",
                fail_standard="坐席表现混乱",
            )
        )
        assert signals["fail"], "adjective-with-referent standard must still produce a signal"
        assert any(not s["checkable"] for s in signals["fail"]), (
            "must be model_based, not gate-checkable"
        )

    # W2: non-list lexicon section must not manufacture garbage
    def test_w2_lexicon_non_list_section_empty(self):
        sections = compile_phrase_lexicon({"a": "not-a-list"})
        assert sections == {"a": []}, (
            "non-list section must yield an empty list, not per-char garbage"
        )

    # W3: None id sanitized
    def test_w3_none_id_sanitized(self):
        signals = decompose_signals(make_item(id=None))
        for s in signals["fail"] + signals["excellence"]:
            assert "None-" not in s["id"], "None id must not leak into signal ids"


# ── B2 re-verification fix round (2026-08-12): F1-F4 ────────────────────────


class TestB2FixRound:
    """Findings F1-F4 closed with red tests. RED phase."""

    # F1: 然后 must not corrupt the ordered pair
    def test_f1_ranhou_no_corruption(self):
        signals = decompose_signals(make_item(fail_standard="先安抚然后处理"))
        ordered = [
            s
            for s in signals["fail"]
            if s.get("evidence_shape", {}).get("shape") == "ordered_relation"
        ]
        assert ordered, "先X然后Y must produce an ordered signal"
        shape = ordered[0]["evidence_shape"]
        assert shape["first"] == "安抚", f"first must be '安抚', got {shape['first']!r}"
        assert shape["second"] == "处理", f"second must be '处理', got {shape['second']!r}"

    def test_f1_enumeration_not_glued(self):
        signals = decompose_signals(make_item(fail_standard="先确认，再处理，最后记录"))
        ordered = [
            s
            for s in signals["fail"]
            if s.get("evidence_shape", {}).get("shape") == "ordered_relation"
        ]
        assert ordered
        second = ordered[0]["evidence_shape"]["second"]
        assert "最后" not in second, "second element must cut at the first clause separator"

    # F2: mis-plumbed pydantic models → malformed error shape, not fabricated signals
    def test_f2_misplumbed_model_error_shape(self):
        from argus.types.compiler_schemas import AlignMap, SpecificRubric

        for model in (AlignMap(entries={}), SpecificRubric(items=[])):
            signals = decompose_signals(model)
            assert signals["rejected"], (
                f"{type(model).__name__} must produce a malformed rejection, not signals"
            )

    # F3: comma before then/before must not break the English ordered form
    def test_f3_comma_then_recognized(self):
        signals = decompose_signals(make_item(fail_standard="acknowledge, then resolve"))
        ordered = [
            s
            for s in signals["fail"]
            if s.get("evidence_shape", {}).get("shape") == "ordered_relation"
        ]
        assert ordered, "'acknowledge, then resolve' must be recognized as ordered"

    def test_f3_sentence_prefix_trimmed(self):
        signals = decompose_signals(
            make_item(fail_standard="agent must acknowledge before resolve")
        )
        ordered = [
            s
            for s in signals["fail"]
            if s.get("evidence_shape", {}).get("shape") == "ordered_relation"
        ]
        assert ordered
        first = ordered[0]["evidence_shape"]["first"]
        assert "agent must" not in first, (
            f"first element must be trimmed to the verb, got {first!r}"
        )

    # F4: checkable False signals must never audit "pass"
    def test_f4_model_based_never_audits_pass(self):
        signals = decompose_signals(
            make_item(fail_standard="agent did not confirm satisfaction in the transcript")
        )
        for s in signals["fail"]:
            if not s["checkable"]:
                assert s["audit_result"] == "model_only", (
                    f"checkable=False signal {s['id']} audited {s['audit_result']} — must be model_only"
                )


# ── B3 re-verification fix round (2026-08-12): BLOCK-1 + WARN-1/2/3/4 ───────


class TestB3FixRound:
    """BLOCK-1 and WARN-1..4 closed with red tests. RED phase."""

    # BLOCK-1: doubled connectives must not glue into the second element
    def test_block1_double_connective_not_glued(self):
        for standard, expected_second in (
            ("先A然后B然后C", "B"),
            ("先A再B再C", "B"),
            ("先A后B后C", "B"),
            ("先A然后再B", "B"),
        ):
            signals = decompose_signals(make_item(fail_standard=standard))
            ordered = [
                s
                for s in signals["fail"]
                if s.get("evidence_shape", {}).get("shape") == "ordered_relation"
            ]
            assert ordered, f"{standard!r} must produce an ordered signal"
            second = ordered[0]["evidence_shape"]["second"]
            assert second == expected_second, (
                f"{standard!r}: second must be {expected_second!r}, got {second!r}"
            )

    # WARN-1: degenerate 先-然后 form must not emit an empty first element
    def test_warn1_empty_first_not_emitted(self):
        signals = decompose_signals(make_item(fail_standard="先，然后处理"))
        for s in signals["fail"]:
            shape = s.get("evidence_shape")
            if shape and shape.get("shape") == "ordered_relation":
                assert shape["first"], f"first must be non-empty, got {shape['first']!r}"

    # WARN-2: full-width comma without space must not break the English form
    def test_warn2_fullwidth_comma_no_space(self):
        signals = decompose_signals(make_item(fail_standard="acknowledge，then resolve"))
        assert any(
            s.get("evidence_shape", {}).get("shape") == "ordered_relation" for s in signals["fail"]
        ), "full-width comma without space must still be recognized as ordered"

    # WARN-3: the literal string "None" must not leak into ids
    def test_warn3_string_none_id_sanitized(self):
        signals = decompose_signals(make_item(id="None"))
        for s in signals["fail"] + signals["excellence"]:
            assert "None-" not in s["id"], "string 'None' id must be sanitized"

    # WARN-4: non-str standard must not fabricate pairs from its repr
    def test_warn4_nonstr_standard_no_repr_corruption(self):
        signals = decompose_signals(make_item(fail_standard=["先安抚然后处理"]))
        for s in signals["fail"]:
            shape = s.get("evidence_shape")
            if shape and shape.get("shape") == "ordered_relation":
                assert "']" not in shape["second"] and "['" not in shape["first"], (
                    "list repr must not leak into the ordered pair"
                )


# ── B4 re-verification fix round (2026-08-12): F1/F2 mirror closures ────────


class TestB4FixRound:
    """Findings F1/F2 closed with red tests. RED phase."""

    # F1: first element must be connective-free (mirror of BLOCK-1)
    def test_f1_first_element_connective_stripped(self):
        for standard, expected_first in (("先A再然后B", "A"), ("先A再B再然后C", "A")):
            signals = decompose_signals(make_item(fail_standard=standard))
            ordered = [
                s
                for s in signals["fail"]
                if s.get("evidence_shape", {}).get("shape") == "ordered_relation"
            ]
            assert ordered, f"{standard!r} must produce an ordered signal"
            first = ordered[0]["evidence_shape"]["first"]
            assert first == expected_first, (
                f"{standard!r}: first must be {expected_first!r}, got {first!r}"
            )

    def test_f1_no_connectives_in_pair(self):
        for standard in ("先A再然后B", "先A再B再然后C", "先A后B然后C"):
            signals = decompose_signals(make_item(fail_standard=standard))
            for s in signals["fail"]:
                shape = s.get("evidence_shape")
                if shape and shape.get("shape") == "ordered_relation":
                    for part in (shape["first"], shape["second"]):
                        assert "再" not in part and "然后" not in part and "后" not in part, (
                            f"{standard!r}: connective leaked into pair part {part!r}"
                        )

    # F2: separator right after the marker must not emit an empty second
    def test_f2_empty_second_not_emitted(self):
        for standard in ("先A然后，B", "先A再，B", "先A后，B", "acknowledge before ，resolve"):
            signals = decompose_signals(make_item(fail_standard=standard))
            for s in signals["fail"]:
                shape = s.get("evidence_shape")
                if shape and shape.get("shape") == "ordered_relation":
                    assert shape["second"], (
                        f"{standard!r}: second must be non-empty, got {shape['second']!r}"
                    )


# ── B5 re-verification fix round (2026-08-12): word-aware connective cuts ───


class TestB5FixRound:
    """B5 findings closed with red tests: cuts must not split real words. RED phase."""

    def test_b5_after_sales_word_not_split(self):
        # 售后 is a real word (after-sales); cutting at its 后 corrupts it
        for standard, expected_first in (("先售后然后处理", "售后"), ("先售后再处理", "售后")):
            signals = decompose_signals(make_item(fail_standard=standard))
            ordered = [
                s
                for s in signals["fail"]
                if s.get("evidence_shape", {}).get("shape") == "ordered_relation"
            ]
            assert ordered, f"{standard!r} must produce an ordered signal"
            first = ordered[0]["evidence_shape"]["first"]
            assert first == expected_first, (
                f"{standard!r}: first must be {expected_first!r}, got {first!r}"
            )

    def test_b5_second_leading_strip_word_aware(self):
        # 后台 is a real word; the leading-connective strip must not eat its 后
        signals = decompose_signals(make_item(fail_standard="先A然后后台处理"))
        ordered = [
            s
            for s in signals["fail"]
            if s.get("evidence_shape", {}).get("shape") == "ordered_relation"
        ]
        assert ordered
        second = ordered[0]["evidence_shape"]["second"]
        assert second == "后台处理", f"second must keep 后台 intact, got {second!r}"

    def test_b5_connective_cuts_still_work(self):
        # The round-4 pins must keep holding alongside the word-awareness
        for standard, expected_first in (("先A再然后B", "A"), ("先A再B再然后C", "A")):
            signals = decompose_signals(make_item(fail_standard=standard))
            ordered = [
                s
                for s in signals["fail"]
                if s.get("evidence_shape", {}).get("shape") == "ordered_relation"
            ]
            first = ordered[0]["evidence_shape"]["first"]
            assert first == expected_first, (
                f"{standard!r}: first must be {expected_first!r}, got {first!r}"
            )


# ── B6 re-verification fix round (2026-08-12): marker-position word awareness ─


class TestB6FixRound:
    """B6 finding closed: the bare-后 marker must not anchor inside protected words."""

    def test_b6_marker_not_inside_protected_word(self):
        # The only 后 in these standards is inside a protected word — no viable
        # marker → fall back to model_based, never emit a corrupted pair.
        for standard in ("坐席先处理售后问题", "先确认后台处理", "先查询后台处理结果"):
            signals = decompose_signals(make_item(fail_standard=standard))
            for s in signals["fail"]:
                shape = s.get("evidence_shape")
                if shape and shape.get("shape") == "ordered_relation":
                    pair = shape["first"] + shape["second"]
                    assert "售后" in pair or "后台" in pair, (
                        f"{standard!r}: ordered pair must not split the protected word, got {shape}"
                    )

    def test_b6_clean_hou_marker_still_works(self):
        signals = decompose_signals(make_item(fail_standard="先安抚后处理"))
        ordered = [
            s
            for s in signals["fail"]
            if s.get("evidence_shape", {}).get("shape") == "ordered_relation"
        ]
        assert ordered, "clean 先X后Y must still produce an ordered signal"
        shape = ordered[0]["evidence_shape"]
        assert shape["first"] == "安抚" and shape["second"] == "处理"


# ── M8 pilot gap closure (2026-08-13): excellence must not reuse fail phrases ─


class TestExcellenceNoPhraseReuse:
    """Pilot gap ②: the excellence lane must derive from the PASS standard's
    observable content, never duplicate the FAIL lane's named phrases."""

    def test_excellence_does_not_reuse_fail_phrases(self):
        item = make_item(
            values={"named_phrases": ["思路混乱", "引导延期"], "numeric_thresholds": []}
        )
        signals = decompose_signals(item)
        fail_phrases = set()
        for s in signals["fail"]:
            if s.get("checkable"):
                for p in ("思路混乱", "引导延期"):
                    if p in s["description"]:
                        fail_phrases.add(p)
        for s in signals["excellence"]:
            for p in fail_phrases:
                assert p not in s["description"], (
                    f"excellence signal {s['id']} must not reuse FAIL phrase {p!r}"
                )

    def test_ordered_pass_standard_yields_ordered_excellence(self):
        item = make_item(pass_standard="情绪激动场景先表达理解再进入处理")
        signals = decompose_signals(item)
        ordered = [
            s
            for s in signals["excellence"]
            if s.get("evidence_shape", {}).get("shape") == "ordered_relation"
        ]
        assert ordered, "先X再Y pass standard must produce an ordered excellence signal"
        assert ordered[0]["checkable"] is True

    def test_unmarked_pass_standard_yields_model_based_excellence(self):
        item = make_item(pass_standard="针对不同的用户理解能力适时调整说话方式")
        signals = decompose_signals(item)
        model = [s for s in signals["excellence"] if s["checkable"] is False]
        assert model, "pass standard without observable markers must yield model_based excellence"


# ── A2-ph: phrase lexicon ────────────────────────────────────────────────────


class TestPhraseLexicon:
    def test_phrase_lexicon_output(self):
        lexicon = {
            "customer-emotion": ["着急", "不满"],
            "agent-attitude": ["抱歉", "请您放心"],
            "agent-competence": ["为您查询", "帮您处理"],
            "interaction-patterns": ["先安抚再处理", "确认后办理"],
        }
        sections = compile_phrase_lexicon(lexicon)
        assert set(sections.keys()) == {
            "customer-emotion",
            "agent-attitude",
            "agent-competence",
            "interaction-patterns",
        }
        assert sum(len(v) for v in sections.values()) == 8
        for entries in sections.values():
            for e in entries:
                assert e["type"] == "phrase"
