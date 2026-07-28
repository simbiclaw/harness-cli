# 9003 — Implement the Soft-Criteria Compiler + Validator

## 1. Purpose

The runtime pipeline (9002) needs enriched `_rubric/` nodes to ground judgment-layer findings — without them, every soft criterion returns `deferred`. The current `INTENTS/_rubric/` holds v1-format compliance rules; the judgment-layer shelf is empty. This plan lands the **offline authoring compiler and validator** specified in `docs/PRD/soft-criteria-authoring-spec-v4.html`: it takes a human-authored Specific QA Rubric (binary checklist), an AI-executed Generic Evaluator Skill (judgment template), and an `align.md` item→dimension map, fuses them through the A1–A7 and B-A..B-D procedures, and emits enriched `_rubric/` nodes plus a ResidueManifest. The compiler is not a runtime stage — it runs once per criterion, offline, and stocks the referent the runtime reads. The validator enforces the ten AUTH prohibitions (§4) at authoring time. The Calibration Manifest is deliberately NOT a compiler input — it arrives on its own channel, injectable alone, re-anchoring severity_map refs with no recompile required.

## 2. Big Picture

This is an authoring-tool plan, not a runtime plan. The compiler reads human-authored inputs from disk, applies the spec's authoring procedure, and **writes enriched nodes into `INTENTS/_rubric/`** — this is the legitimate write path (ADR-0003: write-time, producer-owned, minting a new epoch). It is the exception to the runtime pipeline's "no src/argus write path into INTENTS" rule: the compiler IS the write-time path. Every write is a human-confirmed commit; the compiler never self-triggers from Argus evaluation output (A7).

The compiler touches `types/` (node schema, manifest schema, input schemas), `io/` (reading the three compiler inputs, writing `_rubric/` nodes and manifest), `core/` (pure compilation logic — signal decomposition, gap classification, escape-tier assignment, hard-fail synthesis), and `cli/` (a `compile` subcommand). It does NOT touch the runtime proposer, grounding gate, or scoring functions — those are 9002's domain.

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

**Two required outputs:** enriched `_rubric/` nodes (per the §3 authored-entry schema) plus a ResidueManifest (§3.5) naming what was left behind — including `dimension_coverage_gap` rows for criteria no dimension covers (Item 24). A compiler run that emits nodes without a manifest is rejected (AUTH-5).

**The authoring procedure** (§2) runs once per soft criterion: A1 (decompose to orthogonal dimensions), A2 (decompose signature into gate-checkable FAIL/EXCELLENCE signals — per Patch 1 D10, the old `trigger.spec` with `form ∈ {lexical, ordered_relation, threshold, lookup}` is removed; each signal must pass the Q1/Q2 gate-checkable test and is backed by programmatic or model_based facets), A3 (classify corroborators by independence — redundant class forbidden), A4 (declare the residue — required field), A5 (seed the agreement gate with both tails: κ sample plan + escape sample plan + escape ceiling), A6 (set deduction weight and W_C provisional constant), A7 (register drift detection and iteration policy — re-ground via write-time epoch commit only). Plus A2-ac (author the 12 acoustic indicators into `_rubric/evidence/acoustic/`) and A2-ph (author the phrase lexicon into `_rubric/evidence/phrase-keyword/`).

**The binary→continuous bridge** (§2.6) runs per binary item: B-A (bind item to dimension as weighted evidence via `align.md`, with a `severity_map` reference into the calibration manifest), B-B (compile every NA condition into an `applicability_gate`), B-C (synthesize hard-fail routing rules from item subsets — many-to-one, not copied thresholds), B-D (extract concrete values from checklist text — named phrases → lexical signals, numbers → threshold signals, at confidence 1.0, per Patch 1 D10).

**Gap types** the compiler must handle (§0.5 rev.4 items 1–7): values (binary→continuous bridge), perceiver (NA→applicability gate), proxy (hard-threshold synthesis), calibration_surface_form (AUTH-9 auto-final ban until manifest covers the failure surface), coverage (escape_tier assignment — proxy/coverage → aggressive sampling; values/perceiver/calibration_surface_form → standard), dimension_coverage_gap (Item 24 — defer-until-source-connected, propose new sub-dimension).

