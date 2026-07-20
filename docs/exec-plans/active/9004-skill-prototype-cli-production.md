# 9004 — Audio2Tree: Skill Prototype → CLI Production

## 1. Purpose

Integrate Clio's three-stage pipeline into audio2tree in two phases. Phase A delivers a working skill prototype within one week — Claude handles semantic reasoning (extraction, naming, review) while Python scripts handle deterministic math (embedding, k-means, cosine). The prototype validates design assumptions at small scale (20-50 calls per batch) before investing in CLI engineering. Phase B takes the validated design into production: deterministic embedding pipeline, stability protocol, neighborhood hierarchy, and end-to-end integration with real INTENTS data.

`Source: docs/superpowers/specs/2026-07-19-clio-to-audio2tree-design.md · docs/superpowers/specs/2026-07-20-clio-to-audio2tree-decisions-round-2.md`

## 2. Big Picture

**Phase A (Skill Prototype):** A `.claude/skills/audio2tree/` skill that orchestrates the pipeline. Claude reads call transcripts, extracts Requests, judges criteria-shaped facets, and names clusters. Python scripts in `scripts/` handle embedding (bge-m3), k-means clustering, cosine matching, and manifest JSON writing. No CLI surface. No persistence between runs. Scale target: 20-50 calls per batch for hypothesis validation.

**Phase B (CLI Production):** An `argus audio2tree cluster` CLI command that runs headless. All semantic steps are replaced with API calls or deterministic logic. Full pipeline state persistence, stability protocol, incremental runs. Scale target: 100k+ calls.

