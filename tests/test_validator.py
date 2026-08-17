"""Acceptance tests for M1 — Validator (AUTH-1..10, 9003).

RED phase: these tests fail until `src/argus/core/compiler/validator.py` is
implemented (module import error = the documented RED state; committed only
when green).

The validator is a pure module: each AUTH prohibition is a discrete
`check_*(...)` function returning a list of error strings (empty = pass);
`validate_node(node)` aggregates all node-level checks. Context-dependent
checks (manifest, align_map, siblings, sources) take their context as
arguments — they are invoked by the Planner/orchestrator, not by
`validate_node`.

One red+green pair per AUTH-1..10, per the plan's §5 fixtures, plus the
patch-2 checks (S1/S3/S4), D8, S5 (warn-level), and S2.
"""

from __future__ import annotations

from argus.core.compiler.validator import (
    check_agreement_gate,
    check_applicability_gate,
    check_calibration_coverage,
    check_checkable_audited,
    check_companion_docs,
    check_data_dependency,
    check_depends_on,
    check_edited_consistency,
    check_escape_plan,
    check_exclusion_set_adversarial,
    check_manifest_present,
    check_no_adjective_signals,
    check_no_forced_mapping,
    check_no_redundant_corroborator,
    check_residue_declared,
    validate_node,
    validate_sources,
)


def make_node(**overrides) -> dict:
    """A fully valid AuthoredNode-shaped dict — every check passes on it."""
    node = {
        "node_id": "item-22",
        "category": "rules_criteria",
        "intents_path": "_rubric/rules_criteria/empathy_and_tone/item-22.yaml",
        "intents_sha": "git:deadbeef",
        "layer": "judgment",
        "required_evidence": {},
        "fail_condition": {},
        "deduction": 1.0,
        "authored_by": "rubric-compiler",
        "dimension": "empathy_and_tone",
        "human_version": {
            "item_number": 22,
            "text": "情绪安抚：客户情绪激动时先安抚再处理",
            "na_condition": None,
        },
        "machine_criterion": {
            "criterion_id": "C22",
            "description": "情绪激动场景先表达理解再进入处理",
            "scoring_scale": "1-10",
            "gap_type": "values",
            "auto_final_allowed": True,
            "escape_tier": "standard",
        },
        "signals": {
            "fail": [
                {
                    "id": "22-S01",
                    "description": "transcript contains one of the named phrases: 您别着急",
                    "severity": "high",
                    "checkable": True,
                    "audit_result": "pass",
                }
            ],
            "excellence": [],
        },
        "facets": {"programmatic": [], "model_based": []},
        "corroborators": [
            {
                "signal_type": "lexical_match",
                "node_ref": "item-20-S01",
                "independence_class": "independent",
            }
        ],
        "gap_rationale": "mock template classification",
        "residue_declared": "does not capture tone warmth; sincerity of engagement",
        "agreement": {
            "tau": 0.8,
            "kappa_sample_plan": "rolling 200 calls, weekly kappa",
            "escape_sample_plan": "20 auto-passes/week -> human review",
            "escape_ceiling": 0.05,
            "current_kappa": None,
        },
        "applicability_gate": None,
        "severity_map": "calibration://manifest/epoch-000/severity/22",
        "data_dependency": None,
        "gap_type": "values",
        "escape_tier": "standard",
        "iteration_policy": "re-ground via write-time epoch commit only; no rule edits from Argus output",
        "companion_docs": None,
        "depends_on": None,
    }
    node.update(overrides)
    return node


def make_manifest(covered_criteria: set[str] | None = None) -> dict:
    return {"covered_criteria": covered_criteria or set()}


# ── AUTH-1: no adjective signals ────────────────────────────────────────────


