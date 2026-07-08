# 9002 — Implement the Argus Eval Pipeline

## 1. Purpose

Argus today has a v6 spine — the five-layer architecture is enforced, the INTENTS tree exists with a worked domain, and four ADRs define the epistemic classes and two-stage evaluation contract — but `src/argus/` is near-empty scaffolding. No call can be evaluated. The user-visible gap is that the CLI has no `eval` subcommand, no pipeline that reads a transcript and emits a scored evaluation. This plan fills that gap: it lands the deterministic process-derivation pipeline specified in `docs/PRD/process-derivation-pipeline-spec-v5.html` as working application code, M0 through M7. The spec is the contract — every milestone enforces it, none re-derives it.

## 2. Big Picture

This is the first application-code plan for Argus. It touches every layer of `src/argus/`: types (schemas), config (thresholds and pinning), io (INTENTS Provider, LLM proposer, call-record loader), core (grounding, corroboration, score, adjust, routing, agreement instrument), and cli (eval and replay subcommands). The work is gated on the v6 spine (0000-upgrade-spine-to-v6) being complete — it is.

The scope is the Argus consumer tier only (D13): enforced stages S2 (propose), S3 (ground), S4a (score), S4b (adjust), S5 (route). S0 (ingest: audio to transcript) and S6 (correction: human-confirmed write-back to INTENTS) are other tiers — they survive in this plan only as a typed call-record intake contract (M1) and a no-write-path structural test (M7), never as application code.

The layer mapping follows D18/R7: types → config → io → core → cli. The LLM proposer is an io Provider; pure score, adjust, grounding, corroboration, and routing live in core. The load-bearing fence is `core ✗ model_client` — no module in core imports anthropic or any LLM client. This is what keeps v6's "core is pure" claim true. The governing invariant (§2.5) is model proposes → deterministic gate disposes → pure fn re-derives: score() and adjust() are PROPOSERS on the model side (io); the shipped raw/adjusted come only from the pure re-derivation stages (core).

The INTENTS tree at `INTENTS/` already holds a worked domain (annual-report-submission) with a compliance rubric rule, acoustic indicators, a phrase lexicon, a kb fact, a cookbook precedent, and an error case. The pipeline's IntentsNode schema must accommodate both the current v1-format rubric entries and the enriched authoring-schema entries the companion 9003 will compile. The companion 9003 (`soft-criteria-authoring-spec-v4.html`) defines the `_rubric/` node fields — `required_evidence.form`/`.spec`, `corroborators[].independence_class`, the `agreement` block, `applicability_gate`, `severity_map`, `gap_type`, `escape_tier`, `data_dependency` — that the pipeline's judgment-layer gates read at runtime. 9003 must land its enriched `_rubric/` nodes before 9002's M5 judgment-layer gates activate. Before then, every soft criterion returns `deferred` (no judgment rubric exists to ground against) — correct behavior, not a bug.

The build order (§8) is M0 → M7. The INTENTS Provider is first (everything reads the referent); the LLM proposer is last (quarantined — every other stage must stand before a model can safely propose into them).

The CLI surface this plan introduces: `argus eval <call-record>` (run the full pipeline and emit an EvaluationResult), `argus eval replay <graph>` (re-derive from a stored FindingGraph). Config surface: `argus.intents_path` (default `INTENTS/`), `argus.intents_sha` (pinned from EPOCH.yaml), `argus.rubric_version`, scoring thresholds, τ (default 0.8), W_C provisional constant (0.4).

Deliberately out of scope: S0 ingest (audio → transcript, acoustic measurement extraction), S6 correction (write-time, producer-owned), the companion 9003 compiler itself (this plan READS `_rubric/`, 9003 WRITES it), population of INTENTS beyond the existing worked domain, `references/node_contract.md` (human-owned), Hermes/Metis integration, browser automation scaffolding.

## 3. Milestones

### M0 — INTENTS Provider (io)

One `IntentsProvider` in `src/argus/io/intents.py` that resolves paths in the `INTENTS/` tree at a pinned git-SHA epoch, exposing three category readers (rubric, facts, history) behind a single interface. The Provider is read-only — no write path, no load-and-confirm step (the tree is already single and calibrated per D15/ADR-0003). Q1 default: the nine v6 modules group into three category readers; every count reference carries a `# Q1` comment until `expertise-library.md` reconciles 8-vs-9. The Provider validates every parsed node against the `IntentsNode` Pydantic schema from `types/`.