**Deliberately out of scope for Phase A:**
- CLI surface (`argus audio2tree`)
- Pipeline state persistence between runs
- Stability protocol (Phase A reclusters from scratch each run — acceptable for prototypes)
- Neighborhood hierarchy (scale doesn't trigger it at 20-50 calls)
- Criteria-shaped facets (Phase A tests naming and routing patterns; full facet extraction waits for CLI)

**Deliberately out of scope for Phase B:**
- Claude-in-the-loop reasoning (replaced by API calls or deterministic logic)
- Interactive exploration UI

## 3. Milestones — Phase A: Skill Prototype

### M0 — AGENTS.md routing index

Replace v0 placeholder AGENTS.md with agent-operable navigation protocol. Teaches agents HOW to explore the tree, not WHAT is in it.

`Acceptance Test:` `tests/test_agents_md.py::test_agents_md_provides_routing_protocol` — greps for routing/reading protocols, confirms under 50 lines, confirms references to `find`/`jq`/`intent_manifest.json`.

### M1 — Batch Request extraction

A skill that reads `.structural.json` files from an L1 directory, batches call transcripts (20-50 per batch), and uses Claude's reasoning to extract one Request per call. Claude reads customer turns, writes one Chinese sentence capturing the core need.

**Notes:** See `docs/references/audio2tree-pipeline-design.md` §1 for S1 stage mapping. Claude is the extractor — no LLM API call. Skill handles batch sizing so transcripts fit in context. Request output format: `{audio_id, request_text, source_segment_ids}`.

`Acceptance Test:` A test script (`tests/test_skill_request_extraction.py`) that feeds 5 fixture transcripts into the extraction prompt and asserts: each output is one Chinese sentence, 8-80 characters, contains no agent dialogue markers, and maps to the audio_id in the fixture.

### M2 — Basic clustering + contrastive naming

Python scripts in `scripts/cluster.py` embed Requests (bge-m3), run k-means (silhouette-optimal k), and return cluster assignments. Claude names each cluster using the contrastive prompt structure: 5 samples from the cluster + 5 contrastive samples from the nearest neighboring cluster.

**Notes:** See §4 of the reference document for the full contrastive prompt. Claude's temperature=1.0. Names must be distinctive — "其他咨询" is rejected in validation. Scripts handle embedding, k-means, and centroid extraction; Claude handles naming only.

`Acceptance Test:` `tests/test_cluster_naming.py::test_contrastive_prompt_structure` — generated prompt has both in-cluster and contrastive sections. `tests/test_cluster_naming.py::test_name_not_generic` — given certificate renewal Requests, name is specific, not "其他咨询".

### M3 — Dual-channel routing + deviation detection

Python scripts compute cosine similarity between each Request and all L2 descriptions (extracted from `intent_manifest.json` via the AGENTS.md protocol). Claude reviews the match results: judges whether threshold placement is reasonable, inspects deviation-pool Requests to confirm they genuinely don't match, and flags false-positives where a Request was matched to the wrong L2.

**Notes:** See §2 of the reference document for the routing flow. At prototype scale (20-50 calls), there may not be enough data to trigger the deviation threshold. The test uses synthetic low-similarity Requests to exercise the deviation path. Claude's role here is qualitative review — "does this deviation look real" — not quantitative computation.

`Acceptance Test:` `tests/test_routing.py::test_matched_channel` — a call semantically close to an L2 description is matched. `tests/test_routing.py::test_deviation_channel` — a call distant from all L2s enters the deviation pool. `tests/test_routing.py::test_collision_detection_freezes_anchor` — pairwise cosine > 0.7 freezes the newer L2's anchor.

### M4 — Manifest population + end-to-end skill run

Python scripts write `intent_manifest.json → bottom_up` sections for all L2/L3 nodes produced by M2+M3. Claude reviews the output: checks that `top_down` sections are untouched, validates cluster names are non-generic, and confirms `source` and `calibration_status` fields are correct.

**Notes:** See §5 of the reference document for the four manifest shapes. Never modify `top_down`. L3 manifest files are always audio2tree-created. This milestone is the Phase A gate — a single command (`/audio2tree cluster --l1 法人数字证书业务 --batch-size 30`) that runs M1→M4 end-to-end.

`Acceptance Test:` `tests/test_skill_e2e.py::test_skill_produces_manifests` — given a directory of 5-10 `.structural.json` files, the skill produces at least one `intent_manifest.json` with populated `bottom_up` section, non-generic cluster names, and untouched `top_down`. The test is a script that invokes the skill's pipeline and asserts on output files.

## 4. Milestones — Phase B: CLI Production

### M5 — Embedding pipeline + collision detection

Replace script-based embedding with a deterministic CLI module. Embedding model: bge-m3 (resolved Q3). Implement pairwise collision detection at embedding time: cosine > 0.7 between any two L2 descriptions freezes the newer anchor. CLI: `argus audio2tree embed` subcommand.

**Notes:** See §2 and §3 of the reference document. The embedding module lives in `core/` (pure function, no model). Collision detection reports frozen anchors to stdout. Phase A's manual Claude review of L2 anchor quality is replaced by automated detection.

`Acceptance Test:` `tests/test_embed.py::test_bge_m3_embeddings_computed` — given a set of L2 descriptions, produces 1024-d vectors. `tests/test_embed.py::test_collision_freezes_anchor` — pairwise cosine > 0.7 freezes the newer anchor. `tests/test_embed.py::test_hash_based_incremental` — unchanged description reuses cached embedding.

### M6 — Stability protocol (incremental run)

Implement incremental assignment: load existing centroids from state file, assign new Requests to nearest centroid (cos ≥ 0.65), accumulate unmatched in pool, discover new clusters when pool reaches threshold (15). Merges/splits never automatic. CLI: `argus audio2tree audit --drift-threshold` subcommand.

**Notes:** See §6 of the reference document for the full algorithm and parameter table. State file: `pipeline_state/clusters.json`. Forward-compatible: Phase B state files add `phase: 2` field.

`Acceptance Test:` `tests/test_stability.py::test_idempotent_runs` — same corpus twice → identical intent_ids. `tests/test_stability.py::test_incremental_preserves_centroids` — extended corpus → existing intent_ids survive. `tests/test_stability.py::test_no_auto_merge` — close centroids flagged, not merged.

### M7 — Hierarchy builder (conditional neighborhood mode)

Implement Clio G.7 adapted hierarchy. Enabled when L2 count > 50 per L1. Six-step algorithm: embed → neighborhood (~40) → Claude proposes per-neighborhood (m=5 edge contrast) → dedup → assign → rename. Below threshold: direct full-list naming. CLI: `argus audio2tree hierarchy` subcommand.

**Notes:** See §7 of the reference document. This milestone is gated on having enough L2 data to trigger the 50-cluster threshold. At Phase B launch, most L1s will be below threshold — direct naming suffices.

`Acceptance Test:` `tests/test_hierarchy.py::test_neighborhood_triggered` — > 50 L2s → neighborhood mode produces parents without truncation. `tests/test_hierarchy.py::test_direct_naming` — ≤ 50 L2s → direct mode. `tests/test_hierarchy.py::test_no_orphan_l2` — every L2 assigned to a parent.

### M8 — End-to-end integration with real INTENTS data

Full pipeline: `argus audio2tree cluster --phase 2` against real `.structural.json` files. Reads L2 anchors from manifest.json via AGENTS.md protocol. Produces manifest.json output. Asserts on externally observable properties.

**Notes:** See §8 of the reference document for the two-phase boot sequence. Phase 1 (--phase 1) runs basic facets. Phase 2 (--phase 2) adds criteria-shaped facets. Incremental by default; `--reprocess-all` for full re-extraction. This is the adversarial verification gate (verification-floor.md Rule 3).

`Acceptance Test:` `tests/integration/test_audio2tree_e2e.py::test_full_pipeline_real_data` — exit code 0, bottom_up populated, deviation rate on stdout. `tests/integration/test_audio2tree_e2e.py::test_phase2_enrichment` — facet_stats present. Gated on real call data; uses fixture skip until available.

## 5. Progress

- [x] M0: AGENTS.md routing index  (done 2026-07-19)
- [x] M1: Batch Request extraction (skill)  (done 2026-07-20)
- [x] M2: Basic clustering + contrastive naming (skill)  (done 2026-07-20)
- [x] M3: Dual-channel routing + deviation detection (skill)  (done 2026-07-20)
- [x] M4: Manifest population + E2E skill run  (done 2026-07-20)
- [ ] M5: Embedding pipeline + collision detection (CLI)  (created 2026-07-20)
- [ ] M6: Stability protocol (CLI)  (created 2026-07-20)
- [ ] M7: Hierarchy builder (CLI)  (created 2026-07-20)
- [ ] M8: E2E integration with real INTENTS data (CLI)  (created 2026-07-20)

## 6. Decision Log

### Decision: Two-phase execution — skill prototype before CLI investment

**Rationale:** `Source: Structured interview 2026-07-20` — a skill prototype uses Claude's reasoning to replace "write code calling LLM API" for semantic steps (extraction, naming, review). This is faster to build (no CLI surface, no persistence layer) and validates design assumptions at small scale before committing to CLI engineering. Phase A is deliberately scale-limited (20-50 calls/batch) and does not implement stability protocol or neighborhood hierarchy. Phase B replaces Claude-in-the-loop steps with deterministic logic or API calls, and adds production requirements (state persistence, incremental runs, scalability).

### Decision: Phase A uses Claude reasoning; Phase B replaces with deterministic logic

**Rationale:** In Phase A, Claude is the extractor (reads transcript → writes Request), the namer (reads 5+5 samples → names cluster), and the reviewer (judges routing quality, inspects deviations). Python scripts handle only deterministic math (embedding, k-means, cosine, JSON writing). In Phase B, extraction moves to API calls (small model, same as Clio's Haiku pattern), naming stays as API calls (strong model, same as Clio's Sonnet pattern), and review becomes automated checks (collision detection, gate-checkability audit). The prototype's value is discovering which semantic steps are hard enough to need strong models, and which are automatable.

### Decision: All prior design decisions carry forward

**Rationale:** The 7 decisions from `docs/superpowers/specs/2026-07-19-clio-to-audio2tree-design-decision.md` and the 5 decisions from `docs/superpowers/specs/2026-07-20-clio-to-audio2tree-decisions-round-2.md` apply to both phases. Dual-channel routing, criteria-shaped facets, contrastive naming, no auto-triggers, AGENTS.md as navigation protocol, stability protocol, graduated Phase 1→2 complexity, incremental facets with --reprocess-all, collision detection, deviation centroid participation, calibration git hook, and DKB path convention are all inherited.

### Decision: q4 skipped — no further architectural questions at this stage

**Rationale:** `Source: Structured interview 2026-07-20` — four questions resolved (facet extraction strategy, L2 quality, deviation backlog, calibration trigger, DKB routing). Remaining questions are implementation details to be discovered during Phase A execution. `Confidence: high` that Phase A will surface new questions that are better answered with prototype data.

## 7. Surprises & Discoveries

*None yet — this section grows during execution. Phase A is expected to produce the most surprises.*

## 8. Awaiting Steering

> **Awaiting Steering: resolved — Q1 through Q5.** All architectural questions resolved in Round 2 interview. Remaining questions (deviation queue mechanics, facet_stats schema specifics) are implementation details to be discovered during Phase A execution.

## 9. Outcomes & Retrospective

*Written at completion or cancellation.*