class TestAuth1AdjectiveSignals:
    def test_auth1_red(self):
        node = make_node(
            signals={
                "fail": [{"id": "22-S01", "description": "坐席表现灵活且主动", "severity": "high"}],
                "excellence": [],
            }
        )
        errors = check_no_adjective_signals(node)
        assert errors, "adjective-only signal must be rejected"

    def test_auth1_green(self):
        node = make_node()
        assert check_no_adjective_signals(node) == []


# ── AUTH-2: residue must be declared ────────────────────────────────────────


class TestAuth2Residue:
    def test_auth2_red(self):
        node = make_node(residue_declared=None)
        errors = check_residue_declared(node)
        assert errors, "judgment node without residue_declared must be rejected"

    def test_auth2_green(self):
        node = make_node()
        assert check_residue_declared(node) == []


# ── AUTH-3: agreement gate (tau + kappa_sample_plan) ────────────────────────


class TestAuth3AgreementGate:
    def test_auth3_red(self):
        node = make_node(agreement={"tau": 0.8})  # no kappa_sample_plan
        errors = check_agreement_gate(node)
        assert errors, "agreement without kappa_sample_plan must be rejected"

    def test_auth3_green(self):
        node = make_node()
        assert check_agreement_gate(node) == []


# ── AUTH-4: no redundant corroborator (incl. D16) ───────────────────────────


class TestAuth4RedundantCorroborator:
    def test_auth4_red_redundant_class(self):
        node = make_node(
            corroborators=[
                {
                    "signal_type": "soft_text",
                    "node_ref": "item-26-S01",
                    "independence_class": "redundant",
                }
            ]
        )
        errors = check_no_redundant_corroborator(node)
        assert errors, "redundant-class corroborator must be rejected"

    def test_auth4_red_framework_ref(self):
        # D16: acoustic framework / phrase lexicon are rubric, NOT corroborators
        node = make_node(
            corroborators=[
                {
                    "signal_type": "acoustic_measurement",
                    "node_ref": "_rubric/evidence/acoustic/indicators.yaml",
                    "independence_class": "independent",
                }
            ]
        )
        errors = check_no_redundant_corroborator(node)
        assert errors, "corroborator pointing at the acoustic framework must be rejected (D16)"

    def test_auth4_green(self):
        node = make_node()
        assert check_no_redundant_corroborator(node) == []


# ── AUTH-5: no compile run without a residue manifest ───────────────────────


class TestAuth5ManifestPresent:
    def test_auth5_red(self):
        node = make_node()
        errors = check_manifest_present(manifest=None, nodes=[node])
        assert errors, "run emitting nodes without a manifest must be rejected"

    def test_auth5_green(self):
        node = make_node()
        assert check_manifest_present(manifest=make_manifest(), nodes=[node]) == []


# ── AUTH-6: escape plan required ────────────────────────────────────────────


class TestAuth6EscapePlan:
    def test_auth6_red(self):
        node = make_node(
            agreement={"tau": 0.8, "kappa_sample_plan": "rolling 200", "escape_ceiling": 0.05}
        )  # no escape_sample_plan
        errors = check_escape_plan(node)
        assert errors, "agreement without escape_sample_plan must be rejected"

    def test_auth6_green(self):
        node = make_node()
        assert check_escape_plan(node) == []


# ── AUTH-7: NA-carrying item needs an applicability gate ────────────────────


class TestAuth7ApplicabilityGate:
    def test_auth7_red(self):
        node = make_node(
            human_version={
                "item_number": 21,
                "text": "积极灵活营销",
                "na_condition": "Item 20 为 NA 或无营销机会",
            },
            applicability_gate=None,
        )
        errors = check_applicability_gate(node)
        assert errors, "NA-carrying item without applicability_gate must be rejected"

    def test_auth7_green(self):
        node = make_node()  # no NA condition
        assert check_applicability_gate(node) == []

    def test_auth7_green_with_gate(self):
        node = make_node(
            human_version={
                "item_number": 21,
                "text": "积极灵活营销",
                "na_condition": "no opportunity",
            },
            applicability_gate={"spec": "gate references prerequisite signals of item 20"},
        )
        assert check_applicability_gate(node) == []


