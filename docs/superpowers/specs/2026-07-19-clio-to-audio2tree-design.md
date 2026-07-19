# Audio2Tree: Harnessing Clio's Three-Stage Pipeline — Product Spec

**Date:** 2026-07-19
**Status:** draft
**Source:** Clio paper (arxiv 2412.13678) + Audio2Tree PRD patch + INTENTS structure adversarial review + cross-referencing with Patch-1/Patch-2 compiler design

---

## 1. Goal

Integrate the three-stage pipeline from Anthropic's Clio paper — **extracting facets → semantic clustering → cluster labeling and hierarchization** — into audio2tree, the bottom-up intent discovery system. Three Clio innovations are adapted: contrastive prompting, neighborhood-based hierarchy building, and prefill output constraint. Two architectural innovations are added that Clio does not have: dual-channel L2 routing and criteria-shaped facets.

---

## 2. Product Context

### 2.1 Where audio2tree fits

```
Transformation layer          Semantic layer           Consumer layer

audio2tree ──────────┐
  (Producer: audio    │
   → intents tree)    ├──→ INTENTS/ ──→ Argus (evaluator)
                      │                 Metis (diagnosis)
doc2graph ───────────┘                 Hermes (automation)
  (Producer: manuals
   → intents tree)

audio2tree ────────────────────────────────────────────→ unknown-unknown discovery
  (Consumer: reads _rubric/profiles/, detects patterns no Item covers)
```

Audio2Tree is both a **producer** (fills the INTENTS tree with bottom-up intent data from call recordings) and a **consumer** (reads measurement profiles to detect unknown-unknown patterns).

### 2.2 How the INTENTS tree is filled

Four sources write into one tree. Each writes different files or different JSON keys — no merge conflicts.

| Source | What it writes | Key artifact |
|:---|:---|:---|
| **doc2graph** | Operation manuals, product introductions | `index.md`, `assets/`, `intent_manifest.json → top_down` |
| **audio2tree** | Call transcriptions, intent clusters, request stats | `calls/*.json`, `intent_manifest.json → bottom_up` |
| **9003 compiler** | Compiled rubric Items, residue manifest | `_rubric/rules_criteria/item-XX.yaml` |
| **Curated (human)** | DKB, cookbooks, error cases, AGENTS.md routing index | `dkb.*.yaml`, `cookbook.*.yaml`, `errors.*.yaml` |

### 2.3 What already exists

- `structural-transcription` skill: audio → .structural.json
- Audio2Tree PRD patch: S1 Request extraction, S2 L1 classification, S3 intra-L1 clustering, S4 manifest population
- `expertise-decision-log.md`: 8 expertise types, embed-vs-reference decisions, dual-consumer architecture
- Patch-1 (D1-D12): operationalized artifact structure, per-item compilation procedure
- Patch-2 (S1-S6): compiler pipeline gaps, gate-checkability audit, self-audit pass

### 2.4 What this spec adds

The Clio paper's three-stage pipeline adapted to audio2tree's product context. Specifically: dual-channel L2 routing (no Clio equivalent), criteria-shaped facets (no Clio equivalent), and Clio's three techniques (contrastive naming, neighborhood hierarchy, prefill constraint) adapted to customer-service call data.

---

## 3. What "Done" Looks Like

### 3.1 Deliverables

