# 9003 — Implement the Soft-Criteria Compiler + Validator

## 1. Purpose

The runtime pipeline (9002) needs enriched `_rubric/` nodes to ground judgment-layer findings — without them, every soft criterion returns `deferred`. The current `INTENTS/_rubric/` holds v1-format compliance rules; the judgment-layer shelf is empty. This plan lands the **offline authoring compiler and validator** specified in `docs/PRD/soft-criteria-authoring-spec-v4.html`: it takes a human-authored Specific QA Rubric (binary checklist), an AI-executed Generic Evaluator Skill (judgment template), and an `align.md` item→dimension map, fuses them through the A1–A7 and B-A..B-D procedures, and emits enriched `_rubric/` nodes plus a ResidueManifest. The compiler is not a runtime stage — it runs once per criterion, offline, and stocks the referent the runtime reads. The validator enforces the ten AUTH prohibitions (§4) at authoring time. The Calibration Manifest is deliberately NOT a compiler input — it arrives on its own channel, injectable alone, re-anchoring severity_map refs with no recompile required.

## 2. Big Picture

This is an authoring-tool plan, not a runtime plan. The compiler reads human-authored inputs from disk, applies the spec's authoring procedure, and **writes enriched nodes into `INTENTS/_rubric/`** — this is the legitimate write path (ADR-0003: write-time, producer-owned, minting a new epoch). It is the exception to the runtime pipeline's "no src/argus write path into INTENTS" rule: the compiler IS the write-time path. Every write is a human-confirmed commit; the compiler never self-triggers from Argus evaluation output (A7).

The compiler touches `types/` (node schema, manifest schema, input schemas), `io/` (reading the three compiler inputs, writing `_rubric/` nodes and manifest), `core/` (pure compilation logic — signal decomposition, gap classification, escape-tier assignment, hard-fail synthesis), and `cli/` (a `compile` subcommand). It does NOT touch the runtime proposer, grounding gate, or scoring functions — those are 9002's domain.

**Execution architecture (round-3 decision 1, 2026-08-12):** the compiler is executed as an agent skill — `.claude/skills/rubric-compiler/SKILL.md` — running the patch-2 GAN-style multi-agent compile loop: **Planner** (sole companion-document I/O boundary, S1), **Generator** (per-item compilation over the deterministic core, targeted-fix mode), **Evaluator** (single quality gate; max 3 feedback rounds, simple items batched / complex items isolated, S5 adversarial checks). The deterministic functions of M1–M5 are the loop's backbone; model judgment is confined to authoring-time gaps (exclusion-set polish, signal-split adjudication), and every model intervention is recorded as a decision-log entry. The `argus compile` CLI pipeline (**M6**) is **DEFERRED** until the skill is proven; it will be rebuilt on the skill's frozen output contract.

**Three compiler inputs** (§0.5):

| Input | Executed by | Supplies |
|---|---|---|
| Specific QA Rubric | human inspector | 27 binary `0/1/NA` items with concrete values and company failure examples |
| Generic Evaluator Skill | AI agent (template) | 4 dimensions, 1–10 scale, failure signatures, hard-threshold mechanism |
| `align.md` | authoring | item → dimension mapping |

**One independent channel** — NOT a compiler input:

| Channel | Executed by | Supplies |
|---|---|---|
| Calibration Manifest | human (annotates) | fragments + scores from Error Case Library & Best Practice Cookbook; injectable alone; re-anchors severity_map refs with NO recompile |

**Two required outputs:** enriched `_rubric/` nodes (per the §3 authored-entry schema) plus a ResidueManifest (§3.5) naming what was left behind — including `dimension_coverage_gap` rows for criteria no dimension covers (Item 24). Per patch-1 D3, hard-fail routing rules are per-dimension gates written to `gates/{dimension}.yaml` — never attached to nodes. A compiler run that emits nodes without a manifest is rejected (AUTH-5).

**The authoring procedure** (§2) runs once per soft criterion: A1 (decompose to orthogonal dimensions), A2 (decompose signature into gate-checkable FAIL/EXCELLENCE signals — per Patch 1 D10, the old `trigger.spec` with `form ∈ {lexical, ordered_relation, threshold, lookup}` is removed; each signal must pass the Q1/Q2 gate-checkable test and is backed by programmatic or model_based facets), A3 (classify corroborators by independence — redundant class forbidden), A4 (declare the residue — required field), A5 (seed the agreement gate with both tails: κ sample plan + escape sample plan + escape ceiling), A6 (set deduction weight and W_C provisional constant), A7 (register drift detection and iteration policy — re-ground via write-time epoch commit only). Plus A2-ac (author the 12 acoustic indicators into `_rubric/evidence/acoustic/`) and A2-ph (author the phrase lexicon into `_rubric/evidence/phrase-keyword/`).

**The binary→continuous bridge** (§2.6) runs per binary item: B-A (bind item to dimension as weighted evidence via `align.md`, with a `severity_map` reference into the calibration manifest), B-B (compile every NA condition into an `applicability_gate`), B-C (synthesize hard-fail routing rules from item subsets — many-to-one, not copied thresholds), B-D (extract concrete values from checklist text — named phrases → lexical signals, numbers → threshold signals, at confidence 1.0, per Patch 1 D10).

**Gap types** the compiler must handle (§0.5 rev.4 items 1–7): values (binary→continuous bridge), perceiver (NA→applicability gate), proxy (hard-threshold synthesis), calibration_surface_form (AUTH-9 auto-final ban until manifest covers the failure surface), coverage (escape_tier assignment — proxy/coverage → aggressive sampling; values/perceiver/calibration_surface_form → standard), dimension_coverage_gap (Item 24 — defer-until-source-connected, propose new sub-dimension).

**Ten validator prohibitions** (§4, §5): AUTH-1 (no adjective signals), AUTH-2 (no undeclared residue), AUTH-3 (no ungated soft entry — must have agreement block with tau + kappa_sample_plan), AUTH-4 (no soft⊕soft corroborator — redundant class rejected, plus acoustic framework/phrase lexicon as corroborators rejected per D16), AUTH-5 (no compile run without a residue manifest), AUTH-6 (no soft entry without an escape plan — must have escape_sample_plan + escape_ceiling), AUTH-7 (no NA condition without a compiled applicability_gate), AUTH-8 (no data-dependent signal without data_dependency declaration; connected=false must defer), AUTH-9 (no auto-final on uncalibrated surface-form criterion — gap_type calibration_surface_form must not permit auto-final unless manifest covers its failure surface), AUTH-10 (no unmapped item forced into a dimension — silent miscoding is worse than honest defer).