# ── AUTH-8: data dependency declaration ─────────────────────────────────────


class TestAuth8DataDependency:
    def test_auth8_red_connected_false_without_defer(self):
        node = make_node(
            data_dependency={
                "source": "callback_logs+ticket_status",
                "connected": False,
                "disposition": "route_to_human",
            }
        )
        errors = check_data_dependency(node)
        assert errors, "connected: false without defer disposition must be rejected"

    def test_auth8_green_deferred(self):
        node = make_node(
            data_dependency={
                "source": "callback_logs+ticket_status",
                "connected": False,
                "disposition": "defer_until_source_connected",
            }
        )
        assert check_data_dependency(node) == []

    def test_auth8_green_no_dependency(self):
        node = make_node()
        assert check_data_dependency(node) == []


# ── AUTH-9: no auto-final on uncalibrated surface-form criterion ────────────


class TestAuth9CalibrationCoverage:
    def test_auth9_red(self):
        node = make_node(
            machine_criterion={
                "criterion_id": "C21",
                "description": "针对性推荐",
                "scoring_scale": "1-10",
                "gap_type": "calibration_surface_form",
                "auto_final_allowed": True,
                "escape_tier": "standard",
            },
            gap_type="calibration_surface_form",
            severity_map="calibration://manifest/epoch-000/severity/21",
        )
        errors = check_calibration_coverage(node, manifest=make_manifest(covered_criteria=set()))
        assert errors, (
            "calibration_surface_form with auto_final and no manifest coverage must be rejected"
        )

    def test_auth9_green_no_auto_final(self):
        node = make_node(
            machine_criterion={
                "criterion_id": "C21",
                "description": "针对性推荐",
                "scoring_scale": "1-10",
                "gap_type": "calibration_surface_form",
                "auto_final_allowed": False,
                "escape_tier": "standard",
            },
            gap_type="calibration_surface_form",
        )
        assert check_calibration_coverage(node, manifest=make_manifest()) == []

    def test_auth9_green_covered(self):
        node = make_node(
            machine_criterion={
                "criterion_id": "C21",
                "description": "针对性推荐",
                "scoring_scale": "1-10",
                "gap_type": "calibration_surface_form",
                "auto_final_allowed": True,
                "escape_tier": "standard",
            },
            gap_type="calibration_surface_form",
            severity_map="calibration://manifest/epoch-001/severity/21",
        )
        assert (
            check_calibration_coverage(node, manifest=make_manifest(covered_criteria={"21"})) == []
        )


# ── AUTH-10: no forced mapping ──────────────────────────────────────────────


class TestAuth10ForcedMapping:
    def test_auth10_red(self):
        # Item 24 has no adequate dimension (align_map None) but a node claims one
        node = make_node(
            node_id="item-24",
            dimension="problem_resolution",
            source_binary_items=["24"],
            intents_path="_rubric/rules_criteria/problem_resolution/item-24.yaml",
        )
        errors = check_no_forced_mapping(node, align_map={"24": None, "22": "empathy_and_tone"})
        assert errors, "unmapped item forced into a dimension must be rejected"

    def test_auth10_green(self):
        node = make_node()
        assert check_no_forced_mapping(node, align_map={"22": "empathy_and_tone"}) == []


# ── S1: companion docs carry pinned SHA + role ──────────────────────────────


class TestS1CompanionDocs:
    def test_s1_red_missing_sha(self):
        node = make_node(
            companion_docs=[{"document": "marketing-scripts.md", "role": "standard_scripts"}]
        )
        errors = check_companion_docs(node)
        assert errors, "companion_docs entry without sha256 must be rejected"

    def test_s1_green(self):
        node = make_node(
            companion_docs=[
                {"document": "marketing-scripts.md", "role": "standard_scripts", "sha256": "a" * 64}
            ]
        )
        assert check_companion_docs(node) == []


# ── S3: depends_on refs resolve to sibling signals ──────────────────────────