`Acceptance Test:` `tests/test_intents_provider.py::test_reads_rubric_facts_history` — loads the worked domain's rubric rule, kb fact, and cookbook precedent; asserts typed returns. `tests/test_intents_provider.py::test_no_write_path` — the Provider has no methods that mutate the tree. `tests/test_intents_provider.py::test_missing_node_returns_null` — a read for a non-existent path returns a typed null, not an exception. `tests/test_intents_provider.py::test_s1_no_write_path_into_intents` — structural grep confirms no `src/argus/` path opens an INTENTS file for writing (S1 fixture, red+green).

`Notes:` The Provider's `intents_root` is configurable (default `INTENTS/`), passed via constructor injection — no global singletons. The epoch is read from `EPOCH.yaml` at construction time. This is the foundation; every downstream milestone depends on reading the referent.

### M1 — Call-record intake contract (types + io)

Define the typed contract for the transcript + acoustic-measurement call record Argus consumes from the transformation tier. Land the Pydantic schema in `src/argus/types/call_record.py`: `CallRecord` with `call_id`, `transcript: list[Turn]` (each Turn has `turn_index`, `speaker`, `char_start`, `char_end`, `text`, `start_time`, `end_time`), and `acoustic_measurements: list[AcousticMeasurement]` aligned to spans. Plus a `CallRecordLoader` in `src/argus/io/call_reader.py` that reads and validates JSON from disk. No audio/DSP code — S0 is upstream (D13).

`Acceptance Test:` `tests/test_call_record.py::test_schema_roundtrip` — a valid JSON call record parses into a `CallRecord` and round-trips. `tests/test_call_record.py::test_malformed_rejected` — a record missing `transcript` fails validation.

### M2 — Schemas + validators (types)

Land all §3 Pydantic schemas in `src/argus/types/`: `IntentsNode` (§3.1 — accommodates both current v1-format rubric entries and the enriched authoring schema 9003 will compile; judgment-layer fields like `corroborators`, `agreement`, `applicability_gate`, `severity_map`, `gap_type` are Optional with `default=None`), `Finding` (§3.2 — with `grounding_signals[]`, `proposed_score`), `FindingGraph` (§3.3), `MetaVerificationResult` (§3.4 — with `Corroboration` block), `EvaluationResult` (§3.5 — with `raw`, `adjusted`, `applied_precedents[]`, `coverage`, `proposed_vs_derived[]`, `replay_hash`), `CriterionHealth` (§3.6), `Rubric` (pure data structure with `weight()`, `apply()`, `apply_precedents()` methods), `Precedent` (anchored L3 case-history entry). Plus a `types/validators.py` that rejects a Finding missing `anchor_node`, `span_ref`, or `quoted_text` before it reaches the gate.

`Acceptance Test:` `tests/test_schemas.py::test_all_schemas_roundtrip` — each schema constructs, serializes to JSON, and deserializes. `tests/test_schemas.py::test_finding_missing_anchor_fails_validation` — a Finding without `anchor_node` fails the validator. `tests/test_schemas.py::test_intents_node_accepts_both_formats` — the IntentsNode model parses both a v1-format rubric entry (from the current INTENTS tree) and a full authoring-schema entry (per companion spec §3).

### M3 — Grounding gate S3 (core, pure)

Land the deterministic grounding pass in `src/argus/core/grounding.py`. Every function is pure — no model import, no clock, no RNG, no network. Functions: `verify_span(finding, transcript) → SpanCheckResult` (deterministic lookup), `verify_quote(finding, transcript) → float` (exact substring match; 1.0 if match, <1.0 otherwise), `resolve_anchor(finding, anchor_nodes) → IntentsNode | None` (deterministic dict lookup), `check_applicability(finding, node, transcript) → ApplicabilityVerdict` (per the §4 gradient table — lexical check for Phrase/Keyword, KB lookup for Dynamic KB, ordered-match for Operation Manual, spec lookup for Product Intro, rule-eval for Rules&Criteria objective, threshold comparison for Acoustic Features, structural match stubs for Error Case / Best Practice — not model! just structural), `meta_verify(finding, transcript, anchor_nodes, criterion_health) → MetaVerificationResult` (the full S3 pass). `grounding_confidence` is a property of the wire (from the §4 table), never read from the model. Crucially: `grounding ✗ proposer` and `grounding ✗ matching_model`.