**CLI surface introduced:** `argus compile <specific-rubric> <generic-skill> <align-md>` — runs the full authoring procedure and writes `_rubric/` nodes + manifest. `argus validate <node>` — runs the AUTH-1..10 validator against a single node or directory of nodes.

**Deliberately out of scope:** the companion 9002 runtime pipeline (reads _rubric/ but doesn't write it). The §3.6b per-item compile over all 27 items — that is a FOLLOW-ON task gated on receiving the real Specific QA Rubric + align.md inputs (do not invent item values). Population of the Calibration Manifest — it arrives on its own channel, outside the compiler. The runtime evaluation pipeline. Model calls in the deterministic compile path — the pure core (A1–A7, B-A..B-D, validator) transforms structured inputs deterministically; the agent-skill GAN loop (round-3 decision 1) runs model-judged steps at authoring time, outside the deterministic path, each intervention recorded.

**File Scope:**
- `.claude/skills/rubric-compiler/SKILL.md` (new — GAN-loop agent skill, round-3 decision 1)
- `src/argus/types/compiler_schemas.py` (new)
- `src/argus/core/compiler/validator.py` (new)
- `src/argus/core/compiler/signals.py` (new)
- `src/argus/core/compiler/classify.py` (new)
- `src/argus/core/compiler/agreement.py` (new)
- `src/argus/core/compiler/bridge.py` (new)
- `src/argus/core/compiler/compile.py` (new)
- `src/argus/io/compiler_io.py` (new)
- `src/argus/io/calibration_io.py` (new)
- `src/argus/cli/main.py` (modify — compile + validate subcommands)
- `tests/test_compiler_schemas.py` (new)
- `tests/test_validator.py` (new)
- `tests/test_signals.py` (new)
- `tests/test_classify.py` (new)
- `tests/test_agreement_seed.py` (new)
- `tests/test_bridge.py` (new)
- `tests/test_compiler_pipeline.py` (new)
- `tests/test_manifest_channel.py` (new)
- `tests/test_worked_compilation.py` (new, gated on M8 inputs)
- `docs/exec-plans/active/9003-implement-soft-criteria-compiler.md` (modify — this plan)

## 3. Milestones

### M0 — Compiler input schemas (types)

Define the Pydantic schemas for the three compiler inputs: `SpecificRubric` (27 items, each with id, text, values, NA condition, failure examples), `GenericEvaluatorSkill` (4 dimensions, 1–10 scale, failure signatures, hard-threshold mechanism — note: this is an AI template, not a human artifact), `AlignMap` (item → dimension routing). Plus the `CalibrationManifest` input schema (independent channel — fragments with scores, source_case refs from Error Case Library and Best Practice Cookbook). Plus the output schemas: the enriched `AuthoredNode` (extending IntentsNode with all §3 fields — corroborators, residue_declared, agreement block, applicability_gate, severity_map, gap_type, escape_tier, data_dependency, iteration_policy — plus the four-layer chain fields `human_version` / `machine_criterion` / `signals` / `facets` per patch-1 D7/D10) and `ResidueManifest` (§3.5 — within_dimension and dimension_coverage_gap rows, sources block tracking the three inputs + calibration epoch). Schema is uniform across all items — no `tier` field; assessment mode is inferred from key presence (`deterministic_checks` → binary compliance layer; `signals` + model_based facets → 1-10 perceiver layer) per patch-1 D11. `hard_fail_rule` is NOT a node field (patch-1 D3 — per-dimension gates only); `w_c` is NOT a node field (patch-1 D6 — agreement/config constant).

**REOPENED 2026-08-12 (round-3 decisions 2 & 6):** the AuthoredNode schema is extended with the patch-2 fields — `companion_docs` (S1: list of companion documents with pinned SHA + role, validated pre-compile), `depends_on` (S3: prerequisite Item IDs whose signal IDs this Item's applicability_gate references), `signal.checkable` + `signal.audit_result` (S4: B-F audit outcome — `pass` / `split` / `model_only`, carried in the free-form `signals` entries; schema-level enforcement is M1's `check_checkable_audited`). Input constraints tightened: `GenericEvaluatorSkill.dimensions` ≥ 1 (zero-dimension template rejected), `RubricItem.text` non-empty (min_length=1), `CalibrationManifest.epoch_id` format-constrained (ISO date + external-tree git SHA, per round-3 decision 3).

`Acceptance Test:` `tests/test_compiler_schemas.py::test_all_input_schemas_roundtrip` — each input schema constructs, serializes, and deserializes. `tests/test_compiler_schemas.py::test_authored_node_roundtrip` — an AuthoredNode with all §3 fields round-trips. `tests/test_compiler_schemas.py::test_residue_manifest_roundtrip` — manifest with both row kinds round-trips. `tests/test_compiler_schemas.py::test_patch2_fields_roundtrip` — AuthoredNode with companion_docs / depends_on / checkable / audit_result round-trips. `tests/test_compiler_schemas.py::test_zero_dimension_rejected` — 0-dimension GenericEvaluatorSkill fails construction. `tests/test_compiler_schemas.py::test_empty_item_text_rejected` — empty RubricItem.text fails construction. `tests/test_compiler_schemas.py::test_epoch_id_format_validated` — malformed epoch_id fails construction.

`Allowed Reads: docs/retrospectives/soft-criteria-authoring-spec-v4.html, docs/retrospectives/soft-criteria-authoring-spec-v4-patch-1.md, docs/retrospectives/soft-criteria-authoring-spec-v4-patch-2.md, src/argus/types/**, docs/conventions/layering.md`
`Allowed Writes: src/argus/types/__init__.py, src/argus/types/compiler_schemas.py, tests/test_compiler_schemas.py, docs/exec-plans/active/9003-implement-soft-criteria-compiler-notes/`
`Requires: none  (first milestone — no predecessor)`
`Risk Tier: B`

### M1 — Validator (AUTH-1..10, core)

Land the authoring-time validator in `src/argus/core/compiler/validator.py`. This is a pure function: it takes an `AuthoredNode` and returns a list of `ValidationError` (empty list = valid). Each of the ten prohibitions (§4) is a discrete check function:

- `check_no_adjective_signals(node)` — signal description contains evaluative adjectives without concrete referent → reject (AUTH-1) <span class="p1-note">was `check_no_adjective_triggers` with `trigger.checkable` (Patch 1 D10)</span>
- `check_residue_declared(node)` — judgment-layer node without `residue_declared` → reject (AUTH-2)
- `check_agreement_gate(node)` — judgment-layer node without `agreement.tau` and `kappa_sample_plan` → reject (AUTH-3)
- `check_no_redundant_corroborator(node)` — corroborator with `independence_class: "redundant"` OR corroborator pointing at acoustic framework/phrase lexicon (not measurement) → reject (AUTH-4, D16)
- `check_manifest_present(manifest, nodes)` — compiler run with non-fully-compilable dimension but no manifest → reject the run (AUTH-5)
- `check_escape_plan(node)` — judgment-layer node without `escape_sample_plan`/`escape_ceiling` → reject (AUTH-6)
- `check_applicability_gate(node)` — node from NA-carrying item without `applicability_gate` → reject (AUTH-7)
- `check_data_dependency(node)` — signal with out-of-band data dependency but no `data_dependency` declaration, or `connected: false` without defer disposition → reject (AUTH-8) <span class="p1-note">was "lookup trigger without data_dependency" (Patch 1 D10)</span>
- `check_calibration_coverage(node, manifest)` — `gap_type: "calibration_surface_form"` permitting auto-final while manifest doesn't cover its failure surface → reject (AUTH-9)
- `check_no_forced_mapping(node, align_map)` — item unmapped to any adequate dimension but forced into nearest → reject (AUTH-10)
- `check_companion_docs(node)` — companion_docs entries carry a pinned SHA + role, resolvable pre-compile (S1)
- `check_depends_on(node)` — depends_on refs resolve to existing signal IDs in the prerequisite item (S3)
- `check_checkable_audited(node)` — every signal carries explicit `checkable` + `audit_result` (S4 — no implicit claims)
- `check_edited_consistency(node, siblings)` — D8 (round-3 decision 7): a hand-edited node keeps cross-file consistency (dangling node_id refs, weight-arithmetic coherence)
- `check_exclusion_set_adversarial(signal)` — S5: for each exclusion pattern in an AND-NOT set, pragmatic adversarial cases (pattern embedded in a positive pattern; pure-exclusion case) → mismatch flags the signal for human review. Warn-level, non-blocking — reported alongside the compiled output
- `validate_sources(inputs)` — S2 (round-3 decision 7): pre-compile source validation; conflicting source documents → halt with an explicit conflict report awaiting human adjudication

`Acceptance Test:` `tests/test_validator.py::test_auth1_red` — adjective signal → validator rejects. `tests/test_validator.py::test_auth1_green` — structural signal → accepts. One red+green pair per AUTH-1..10, matching the §5 fixtures exactly. `tests/test_validator.py::test_s4_implicit_checkable_rejected` — signal without checkable/audit_result → reject. `tests/test_validator.py::test_d8_edited_inconsistency_rejected` — hand-edited node with dangling node_id ref → reject. `tests/test_validator.py::test_s5_exclusion_overfire_flagged` — exclusion pattern embedded in a positive pattern → warn flag, compilation proceeds. `tests/test_validator.py::test_s2_source_conflict_halts` — contradictory source docs → conflict report, no compile.

**M0-schema gap (discovered at M1):** AUTH-2 needs `residue_declared` on AuthoredNode — the plan's M0 contract listed it, but the 7-28 implementation omitted it. M1 adds it as an Optional `str | None = None` field (backward-compatible).

`Allowed Reads: docs/retrospectives/soft-criteria-authoring-spec-v4.html, docs/retrospectives/soft-criteria-authoring-spec-v4-patch-1.md, docs/retrospectives/soft-criteria-authoring-spec-v4-patch-2.md, src/argus/types/**, docs/conventions/layering.md`
`Allowed Writes: src/argus/core/compiler/**, src/argus/types/compiler_schemas.py, tests/test_validator.py, .claude/skills/rubric-compiler/scripts/run_compile.py, docs/exec-plans/active/9003-implement-soft-criteria-compiler-notes/`
`Requires: M0`
`Risk Tier: B`

### M2 — Signal Decomposition + Evidence authoring (A1, A2, A2-ac, A2-ph, core) <span class="p1-note">(was "Trigger compiler" — trigger.spec removed per Patch 1 D10)</span>

Land the pure signal-decomposition and evidence-authoring functions in `src/argus/core/compiler/signals.py` <span class="p1-note">(was `triggers.py`)</span>. The compiler takes a dimension description (from the generic skill template) and the human rubric's pass/fail standards and produces a `machine_criterion` + `signals` + `facets` block per the four-layer operationalized artifact (Patch 1 D10):

- `decompose_dimension(dimension) → list[SignalCandidate]` — A1: apply independence, exhaustiveness, and operationalizability tests; split what's signal-decomposable from what's residue
- `decompose_signals(item) → Signals` — A2 + B-E (Patch 1 D12): translate failure/pass standards into FAIL + EXCELLENCE signals. Each signal must pass the gate-checkable test: a proposer can find a transcript span (Q1) AND a gate can deterministically verify that span (Q2). No adjectives survive. Signals that are still conclusions ("坐席表现混乱") without concrete referents → rejected (AUTH-1 extended). <span class="p1-note">The old `compile_trigger(candidate) → Trigger` with `form ∈ {lexical, ordered_relation, threshold, lookup}` is removed — replaced by the human_version → machine_criterion → signals → facets four-layer chain (Patch 1 D10)</span>
- `audit_gate_checkable(signal) → AuditResult` — B-F (patch-2 S4): per signal, the Q1/Q2 gate-checkability test; returns `pass`, `split` (auto-split into gate-checkable + model_based sibling), or `model_only` (checkable: false, quarantined to S2). No implicit checkability claims survive.
- `assign_facets(signals, gap) → FacetGroup` — assigns programmatic or model_based facets per signal (D5/D9). Each programmatic facet carries indicator + calculation + output_schema. Each model_based facet carries a complete extraction prompt (checkpoints + output_schema) authored by the compiler.
- `compile_acoustic_framework(indicators) → list[EvidenceEntry]` — A2-ac: author 12 acoustic indicators as pure data (EvidenceEntry, not AuthoredNode per Patch 1 D2), written to `_rubric/evidence/acoustic/indicators.yaml` with `edited_by_human: false` guard (D8)
- `compile_phrase_lexicon(lexicon) → list[EvidenceEntry]` — A2-ph: author phrase/pattern lists as pure data, written to `_rubric/evidence/phrase-keyword/` with `edited_by_human: false` guard (D8)

`Acceptance Test:` `tests/test_signals.py::test_lexical_signal_decomposed` — a phrase-based criterion → signal with programmatic lexical facet. `tests/test_signals.py::test_ordered_relation_signal_decomposed` — "acknowledge before resolve" → FAIL signal with ordered-relation evidence shape, gate-checkable. `tests/test_signals.py::test_adjective_signal_rejected` — "agent should sound empathetic" → rejected, no concrete referent. `tests/test_signals.py::test_signal_split_needed` — "context-appropriate recommendation" → auto-split into programmatic (temporal proximity) + model_based (context adaptation quality, checkable: false) per B-F audit. `tests/test_signals.py::test_acoustic_framework_has_12_indicators` — A2-ac output has exactly 12 EvidenceEntry items. `tests/test_signals.py::test_phrase_lexicon_output` — A2-ph output has customer-emotion/, agent-attitude/, agent-competence/, interaction-patterns/ sections.

### M3 — Corroborator classifier + residue declarer (A3, A4, core)

Land the pure classification functions in `src/argus/core/compiler/classify.py`:

- `classify_corroborators(criterion, available_signals) → list[Corroborator]` — A3: for each available corroborating signal, assign `independence_class` by error-source disjointness. Acoustic measurement → independent (1.0). Exemplar/case match → correlated (W_C 0.4). Another soft text criterion → redundant (0.0) — rejected by AUTH-4. The acoustic framework and phrase lexicon are rubric, NOT corroborators (D16 double-count guard).
- `declare_residue(signals, dimension) → str` — A4: name what the compiled signals do NOT capture. Required field; empty → AUTH-2 rejects. <span class="p1-note">was `declare_residue(trigger, dimension)` (Patch 1 D10)</span>
- `classify_gap(item, dimension, signals) → GapClassification` — rev.4: classify the gap as values, perceiver, proxy, calibration_surface_form, or coverage, informed by signal coverage. Determines `escape_tier` (standard vs aggressive) and whether AUTH-9 auto-final ban applies.
- `assign_escape_tier(gap_type) → str` — proxy and coverage gaps → `"aggressive"`; values, perceiver, calibration_surface_form → `"standard"`.

`Acceptance Test:` `tests/test_classify.py::test_acoustic_measurement_is_independent` — acoustic measurement signal → `independence_class: "independent"`. `tests/test_classify.py::test_error_case_match_is_correlated` — exemplar match → `independence_class: "correlated"`. `tests/test_classify.py::test_soft_plus_soft_is_redundant` — another model-judged text criterion → `independence_class: "redundant"`, rejected. `tests/test_classify.py::test_residue_empty_rejected` — empty residue → fails AUTH-2. `tests/test_classify.py::test_proxy_gap_gets_aggressive_escape` — proxy gap → `escape_tier: "aggressive"`.

### M4 — Agreement seeder + deduction setter (A5, A6, core)

Land the pure functions in `src/argus/core/compiler/agreement.py`:

- `seed_agreement_gate(criterion) → AgreementBlock` — A5: set initial `tau` (start 0.8), `kappa_sample_plan` (agreement tail), `escape_sample_plan` + `escape_ceiling` (auto-pass tail). Initialize `current_kappa: null`. Judgment-layer entries without both plans → AUTH-3/AUTH-6 reject.
- `set_deduction_weight(item, dimension) → float` — A6: the human rubric's deduction weight if violated. Not scaled by corroboration (corroboration moves routing, not arithmetic).
- `set_w_c(criterion) → float` — A6: `W_C = 0.4` PROVISIONAL, flagged for empirical measurement. Reconciled with patch-1 D6: `w_c` is NOT a per-item AuthoredNode field — it is an agreement-module/config constant, one value shared with the runtime aggregator (the node's agreement block references it; it is not written into the node).
- `set_iteration_policy(criterion) → str` — A7: "re-ground via write-time epoch commit only; no rule edits from Argus output."

`Acceptance Test:` `tests/test_agreement_seed.py::test_agreement_block_has_both_tails` — tau + kappa_sample_plan + escape_sample_plan + escape_ceiling all present. `tests/test_agreement_seed.py::test_missing_escape_plan_rejected` — kappa plan present but no escape plan → AUTH-6 rejects. `tests/test_agreement_seed.py::test_w_c_provisional_flagged` — W_C field has PROVISIONAL comment. `tests/test_agreement_seed.py::test_iteration_policy_forbids_model_edits` — iteration policy string contains "no rule edits from Argus output."

### M5 — Binary→continuous bridge (B-A..B-D, core)

Land the pure bridge functions in `src/argus/core/compiler/bridge.py`:

- `bind_item_to_dimension(item, align_map, manifest_epoch) → DimensionBinding` — B-A: via `align.md`, attach item to its dimension with `deduction` and `severity_map` (a reference into the calibration manifest at its current epoch). If no manifest exists yet, the node compiles but surface-form-sensitive criteria get `auto_final: false` (AUTH-9).
- `compile_applicability_gate(item) → ApplicabilityGate | None` — B-B: translate NA condition into `applicability_gate.spec`. Item with NA condition but no gate → AUTH-7 rejects. Returns `None` if item has no NA condition.
- `synthesize_hard_fail(items, dimension) → HardFailRule | None` — B-C: identify subset of binary items whose collective failure indicates severe dimension failure. Author a many-to-one routing rule. This is synthesized, not copied from the template's single threshold. Output is a per-dimension gate written to `gates/{dimension}.yaml` (patch-1 D3 — never attached to a node), with `edited_by_human: false` guard (D8).
- `extract_values(item) → list[ValueExtraction]` — B-D: parse named phrases → lexical signal spec, numeric thresholds → threshold signal spec, at `confidence 1.0`. <span class="p1-note">values now enrich machine_criterion and signals, not a standalone trigger spec (Patch 1 D10)</span> Never settle for principle-level when the rubric text carries the exact value.
- `check_dimension_coverage(item, align_map, dimensions) → CoverageVerdict` — after binding: does some dimension adequately measure what this item measures? If no (Item 24), emit `data_dependency` with `connected: false` + defer disposition + `dimension_coverage_gap` manifest row. Do NOT force-fit. AUTH-10 rejects forced mappings.

`Acceptance Test:` `tests/test_bridge.py::test_bind_item_via_align` — item routes to correct dimension via align.md. `tests/test_bridge.py::test_na_condition_compiles_to_gate` — NA condition → applicability_gate with spec. `tests/test_bridge.py::test_missing_applicability_gate_rejected` — NA-bearing item without gate → AUTH-7 rejects. `tests/test_bridge.py::test_hard_fail_synthesized_not_copied` — hard_fail_rule is many-to-one, not a copied threshold. `tests/test_bridge.py::test_values_extracted_from_checklist` — named phrases → lexical; numbers → threshold. `tests/test_bridge.py::test_unmapped_item_not_force_fit` — Item 24 business-harm forced into Problem Resolution → AUTH-10 rejects, dimension_coverage_gap row required. `tests/test_bridge.py::test_uncalibrated_surface_form_no_auto_final` — gap_type calibration_surface_form without manifest coverage → auto_final forbidden (AUTH-9).

### M6a — Compiler agent skill: GAN-style compile loop (round-3 decision 1)

Land the compiler as an agent skill (`.claude/skills/rubric-compiler/SKILL.md`) executing the patch-2 execution architecture over the M1–M5 deterministic core:

- **Planner role** — sole I/O boundary for companion documents (S1): pins SHAs, detects source conflicts via `validate_sources` (S2), halts for human adjudication; runs the dependency scan and topological compile order (S3: Items 20→21, 22→26 — dependent items compile only after their prerequisite signal IDs are locked).
- **Generator role** — per-item compilation calling the pure core (decompose → classify → seed → bridge); targeted-fix mode `{signal_id, field, issue, suggested_fix}` instead of full recompiles.
- **Evaluator role** — single quality gate: runs the M1 validator (AUTH-1..10 + S1/S3/S4 checks) plus pragmatic adversarial tests for exclusion sets (S5); max 3 feedback rounds per item; simple items batched, complex items isolated.
- Every model intervention in the loop is recorded as a decision-log entry; the loop's final outputs are frozen into the output contract (nodes + `gates/{dimension}.yaml` + residue manifest) that the deferred CLI (M6) will later execute deterministically.

`Acceptance Test:` `tests/test_compiler_pipeline.py::test_skill_loop_output_passes_validator` — run the skill against a fixture rubric (incl. the Item 20/21 pair) → emitted nodes pass the full validator, residue manifest present, every model-judged step has a recorded decision. `tests/test_compiler_pipeline.py::test_skill_halt_on_source_conflict` — conflicting companion docs → loop halts with conflict report.

`Allowed Reads: docs/retrospectives/soft-criteria-authoring-spec-v4-patch-2.md, docs/exec-plans/active/9003-implement-soft-criteria-compiler.md, .claude/skills/**`
`Allowed Writes: .claude/skills/rubric-compiler/**, docs/exec-plans/active/9003-implement-soft-criteria-compiler-notes/, tests/test_compiler_pipeline.py`
`Requires: M5`
`Risk Tier: B`

### M6 — Full compiler pipeline (orchestration, io + core + cli)  <span class="p1-note">**DEFERRED 2026-08-12 (round-3 decision 1)** — superseded by M6a: the compiler is built as an agent skill first; the CLI is rebuilt after the skill is proven, on the frozen output contract</span>

Land the compiler orchestration that runs the full A1–A7 + B-A..B-D procedure, reading the three inputs and writing `_rubric/` nodes + ResidueManifest:

- `compile_rubric(specific_rubric, generic_skill, align_map, *, manifest_epoch=None) → CompileResult` — pure orchestration in `core/compiler/compile.py`. Returns `(list[AuthoredNode], ResidueManifest)`. Does NOT do I/O — receives parsed inputs, returns typed outputs.
- `CompilerIO` in `io/compiler_io.py` — reads the three input files from disk (parsing YAML/JSON/markdown), writes AuthoredNodes to `INTENTS/_rubric/rules_criteria/{dimension}/item-XX.yaml` (per-dimension layout, patch-1 D1), gates to `INTENTS/_rubric/gates/{dimension}.yaml` (D3), writes ResidueManifest to `INTENTS/_meta/residue-manifest.yaml`. On recompile, skips files with `edited_by_human: true` (D8). Follows the INTENTS symlink into the external tree; epoch commits happen in the external repo (round-3 decision 3). This IS the legitimate write path into INTENTS (ADR-0003: write-time, producer-owned).
- `compile` subcommand in `cli/commands.py` — `argus compile <specific-rubric> <generic-skill> <align-md> [--manifest-epoch <ref>]`. Reads inputs, calls `compile_rubric()`, writes outputs via `CompilerIO`.
- `validate` subcommand — `argus validate <path>` runs the AUTH-1..10 validator against one node or a directory of nodes.

`Acceptance Test:` `tests/test_compiler_pipeline.py::test_full_compile_emits_nodes_and_manifest` — given three valid inputs, the compiler outputs enriched nodes AND a residue manifest. `tests/test_compiler_pipeline.py::test_manifest_missing_from_run_rejected` — AUTH-5: a compile that would emit nodes without a manifest row for a non-fully-compilable dimension → rejected. `tests/test_compiler_pipeline.py::test_no_model_call_during_compile` — structural check confirms no `anthropic` import in compiler code. `tests/test_compiler_pipeline.py::test_compile_is_deterministic` — same inputs → byte-identical outputs. `tests/test_compiler_pipeline.py::test_validate_subcommand_rejects_bad_node` — `argus validate` on a node with adjective signal → non-zero exit. `tests/test_cli_compile.py::test_compile_subcommand_help` — CLI smoke test.

### M7 — Calibration manifest channel (independent)

Land the calibration manifest ingestion — NOT as a compiler input, but as an independent channel that can be injected alone:

- `CalibrationManifestLoader` in `io/calibration_io.py` — reads a manifest epoch from `INTENTS/_meta/calibration-manifest.<epoch>.yaml` (round-3 decision 8, rewritten). Same style as `residue-manifest.yaml` (schema_version / generated_at / sources). Validates fragments **structurally**: `source_case` refs must match the conventions.yaml grammar (`cookbook.<slug>.yaml` / `errors.<slug>.yaml` under a domain path) — **never existence-checked**: the Error Case Library and Best Practice Cookbook are currently EMPTY (no cookbook.* / errors.* files exist in the tree), and the first manifest arrives before any library content. `severity_map` URI refs (`calibration://manifest/<epoch>/severity/<criterion>`) must align with the manifest file's epoch.
- `apply_manifest_epoch(nodes, manifest) → list[AuthoredNode]` — re-anchors `severity_map` refs on existing nodes to the new manifest epoch. Re-evaluates AUTH-9 coverage: surface-form-sensitive nodes that were deferred may get auto-final rights if the manifest now covers their failure surface. Does NOT recompile — the nodes' signals, corroborators, and agreement blocks are unchanged.
- `manifest inject` subcommand — `argus manifest inject <manifest-file>` — reads a new manifest epoch, re-anchors existing `_rubric/` nodes' severity_map refs, re-evaluates AUTH-9 coverage, writes updated nodes back. This is a standalone operation — no compiler run required.

`Acceptance Test:` `tests/test_manifest_channel.py::test_manifest_injection_reanchors_severity` — nodes' severity_map refs update to new epoch, signals unchanged. `tests/test_manifest_channel.py::test_auth9_reevaluated_on_injection` — a surface-form node that was `auto_final: false` gets `auto_final: true` after manifest injection covers its failure surface. `tests/test_manifest_channel.py::test_manifest_injection_no_recompile` — injection does not change signals, corroborators, or agreement blocks. `tests/test_manifest_channel.py::test_manifest_epoch_independent_of_rule_epoch` — manifest epochs advance independently; rule epochs unchanged by manifest injection.

### M8 — Worked compilation (§3.6b follow-on, gated)

**GATED — do not start until the Specific QA Rubric (27 binary items) and `align.md` land.** When they arrive, this milestone runs the full per-item compile pattern (§3.6b pseudocode) over all 27 real items:

```
for each item in specific_rubric (27):
    dim   = align.md[item]                         # bind to dimension (B-A)
    form  = extract_values(item.text)              # phrases→lexical, numbers→threshold (B-D)
    gate  = compile_na(item.na_condition)          # → applicability_gate (B-B)
    sev   = manifest.severity_ref(item) if manifest else None
    gap   = classify_gap(item, dim)                # values|perceiver|proxy|calibration_surface_form|coverage
    tier  = aggressive if gap in {proxy, coverage} else standard
    if no dimension adequately covers item:        # (Item24)
        emit signal with data_dependency; defer_until_source_connected
        write dimension_coverage_gap row
    elif surface_form_sensitive(item) and not calibration.covers(item):
        emit node but forbid auto_final (AUTH-9)
    else:
        emit _rubric/ node (§3 schema) + within_dimension residue row if lossy
then: synthesize per-dimension hard_fail_rule from item subsets (B-C)
emit: _rubric/ nodes + ResidueManifest (both required)
```

The filled-§3.6b table in the companion spec becomes the deliverable: every row real, no invented item values. Wired into the CLI as `argus compile` with the real inputs.

`Acceptance Test:` `tests/test_worked_compilation.py::test_all_27_items_compiled` — every item in the Specific QA Rubric produces either a compiled node or a manifest row. `tests/test_worked_compilation.py::test_no_invented_values` — every extracted value traces to a real item text. `tests/test_worked_compilation.py::test_hard_fail_rules_per_dimension` — each dimension with an IMMEDIATE-FAIL threshold has a synthesized hard_fail_rule. `tests/test_worked_compilation.py::test_manifest_covers_all_lossy_items` — every item that didn't fully compile has a manifest row naming what was left behind.

`Notes:` This milestone is deliberately gated on external inputs. The compiler infrastructure (M0–M7) is fully operational before this runs — only the per-item iteration body is new. Do not invent item values to unblock this milestone; the spec explicitly forbids it.

## 4. Progress

- [x] M0: Compiler input schemas — REOPENED 2026-08-12, re-flipped 2026-08-12 (round-3 decisions 2 & 6: patch-2 fields, constraint tightening)  (originally done 2026-07-28)
- [ ] M1: Validator (AUTH-1..10 + S1/S2/S3/S4 + D8)  (created 2026-07-08)
- [ ] M2: Trigger compiler (A1, A2, A2-ac, A2-ph)  (created 2026-07-08)
- [ ] M3: Corroborator classifier + residue declarer (A3, A4)  (created 2026-07-08)
- [ ] M4: Agreement seeder + deduction setter (A5, A6, A7)  (created 2026-07-08)
- [ ] M5: Binary→continuous bridge (B-A..B-D)  (created 2026-07-08)
- [ ] M6a: Compiler agent skill (GAN loop)  (created 2026-08-12, round-3 decision 1)
- [ ] M6: Full compiler pipeline (orchestration + io + cli) — DEFERRED 2026-08-12 (round-3 decision 1; see M6a)  (created 2026-07-08)
- [ ] M7: Calibration manifest channel (independent)  (created 2026-07-08)
- [ ] M8: Worked compilation §3.6b (gated on real inputs)  (created 2026-07-08)

## 5. Decision Log

### M0 adversarial verification

Verdict: CONFIRMED

**Rationale:** `Source: subagent B adversarial verification (2026-07-28)` — Acceptance tests: 9/9 pass. Edge cases: 13/13 behave correctly (9 structural successes, 4 validation rejections correctly triggered). Three domain-level design gaps noted for future milestones (zero-dimension handling, text min_length, epoch_id format) but none are mechanical failures. Implementation notes validated — 2 plan-confirmed + 2 discovery entries, all with resolved actions.

### Decision: The compiler is the legitimate write path into INTENTS/_rubric/

**Rationale:** `Source: ADR-0003` — the runtime pipeline (9002) has a hard "no src/argus write path into INTENTS" prohibition (D15). The compiler is the EXCEPTION: it is the write-time, producer-owned path that ADR-0003 describes. The compiler does not write during evaluation — it writes during authoring, once per criterion, as a human-confirmed commit that mints a new INTENTS epoch. The `CompilerIO` class is the only code path in `src/argus/` permitted to open an INTENTS file for writing, and it is gated by the `compile` subcommand (never called during `eval`). This is documented here so a later agent does not incorrectly flag it as a violation.

### Decision: Compiler logic is pure; I/O is at the boundary

**Rationale:** The compilation functions (A1–A7, B-A..B-D, validator) are pure functions in `core/compiler/` — they receive typed inputs and return typed outputs. The `CompilerIO` class in `io/` handles reading input files and writing `_rubric/` nodes. The CLI orchestrates: read inputs → call pure compile → write outputs. This follows the same layering discipline as the runtime pipeline: core is pure, io does the external effects. The compiler never calls a model — it transforms structured inputs deterministically.

### Decision: The Calibration Manifest is NOT a compiler input — independent channel

**Rationale:** `Source: soft-criteria-authoring-spec-v4.html §0.5` — the manifest is "deliberately not a compiler input." It arrives on its own channel, injectable alone without a compile run. The compiler produces nodes with `severity_map` refs that point at the manifest epoch in effect at compile time; when a new manifest arrives, `manifest inject` re-anchors those refs and re-evaluates AUTH-9 coverage — no recompile. This separation means: miss a compiler input and the projection is unsound; miss the manifest and the projection is sound but conservative (AUTH-9 withholds auto-final from surface-form-sensitive criteria). The compiler must never silently degrade when a compiler input is missing; it must fail fast.

### Decision: W_C=0.4 PROVISIONAL — same constant, same debt, different location

**Rationale:** `Source: soft-criteria-authoring-spec-v4.html A6` — the compiler sets `w_c` on each authored node. This is the same provisional 0.4 from the pipeline spec (§4.1), logged as the same debt: the correct value is `1 − corr(matcher_error, proposer_error)` measured on a human-labeled sample. The constant appears in two places (config for the runtime aggregator, authored field for each node) but is one value. `Confidence: low` on 0.4; `Revisit:` when escape-rate data accumulates.

### Decision: The Generic Evaluator Skill is an AI template, not a human artifact

**Rationale:** `Source: soft-criteria-authoring-spec-v4.html §0.5, rev.4 framing correction` — earlier revisions treated the generic skill as "the human version." It is not. It is an AI-executed template that supplies judgment STRUCTURE (four dimensions, 1–10 scale, failure signatures, hard-threshold mechanism), not ground truth. The human artifact is the Specific QA Rubric (27 binary items with values). The compiler must not treat the generic skill's 1–10 grades or few-shot examples as authoritative — they are scaffolding that gets replaced by the §6 agreement instrument and the calibration manifest. This distinction is encoded in the input schema: the `GenericEvaluatorSkill` model carries a `source: "ai_template"` discriminator field.

### Decision: M8 (§3.6b) is gated on real inputs — never invent item values

**Rationale:** `Source: soft-criteria-authoring-spec-v4.html §3.6b` — the spec explicitly states "do not invent item values." The per-item compile pattern is fully specified (§2.6 B-A..B-D, gap handling in §0.5), and M0–M7 build the infrastructure to execute it, but the 27-item run requires the real Specific QA Rubric and `align.md`. When those inputs arrive, the filled §3.6b table becomes the deliverable. Until then, the compiler is tested against fixture data that exercises each gap type and edge case without pretending to be the real rubric.

### Round-3 interview decisions (2026-08-12)

Eight questions answered by the human in `docs/retrospectives/9003-ambiguities-interview-round3.html`. Conflict flags from the requested pre-update scan are recorded inline.

### Decision: Compiler executed as an agent skill with a GAN-style loop; M6 CLI deferred (round-3 Q1)

**Rationale:** `Source: round-3 interview decision 1 (2026-08-12, human)` — the compiler is first built as `.claude/skills/rubric-compiler/` running the patch-2 Planner/Generator/Evaluator loop; the deterministic core (M1–M5) is the loop's backbone; the CLI pipeline (M6) is deferred until the skill is proven. **CONFLICT FLAG:** amends the earlier decision "Compiler logic is pure; I/O is at the boundary" and the out-of-scope claim "no model call during compilation" — the purity claim now applies to the deterministic compile path only; model-judged authoring steps live in the skill and are recorded as decisions.

### Decision: Patch-2 schema fields retrofitted into AuthoredNode — M0 reopened (round-3 Q2)

**Rationale:** `Source: round-3 interview decision 2 (2026-08-12, human)` — M0 is reopened to add `companion_docs` (S1), `depends_on` (S3), `signal.checkable`/`signal.audit_result` (S4). **CONFLICT FLAG:** M0's 2026-07-28 CONFIRMED verdict covered the original scope; the reopen is a scope change, not a revocation of the original acceptance tests — they remain, with new tests added.

### Decision: Epoch commits follow the INTENTS symlink into the external tree (round-3 Q3)

**Rationale:** `Source: round-3 interview decision 3 (2026-08-12, human)` — CompilerIO writes through the symlink to `/Users/prometheus/workspace/INTENTS`; epoch commits happen in the external repo; harness-cli references by SHA / EPOCH.yaml. `intents_sha` (I4) pins the external tree SHA. The current all-zero EPOCH placeholder is replaced on the first real compile.

### Decision: Recompile = in-place overwrite + new epoch commit (round-3 Q4)

**Rationale:** `Source: round-3 interview decision 4 (2026-08-12, human)` — node paths stay stable (`item-22.yaml`); each compile mints a new epoch; history is preserved by SHA pinning, not directory versioning. Constraint (couples with decision 7): `edited_by_human` files are never overwritten by a recompile.

### Decision: `_rubric/evidence/` is a runtime dependency (round-3 Q5)

**Rationale:** `Source: round-3 interview decision 5 (2026-08-12, human)` — acoustic indicators and phrase lexicon stay in `_rubric/evidence/` and are loaded by the 9002 rubric reader. Confirms D16 (framework/lexicon are rubric, not corroborators). No conflict.

### Decision: Schema constraints tightened — dimensions ≥1, text non-empty, epoch_id format (round-3 Q6)

**Rationale:** `Source: round-3 interview decision 6 (2026-08-12, human)` — the three M0-deferred gaps close: zero-dimension skill rejected, empty item text rejected, `epoch_id` format = ISO date + external-tree SHA (couples with decision 3). `Confidence: high` — direct schema-level rejections, no ambiguity left.

### Decision: Human edits — S2 source adjudication AND D8 output escape hatch (round-3 Q7)

**Rationale:** `Source: round-3 interview decision 7 (2026-08-12, human)` — both mechanisms live: `validate_sources` halts on source conflict for human adjudication (S2); `edited_by_human` marks output-layer escape edits that recompiles skip (D8); the validator checks edited files for cross-file consistency. Additive — the plan previously had neither; no conflict with D1–D16 / S1–S6.

### Decision: Calibration manifest at `_meta/calibration-manifest.<epoch>.yaml`, structural-only validation (round-3 Q8, rewritten)

**Rationale:** `Source: round-3 interview decision 8 (2026-08-12, human; rewritten after empirical inspection of the INTENTS tree)` — the interview's original answer (`INTENTS/_calibration/`) is overridden: the manifest lives at `_meta/calibration-manifest.<epoch>.yaml` in the same style as `residue-manifest.yaml`. `source_case` refs are validated **structurally** (conventions.yaml grammar `cookbook.<slug>.yaml` / `errors.<slug>.yaml`), never by existence — the Error Case Library and Best Practice Cookbook are currently empty (zero cookbook.* / errors.* files in the tree; business domains hold only `.gitkeep`), and the first manifest arrives before any library content. `severity_map` URI refs (`calibration://manifest/<epoch>/severity/<criterion>`) must align with the manifest file's epoch. conventions.yaml has no `calibration` file type — `_meta/` avoids a tree-level convention change.

### Decision: Plan reconciled with patch-1 (D1–D12) and patch-2 (S1–S6) (2026-08-12)

**Rationale:** `Source: audit of docs/retrospectives/soft-criteria-authoring-spec-v4-patch-1.md and soft-criteria-authoring-spec-v4-patch-2.md against this plan` — deltas applied: (1) `hard_fail_rule` removed from AuthoredNode (D3 → per-dimension `gates/{dimension}.yaml`); (2) `w_c` is not a node field (D6 → agreement/config constant); (3) per-dimension output layout `rules_criteria/{dimension}/item-XX.yaml` (D1); (4) `edited_by_human` guard (D8) extended to evidence/ and gates/ writers; (5) uniform schema, no tier field (D11); (6) B-F `audit_gate_checkable` named in M2 (S4); (7) topological compile order in M6a Planner (S3); (8) S5 exclusion-set adversarial check in M1 (warn-level, non-blocking); (9) item count: patch-1's pseudocode "25" is stale — the plan's 27 (spec rev.4, incl. Item 24) stands; (10) **supersession**: round-3 decision 5 (evidence/ is a runtime dependency) overrides patch-1 D4's "evidence is not a runtime dependency" — D4's self-contained-node principle (thresholds inline) is preserved; evidence/ gains a runtime role (indicator framework + lexicon loaded by the 9002 rubric reader).

### Decision: Skill renamed to rubric-compiler (M6a)

**Rationale:** `Source: human decision (2026-08-12)` — the agent skill lands as `.claude/skills/rubric-compiler/`, matching the repo's descriptive kebab-case skill-naming house style (verifier, dep-vetter, harness-go — no plan-numbered skill directories). The plan's earlier `9003-compiler` name is superseded; all plan references updated accordingly (execution architecture, File Scope, M6a, Allowed Writes).

### M0 reopen adversarial verification (2026-08-12)

Verdict: CONFIRMED

**Rationale:** `Source: subagent B adversarial verification (2026-08-12)` — acceptance tests 15/15 pass (3 original roundtrips + patch-2 fields roundtrip + 4 constraint rejections incl. B-finding F3 whitespace-only text); structural suite 195/195 green; consumer mock loop end-to-end verified (nodes/gates/manifest reload into the new schema; conflict fixture halts). B's initial REJECTED verdict adjudicated by the orchestrator: **F1** (unflipped notes carried verdict badges, tripping the flip gate) — resolved by keeping no notes file until flip, recreated with badges at flip; **F3** (whitespace-only text accepted) — fixed via a strip validator (RED test → subagent A fix round); **F5** (plan wording implied S4 schema fields) — plan clarified: S4 flows through free-form `signals`, enforced by M1's `check_checkable_audited`; **F2** (epoch_id shape-only validation, no calendar validity) — accepted as residual (compiler-derived, unreachable in practice); **F4** (mock runner emits companion_docs without sha256) — deferred to M6a (see Surprises). Environment fixes during verification: stale prunable worktree `/tmp/impl-4c608a59` pruned; 9006 `state.json` reconciled to the completed plan.

## 6. Surprises & Discoveries

* M0 adversarial verification found 3 domain-level design gaps (non-blocking): GenericEvaluatorSkill accepts 0 dimensions without error, RubricItem.text has no min_length constraint, CalibrationManifest.epoch_id has no format validation. All deferred — these are design choices for later milestones, not M0 mechanical failures.
* 2026-08-12 (M0 reopen): two PEV gates conflict while a milestone is unflipped with notes present — the checkbox-flip gate forbids `[badge]` headings in unflipped notes, the implementation-notes gate requires them whenever the file exists. Resolution: no notes file while unflipped; notes recreated with badges at flip. Worth a future harness reconciliation.
* 2026-08-12 (M0 reopen): `epoch_id` enforces shape (`YYYY-MM-DD-<40-hex>`) but not ISO calendar validity (F2 residual) — "2026-13-99-…" constructs; accepted since epochs are compiler-derived.
* 2026-08-12 (M0 reopen): the mock runner emits `companion_docs` entries without `sha256` (F4) — the SHA lives only in `compile-plan.json`. When M1's `check_companion_docs` requires per-entry SHA, either the runner must embed it or the checker must accept plan-sourced SHAs. Deferred to M6a execution.
* 2026-08-12 (pre-M1 inspection for round-3 interview): the INTENTS tree is a skeleton — no L2/L3 case nodes, zero `cookbook.*` / `errors.*` files, EPOCH.yaml is an all-zero placeholder. The calibration manifest's `source_case` refs therefore cannot be existence-validated, only grammar-validated (drove the Q8 rewrite). conventions.yaml's naming types (kb/cookbook/errors/case/index/ui_step) have no `calibration` type — placing the manifest in `_meta/` (like residue-manifest.yaml) avoids a tree-level convention change.

## 7. Awaiting Steering

> **Awaiting Steering: resolved — Q1.** PENDING INPUTS: Specific QA Rubric (27 binary items) + `align.md`. These are the compiler's primary inputs (§0.5). The compiler infrastructure (M0–M7) can be built and tested with fixture data. M8 (§3.6b per-item compile) is gated on receiving the real inputs. Default: proceed with M0–M7; M8 waits. If the inputs are delayed past M7 completion, M0–M7 ship as a working compiler that is input-ready.

> **Awaiting Steering: resolved — Q2.** Calibration Manifest first injection. The manifest channel infrastructure (M7) supports standalone injection with no compile run. The first manifest injection requires human-annotated fragments from the Error Case Library and Best Practice Cookbook. Default: M7 ships the mechanism; the first injection is triggered by the pipeline's drift detector (§6) when κ falls or escape rate rises — not at plan completion.

> **Awaiting Steering: resolved — Q3 (round-3 interview, 2026-08-12).** All eight round-3 interview questions were answered by the human and recorded in the Decision Log (incl. conflict flags). No open steering items remain before M0 (reopen) → M1 → … → M6a (agent skill).

> **Awaiting Steering: resolved — M6a registration (2026-08-12).** CLAUDE.md registration of the rubric-compiler skill in "## Skills available" (one line, house style) is approved. The path CLAUDE.md is exempted for this one-line addition.

## 8. Outcomes & Retrospective

*Written at completion or cancellation.*