class TestS3DependsOn:
    def test_s3_red_unresolved(self):
        node = make_node(
            node_id="item-21",
            depends_on=["20"],
            applicability_gate={
                "spec": "gate references prerequisite signals",
                "refs": ["20-S01", "20-S99"],
            },
        )
        sibling20 = make_node(
            node_id="item-20", signals={"fail": [{"id": "20-S01"}], "excellence": []}
        )
        errors = check_depends_on(node, siblings=[sibling20])
        assert errors, "depends_on ref to a non-existent sibling signal must be rejected"

    def test_s3_green(self):
        node = make_node(
            node_id="item-21",
            depends_on=["20"],
            applicability_gate={"spec": "gate references prerequisite signals", "refs": ["20-S01"]},
        )
        sibling20 = make_node(
            node_id="item-20", signals={"fail": [{"id": "20-S01"}], "excellence": []}
        )
        assert check_depends_on(node, siblings=[sibling20]) == []


# ── S4: no implicit checkability claims ─────────────────────────────────────


class TestS4CheckableAudited:
    def test_s4_red_implicit_checkable(self):
        node = make_node(
            signals={
                "fail": [{"id": "22-S01", "description": "phrase present", "severity": "high"}],
                "excellence": [],
            }
        )  # no checkable / audit_result
        errors = check_checkable_audited(node)
        assert errors, "signal without checkable + audit_result must be rejected"

    def test_s4_green(self):
        node = make_node()
        assert check_checkable_audited(node) == []


# ── D8: hand-edited nodes keep cross-file consistency ───────────────────────


class TestD8EditedConsistency:
    def test_d8_red_dangling_ref(self):
        node = make_node(depends_on=["20"], applicability_gate={"refs": ["20-S99"]})
        errors = check_edited_consistency(node, siblings=[])
        assert errors, "dangling node_id ref in an edited node must be rejected"

    def test_d8_green(self):
        node = make_node()
        assert check_edited_consistency(node, siblings=[]) == []


# ── S5: exclusion-set adversarial test (warn-level) ─────────────────────────


class TestS5ExclusionAdversarial:
    def test_s5_overfire_flagged(self):
        # AND-NOT gate: inclusion 建议, exclusion 您可以选择.
        # Combined utterance 我建议您可以选择办理移动证书 IS a positive case in
        # Chinese pragmatics (patch-2 Surprise 5) — the naive exclusion over-fires.
        signal = {
            "id": "20-S01",
            "description": "specific recommendation present",
            "checkable": True,
            "audit_result": "pass",
            "inclusion_patterns": ["建议", "推荐"],
            "exclusion_set": ["您可以选择", "随您方便"],
        }
        warnings = check_exclusion_set_adversarial(signal)
        assert warnings, "exclusion pattern embedded in a positive pattern must be flagged"

    def test_s5_green_no_exclusions(self):
        signal = {
            "id": "20-S01",
            "description": "specific recommendation present",
            "checkable": True,
        }
        assert check_exclusion_set_adversarial(signal) == []


# ── S2: source validation halts on conflict ─────────────────────────────────


class TestS2SourceConflict:
    def test_s2_red_conflicting_sources(self):
        sources = {
            "marketing-scripts.md": {"T001": ["移动证书", "解锁推荐"], "T002": ["子证书"]},
            "marketing-scripts-v2.md": {"T001": ["子证书", "单独领证"]},  # T001 redefined
        }
        conflicts = validate_sources(sources)
        assert conflicts, (
            "trigger ID redefined with different keywords must produce a conflict report"
        )

    def test_s2_green_consistent(self):
        sources = {
            "marketing-scripts.md": {"T001": ["移动证书", "解锁推荐"], "T002": ["子证书"]},
            "marketing-scripts-v2.md": {"T001": ["移动证书", "解锁推荐"], "T003": ["年报"]},
        }
        assert validate_sources(sources) == []


