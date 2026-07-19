# 9004 — Harness Clio's Three-Stage Pipeline into Audio2Tree

## 1. Purpose

The audio2tree bottom-up intent discovery system currently clusters call transcripts into a flat L2/L3 tree using the PRD patch's four-stage pipeline (Request extraction → L1 classification → intra-L1 clustering → manifest population). This works but misses three capabilities the Clio paper demonstrated at production scale: contrastive cluster naming that produces distinctive labels rather than generic ones, neighborhood-based hierarchy building that handles hundreds of clusters without context-window truncation, and criteria-shaped facets that trace every extracted signal to a specific QA rubric Item. Without these, audio2tree produces clusters with weak names, no scalability beyond ~50 L2 intents per business line, and facets that Argus must re-extract independently. This plan integrates Clio's three-stage pipeline into audio2tree, adapted to customer-service call data and the four-source INTENTS tree architecture.

`Source: docs/superpowers/specs/2026-07-19-clio-to-audio2tree-design.md`

## 2. Big Picture

This plan adds a new `audio2tree` subcommand to the Argus CLI: `argus audio2tree cluster` runs the full pipeline end-to-end. The pipeline reads `.structural.json` files from `INTENTS/<L1>/<L2>/<L3>/calls/`, reads L2 semantic anchors from `intent_manifest.json` via the AGENTS.md routing protocol, and writes `intent_manifest.json → bottom_up` sections throughout the INTENTS tree.

**Modules touched:**

| Module | What changes |
|:---|:---|
| `src/argus/io/` | New: `call_reader.py` (reads .structural.json, extracts Request + facets). Modified: `intents_provider.py` (reads manifest.json for L2 anchors) |
| `src/argus/core/` | New: `routing.py` (dual-channel: cosine match → dispatch), `clustering.py` (silhouette-optimal k-means + stability protocol), `naming.py` (contrastive prompt + LLM integration), `hierarchy.py` (neighborhood-based hierarchy), `facets.py` (programmatic + model-based facet extractors) |
| `src/argus/cli/` | New: `audio2tree` subcommand group with `cluster`, `status`, `audit` |

**Deliberately out of scope:**

