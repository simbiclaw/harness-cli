"""Compiler input and output schemas for the soft-criteria compiler (9003 M0).

These Pydantic models define the shape of the three compiler inputs
(SpecificRubric, GenericEvaluatorSkill, AlignMap), the independent
CalibrationManifest channel, and the two required compiler outputs
(AuthoredNode extending IntentsNode, ResidueManifest).

Lives in types/ per layering.md: pure data definitions, no I/O, no
imports from other argus.* modules. Only stdlib + pydantic imports.

Reference: docs/retrospectives/soft-criteria-authoring-spec-v4.html
           docs/retrospectives/soft-criteria-authoring-spec-v4-patch-1.md
           docs/retrospectives/soft-criteria-authoring-spec-v4-patch-2.md
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

# ──────────────────────────────────────────────────────────────────────────────
# §0.5 Compiler Input 1: SpecificRubric  (human-inspector binary checklist)
# ──────────────────────────────────────────────────────────────────────────────


class RubricItemValues(BaseModel):
    """Concrete values extracted from checklist text (§0.5, B-D).

    Named phrases → lexical signals; numeric thresholds → threshold signals.
    Both at confidence 1.0.
    """

    named_phrases: list[str] = Field(default_factory=list)
    numeric_thresholds: list[dict[str, Any]] = Field(default_factory=list)


class RubricItem(BaseModel):
    """One binary item in the Specific QA Rubric (§0.5).

    Per Patch 1 D11: items share the same schema; keys that don't apply
    simply don't appear. The evaluator infers mode from which keys exist.
    """

    id: str
    text: str
    values: RubricItemValues = Field(default_factory=RubricItemValues)
    na_condition: str | None = None
    failure_examples: list[str] = Field(default_factory=list)
    pass_standard: str = ""
    fail_standard: str = ""


class SpecificRubric(BaseModel):
    """Human-inspector binary checklist — 27 items (§0.5).

    The primary compiler input. Each item is a binary (pass/fail) rule
    with concrete values and company-specific failure examples.
    """

    items: list[RubricItem]


# ──────────────────────────────────────────────────────────────────────────────
# §0.5 Compiler Input 2: GenericEvaluatorSkill  (AI-executed template)
# ──────────────────────────────────────────────────────────────────────────────


class DimensionDef(BaseModel):
    """One of the four judgment dimensions from the generic skill template."""

    name: str
    description: str = ""
    failure_signatures: list[str] = Field(default_factory=list)


class HardThresholdMechanism(BaseModel):
    """Hard-threshold rules synthesized per-dimension (not copied per-item)."""

    rules: list[dict[str, Any]] = Field(default_factory=list)
    description: str = ""


class GenericEvaluatorSkill(BaseModel):
    """AI-executed judgment template — supplies structure, not ground truth (§0.5).

    The `source: "ai_template"` discriminator distinguishes this from
    human-authored artifacts. The template's few_shot_examples are
    scaffolding replaced by the §6 agreement instrument.
    """

    source: Literal["ai_template"] = "ai_template"
    dimensions: list[DimensionDef]
    scale: dict[str, int] = Field(default_factory=lambda: {"min": 1, "max": 10})
    hard_threshold_mechanism: dict[str, Any] = Field(default_factory=dict)
    few_shot_examples: list[dict[str, Any]] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# §0.5 Compiler Input 3: AlignMap  (item → dimension bridge)
# ──────────────────────────────────────────────────────────────────────────────


class AlignMap(BaseModel):
    """Item-to-dimension routing map (§0.5, §2.6 B-A).

    entries: item_id → dimension_name, or None if no dimension covers
             this item (triggers dimension_coverage_gap manifest row).
    """

    entries: dict[str, str | None] = Field(default_factory=dict)
    format: str = "yaml"


# ──────────────────────────────────────────────────────────────────────────────
# Independent Channel: CalibrationManifest  (NOT a compiler input)
# ──────────────────────────────────────────────────────────────────────────────


class CalibrationFragment(BaseModel):
    """One annotated case from Error Case Library or Best Practice Cookbook."""

    fragment_id: str
    source_case: str
    transcript_span: dict[str, int] = Field(default_factory=dict)
    human_score: float
    affected_criterion: str
    failure_surface: str
    severity_anchor: str


class CalibrationManifest(BaseModel):
    """Independent calibration channel (§0.5, M7).

    Injected alone — re-anchors severity_map refs with no recompile.
    Deliberately uneven distribution: ~2:1 danger-zone ratio because
    false-pass costs more asymmetrically than false-fail.
    """

    epoch_id: str
    fragments: list[CalibrationFragment] = Field(default_factory=list)
    source_case_refs: list[str] = Field(default_factory=list)
    distribution: dict[str, int] = Field(default_factory=lambda: {"danger_zone_ratio": 2})


# ──────────────────────────────────────────────────────────────────────────────
# §3 AuthoredNode  (extends IntentsNode with judgment-layer fields)
# ──────────────────────────────────────────────────────────────────────────────

# --- Sub-structs shared across AuthoredNode ---


class CorroboratorEntry(BaseModel):
    """One corroborating signal with its independence classification (A3).

    AUTH-4 forbids independence_class: "redundant".
    D16: acoustic framework / phrase lexicon are rubric, not corroborators.
    """

    signal_type: str
    node_ref: str
    independence_class: Literal["independent", "correlated", "redundant"]


class AgreementBlock(BaseModel):
    """Agreement gate seeded by the compiler (A5).

    Required for judgment-layer nodes (AUTH-3, AUTH-6).
    Initial tau = 0.8; current_kappa filled by rolling sample at runtime.
    """

    tau: float = 0.8
    kappa_sample_plan: str = ""
    escape_sample_plan: str = ""
    escape_ceiling: float = 0.05
    current_kappa: float | None = None


class AuthoredNode(BaseModel):
    """Enriched _rubric/ node extending the IntentsNode base with §3 fields.

    All judgment-layer fields are Optional with default=None for
    v1-backward-compatibility (v6 conformance).
    """

    # --- Base IntentsNode fields (pipeline spec v5 §3.1) ---

    node_id: str
    category: str
    intents_path: str
    intents_sha: str
    layer: Literal["compliance", "judgment"] = "judgment"
    required_evidence: dict[str, Any] = Field(default_factory=dict)
    fail_condition: dict[str, Any] = Field(default_factory=dict)
    deduction: float = 1.0

    # --- Required §3 fields ---

    authored_by: str
    dimension: str

    # --- Optional §3 judgment-layer fields (v6: Optional, default=None) ---

    human_version: dict[str, Any] | None = None
    machine_criterion: dict[str, Any] | None = None
    signals: dict[str, list[dict[str, Any]]] | None = None
    facets: dict[str, list[dict[str, Any]]] | None = None
    corroborators: list[dict[str, Any]] | None = None
    gap_rationale: str | None = None
    agreement: dict[str, Any] | None = None
    proposed_score_hook: bool | None = None
    source_binary_items: list[str] | None = None
    dimension_ref: str | None = None
    applicability_gate: dict[str, Any] | None = None
    severity_map: str | None = None
    data_dependency: dict[str, Any] | None = None
    gap_type: (
        Literal["values", "perceiver", "proxy", "calibration_surface_form", "coverage"] | None
    ) = None
    escape_tier: Literal["standard", "aggressive"] | None = None
    iteration_policy: str | None = None


# ──────────────────────────────────────────────────────────────────────────────
# §3.5 ResidueManifest  (lossy-projection ledger, required output)
# ──────────────────────────────────────────────────────────────────────────────


class WithinDimensionRow(BaseModel):
    """Residue inside a dimension the item maps to — imperfect capture."""

    kind: Literal["within_dimension"]
    dimension: str
    source_items: list[str]
    compiled_to: list[str]
    left_behind: str
    disposition: str


class DimensionCoverageGapRow(BaseModel):
    """Complete coverage failure — no dimension measures this criterion (Item 24)."""

    kind: Literal["dimension_coverage_gap"]
    source_items: list[str]
    measures: str
    compiled_to: list[str]
    data_dependency: dict[str, Any] = Field(default_factory=dict)
    disposition: str
    proposes: str | None = None


ResidueRow = Annotated[
    WithinDimensionRow | DimensionCoverageGapRow,
    Field(discriminator="kind"),
]


class ResidueManifest(BaseModel):
    """Lossy-projection ledger (§3.5, AUTH-5).

    A compiler run that emits nodes without a manifest row for
    non-fully-compilable dimensions is rejected.
    """

    sources: dict[str, Any] = Field(default_factory=dict)
    rows: list[ResidueRow] = Field(default_factory=list)