`Acceptance Test:` `tests/test_grounding.py::test_i2_anchor_or_quarantine_red` — finding cites non-existent `anchor_node: "rc-9999"`, gate moves it to `ungrounded`. `tests/test_grounding.py::test_i2_green` — finding cites existing `AR-LF-001-a`, enters `findings`. `tests/test_grounding.py::test_quote_fidelity_red` — quoted_text doesn't match span, `quote_fidelity < 1.0`, `meta_verdict: rejected`. `tests/test_grounding.py::test_quote_fidelity_green` — exact match, `quote_fidelity = 1.0`, proceeds. `tests/test_grounding.py::test_i6c_no_model_import` — structural check confirms `grounding` does not import `anthropic` or any model client.

### M3.5 — Corroboration aggregator S3⁺ (core, pure)

Land the independence-weighted noisy-OR in `src/argus/core/corroboration.py`. Pure function over verified signals — S3 already confirmed each resolves and co-locates. `aggregate_corroboration(signals, primary_channel) → Corroboration` per §4.1 pseudocode. W_C (0.4) read from config as a pinned rubric constant with `# PROVISIONAL` comment. `assign_defer_reason(verification, criterion_health) → str | None` — assigns `finding_thin`, `criterion_below_tau`, `ungrounded`, or `None`. Corroboration clears `finding_thin` but never `criterion_below_tau` (D4).

`Acceptance Test:` `tests/test_corroboration.py::test_i6a_red` — two redundant signals → `aggregate = 0.0`, `independent_present: false`. `tests/test_corroboration.py::test_i6a_green` — one independent signal → `aggregate = 1.0`, `independent_present: true`. `tests/test_corroboration.py::test_i6b_red` — criterion κ < τ, finding has independent anchor → still `deferred` with `criterion_below_tau`. `tests/test_corroboration.py::test_i6b_green` — κ ≥ τ, `finding_thin` cleared by independent anchor → both axes clear. `tests/test_corroboration.py::test_aggregate_is_pure` — byte-identical on replay. `tests/test_corroboration.py::test_i6c_no_model_client` — `aggregate ✗ model_client`.

### M4 — Stage 1: score() S4a (core, pure, history-free)

Land the `score()` function in `src/argus/core/score.py`. Takes only confirmed findings and the rubric — history is NOT an argument (D17). Runtime purity assert rejects any confirmed finding citing a precedent. Properties: total (empty findings → raw=1.0), monotone (adding a violation never raises raw), pure (no clock, RNG, network, model), history-pure (enforced by signature AND runtime assert), replayable (replay_hash is function of grounded inputs only, never proposed_score). The `Rubric` class in `types/` is a pure data structure loaded by io, passed into score() as a typed argument.

`Acceptance Test:` `tests/test_score.py::test_i3_determinism_canary` — same FindingGraph fed twice produces byte-identical `raw` and `replay_hash`. `tests/test_score.py::test_total_empty_findings` — no findings → raw=1.0. `tests/test_score.py::test_monotone` — adding a violation never raises raw. `tests/test_score.py::test_purity_assert_fires` — a confirmed finding with `cites_precedent=True` triggers the runtime assert. `tests/test_score.py::test_i7_red` — proposed_score reaches EvaluationResult.score or replay_hash → must fail. `tests/test_score.py::test_i7_green` — S4 ignores proposed_score, derives from grounded evidence, logs divergence as probe. `tests/test_score.py::test_core_no_model_client`.

### M4.5 — Stage 2: adjust() S4b (core, pure precedent application)

Land the `adjust()` function in `src/argus/core/adjust.py`. Takes `raw`, anchored precedents (resolved against L3 history), graph, and rubric. Each precedent must resolve in the INTENTS history category at the pinned SHA — unanchored precedents are dropped, never applied. Empty precedents → adjusted == raw. `applied_precedents[]` matches the anchored set. Replay is byte-identical including precedent set.

`Acceptance Test:` `tests/test_adjust.py::test_empty_precedents_adjusted_equals_raw` — no precedent anchors → `adjusted == raw`. `tests/test_adjust.py::test_unanchored_precedent_dropped` — precedent with unresolvable history anchor is dropped. `tests/test_adjust.py::test_applied_precedents_recorded` — `applied_precedents[]` matches the anchored set. `tests/test_adjust.py::test_replay_identical` — same inputs → byte-identical EvaluationResult. `tests/test_adjust.py::test_core_no_model_client`.

### M5 — Agreement instrument + routing S5 (core)

