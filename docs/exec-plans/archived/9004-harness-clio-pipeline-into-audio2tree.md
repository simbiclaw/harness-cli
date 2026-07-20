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

Read all L2 `intent_manifest.json` files via the protocol in AGENTS.md. Extract `description` fields as semantic anchors, embed them (bge-m3), and cache. Implement cosine-matching dispatch: S_max ≥ T → matched channel, S_max < T → deviation channel. Compute and report deviation rate per run.

**Notes — see `docs/references/audio2tree-pipeline-design.md` §2 for the full routing flow and §5 for L2 manifest schema.**

- **L2 anchors come from manifest.json, not AGENTS.md.** AGENTS.md teaches agents how to find them via `find`/`jq`. The extraction script reads manifest files at runtime. If a description changes between runs, only re-embed that one L2 (hash check).
- **Dual-channel dispatch is the core architectural innovation.** A call is never force-assigned to a mismatched L2. The deviation pool is a first-class output, not an error bucket. Deviation rate = |D_deviation| / |D_total| is computed and reported on stdout after every run — this is the management metric that tells Curated whether the manual taxonomy is keeping up with real customer needs.
- **Pipeline mapping reference:** S2 stage in the design session — L1 classification (cosine to L1 descriptions) runs first, then L2 routing within the assigned L1. Two cosine passes, not one. L1 descriptions also come from manifest.json files at the L1 directory level.
- **Threshold T = 0.60 initial.** This is human-calibrated after the first batch run — not a fixed constant. Store in pipeline config, not hardcoded.
- **Collision detection at embedding time.** After embedding all L2 descriptions, compute pairwise cosine distances. If any pair has cosine > 0.7, freeze the newer L2's anchor — exclude from matching. Flag for Curated review via `argus audio2tree audit --collisions`. The collision threshold is configurable in pipeline config.

`Acceptance Test:` `tests/test_routing.py::test_collision_detection_freezes_anchor` — given two L2 descriptions with cosine > 0.7, the newer one is frozen and excluded from matching. `tests/test_routing.py::test_matched_channel` — given a Request semantically close to an existing L2 description (cos > 0.60), the router assigns it to that L2. `tests/test_routing.py::test_deviation_channel` — given a Request semantically distant from all L2 descriptions (cos < 0.60), the router routes it to the deviation pool rather than force-assigning. `tests/test_routing.py::test_deviation_rate_computed` — after processing a batch, deviation rate = |deviation| / |total| is correctly reported.

### M2 — Criteria-shaped facet extractors

Implement programmatic facet extractors (acoustic features, turn stats, pause metrics from .structural.json) and model-based facet extractors (LLM-powered signal detection for rubric Items). Every extracted facet must carry an `item_signal` trace field. Gate-checkable facets (lexical, threshold, lookup) are tagged `checkable: true`. Model-only facets (semantic judgment requiring NLU) are tagged `checkable: false`. Apply the B-F gate-checkability audit from Patch-2 to every model-based facet.

**Notes — see `docs/references/audio2tree-pipeline-design.md` §3 for the full facet-to-Item/Signal mapping table and quarantine boundary rules.**

- **The facet taxonomy IS the rubric taxonomy, reversed.** Don't ask "what can we extract." Ask "what does the rubric need to measure." The 25 Items × 4 Dimensions mapping table from the design session is the reference: every model-based facet must trace to at least one Item.Signal. If a proposed facet can't name its Item.Signal, it doesn't belong in the extractor.
- **Programmatic vs model-based split is a quarantine boundary (I1).** Programmatic facets (acoustic, turn stats, pause metrics) are deterministic — they live in `core/`. Model-based facets (LLM-extracted signals) touch the model — they live in `io/`. Same fence as the 9002 runtime pipeline. The B-F gate-checkability audit from Patch-2 runs on every model-based facet: Q1 (can proposer find a span?) → Q2 (can gate deterministically verify that span?) → tag as checkable, split, or model_only.
- **Start with the subset of facets that are gate-checkable.** Items 01-07 (procedural accuracy) are almost entirely lexical — greeting, address terms, hold, closing. These are the lowest-risk facets to implement first. Semantic facets (knowledge_accuracy, emotion_sync, tone_friendliness) come later and default to checkable=false.
- **Facet extraction is additive.** Phase 1 extracts Request only. Phase 2 adds criteria-shaped facets to the same Request objects. The Request text doesn't change — only the metadata attached to it grows. Phase 2 is incremental by default: only calls not in `pipeline_state/processed_calls.json` get criteria-shaped extraction. `--reprocess-all` flag enables full re-extraction.
- **DKB/Cookbook/Errors resolved by path convention.** For knowledge_accuracy and other expertise-dependent facets, resolve the relevant curated file by walking the L2 directory first, falling back to L1, resolving parent/extends/overrides per the expertise-decision-log inheritance rules. Pure function in `core/`. If no DKB found at any level, return checkable=false.

