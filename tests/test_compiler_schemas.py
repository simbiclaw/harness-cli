"""Acceptance tests for M0 — Compiler input schemas (9003).

Validates that all Pydantic schemas for the soft-criteria compiler
construct, serialize, deserialize, and enforce required fields correctly.

Red phase: these tests FAIL until src/argus/types/compiler_schemas.py is implemented.
"""

from __future__ import annotations

import pytest

# ── Import the schemas (will fail until implemented) ──────────────────────
# Intentionally at module level so the import error is visible.
# Once implemented, these imports resolve.
src_argus_types = pytest.importorskip(
    "src.argus.types.compiler_schemas",
    reason="M0 schemas not yet implemented — expected red phase",
)


class TestAllInputSchemasRoundtrip:
    """Each compiler input schema constructs, serializes, and deserializes."""

    def test_specific_rubric_roundtrip(self):
        """A SpecificRubric with all 27 items round-trips through JSON."""
        SpecificRubric = src_argus_types.SpecificRubric

        item = {
            "id": "item-01",
            "text": "Agent acknowledged the customer's emotional state before proceeding.",
            "values": {"named_phrases": ["I understand", "I hear you"], "numeric_thresholds": []},
            "na_condition": "No emotional content detected in customer message.",
            "failure_examples": [
                "Agent opened with 'How can I help?' after customer described frustration.",
                "Agent ignored customer's 'I've been waiting for an hour' and proceeded to troubleshooting.",
            ],
            "pass_standard": "Agent names or reflects the customer's emotional state before transitioning to problem-solving.",
            "fail_standard": "Agent proceeds to problem-solving without any acknowledgment of customer's emotional state.",
        }

        rubric = SpecificRubric.model_validate({"items": [item]})
        assert len(rubric.items) == 1
        assert rubric.items[0].id == "item-01"
        assert rubric.items[0].text == item["text"]
        assert rubric.items[0].na_condition == "No emotional content detected in customer message."
        assert len(rubric.items[0].failure_examples) == 2

        # Round-trip through JSON
        dumped = rubric.model_dump_json()
        reloaded = SpecificRubric.model_validate_json(dumped)
        assert reloaded.items[0].id == rubric.items[0].id
        assert reloaded.items[0].failure_examples == rubric.items[0].failure_examples

    def test_specific_rubric_missing_fields_default(self):
        """Fields without defaults that are missing should raise ValidationError."""
        SpecificRubric = src_argus_types.SpecificRubric

        # items is required — missing should fail
        with pytest.raises(Exception):
            SpecificRubric.model_validate({})

    def test_generic_evaluator_skill_roundtrip(self):
        """A GenericEvaluatorSkill round-trips through JSON."""
        GenericEvaluatorSkill = src_argus_types.GenericEvaluatorSkill

        skill_data = {
            "source": "ai_template",
            "dimensions": [
                {
                    "name": "Empathy & Tone",
                    "description": "Agent demonstrates emotional awareness and appropriate tone.",
                    "failure_signatures": [
                        "No acknowledgment of customer emotion.",
                        "Formulaic or insincere empathy phrases.",
                    ],
                },
                {
                    "name": "Problem Resolution",
                    "description": "Agent resolves the customer's issue completely.",
                    "failure_signatures": [
                        "Partial resolution requiring follow-up.",
                        "Incorrect solution applied.",
                    ],
                },
                {
                    "name": "Procedural Accuracy",
                    "description": "Agent follows required procedures correctly.",
                    "failure_signatures": [
                        "Skipped required verification step.",
                        "Wrong escalation path used.",
                    ],
                },
                {
                    "name": "Proactive Value",
                    "description": "Agent adds value beyond the immediate request.",
                    "failure_signatures": [
                        "Missed upsell opportunity.",
                        "No proactive guidance offered.",
                    ],
                },
            ],
            "scale": {"min": 1, "max": 10},
            "hard_threshold_mechanism": {
                "rules": [{"dimension": "Problem Resolution", "threshold": 7, "condition": "<"}],
                "description": "Problem Resolution < 7 = IMMEDIATE FAIL",
            },
            "few_shot_examples": [],
        }

        skill = GenericEvaluatorSkill.model_validate(skill_data)
        assert skill.source == "ai_template"
        assert len(skill.dimensions) == 4
        assert skill.dimensions[0].name == "Empathy & Tone"
        assert skill.scale == {"min": 1, "max": 10}
        assert skill.hard_threshold_mechanism["rules"][0]["dimension"] == "Problem Resolution"

        # Round-trip through JSON
        dumped = skill.model_dump_json()
        reloaded = GenericEvaluatorSkill.model_validate_json(dumped)
        assert (
            reloaded.dimensions[0].failure_signatures
            == skill_data["dimensions"][0]["failure_signatures"]
        )

    def test_align_map_roundtrip(self):
        """An AlignMap round-trips through JSON."""
        AlignMap = src_argus_types.AlignMap

        align_data = {
            "entries": {
                "item-01": "empathy",
                "item-02": "empathy",
                "item-03": "problem_resolution",
                "item-24": None,  # no dimension covers this
            },
            "format": "yaml",
        }

        align = AlignMap.model_validate(align_data)
        assert align.entries["item-01"] == "empathy"
        assert align.entries["item-24"] is None
        assert len(align.entries) == 4

        # Round-trip through JSON
        dumped = align.model_dump_json()
        reloaded = AlignMap.model_validate_json(dumped)
        assert reloaded.entries["item-24"] is None
        assert reloaded.format == "yaml"

    def test_calibration_manifest_roundtrip(self):
        """A CalibrationManifest round-trips through JSON."""
        CalibrationManifest = src_argus_types.CalibrationManifest

        manifest_data = {
            "epoch_id": "cs-calibration v3",
            "fragments": [
                {
                    "fragment_id": "frag-001",
                    "source_case": "error-case-lib/case-0042",
                    "transcript_span": {"start": 120, "end": 340},
                    "human_score": 3,
                    "affected_criterion": "rc-soft-0118",
                    "failure_surface": "false-positive on formulaic empathy",
                    "severity_anchor": "emp-sev-v3:low",
                }
            ],
            "source_case_refs": ["error-case-lib/case-0042"],
            "distribution": {"danger_zone_ratio": 2},
        }

        manifest = CalibrationManifest.model_validate(manifest_data)
        assert manifest.epoch_id == "cs-calibration v3"
        assert len(manifest.fragments) == 1
        assert manifest.fragments[0].human_score == 3
        assert manifest.distribution == {"danger_zone_ratio": 2}

        # Round-trip through JSON
        dumped = manifest.model_dump_json()
        reloaded = CalibrationManifest.model_validate_json(dumped)
        assert reloaded.fragments[0].fragment_id == "frag-001"