# ── B-verification fix round (2026-08-12): type confusion + bypass closures ──


class TestBFixRound:
    """Adversarial findings F1-F10 closed with red tests. RED phase."""

    # F1: AUTH-8 string-bool type confusion
    def test_auth8_string_false_rejected(self):
        node = make_node(
            data_dependency={"source": "s", "connected": "false", "disposition": "route_to_human"}
        )
        errors = check_data_dependency(node)
        assert errors, "connected as truthy string 'false' must be rejected"

    # F2: AUTH-8 defer substring denial
    def test_auth8_disposition_denies_defer_rejected(self):
        node = make_node(
            data_dependency={
                "source": "s",
                "connected": False,
                "disposition": "no defer — judge anyway",
            }
        )
        errors = check_data_dependency(node)
        assert errors, "disposition containing 'no defer' must be rejected"

    # F3: AUTH-1 traditional / spaced adjectives
    def test_auth1_traditional_chinese_adjective_rejected(self):
        node = make_node(
            signals={
                "fail": [{"id": "22-S01", "description": "坐席表現靈活", "severity": "high"}],
                "excellence": [],
            }
        )
        errors = check_no_adjective_signals(node)
        assert errors, "traditional-Chinese adjective must be rejected"

    def test_auth1_spaced_adjective_rejected(self):
        node = make_node(
            signals={
                "fail": [{"id": "22-S01", "description": "坐席表现灵 活", "severity": "high"}],
                "excellence": [],
            }
        )
        errors = check_no_adjective_signals(node)
        assert errors, "space-split adjective must be rejected"

    # F4: AUTH-3 degenerate / typed-wrong tau
    def test_auth3_tau_string_rejected(self):
        node = make_node(agreement={"tau": "0.8", "kappa_sample_plan": "rolling 200"})
        errors = check_agreement_gate(node)
        assert errors, "string tau must be rejected"

    def test_auth3_tau_zero_rejected(self):
        node = make_node(agreement={"tau": 0, "kappa_sample_plan": "rolling 200"})
        errors = check_agreement_gate(node)
        assert errors, "tau=0 must be rejected (ungated soft entry)"

    # F5: AUTH-4 casing + path-form bypasses
    def test_auth4_cased_redundant_rejected(self):
        node = make_node(
            corroborators=[
                {
                    "signal_type": "soft_text",
                    "node_ref": "item-26-S01",
                    "independence_class": "Redundant",
                }
            ]
        )
        errors = check_no_redundant_corroborator(node)
        assert errors, "case-variant 'Redundant' must be rejected"

    def test_auth4_framework_ref_variants_rejected(self):
        for ref in ("_rubric/evidence/acoustic", "../evidence/acoustic/indicators.yaml"):
            node = make_node(
                corroborators=[
                    {
                        "signal_type": "acoustic_measurement",
                        "node_ref": ref,
                        "independence_class": "independent",
                    }
                ]
            )
            errors = check_no_redundant_corroborator(node)
            assert errors, f"framework ref variant {ref!r} must be rejected (D16)"

    # F6: AUTH-9 type confusion + manifest rows shape
    def test_auth9_uppercase_gap_type_rejected(self):
        node = make_node(
            machine_criterion={
                "criterion_id": "C21",
                "description": "针对性推荐",
                "scoring_scale": "1-10",
                "gap_type": "CALIBRATION_SURFACE_FORM",
                "auto_final_allowed": True,
                "escape_tier": "standard",
            },
            gap_type="CALIBRATION_SURFACE_FORM",
        )
        errors = check_calibration_coverage(node, manifest=make_manifest())
        assert errors, "uppercase gap_type must not skip the AUTH-9 gate"

    def test_auth9_manifest_rows_shape_covered(self):
        # Real manifest shape (M6): {"rows": [...]} with source_items as coverage
        node = make_node(
            machine_criterion={
                "criterion_id": "C21",
                "description": "针对性推荐",
                "scoring_scale": "1-10",
                "gap_type": "calibration_surface_form",
                "auto_final_allowed": True,
                "escape_tier": "standard",
            },
            gap_type="calibration_surface_form",
            severity_map="calibration://manifest/epoch-001/severity/21",
        )
        manifest = {
            "rows": [
                {
                    "kind": "within_dimension",
                    "source_items": ["21"],
                    "dimension": "commercial_guidance",
                }
            ]
        }
        assert check_calibration_coverage(node, manifest=manifest) == []

    # F7: S1 sha256 format
    def test_s1_sha256_format_validated(self):
        node = make_node(
            companion_docs=[
                {"document": "marketing-scripts.md", "role": "standard_scripts", "sha256": "abc"}
            ]
        )
        errors = check_companion_docs(node)
        assert errors, "3-char sha256 'pin' must be rejected"

    # F8: malformed input robustness
    def test_validate_node_non_dict_returns_error(self):
        for bad in (None, "x", 42):
            errors = validate_node(bad)
            assert errors, f"validate_node({bad!r}) must return an error, not crash"

    def test_context_checks_tolerate_none(self):
        node = make_node()
        assert check_depends_on(node, None) == []
        assert check_edited_consistency(node, None) == []

    # F10: vacuous declarations
    def test_auth2_vacuous_residue_rejected(self):
        for vacuous in ("None", "N/A", "无"):
            node = make_node(residue_declared=vacuous)
            errors = check_residue_declared(node)
            assert errors, f"vacuous residue_declared {vacuous!r} must be rejected"

    def test_auth5_empty_dict_manifest_rejected(self):
        node = make_node()
        errors = check_manifest_present(manifest={}, nodes=[node])
        assert errors, "empty-dict manifest must not satisfy AUTH-5"