- Interactive UI for cluster exploration (Clio's Map View / Tree View). Audio2Tree's consumer is downstream AI, not human analysts
- Privacy layers. Internal enterprise call data does not need Clio's 5-layer defense
- Fully bottom-up L1 discovery. L1 is Doc2Graph-anchored per the Audio2Tree PRD patch
- Auto-triggering Doc2Graph or 9003 compiler. These are independent systems with their own invocation cadences
- Detailed prompt template tuning, exact parameter calibration, embedding model selection. These are discovered during execution, not prescribed by the plan

**CLI surface introduced:**

```
argus audio2tree cluster [--phase {1|2}] [--l1 <name>] [--force]
argus audio2tree status [--l1 <name>]
argus audio2tree audit [--l1 <name>] [--drift-threshold <float>]
```

## 3. Milestones

### M0 — AGENTS.md as agent routing index

Replace the v0 placeholder AGENTS.md with the CLAUDE.md-style navigation protocol: teaches agents how to find and use the tree via `find`/`grep`/`cat`/`jq`, does not enumerate every L2/L3. Includes routing protocol for audio2tree Consumer and reading protocol for Argus Evaluator.

`Acceptance Test:` A downstream agent can, by reading AGENTS.md and using only standard bash tools, locate the intent_manifest.json for a given L3 intent and extract the fields needed for evaluation. Verified by `tests/test_agents_md.py::test_agents_md_provides_routing_protocol` — the test greps AGENTS.md for the routing protocol section, confirms it references `intent_manifest.json` and `find`/`jq`, and confirms the file is under 50 lines.

### M1 — L2 semantic anchor extraction + dual-channel routing engine

Read all L2 `intent_manifest.json` files via the protocol in AGENTS.md. Extract `description` fields as semantic anchors, embed them, and cache. Implement cosine-matching dispatch: S_max ≥ T → matched channel, S_max < T → deviation channel. Compute and report deviation rate per run.

`Acceptance Test:` `tests/test_routing.py::test_matched_channel` — given a Request semantically close to an existing L2 description (cos > 0.60), the router assigns it to that L2. `tests/test_routing.py::test_deviation_channel` — given a Request semantically distant from all L2 descriptions (cos < 0.60), the router routes it to the deviation pool rather than force-assigning. `tests/test_routing.py::test_deviation_rate_computed` — after processing a batch, deviation rate = |deviation| / |total| is correctly reported.

### M2 — Criteria-shaped facet extractors

Implement programmatic facet extractors (acoustic features, turn stats, pause metrics from .structural.json) and model-based facet extractors (LLM-powered signal detection for rubric Items). Every extracted facet must carry an `item_signal` trace field. Gate-checkable facets (lexical, threshold, lookup) are tagged `checkable: true`. Model-only facets (semantic judgment requiring NLU) are tagged `checkable: false`. Apply the B-F gate-checkability audit from Patch-2 to every model-based facet.

`Acceptance Test:` `tests/test_facets.py::test_programmatic_facets_computed` — given a .structural.json fixture, all programmatic facets (f0_mean, speaking_rate, turn_count, etc.) are computed without error. `tests/test_facets.py::test_model_facets_trace_to_item_signal` — every model-based facet in the output carries a non-null `item_signal` field that resolves to a known Item in the 25-Item rubric. `tests/test_facets.py::test_gate_checkable_tagged` — lexical facets are tagged checkable=true, semantic facets tagged checkable=false.

### M3 — Contrastive cluster naming

Implement contrastive naming: for each cluster, select 5 representative Requests closest to the centroid (in-cluster) + 5 Requests from the nearest neighboring cluster's centroid but not assigned to this cluster (contrastive). Use an LLM with temperature=1.0 and the contrastive prompt structure to generate a distinctive Chinese name and two-sentence description. Validate that names are not generic ("其他咨询", "综合问题").

`Acceptance Test:` `tests/test_naming.py::test_contrastive_prompt_structure` — the generated prompt includes both in-cluster and contrastive samples, clearly separated by XML tags. `tests/test_naming.py::test_name_not_generic` — given a cluster of certificate renewal calls, the generated name is specific (e.g., "咨询证书续费流程") not generic. `tests/test_naming.py::test_llm_temperature_is_1` — the LLM call for naming uses temperature=1.0.

### M4 — INTENTS tree population (bottom_up section)

Write audio2tree's clustering output to `intent_manifest.json` files throughout the INTENTS tree. For matched-channel L2 nodes: update `bottom_up` section (request_count, cluster_centroid, representative_requests), write L3 child nodes (each as its own intent_manifest.json). For deviation-channel L2 nodes: create new L2 directory + manifest (source: audio2tree, status: pending_review), create L3 child nodes. Never modify `top_down` section. Update AGENTS.md routing index only if a new L2 is created (add the L2 entry).

`Acceptance Test:` `tests/test_manifest_population.py::test_matched_channel_writes_bottom_up` — after clustering a matched-channel L2, its manifest.json contains a populated bottom_up section and the top_down section is unchanged. `tests/test_manifest_population.py::test_deviation_channel_creates_new_l2` — a deviation-channel cluster with request_count > threshold creates a new L2 directory with manifest.json (source: audio2tree, status: pending_review). `tests/test_manifest_population.py::test_l3_manifests_created` — each L2 receives L3 child directories with their own intent_manifest.json files.

### M5 — Stability protocol (incremental run)

Implement incremental assignment: load existing cluster centroids from previous run state. New Requests assigned to nearest centroid above threshold (0.65). Unassigned Requests accumulate in pool; when pool reaches discovery_threshold (15), run k-means on pool only to discover new clusters. Existing centroids are updated as running means, not replaced. Merges and splits are never automatic — they require manual `audit` invocation. Centroid drift detection: flag when two centroids approach within cosine 0.95.

`Acceptance Test:` `tests/test_stability.py::test_idempotent_runs` — running audio2tree twice on the same corpus produces identical cluster assignments (same intent_ids). `tests/test_stability.py::test_incremental_preserves_centroids` — running on an extended corpus preserves all existing intent_ids; new data assigned to existing or new clusters correctly. `tests/test_stability.py::test_deviation_pool_accumulates` — calls below assignment threshold enter the unassigned pool; pool reaches discovery_threshold → new clusters created. `tests/test_stability.py::test_no_auto_merge` — two clusters whose centroids drift close together are flagged by audit, not auto-merged.

### M6 — Neighborhood-based hierarchy builder

Implement Clio G.7 adapted hierarchy: when an L1 has L2 count exceeding the context threshold (~50), group L2 clusters into neighborhoods (~40 per neighborhood), propose parent cluster names per neighborhood with contrastive edge clusters (m=5 nearest outside the neighborhood), deduplicate across neighborhoods, assign L2s to parents, rename parents. Below the threshold, use direct full-list naming (all L2 names fit in a single context window).

`Acceptance Test:` `tests/test_hierarchy.py::test_neighborhood_triggered_above_threshold` — with > 50 L2 clusters in one L1, the hierarchy builder activates neighborhood mode and produces parent clusters without truncation. `tests/test_hierarchy.py::test_direct_naming_below_threshold` — with ≤ 50 L2 clusters, the hierarchy builder uses direct full-list naming. `tests/test_hierarchy.py::test_no_orphan_l2` — every L2 cluster is assigned to a parent; no L2 is left unassigned.

### M7 — Boot sequence: Phase 1 → Phase 2 orchestration

Implement the two-phase boot sequence. Phase 1 (--phase 1): Request extraction + programmatic facets only, basic L2/L3 clustering. Phase 2 (--phase 2): full criteria-shaped facets, dual-channel routing, enriched clustering. When transitioning from Phase 1 to Phase 2, existing cluster centroids survive unchanged — only facet_stats metadata is added. Request text is the same across phases, so the vector space is stable.

`Acceptance Test:` `tests/test_boot_sequence.py::test_phase1_produces_clusters` — Phase 1 runs on a corpus with no compiled Items and produces valid L2/L3 clusters. `tests/test_boot_sequence.py::test_phase2_preserves_phase1_centroids` — Phase 2 runs on the same corpus and all Phase 1 intent_ids survive; centroids are within cosine 0.99 of Phase 1 values. `tests/test_boot_sequence.py::test_phase2_adds_facet_stats` — Phase 2 output includes facet_stats that Phase 1 output does not.

### M8 — End-to-end integration: real INTENTS data

Run the full pipeline against real call data from the INTENTS tree. The test exercises the CLI entry point, reads actual .structural.json files, produces manifest.json output, and asserts on externally observable properties: exit code 0, non-empty bottom_up sections written, deviation rate within expected bounds, cluster names non-generic.

`Acceptance Test:` `tests/integration/test_audio2tree_e2e.py::test_full_pipeline_real_data` — invokes `argus audio2tree cluster --phase 1` against the INTENTS tree's call corpus, asserts exit code 0, asserts at least one manifest.json has a populated bottom_up section, asserts deviation rate is computed and reported on stdout. `tests/integration/test_audio2tree_e2e.py::test_phase2_enrichment` — invokes `argus audio2tree cluster --phase 2` and asserts facet_stats are present in output.

## 4. Progress

- [x] M0: AGENTS.md as agent routing index  (done 2026-07-19)
- [ ] M1: L2 semantic anchor extraction + dual-channel routing engine  (created 2026-07-19)
- [ ] M2: Criteria-shaped facet extractors  (created 2026-07-19)
- [ ] M3: Contrastive cluster naming  (created 2026-07-19)
- [ ] M4: INTENTS tree population (bottom_up section)  (created 2026-07-19)
- [ ] M5: Stability protocol (incremental run)  (created 2026-07-19)
- [ ] M6: Neighborhood-based hierarchy builder  (created 2026-07-19)
- [ ] M7: Boot sequence: Phase 1 → Phase 2  (created 2026-07-19)
- [ ] M8: End-to-end integration with real INTENTS data  (created 2026-07-19)

## 5. Decision Log

### Decision: Dual-channel routing with cosine threshold, not force-assignment

**Rationale:** `Source: docs/superpowers/specs/2026-07-19-clio-to-audio2tree-design-decision.md §Decision 1` — three options considered: pure bottom-up (loses Doc2Graph anchor), force-assign (pollutes clustering), dual-channel (selected). The deviation channel turns coverage gap into a measurable metric.

### Decision: Criteria-shaped facets traced to rubric Items

**Rationale:** `Source: docs/superpowers/specs/2026-07-19-clio-to-audio2tree-design-decision.md §Decision 2` — facets extracted for QA evaluation, not general exploration. Every facet carries an Item.Signal trace. Gate-checkability tagged per Patch-2 B-F.

### Decision: Contrastive naming with reduced sample count (5+5 vs Clio's 50+50)

**Rationale:** `Source: docs/superpowers/specs/2026-07-19-clio-to-audio2tree-design-decision.md §Decision 3` — CS intents are more convergent than open-ended AI conversations. The contrastive structure (not sample count) is the load-bearing innovation.

### Decision: No cross-system auto-triggers

**Rationale:** `Source: docs/superpowers/specs/2026-07-19-clio-to-audio2tree-design-decision.md §Decision 4` — audio2tree, Doc2Graph, and 9003 are independent systems. Their only coupling is writing different fields into the same INTENTS tree. The audio2tree feedback loop closes at Curated confirmation.

### Decision: AGENTS.md teaches navigation, not enumeration

**Rationale:** `Source: docs/superpowers/specs/2026-07-19-clio-to-audio2tree-design-decision.md §Decision 5` — a catalogue must be manually synchronized with the tree. A navigation protocol stays valid as the tree grows. Agents use `find`/`grep`/`cat`/`jq` to discover content at runtime.

### Decision: Additive tree growth via stability protocol

**Rationale:** `Source: docs/superpowers/specs/2026-07-19-clio-to-audio2tree-design-decision.md §Decision 6` — full reclustering breaks downstream reproducibility (Argus pins to intent_ids). Locked tree prevents new intent discovery. Incremental assignment preserves existing centroids while allowing new cluster creation from the unassigned pool.

### Decision: Phase 1 before Phase 2 — graduated complexity, not blocking dependency

**Rationale:** `Source: docs/superpowers/specs/2026-07-19-clio-to-audio2tree-design-decision.md §Decision 7` — Phase 1 delivers value immediately (basic clustering) without waiting for the 9003 compiler. Phase 2 adds criteria-shaped facets as enrichment. The Request text is unchanged across phases, so the vector space is stable and Phase 1 centroids survive unchanged.

### Decision: Implementation details discovered during execution, not prescribed by the plan

**Rationale:** `Source: docs/superpowers/specs/2026-07-19-clio-to-audio2tree-design.md §6` — prompt templates, embedding model selection, exact parameter values, k-selection strategy, model tiering economics are execution details. The plan defines acceptance criteria (what "done" looks like) and architectural constraints (what must not be violated). The path is figured out during implementation. `Confidence: high` on the approach — this is the same discipline used by the 9003 compiler plan, which separated spec (what) from exec-plan (milestones) from execution (how).

## 6. Surprises & Discoveries

*None yet — this section grows during execution. The Verifier records milestone-flip failures here.*

## 7. Awaiting Steering

> **Awaiting Steering: resolved — Q1.** M8 requires real call data in the INTENTS tree. Currently the _demo structure has placeholder calls. The E2E test can use fixture data until real calls are available. Default: M8 ships with fixtures; re-run when real data lands.

> **Awaiting Steering: resolved — Q2.** The model-based facet extractors (M2) require LLM access. The compiler (9003) has a hard "core ✗ model_client" fence. Does this fence apply to audio2tree? Default: audio2tree's model-based extraction lives in `io/`, not `core/` — same quarantine pattern as the 9002 runtime pipeline. The facet extraction prompt is the only place the model touches; the routing, clustering, and stability logic in `core/` remain pure functions.

> **Awaiting Steering: resolved — Q3.** Embedding model: BAAI/bge-m3. Chosen for: Chinese-English multilingual support (critical for mixed-language CS calls), 1024-dimensional embeddings, strong performance on both semantic similarity and retrieval tasks. Resolved 2026-07-19.

## 8. Outcomes & Retrospective

*Written at completion or cancellation.*