class TestAuthoredNodeRoundtrip:
    """AuthoredNode with all §3 fields round-trips through JSON."""

    def test_authored_node_full_roundtrip(self):
        """An AuthoredNode with every §3 optional field populated round-trips."""
        AuthoredNode = src_argus_types.AuthoredNode

        node_data = {
            # Base IntentsNode fields
            "node_id": "rc-soft-0118",
            "category": "rules_criteria",
            "intents_path": "_rubric/rules/rc-soft-0118.yaml",
            "intents_sha": "git:a1b2c3d4e5f6",
            "layer": "judgment",
            "required_evidence": {
                "signal_id": "ack_seq_01",
                "description": "Acknowledgment sequence exists and precedes resolution",
                "checkable": True,
                "extraction_method": "ordered_relation",
            },
            "fail_condition": {"logic": "no ack_span OR ack_span FOLLOWS resolution_span"},
            "deduction": 5.0,
            # §3 judgment-layer fields
            "authored_by": "qa_lead_22",
            "dimension": "empathy",
            "human_version": {
                "item_id": "item-22",
                "text": "Agent acknowledged the customer's emotional state before proceeding.",
                "values": {"named_phrases": ["I understand", "I hear you"]},
                "na_condition": "No emotional content detected.",
                "failure_examples": ["Agent ignored frustration signals."],
                "pass_standard": "Agent names or reflects emotional state.",
                "fail_standard": "No acknowledgment of emotional state.",
            },
            "machine_criterion": {
                "criterion_id": "mc-emp-001",
                "description": "Gradable empathy acknowledgment criterion.",
                "scoring_scale": {"min": 1, "max": 10},
                "gap_type": "perceiver",
                "auto_final_allowed": False,
                "escape_tier": "standard",
            },
            "signals": {
                "fail": [
                    {
                        "id": "sig-fail-001",
                        "description": "No acknowledgment span found in agent utterance before resolution.",
                        "severity": "high",
                    }
                ],
                "excellence": [
                    {
                        "id": "sig-exc-001",
                        "description": "Agent uses personalized empathy language beyond formulaic phrases.",
                        "severity": "low",
                    }
                ],
            },
            "facets": {
                "programmatic": [
                    {
                        "facet_name": "ack_sequence_check",
                        "enables_signals": [
                            {"signal_id": "sig-fail-001", "extraction_shape": "ordered_relation"}
                        ],
                        "indicator": "ack_span precedes resolution_span",
                        "calculation": "check_ordering(ack_span, resolution_span)",
                        "output_schema": {
                            "type": "object",
                            "properties": {"precedes": {"type": "boolean"}},
                        },
                    }
                ],
                "model_based": [],
            },
            "corroborators": [
                {
                    "signal_type": "acoustic_measurement",
                    "node_ref": "_rubric/evidence/acoustic/indicators.yaml",
                    "independence_class": "independent",
                }
            ],
            "gap_rationale": "Captures acknowledgment SEQUENCE; does NOT capture warmth, sincerity, or sarcasm with correct sequence.",
            "agreement": {
                "tau": 0.8,
                "kappa_sample_plan": "rolling 200 calls, weekly kappa",
                "escape_sample_plan": "20 auto-passes/week -> human review",
                "escape_ceiling": 0.05,
                "current_kappa": None,
            },
            "proposed_score_hook": True,
            "source_binary_items": ["item-22"],
            "dimension_ref": "empathy",
            "applicability_gate": {"spec": "customer_message.emotional_content == True"},
            "severity_map": "calibration:emp-sev-v3",
            "data_dependency": None,
            "gap_type": "perceiver",
            "escape_tier": "standard",
            "iteration_policy": "re-ground via write-time epoch commit only; no rule edits from Argus output.",
        }

        node = AuthoredNode.model_validate(node_data)
        assert node.node_id == "rc-soft-0118"
        assert node.layer == "judgment"
        assert node.authored_by == "qa_lead_22"
        assert node.signals["fail"][0]["id"] == "sig-fail-001"
        assert node.corroborators[0]["independence_class"] == "independent"
        assert node.agreement["tau"] == 0.8
        assert node.gap_rationale is not None

        # Round-trip through JSON
        dumped = node.model_dump_json()
        reloaded = AuthoredNode.model_validate_json(dumped)
        assert reloaded.node_id == node.node_id
        assert reloaded.corroborators == node.corroborators
        assert reloaded.agreement["tau"] == 0.8
        assert reloaded.signals["fail"][0]["description"] == node.signals["fail"][0]["description"]

    def test_authored_node_minimal_fields(self):
        """An AuthoredNode with only required base fields constructs successfully."""
        AuthoredNode = src_argus_types.AuthoredNode

        minimal = {
            "node_id": "rc-soft-0001",
            "category": "rules_criteria",
            "intents_path": "_rubric/rules/rc-soft-0001.yaml",
            "intents_sha": "git:b1b1b1",
            "layer": "judgment",
            "required_evidence": {
                "signal_id": "min_01",
                "description": "Minimal signal",
                "checkable": True,
                "extraction_method": "lexical",
            },
            "fail_condition": {"logic": "signal not detected"},
            "deduction": 1.0,
            "authored_by": "test_author",
            "dimension": "test_dim",
        }

        node = AuthoredNode.model_validate(minimal)
        assert node.node_id == "rc-soft-0001"
        # Optional §3 fields should default to None
        assert node.corroborators is None
        assert node.agreement is None
        assert node.gap_rationale is None