`Acceptance Test:` `tests/test_facets.py::test_programmatic_facets_computed` — given a .structural.json fixture, all programmatic facets (f0_mean, speaking_rate, turn_count, etc.) are computed without error. `tests/test_facets.py::test_model_facets_trace_to_item_signal` — every model-based facet in the output carries a non-null `item_signal` field that resolves to a known Item in the 25-Item rubric. `tests/test_facets.py::test_gate_checkable_tagged` — lexical facets are tagged checkable=true, semantic facets tagged checkable=false.

### M3 — Contrastive cluster naming

Implement contrastive naming: for each cluster, select 5 representative Requests closest to the centroid (in-cluster) + 5 Requests from the nearest neighboring cluster's centroid but not assigned to this cluster (contrastive). Use an LLM with temperature=1.0 and the contrastive prompt structure to generate a distinctive Chinese name and two-sentence description. Validate that names are not generic ("其他咨询", "综合问题").

**Notes — see `docs/references/audio2tree-pipeline-design.md` §4 for the full contrastive prompt structure and selection algorithm.**

- **The contrastive structure is the load-bearing innovation from Clio G.5.** The model must identify what is DISTINCTIVE about this cluster, not just what is common. The prompt has two explicitly separated sections: `<同类 Request>` (5 samples FROM the cluster, closest to centroid) and `<对比 Request>` (5 samples from the nearest neighboring cluster's centroid that are NOT in this cluster). This forces the model to name the boundary, not the center.
- **Temperature = 1.0 for naming.** Naming needs diversity, not determinism. This is a direct adaptation from Clio — Sonnet at temp=1.0. Audio2Tree uses the same principle with its own strong model.
- **The prompt is in Chinese with domain context.** The model is told which L1 and L2 this cluster belongs to. The name must describe "客户想要什么" (what the customer wants), not "客户情绪如何" (how the customer feels). Generic names like "其他咨询" are explicitly rejected in validation.
- **Clio uses 50+50 samples; Audio2Tree uses 5+5.** Customer service intents are significantly more convergent than open-ended AI conversations. The reduced sample count fits CS data's lower variance while preserving the contrastive mechanism.
- **Model tiering: small model for S1 extraction, strong model for S3 naming.** Clio's pattern (Haiku for facets, Sonnet for naming) is directly adapted.

`Acceptance Test:` `tests/test_naming.py::test_contrastive_prompt_structure` — the generated prompt includes both in-cluster and contrastive samples, clearly separated by XML tags. `tests/test_naming.py::test_name_not_generic` — given a cluster of certificate renewal calls, the generated name is specific (e.g., "咨询证书续费流程") not generic. `tests/test_naming.py::test_llm_temperature_is_1` — the LLM call for naming uses temperature=1.0.

### M4 — INTENTS tree population (bottom_up section)

Write audio2tree's clustering output to `intent_manifest.json` files throughout the INTENTS tree. For matched-channel L2 nodes: update `bottom_up` section (request_count, cluster_centroid, representative_requests), write L3 child nodes (each as its own intent_manifest.json). For deviation-channel L2 nodes: create new L2 directory + manifest (source: audio2tree, status: pending_review), create L3 child nodes. Never modify `top_down` section. Update AGENTS.md routing index only if a new L2 is created (add the L2 entry).

**Notes — see `docs/references/audio2tree-pipeline-design.md` §5 for the full four-shape manifest schema (L1, L2 matched, L2 deviation, L3) and merge rules.**

- **Key-level isolation is the non-negotiable contract.** Doc2Graph writes `top_down`. Audio2Tree writes `bottom_up`. Neither reads the other's section during write. The manifest merge logic is: if the file exists, read it, update only `bottom_up` + `last_updated` + `last_updated_by`, write back. If the file doesn't exist (deviation channel), create it with `source: "audio2tree"` and `status: "pending_review"`.
- **Four distinct manifest shapes.** The design session produced schemas for L1 (directory node: intent_id, title, description, child_intents), L2 matched (source: both, top_down present, bottom_up.channel: matched), L2 deviation (source: audio2tree, top_down empty, bottom_up.channel: deviation, status: pending_review), and L3 (parent_intent_id links to L2, no top_down). The implementation must handle all four without a `level` field — level is expressed by directory path.
- **L3 nodes are always audio2tree-created.** Doc2Graph writes L1 and L2 structure. L3 is the granularity at which audio2tree clusters calls within an L2. L3 manifests have `parent_intent_id`, not `child_intents`.
- **AGENTS.md update is a side effect, not the primary output.** Only when a deviation-channel L2 is confirmed (status changes from pending_review to active) does the L2 entry get added to AGENTS.md. Until then, the L2 is discoverable via `find` but not listed in the routing index.

`Acceptance Test:` `tests/test_manifest_population.py::test_matched_channel_writes_bottom_up` — after clustering a matched-channel L2, its manifest.json contains a populated bottom_up section and the top_down section is unchanged. `tests/test_manifest_population.py::test_deviation_channel_creates_new_l2` — a deviation-channel cluster with request_count > threshold creates a new L2 directory with manifest.json (source: audio2tree, status: pending_review). `tests/test_manifest_population.py::test_l3_manifests_created` — each L2 receives L3 child directories with their own intent_manifest.json files.

### M5 — Stability protocol (incremental run)

Implement incremental assignment: load existing cluster centroids from previous run state. New Requests assigned to nearest centroid above threshold (0.65). Unassigned Requests accumulate in pool; when pool reaches discovery_threshold (15), run k-means on pool only to discover new clusters. Existing centroids are updated as running means, not replaced. Merges and splits are never automatic — they require manual `audit` invocation. Centroid drift detection: flag when two centroids approach within cosine 0.95.

**Notes — see `docs/references/audio2tree-pipeline-design.md` §6 for the full stability algorithm, parameter table, and state file spec.**

- **The stability protocol is directly adapted from Clio's incremental assignment.** The core rule: existing cluster centroids are preserved. New data is assigned to the nearest existing centroid (cos ≥ 0.65). Only data that doesn't match any existing cluster accumulates in an unassigned pool. When the pool reaches discovery_threshold (15), k-means runs on the pool only — never on the full dataset. This guarantees existing intent_ids never change.
- **Centroid updates are running means, not replacements.** When a new Request is assigned to an existing cluster, the centroid moves: centroid_new = (centroid_old × n + V_new) / (n + 1). This is bounded drift — a single new Request can't radically shift a cluster with hundreds of existing members.
- **Merges and splits are human-triggered, never automatic.** The `argus audio2tree audit --drift-threshold 0.95` command surfaces clusters whose centroids have drifted close together. But the merge decision is Curated's. The stability protocol flags; it never acts.
- **State is persisted between runs.** Cluster centroids, member counts, and pool state are written to `pipeline_state/` after each run and loaded at the start of the next. This is what makes idempotent re-runs possible: same corpus → same state file → same assignments.

`Acceptance Test:` `tests/test_stability.py::test_idempotent_runs` — running audio2tree twice on the same corpus produces identical cluster assignments (same intent_ids). `tests/test_stability.py::test_incremental_preserves_centroids` — running on an extended corpus preserves all existing intent_ids; new data assigned to existing or new clusters correctly. `tests/test_stability.py::test_deviation_pool_accumulates` — calls below assignment threshold enter the unassigned pool; pool reaches discovery_threshold → new clusters created. `tests/test_stability.py::test_no_auto_merge` — two clusters whose centroids drift close together are flagged by audit, not auto-merged.

### M6 — Neighborhood-based hierarchy builder

Implement Clio G.7 adapted hierarchy: when an L1 has L2 count exceeding the context threshold (~50), group L2 clusters into neighborhoods (~40 per neighborhood), propose parent cluster names per neighborhood with contrastive edge clusters (m=5 nearest outside the neighborhood), deduplicate across neighborhoods, assign L2s to parents, rename parents. Below the threshold, use direct full-list naming (all L2 names fit in a single context window).

**Notes — see `docs/references/audio2tree-pipeline-design.md` §7 for the full six-step neighborhood hierarchy algorithm and parameters.**

- **This is Clio G.7 adapted — but conditionally enabled.** Clio always uses neighborhood-based hierarchy. Audio2Tree only enables it when an L1 has > 50 L2 clusters. Below that threshold, all L2 names + descriptions fit in a single LLM context window, so direct full-list naming is simpler and equally accurate.
- **The six-step algorithm is directly from Clio Appendix G.7:**
  1. Embed each L2 cluster's name + description (bge-m3)
  2. K-means group embeddings into neighborhoods (~40 clusters each). k is chosen so each neighborhood fits in context
  3. For each neighborhood: Claude proposes candidate parent names. Claude sees BOTH the clusters in the neighborhood AND the nearest m=5 clusters OUTSIDE it — this prevents boundary clusters from being miscategorized or double-counted
  4. Claude deduplicates across all neighborhood proposals — merges semantically equivalent parent names, ensures coverage
  5. Each L2 is assigned to its best-fit parent
  6. Parents are renamed based on their actual assigned children (not the original proposal)
- **The contrastive edge clusters (m=5) are the key Clio insight preserved.** Without them, a cluster on the boundary between two neighborhoods could be assigned to a parent that doesn't represent it, because the parent proposer never saw it. The m=5 edge samples prevent this.
- **This milestone is lower priority than M1-M5.** Most CS domains will not reach 50 L2 intents per L1. The direct full-list path handles the common case. Neighborhood mode is a scalability safety valve.

`Acceptance Test:` `tests/test_hierarchy.py::test_neighborhood_triggered_above_threshold` — with > 50 L2 clusters in one L1, the hierarchy builder activates neighborhood mode and produces parent clusters without truncation. `tests/test_hierarchy.py::test_direct_naming_below_threshold` — with ≤ 50 L2 clusters, the hierarchy builder uses direct full-list naming. `tests/test_hierarchy.py::test_no_orphan_l2` — every L2 cluster is assigned to a parent; no L2 is left unassigned.

### M7 — Boot sequence: Phase 1 → Phase 2 orchestration

Implement the two-phase boot sequence. Phase 1 (--phase 1): Request extraction + programmatic facets only, basic L2/L3 clustering. Phase 2 (--phase 2): full criteria-shaped facets, dual-channel routing, enriched clustering. When transitioning from Phase 1 to Phase 2, existing cluster centroids survive unchanged — only facet_stats metadata is added. Request text is the same across phases, so the vector space is stable.

**Notes — see `docs/references/audio2tree-pipeline-design.md` §8 for the full boot sequence spec, state file compatibility rules, and migration guarantee.**

- **Phase 1 delivers value without waiting for the 9003 compiler.** The only dependency is structural transcription (S0, already exists). Phase 1 extracts a single Request per call + programmatic facets (acoustic, turn stats), classifies to L1, and runs basic L2/L3 clustering. This gives Curated an immediately usable intent tree — which calls are about which topics, at what volume.
- **Phase 2 is enrichment, not replacement.** When the 9003 compiler finishes and Items are available, Phase 2 re-processes the same call corpus. It adds criteria-shaped facets (M2) and dual-channel routing (M1) on top of the Phase 1 pipeline. The key guarantee: Request text doesn't change between phases → embedding vectors are identical → Phase 1 centroids survive unchanged. Phase 2 only adds `facet_stats` metadata to existing clusters.
- **The `--phase` flag gates which facet extractors are loaded.** Phase 1 loads only the Request extractor + programmatic extractors. Phase 2 additionally loads model-based criteria-shaped extractors. This is a runtime composition choice, not two separate code paths.
- **Migration is automatic.** The first Phase 2 run on a corpus that has Phase 1 state loads the existing centroids (M5 stability protocol) and enriches them. No manual migration step. No data conversion. The state file format is forward-compatible: Phase 2 state files have a `phase: 2` field and may contain `facet_stats` that Phase 1 files lack.

`Acceptance Test:` `tests/test_boot_sequence.py::test_phase1_produces_clusters` — Phase 1 runs on a corpus with no compiled Items and produces valid L2/L3 clusters. `tests/test_boot_sequence.py::test_phase2_preserves_phase1_centroids` — Phase 2 runs on the same corpus and all Phase 1 intent_ids survive; centroids are within cosine 0.99 of Phase 1 values. `tests/test_boot_sequence.py::test_phase2_adds_facet_stats` — Phase 2 output includes facet_stats that Phase 1 output does not.

### M8 — End-to-end integration: real INTENTS data

Run the full pipeline against real call data from the INTENTS tree. The test exercises the CLI entry point, reads actual .structural.json files, produces manifest.json output, and asserts on externally observable properties: exit code 0, non-empty bottom_up sections written, deviation rate within expected bounds, cluster names non-generic.

**Notes — design patterns to follow during implementation:**

- **This is the adversarial verification gate.** Per `verification-floor.md` Rule 3: "E2E integration test with real data. After all milestones complete, a separate end-to-end test runs against real (not mock, not stub) data from the INTENTS tree." The test uses the call corpus under `INTENTS/<domain>/<case>/<L3>/calls/`. If real calls are not yet available, this milestone is gated — do not invent fixture data that pretends to be real.
- **The test invokes the CLI as a subprocess** (`subprocess.run(["uv", "run", "argus", "audio2tree", "cluster", "--phase", "1"])`) and asserts on the externally observable surface: exit code, stdout (deviation rate reported), and files written to disk (manifest.json files with populated bottom_up sections). Same pattern as `verification-floor.md` canonical example.
- **Phase 1 and Phase 2 are tested separately.** Phase 1 test: run on real calls, assert clusters produced. Phase 2 test: run on same calls, assert facet_stats present AND Phase 1 intent_ids survived. The replay_hash pattern from the Argus pipeline (I5: Replayability) applies here: same input → same output.
- **If real calls are unavailable at M8 execution time, use the fixture path but mark the milestone as `gated`.** The acceptance test file exists and is written, but the test is skipped (`pytest.skip`) until real data lands.

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

### Decision: Phase 2 facet extraction — incremental by default, full reprocess on demand

**Rationale:** `Source: docs/superpowers/specs/2026-07-20-clio-to-audio2tree-decisions-round-2.md §Decision 1` — three options: full re-extraction every run (cost grows with corpus), new calls only (cost bounded but needs tracking), incremental + --reprocess-all flag (selected). Tracks processed calls via `pipeline_state/processed_calls.json`.

### Decision: L2 description collision detection with automated freeze

**Rationale:** `Source: docs/superpowers/specs/2026-07-20-clio-to-audio2tree-decisions-round-2.md §Decision 2` — at embedding time, detect L2 descriptions with pairwise cosine > 0.7. Freeze the newer one's anchor (exclude from matching). Flag for Curated review. Prevents false positives from weak descriptions without blocking the pipeline.

### Decision: Deviation L2 centroids participate in matching like any other centroid

**Rationale:** `Source: docs/superpowers/specs/2026-07-20-clio-to-audio2tree-decisions-round-2.md §Decision 3` — once a deviation L2 exists, its centroid is part of the routing pool. New calls can match to it. request_count grows naturally. This is consistent with the stability protocol: existing centroids always participate. The only distinction from matched L2s is the status field in the manifest.

### Decision: Calibration runs as a git hook on INTENTS commits

**Rationale:** `Source: docs/superpowers/specs/2026-07-20-clio-to-audio2tree-decisions-round-2.md §Decision 4` — calibration is not part of the audio2tree pipeline. A post-commit hook fires when commits touch intent_manifest.json. Most timely option, no manual triggering. The hook must handle double-commit patterns gracefully.

### Decision: DKB/Cookbook/Errors routing via path convention

**Rationale:** `Source: docs/superpowers/specs/2026-07-20-clio-to-audio2tree-decisions-round-2.md §Decision 5` — for a call assigned to an L2, resolve expertise files by checking the L2 directory first, falling back to the L1 directory, resolving the parent/extends/overrides inheritance chain. No new manifest fields needed. Pure function in core/. If no DKB found, knowledge_accuracy returns checkable=false.

## 6. Surprises & Discoveries

*None yet — this section grows during execution. The Verifier records milestone-flip failures here.*

## 7. Awaiting Steering

> **Awaiting Steering: resolved — Q1.** M8 requires real call data in the INTENTS tree. Currently the _demo structure has placeholder calls. The E2E test can use fixture data until real calls are available. Default: M8 ships with fixtures; re-run when real data lands.

> **Awaiting Steering: resolved — Q2.** The model-based facet extractors (M2) require LLM access. The compiler (9003) has a hard "core ✗ model_client" fence. Does this fence apply to audio2tree? Default: audio2tree's model-based extraction lives in `io/`, not `core/` — same quarantine pattern as the 9002 runtime pipeline. The facet extraction prompt is the only place the model touches; the routing, clustering, and stability logic in `core/` remain pure functions.

> **Awaiting Steering: resolved — Q3.** Embedding model: BAAI/bge-m3. Chosen for: Chinese-English multilingual support (critical for mixed-language CS calls), 1024-dimensional embeddings, strong performance on both semantic similarity and retrieval tasks. Resolved 2026-07-19.

## 8. Outcomes & Retrospective

*Written at completion or cancellation.*