| # | Deliverable | Description |
|:--|:---|:---|
| D1 | **Dual-channel L2 routing engine** | For each call Request, cosine-match against existing L2 descriptions. Above threshold → matched channel (L3 clustering under that L2). Below threshold → deviation channel (auto-discover new L2 clusters) |
| D2 | **Criteria-shaped facet extractors** | Programmatic facets (acoustic, turn stats) + model-based facets (LLM-extracted signals). Every facet traces to at least one Item/Signal in the 25-Item QA rubric. Gate-checkable facets tagged as such |
| D3 | **Contrastive cluster naming** | Clusters named by LLM using contrastive prompting: samples from within the cluster + contrastive samples from nearby-but-outside clusters. Names are distinctive, specific, and in Chinese |
| D4 | **Neighborhood-based hierarchy builder** | When an L1 has too many L2 clusters to fit in a single context window, enable Clio's neighborhood-based hierarchy: group into ~40-cluster neighborhoods, propose parents per neighborhood with contrastive edge clusters, deduplicate across neighborhoods |
| D5 | **INTENTS tree population (bottom_up)** | Audio2Tree writes `bottom_up` section of `intent_manifest.json` for L2 and L3 nodes. Does not touch `top_down` (Doc2Graph's section). L3 nodes are always audio2tree-created |
| D6 | **AGENTS.md routing index** | Agent-operable navigation file teaching downstream agents how to find and use the tree (not an exhaustive catalogue). Includes routing protocol for audio2tree Consumer and reading protocol for Argus Evaluator |
| D7 | **Stability protocol** | Incremental runs preserve existing cluster centroids. New data assigned to nearest existing centroid above threshold. New clusters created only when unassigned data accumulates above discovery threshold. Tree grows additively, never re-clustered from scratch |
| D8 | **Boot sequence (Phase 1 → Phase 2)** | Phase 1: basic facets + clustering (no dependency on compiled Items). Phase 2: criteria-shaped facets added (after 9003 compiler completes). Phase 1 centroids survive unchanged into Phase 2 |

### 3.2 Acceptance Criteria

Each deliverable must satisfy these criteria before it is considered complete:

| Deliverable | Acceptance Criteria |
|:--|:---|
| D1 | A call Request is correctly routed to its known L2 manual when cosine similarity ≥ threshold. A call Request with no close L2 match enters the deviation pool rather than being force-assigned. Deviation rate is computed and reported per run |
| D2 | Every extracted facet has a documented trace to at least one Item.Signal in the 25-Item rubric. Gate-checkable facets (lexical, threshold, lookup) are tagged checkable=true. Model-only facets (semantic judgment, NLU-requiring) are tagged checkable=false. The B-F gate-checkability audit from Patch-2 is applied to every model-based facet |
| D3 | Cluster names are distinctive (not "其他咨询" or generic labels). A human reviewer confirms that names capture what the cluster IS and distinguish it from neighboring clusters. Naming quality ≥ human-acceptable for 90% of clusters |
| D4 | When L2 count exceeds the context threshold, hierarchy building succeeds without truncation. Parent cluster names accurately reflect their children. No L2 cluster is orphaned (unassigned to any parent) |
| D5 | `intent_manifest.json` files are valid JSON. `bottom_up` section is present for all L2/L3 nodes populated by audio2tree. `top_down` section is never modified by audio2tree. `source` and `calibration_status` fields are correctly computed by Calibration (0017) |
| D6 | A downstream agent (Argus) can, by reading AGENTS.md and using standard bash tools (find, grep, cat, jq), locate the intent_manifest.json for a given L3 intent and extract the fields needed for evaluation. The file does not enumerate every L2/L3 — it teaches navigation |
| D7 | Running audio2tree twice on the same corpus produces identical cluster assignments (same intent_ids, same centroids). Running on an extended corpus preserves all existing intent_ids. New data is assigned to existing clusters or pools correctly |
| D8 | Phase 1 runs before any Items are compiled and produces valid L2/L3 clusters. Phase 2 runs after Items are compiled and enriches those same clusters with criteria-shaped facet statistics. No Phase 1 clusters are lost or renamed in Phase 2 |

---

## 4. Architectural Constraints

These are non-negotiable. Every implementation decision must preserve them.

### 4.1 Inherited from the platform

| Constraint | Source |
|:---|:---|
| **L1 is pre-defined.** Doc2Graph anchors the top-level business taxonomy. Audio2Tree does not create L1s | Audio2Tree PRD patch, Decision 2 |
| **Single tree, key-level isolation.** Doc2Graph writes `top_down`. Audio2Tree writes `bottom_up`. Neither reads the other's section during write. Calibration (0017) reads both | Audio2Tree PRD patch, Decision 5 |
| **Path-as-ontology.** Directory structure IS the taxonomy. Level is expressed by path, not by a field in the manifest | `intents-semantic-layer.md` |
| **Stable intent_ids.** Once assigned, never changed — even if the Chinese title is renamed. Downstream agents (Argus) pin to specific git SHAs and must be able to resolve historical evaluations | ADR-0002, ADR-0003 |
| **Write through the transformation layer.** No agent writes directly to INTENTS. All writes go through audio2tree, doc2graph, or Curated | ADR-0003 |

### 4.2 New in this spec

| Constraint | Rationale |
|:---|:---|
| **Dual-channel routing.** Calls are never force-assigned to a mismatched L2. Below-threshold calls enter the deviation channel rather than polluting matched-channel clustering | Avoids the Clio "3% boundary misassignment" problem compounding with forced categorization |
| **Criteria-shaped facets.** Facets serve the QA rubric, not general exploration. Every facet has a documented Item.Signal trace | Prevents facet extraction from drifting into general-purpose NLP. Keeps audio2tree's output directly consumable by Argus |
| **No cross-system auto-triggers.** Audio2Tree does not trigger Doc2Graph. Doc2Graph does not trigger 9003. Each system is independently invoked | Prevents cascading side-effects. A deviation L2 discovery does not silently launch a manual-writing pipeline |
| **Feedback loop closes at Curated confirmation.** The audio2tree loop ends when a human confirms or rejects a deviation L2. What happens after (manual writing, Item compilation) is a separate decision with its own cadence | Keeps the audio2tree feedback loop bounded and testable |
| **Stability over novelty.** Existing clusters are preserved across runs. The tree grows additively. Full reclustering is a manual Curated operation, not an automated pipeline step | Required for downstream agents to pin to stable intent_ids. A shifting taxonomy breaks evaluation reproducibility |
| **AGENTS.md teaches navigation, not enumeration.** The file tells agents how to use `find`/`grep`/`cat`/`jq` to explore the tree. It does not list every L2/L3 — those are discovered at runtime | Prevents AGENTS.md from becoming a stale catalogue that must be manually synchronized with the tree | 

---

## 5. Explicit Non-Goals

These are deliberately out of scope. They may be revisited in future specs.

- **Interactive UI for cluster exploration.** Audio2Tree's consumer is downstream AI (Argus, Metis, Hermes), not human analysts. Clio's Map View and Tree View are not adapted
- **Privacy layers.** Clio's 5-layer privacy defense is not needed for internal enterprise call data
- **Temporal trend monitoring.** Clio's time-series facet overlays are not adapted. Audio2Tree builds a stable reference tree; trend analysis belongs to Argus or Metis
- **Fully bottom-up L1 discovery.** L1 is Doc2Graph-anchored. Bottom-up L1 proposals may be added as a future Curated-triggered process, not as an automated pipeline feature
- **Detailed prompt templates, JSON schemas, algorithm pseudocode, exact parameter values.** These are execution details discovered during implementation. The spec defines WHAT must be true of the result, not HOW to achieve it

---

## 6. Open Design Questions

These are acknowledged as unresolved. They must be answered during exec-plan execution, not in this spec:

1. **L2 description quality.** Who ensures L2 descriptions have sufficient contrastive boundary for cosine matching? Is this Doc2Graph's output quality problem, Curated's responsibility, or both?
2. **Deviation queue mechanics.** When audio2tree discovers a deviation L2 with request_count > 100, how is Curated notified? What does the review workflow look like?
3. **Facet extraction model choice.** Small model (cost-optimized) vs strong model (accuracy-optimized) for S1 Request extraction. Does the choice depend on call volume? On language?
4. **Calibration (0017) integration.** How does calibration_status transition from "uncalibrated" to "needs_manual"/"needs_calls"/"calibrated"? Is this a separate pipeline run or a hook on git commit?

---

## Changelog

| Date | Change | Source |
|------|--------|--------|
| 2026-07-19 | v2 rewrite. Spec restricted to WHAT: goal, deliverables, acceptance criteria, architectural constraints, non-goals, open questions. All implementation details (algorithms, schemas, prompts, parameters) removed. | User directive: spec at product-context + high-level technical design level; execution details belong in exec-plan |
| 2026-07-19 | v1 created. Pipeline mapping, criteria-shaped facets, S3 algorithm, output format, AGENTS.md, boot sequence, Clio technique tables. | Clio paper, Audio2Tree PRD patch, Patch-1/Patch-2, expertise-decision-log |