class TestResidueManifestRoundtrip:
    """ResidueManifest with both row kinds round-trips."""

    def test_residue_manifest_both_row_kinds_roundtrip(self):
        """A ResidueManifest with within_dimension + dimension_coverage_gap rows."""
        ResidueManifest = src_argus_types.ResidueManifest

        manifest_data = {
            "sources": {
                "specific_rubric": "cs-qa-rubric v3.2",
                "generic_skill": "evaluator-criteria-customer-service-generic v1.3",
                "calibration_epoch": None,
                "align": "align.md@git:abcdef",
            },
            "rows": [
                {
                    "kind": "within_dimension",
                    "dimension": "empathy",
                    "source_items": ["item-11", "item-22"],
                    "compiled_to": ["rc-soft-0118"],
                    "left_behind": "sincerity of engagement; sarcasm with correct sequence",
                    "disposition": "human_review",
                },
                {
                    "kind": "dimension_coverage_gap",
                    "source_items": ["item-24"],
                    "measures": "consequential business harm — callback inevitability, unnecessary cost",
                    "compiled_to": ["signal-biz-0007"],
                    "data_dependency": {
                        "source": "callback_logs+ticket_status",
                        "connected": False,
                    },
                    "disposition": "defer_until_source_connected",
                    "proposes": "new sub-dimension: Business Impact",
                },
            ],
        }

        manifest = ResidueManifest.model_validate(manifest_data)
        assert manifest.sources["specific_rubric"] == "cs-qa-rubric v3.2"
        assert len(manifest.rows) == 2

        within = manifest.rows[0]
        assert within.kind == "within_dimension"
        assert within.dimension == "empathy"
        assert len(within.source_items) == 2

        gap = manifest.rows[1]
        assert gap.kind == "dimension_coverage_gap"
        assert gap.disposition == "defer_until_source_connected"
        assert gap.proposes == "new sub-dimension: Business Impact"

        # Round-trip through JSON
        dumped = manifest.model_dump_json()
        reloaded = ResidueManifest.model_validate_json(dumped)
        assert reloaded.sources == manifest.sources
        assert len(reloaded.rows) == 2
        assert reloaded.rows[0].kind == "within_dimension"
        assert reloaded.rows[1].kind == "dimension_coverage_gap"

    def test_residue_manifest_empty_rows(self):
        """A ResidueManifest with no rows (all items fully compiled) is valid."""
        ResidueManifest = src_argus_types.ResidueManifest

        empty_manifest = ResidueManifest.model_validate(
            {
                "sources": {
                    "specific_rubric": "cs-qa-rubric v3.2",
                    "generic_skill": "evaluator-criteria-customer-service-generic v1.3",
                    "calibration_epoch": "cs-calibration v3",
                    "align": "align.md@git:abcdef",
                },
                "rows": [],
            }
        )
        assert empty_manifest.rows == []
        assert empty_manifest.sources["calibration_epoch"] == "cs-calibration v3"