# ── B2 re-verification fix round (2026-08-12): crash-proofing + gate closures ──


class TestB2FixRound:
    """Findings B1/B2/W1/W3 closed with red tests. RED phase."""

    # B1: no-crash contract on schema-valid malformed shapes
    def test_b1_signals_list_crash(self):
        assert validate_node({"signals": ["x"]}), "non-dict signals must error, not crash"

    def test_b1_disposition_int_crash(self):
        node = make_node(data_dependency={"source": "s", "connected": False, "disposition": 42})
        assert validate_node(node), "non-str disposition must error, not crash"

    def test_b1_corroborator_ref_int_crash(self):
        node = make_node(
            corroborators=[{"signal_type": "x", "node_ref": 5, "independence_class": "independent"}]
        )
        assert validate_node(node), "non-str node_ref must error, not crash"

    def test_b1_depends_on_refs_int_crash(self):
        node = make_node(applicability_gate={"refs": 5}, depends_on=["20"])
        assert check_depends_on(node, []), "non-iterable refs must error, not crash"

    # B2: whitespace-padded gap_type + machine_criterion consistency
    def test_b2_padded_gap_type_rejected(self):
        node = make_node(
            machine_criterion={
                "criterion_id": "C21",
                "description": "x",
                "scoring_scale": "1-10",
                "gap_type": " calibration_surface_form ",
                "auto_final_allowed": True,
                "escape_tier": "standard",
            },
            gap_type=" calibration_surface_form ",
        )
        errors = check_calibration_coverage(node, manifest=None)
        assert errors, "whitespace-padded gap_type must not skip the AUTH-9 gate"

    def test_b2_machine_criterion_gap_type_checked(self):
        # node.gap_type says values but machine_criterion says calibration_surface_form
        node = make_node(
            machine_criterion={
                "criterion_id": "C21",
                "description": "x",
                "scoring_scale": "1-10",
                "gap_type": "calibration_surface_form",
                "auto_final_allowed": True,
                "escape_tier": "standard",
            },
            gap_type="values",
        )
        errors = check_calibration_coverage(node, manifest=None)
        assert errors, "machine_criterion gap_type must also gate AUTH-9"

    # W1: orthographic mutations of adjectives
    def test_w1_zero_width_space_rejected(self):
        node = make_node(
            signals={
                "fail": [{"id": "22-S01", "description": "坐席表现灵​活", "severity": "high"}],
                "excellence": [],
            }
        )
        assert check_no_adjective_signals(node), "zero-width-space adjective must be rejected"

    def test_w1_hyphenated_english_rejected(self):
        for desc in ("pro-active service", "pro active service", "flexibility shown"):
            node = make_node(
                signals={
                    "fail": [{"id": "22-S01", "description": desc, "severity": "high"}],
                    "excellence": [],
                }
            )
            assert check_no_adjective_signals(node), f"mutation {desc!r} must be rejected"

    # W3: D16 ref matching with segment boundary
    def test_w3_bare_evidence_ref_rejected(self):
        node = make_node(
            corroborators=[
                {
                    "signal_type": "acoustic_measurement",
                    "node_ref": "evidence/acoustic",
                    "independence_class": "independent",
                }
            ]
        )
        assert check_no_redundant_corroborator(node), (
            "bare evidence/acoustic ref must be rejected (D16)"
        )

    def test_w3_sibling_dir_not_rejected(self):
        node = make_node(
            corroborators=[
                {
                    "signal_type": "acoustic_measurement",
                    "node_ref": "_rubric/evidence/acousticfoo/indicators.yaml",
                    "independence_class": "independent",
                }
            ]
        )
        assert check_no_redundant_corroborator(node) == [], (
            "sibling dir acousticfoo must NOT be rejected"
        )