Land the routing logic and agreement instrument in `src/argus/core/routing.py`. `compute_coverage(graph) → float` — fraction of verdict resting on grounded findings vs ungrounded (D10, per-call, computable). `determine_routing(graph, raw, criterion_health) → RoutingDecision` — two-axis auto-final gate (§5.1): coverage clear (no ungrounded, no deferred) AND criterion health clear (every cited criterion `trusted`). `compute_kappa(argus_verdicts, human_verdicts) → float` — Cohen's κ per criterion, pure function. `check_drift(criterion_id, windowed_kappas) → DriftStatus` — detects falling κ across windows. `CriterionHealthStore` — persistence in `io/`, pure computation in `core/`. τ defaults to 0.8 (configurable). No Argus-vs-Argus voting path exists — structural test enforces.

`Acceptance Test:` `tests/test_routing.py::test_agreement_gate_red` — soft criterion κ < τ → `deferred`, `human_review`. `tests/test_routing.py::test_agreement_gate_green` — compliance finding, all anchored, no deferrals → `auto_final`. `tests/test_routing.py::test_d10_coverage_red` — low-coverage call with clean proposed_score → `human_review` (model number doesn't buy coverage). `tests/test_routing.py::test_d10_coverage_green` — fully covered on trusted criteria → `auto_final`. `tests/test_routing.py::test_drift_demotes` — falling κ demotes criterion. `tests/test_routing.py::test_no_argus_vs_argus_voting` — structural grep confirms zero N-model-sample voting paths. `tests/test_routing.py::test_d12_red` — any code path that reads resample variance and uses it for routing → must fail.

### M5.5 — Escape-rate sampler + CriterionHealth (§6 auto-pass tail, core)

Land the escape-rate computation in `src/argus/core/escape_rate.py`. `compute_escape_rate(reviewed_samples) → float` — human-caught misses ÷ sampled auto-passes (D11, floor on knowable residue). `compute_trend(rates_over_windows) → str` — "falling", "flat", or "rising". `update_criterion_health(criterion, kappa, escape_rate, trend) → CriterionHealth` — sets status to `trusted` only when κ ≥ τ AND escape rate acceptable and not rising. A rising escape rate demotes the criterion even when κ is healthy (D11).

`Acceptance Test:` `tests/test_escape_rate.py::test_d11_red` — criterion with healthy κ but rising escape rate → `status: "demoted"`, routes to human. `tests/test_escape_rate.py::test_d11_green` — κ ≥ τ, escape rate below ceiling, not rising → `status: "trusted"`. `tests/test_escape_rate.py::test_d12_green` — resample variance written only to triage-priority field; routing ignores it.

### M6 — Proposer S2 (io, quarantined)

Land the LLM-based finding proposer in `src/argus/io/proposer.py`. This is the ONLY component that imports `anthropic`. It is an io Provider, never core. The proposer walks transcript spans and emits candidate `Finding` objects via a structured LLM call. It populates `grounding_signals[]` with independence classes copied from the resolved INTENTS nodes (D3) — it reads the node's authored class, never judges independence itself. It optionally emits a quarantined `proposed_score` (D7), logged for drift probing, never shipped. Temperature/seed are pinned; output is never trusted past the gate.

`Acceptance Test:` `tests/test_proposer.py::test_output_is_schema_valid` — every proposer output passes the M2 schema validator. `tests/test_proposer.py::test_proposer_is_io_not_core` — structural check confirms `core ✗ proposer`. `tests/test_proposer.py::test_i7_end_to_end` — a proposed_score never reaches the shipped raw/adjusted or replay_hash. `tests/test_proposer.py::test_end_to_end_replay` — stored FindingGraph reproduces identical EvaluationResult.

### M7 — Correction boundary (structural test only)

No application code. A structural test confirms no code path in `src/argus/` writes to the `INTENTS/` tree. This is how v6 severs the co-degradation loop — Argus, the consumer, has no write path back into its own referent (D15). A corrected epoch (produced upstream) becomes visible only by re-pinning to a newer SHA.

`Acceptance Test:` `tests/test_no_write_path.py::test_s1_red` — any code path in `src/argus/` that opens an INTENTS file for writing → CI fails (AST grep for open-with-write-mode targeting INTENTS paths). `tests/test_no_write_path.py::test_s1_green` — Argus reads INTENTS through the one Provider at a pinned SHA and emits only report + coaching.

## 4. Progress

- [ ] M0: INTENTS Provider (io)  (created 2026-07-08)
- [ ] M1: Call-record intake contract  (created 2026-07-08)
- [ ] M2: Schemas + validators  (created 2026-07-08)
- [ ] M3: Grounding gate S3  (created 2026-07-08)
- [ ] M3.5: Corroboration aggregator S3⁺  (created 2026-07-08)
- [ ] M4: Stage 1 — score() S4a  (created 2026-07-08)
- [ ] M4.5: Stage 2 — adjust() S4b  (created 2026-07-08)
- [ ] M5: Agreement instrument + routing S5  (created 2026-07-08)
- [ ] M5.5: Escape-rate sampler + CriterionHealth  (created 2026-07-08)
- [ ] M6: Proposer S2  (created 2026-07-08)
- [ ] M7: Correction boundary  (created 2026-07-08)

## 5. Decision Log

### Decision: W_C=0.4 is a provisional constant, versioned with rubric

**Rationale:** `Source: docs/PRD/process-derivation-pipeline-spec-v5.html §4.1` — the spec states `W_C≈0.4` and the critique panel warns "w_c is a guess until measured." The constant is stored in `config` as `corroboration_correlated_weight` with a `# PROVISIONAL` comment. The correct value should be set empirically as `1 − corr(matcher_error, proposer_error)` on a human-labeled sample. `Confidence: low` on 0.4; `Revisit:` when escape-rate data accumulates sufficient sample.

### Decision: Three category readers behind one Provider, Q1 module-count flag

**Rationale:** `Source: ADR-0004` — the nine v1 reader interfaces collapse to `read_rubric`, `read_facts`, `read_history`. The spec's Q1 default adopts v6's nine modules grouped into three category readers. Until `expertise-library.md` reconciles 8-vs-9, every module-count reference carries a `# Q1: 9 modules → 3 readers` comment.

### Decision: Fixture-first build order — red fixtures written before implementation

**Rationale:** `Source: docs/conventions/verification-floor.md` — each milestone's red+green fixtures (§7) are written as the first commit of the milestone. The red fixture fails before implementation (dead-man's switch), the green fixture passes after. A passing red fixture means the gate died.