**Ten validator prohibitions** (§4, §5): AUTH-1 (no adjective signals), AUTH-2 (no undeclared residue), AUTH-3 (no ungated soft entry — must have agreement block with tau + kappa_sample_plan), AUTH-4 (no soft⊕soft corroborator — redundant class rejected, plus acoustic framework/phrase lexicon as corroborators rejected per D16), AUTH-5 (no compile run without a residue manifest), AUTH-6 (no soft entry without an escape plan — must have escape_sample_plan + escape_ceiling), AUTH-7 (no NA condition without a compiled applicability_gate), AUTH-8 (no data-dependent signal without data_dependency declaration; connected=false must defer), AUTH-9 (no auto-final on uncalibrated surface-form criterion — gap_type calibration_surface_form must not permit auto-final unless manifest covers its failure surface), AUTH-10 (no unmapped item forced into a dimension — silent miscoding is worse than honest defer).

**CLI surface introduced:** `argus compile <specific-rubric> <generic-skill> <align-md>` — runs the full authoring procedure and writes `_rubric/` nodes + manifest. `argus validate <node>` — runs the AUTH-1..10 validator against a single node or directory of nodes.

**Deliberately out of scope:** the companion 9002 runtime pipeline (reads _rubric/ but doesn't write it). The §3.6b per-item compile over all 27 items — that is a FOLLOW-ON task gated on receiving the real Specific QA Rubric + align.md inputs (do not invent item values). Population of the Calibration Manifest — it arrives on its own channel, outside the compiler. The runtime evaluation pipeline. Any model call during compilation — the compiler transforms structured inputs deterministically; it does not use an LLM to author signals.

## 3. Milestones

### M0 — Compiler input schemas (types)

Define the Pydantic schemas for the three compiler inputs: `SpecificRubric` (27 items, each with id, text, values, NA condition, failure examples), `GenericEvaluatorSkill` (4 dimensions, 1–10 scale, failure signatures, hard-threshold mechanism — note: this is an AI template, not a human artifact), `AlignMap` (item → dimension routing). Plus the `CalibrationManifest` input schema (independent channel — fragments with scores, source_case refs from Error Case Library and Best Practice Cookbook). Plus the output schemas: the enriched `AuthoredNode` (extending IntentsNode with all §3 fields — corroborators, residue_declared, agreement block, applicability_gate, severity_map, gap_type, escape_tier, data_dependency, hard_fail_rule, iteration_policy) and `ResidueManifest` (§3.5 — within_dimension and dimension_coverage_gap rows, sources block tracking the three inputs + calibration epoch).

`Acceptance Test:` `tests/test_compiler_schemas.py::test_all_input_schemas_roundtrip` — each input schema constructs, serializes, and deserializes. `tests/test_compiler_schemas.py::test_authored_node_roundtrip` — an AuthoredNode with all §3 fields round-trips. `tests/test_compiler_schemas.py::test_residue_manifest_roundtrip` — manifest with both row kinds round-trips.

`Allowed Reads: docs/retrospectives/soft-criteria-authoring-spec-v4.html, docs/retrospectives/soft-criteria-authoring-spec-v4-patch-1.md, docs/retrospectives/soft-criteria-authoring-spec-v4-patch-2.md, src/argus/types/**, docs/conventions/layering.md`
`Allowed Writes: src/argus/types/__init__.py, src/argus/types/compiler_schemas.py, tests/test_compiler_schemas.py`
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

`Acceptance Test:` `tests/test_validator.py::test_auth1_red` — adjective signal → validator rejects. `tests/test_validator.py::test_auth1_green` — structural signal → accepts. One red+green pair per AUTH-1..10, matching the §5 fixtures exactly.

### M2 — Signal Decomposition + Evidence authoring (A1, A2, A2-ac, A2-ph, core) <span class="p1-note">(was "Trigger compiler" — trigger.spec removed per Patch 1 D10)</span>

Land the pure signal-decomposition and evidence-authoring functions in `src/argus/core/compiler/signals.py` <span class="p1-note">(was `triggers.py`)</span>. The compiler takes a dimension description (from the generic skill template) and the human rubric's pass/fail standards and produces a `machine_criterion` + `signals` + `facets` block per the four-layer operationalized artifact (Patch 1 D10):

- `decompose_dimension(dimension) → list[SignalCandidate]` — A1: apply independence, exhaustiveness, and operationalizability tests; split what's signal-decomposable from what's residue
- `decompose_signals(item) → Signals` — A2 + B-E (Patch 1 D12): translate failure/pass standards into FAIL + EXCELLENCE signals. Each signal must pass the gate-checkable test: a proposer can find a transcript span (Q1) AND a gate can deterministically verify that span (Q2). No adjectives survive. Signals that are still conclusions ("坐席表现混乱") without concrete referents → rejected (AUTH-1 extended). <span class="p1-note">The old `compile_trigger(candidate) → Trigger` with `form ∈ {lexical, ordered_relation, threshold, lookup}` is removed — replaced by the human_version → machine_criterion → signals → facets four-layer chain (Patch 1 D10)</span>
- `assign_facets(signals, gap) → FacetGroup` — assigns programmatic or model_based facets per signal (D5/D9). Each programmatic facet carries indicator + calculation + output_schema. Each model_based facet carries a complete extraction prompt (checkpoints + output_schema) authored by the compiler.
- `compile_acoustic_framework(indicators) → list[EvidenceEntry]` — A2-ac: author 12 acoustic indicators as pure data (EvidenceEntry, not AuthoredNode per Patch 1 D2), written to `_rubric/evidence/acoustic/indicators.yaml`
- `compile_phrase_lexicon(lexicon) → list[EvidenceEntry]` — A2-ph: author phrase/pattern lists as pure data, written to `_rubric/evidence/phrase-keyword/`

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
- `set_w_c(criterion) → float` — A6: `W_C = 0.4` PROVISIONAL, flagged for empirical measurement.
- `set_iteration_policy(criterion) → str` — A7: "re-ground via write-time epoch commit only; no rule edits from Argus output."

`Acceptance Test:` `tests/test_agreement_seed.py::test_agreement_block_has_both_tails` — tau + kappa_sample_plan + escape_sample_plan + escape_ceiling all present. `tests/test_agreement_seed.py::test_missing_escape_plan_rejected` — kappa plan present but no escape plan → AUTH-6 rejects. `tests/test_agreement_seed.py::test_w_c_provisional_flagged` — W_C field has PROVISIONAL comment. `tests/test_agreement_seed.py::test_iteration_policy_forbids_model_edits` — iteration policy string contains "no rule edits from Argus output."

### M5 — Binary→continuous bridge (B-A..B-D, core)

Land the pure bridge functions in `src/argus/core/compiler/bridge.py`:

- `bind_item_to_dimension(item, align_map, manifest_epoch) → DimensionBinding` — B-A: via `align.md`, attach item to its dimension with `deduction` and `severity_map` (a reference into the calibration manifest at its current epoch). If no manifest exists yet, the node compiles but surface-form-sensitive criteria get `auto_final: false` (AUTH-9).
- `compile_applicability_gate(item) → ApplicabilityGate | None` — B-B: translate NA condition into `applicability_gate.spec`. Item with NA condition but no gate → AUTH-7 rejects. Returns `None` if item has no NA condition.
- `synthesize_hard_fail(items, dimension) → HardFailRule | None` — B-C: identify subset of binary items whose collective failure indicates severe dimension failure. Author a many-to-one routing rule. This is synthesized, not copied from the template's single threshold.
- `extract_values(item) → list[ValueExtraction]` — B-D: parse named phrases → lexical signal spec, numeric thresholds → threshold signal spec, at `confidence 1.0`. <span class="p1-note">values now enrich machine_criterion and signals, not a standalone trigger spec (Patch 1 D10)</span> Never settle for principle-level when the rubric text carries the exact value.
- `check_dimension_coverage(item, align_map, dimensions) → CoverageVerdict` — after binding: does some dimension adequately measure what this item measures? If no (Item 24), emit `data_dependency` with `connected: false` + defer disposition + `dimension_coverage_gap` manifest row. Do NOT force-fit. AUTH-10 rejects forced mappings.

`Acceptance Test:` `tests/test_bridge.py::test_bind_item_via_align` — item routes to correct dimension via align.md. `tests/test_bridge.py::test_na_condition_compiles_to_gate` — NA condition → applicability_gate with spec. `tests/test_bridge.py::test_missing_applicability_gate_rejected` — NA-bearing item without gate → AUTH-7 rejects. `tests/test_bridge.py::test_hard_fail_synthesized_not_copied` — hard_fail_rule is many-to-one, not a copied threshold. `tests/test_bridge.py::test_values_extracted_from_checklist` — named phrases → lexical; numbers → threshold. `tests/test_bridge.py::test_unmapped_item_not_force_fit` — Item 24 business-harm forced into Problem Resolution → AUTH-10 rejects, dimension_coverage_gap row required. `tests/test_bridge.py::test_uncalibrated_surface_form_no_auto_final` — gap_type calibration_surface_form without manifest coverage → auto_final forbidden (AUTH-9).

### M6 — Full compiler pipeline (orchestration, io + core + cli)

Land the compiler orchestration that runs the full A1–A7 + B-A..B-D procedure, reading the three inputs and writing `_rubric/` nodes + ResidueManifest:

- `compile_rubric(specific_rubric, generic_skill, align_map, *, manifest_epoch=None) → CompileResult` — pure orchestration in `core/compiler/compile.py`. Returns `(list[AuthoredNode], ResidueManifest)`. Does NOT do I/O — receives parsed inputs, returns typed outputs.
- `CompilerIO` in `io/compiler_io.py` — reads the three input files from disk (parsing YAML/JSON/markdown), writes AuthoredNodes to `INTENTS/_rubric/` paths, writes ResidueManifest to `INTENTS/_meta/residue-manifest.yaml`. This IS the legitimate write path into INTENTS (ADR-0003: write-time, producer-owned).
- `compile` subcommand in `cli/commands.py` — `argus compile <specific-rubric> <generic-skill> <align-md> [--manifest-epoch <ref>]`. Reads inputs, calls `compile_rubric()`, writes outputs via `CompilerIO`.
- `validate` subcommand — `argus validate <path>` runs the AUTH-1..10 validator against one node or a directory of nodes.

`Acceptance Test:` `tests/test_compiler_pipeline.py::test_full_compile_emits_nodes_and_manifest` — given three valid inputs, the compiler outputs enriched nodes AND a residue manifest. `tests/test_compiler_pipeline.py::test_manifest_missing_from_run_rejected` — AUTH-5: a compile that would emit nodes without a manifest row for a non-fully-compilable dimension → rejected. `tests/test_compiler_pipeline.py::test_no_model_call_during_compile` — structural check confirms no `anthropic` import in compiler code. `tests/test_compiler_pipeline.py::test_compile_is_deterministic` — same inputs → byte-identical outputs. `tests/test_compiler_pipeline.py::test_validate_subcommand_rejects_bad_node` — `argus validate` on a node with adjective signal → non-zero exit. `tests/test_cli_compile.py::test_compile_subcommand_help` — CLI smoke test.

### M7 — Calibration manifest channel (independent)

Land the calibration manifest ingestion — NOT as a compiler input, but as an independent channel that can be injected alone:

- `CalibrationManifestLoader` in `io/calibration_io.py` — reads a manifest epoch (JSON/YAML), validates fragments have source_case refs from Error Case Library or Best Practice Cookbook.
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

- [x] M0: Compiler input schemas  (done 2026-07-28)
- [ ] M1: Validator (AUTH-1..10)  (created 2026-07-08)
- [ ] M2: Trigger compiler (A1, A2, A2-ac, A2-ph)  (created 2026-07-08)
- [ ] M3: Corroborator classifier + residue declarer (A3, A4)  (created 2026-07-08)
- [ ] M4: Agreement seeder + deduction setter (A5, A6, A7)  (created 2026-07-08)
- [ ] M5: Binary→continuous bridge (B-A..B-D)  (created 2026-07-08)
- [ ] M6: Full compiler pipeline (orchestration + io + cli)  (created 2026-07-08)
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

## 6. Surprises & Discoveries

* M0 adversarial verification found 3 domain-level design gaps (non-blocking): GenericEvaluatorSkill accepts 0 dimensions without error, RubricItem.text has no min_length constraint, CalibrationManifest.epoch_id has no format validation. All deferred — these are design choices for later milestones, not M0 mechanical failures.

## 7. Awaiting Steering

> **Awaiting Steering: resolved — Q1.** PENDING INPUTS: Specific QA Rubric (27 binary items) + `align.md`. These are the compiler's primary inputs (§0.5). The compiler infrastructure (M0–M7) can be built and tested with fixture data. M8 (§3.6b per-item compile) is gated on receiving the real inputs. Default: proceed with M0–M7; M8 waits. If the inputs are delayed past M7 completion, M0–M7 ship as a working compiler that is input-ready.

> **Awaiting Steering: resolved — Q2.** Calibration Manifest first injection. The manifest channel infrastructure (M7) supports standalone injection with no compile run. The first manifest injection requires human-annotated fragments from the Error Case Library and Best Practice Cookbook. Default: M7 ships the mechanism; the first injection is triggered by the pipeline's drift detector (§6) when κ falls or escape rate rises — not at plan completion.

## 8. Outcomes & Retrospective

*Written at completion or cancellation.*