# ── B3 re-verification fix round (2026-08-12): case + invisible-char families ──


class TestB3FixRound:
    """Findings F11/F12/F13 closed with red tests. RED phase."""

    # F11: AUTH-1 case mutations
    def test_f11_case_mutations_rejected(self):
        for desc in (
            "Flexible approach to escalations",
            "agent was VERY FLEXIBLE",
            "showed Flexibility throughout",
            "PRO-active service",
        ):
            node = make_node(
                signals={
                    "fail": [{"id": "22-S01", "description": desc, "severity": "high"}],
                    "excellence": [],
                }
            )
            assert check_no_adjective_signals(node), f"case mutation {desc!r} must be rejected"

    # F12: AUTH-1 invisible chars beyond the closed set
    def test_f12_invisible_char_mutations_rejected(self):
        for desc in ("坐席表现灵﻿活", "坐席表现灵⁠活", "坐席表现灵­活"):
            node = make_node(
                signals={
                    "fail": [{"id": "22-S01", "description": desc, "severity": "high"}],
                    "excellence": [],
                }
            )
            assert check_no_adjective_signals(node), "invisible-char mutation must be rejected"

    # F13: D16 ref case + padding
    def test_f13_d16_case_and_padding_rejected(self):
        for ref in (
            "_rubric/evidence/Acoustic/indicators.yaml",
            "EVIDENCE/ACOUSTIC",
            " evidence/acoustic ",
            "evidence/Phrase-Keyword/lexicon.yaml",
        ):
            node = make_node(
                corroborators=[
                    {
                        "signal_type": "acoustic_measurement",
                        "node_ref": ref,
                        "independence_class": "independent",
                    }
                ]
            )
            assert check_no_redundant_corroborator(node), (
                f"D16 ref variant {ref!r} must be rejected"
            )


# ── validate_node: aggregate entry (the runner's contract) ──────────────────


class TestValidateNode:
    def test_validate_node_aggregates(self):
        assert validate_node(make_node()) == []

    def test_validate_node_catches_multiple(self):
        node = make_node(
            residue_declared=None,
            signals={
                "fail": [{"id": "22-S01", "description": "坐席表现灵活", "severity": "high"}],
                "excellence": [],
            },
        )
        errors = validate_node(node)
        assert len(errors) >= 2, "validate_node must aggregate AUTH-1 + AUTH-2 failures"