### Decision: Rubric is a typed data structure loaded by io, passed to core as argument

**Rationale:** The `Rubric` class is defined in `types/` (pure data shape), loaded by the INTENTS Provider in `io/` (reads `_rubric/` YAML), and passed into `score()` and `adjust()` in `core/` as a typed argument. This keeps core pure — it receives the rubric, never reads it. Follows the layering convention: config/IO happens before core runs; core receives typed arguments.

### Decision: The existing `providers/` directory stays; new Providers go in `io/`

**Rationale:** `Source: ARCHITECTURE.md §1` — "providers + utils" maps to the `io` layer. The existing `src/argus/providers/browser_automation.py` is Hermes scaffolding (out of scope). The INTENTS Provider and LLM Proposer go in `src/argus/io/` per the architecture. No structural change to existing files in this plan.

### Decision: CallRecord is consumed from JSON on disk, not produced by this repo

**Rationale:** `Source: D13` — S0 Ingest is the transformation tier, not this repo. Argus reads the call record as a JSON file produced upstream. The `CallRecordLoader` in `io/` reads and validates; it does not transcribe, extract acoustic features, or align measurements to spans.

### Decision: IntentsNode accommodates both v1-format and enriched rubric entries

**Rationale:** The current worked INTENTS `_rubric/` entries (e.g. `late-filing-requirements.yaml`) use a v1 format — simple rule with `rule_id`, `criteria[]`, prose `required_evidence` and `fail_condition`. The companion 9003 will enrich these with the full authoring schema (structured `required_evidence.form`/`.spec`, `corroborators[]`, `agreement` block, etc.). The `IntentsNode` Pydantic model uses `Optional` fields with `default=None` for all judgment-layer and enriched fields, so it parses both formats. M0-M4 work against the current compliance rubric; M3.5 and M5 define interfaces whose full behavior activates when 9003 lands enriched nodes.

## 6. Surprises & Discoveries

*None yet — this section grows during execution. The Verifier records milestone-flip failures here.*

## 7. Awaiting Steering

*None at plan creation. The spec resolves all Tier C questions: scope (D13), layers (D18), build order (§8), Q1 module-count default. W_C provisional constant is logged technical debt, not a steering question.*

> **Pre-answered — Q1 (module count).** The spec's default (9 modules → 3 category readers) is adopted. Flag every count reference with `# Q1` comment. When `expertise-library.md` reconciles 8-vs-9, remove the flags.

## 8. Outcomes & Retrospective

*Written at completion or cancellation.*
