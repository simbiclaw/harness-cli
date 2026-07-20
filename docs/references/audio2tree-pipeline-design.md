# Audio2Tree Pipeline — Design Reference

**Date:** 2026-07-20
**Audience:** Agents executing 9004 milestones
**Source:** Design sessions; Clio paper (arxiv 2412.13678, Appendices B/C/D/G); Audio2Tree PRD patch

Reference for design patterns the exec-plan milestones should follow. Not a spec — see `docs/superpowers/specs/2026-07-19-clio-to-audio2tree-design.md` for the WHAT. This document captures the HOW patterns discovered during the design process.

---

## 1. Pipeline Architecture: Clio → Audio2Tree Mapping

```
S0: (Clio has no equivalent)
    Audio2Tree: ASR → .structural.json

S1: Clio Extracting Facets → Audio2Tree Request Extraction
    Clio: multi-facet (summary, language, concern score), Haiku temp=0.2, PII omission
    Audio2Tree: single Request (one Chinese sentence), small model temp=0.2, prefill trick

S2: Clio Semantic Clustering → Audio2Tree L1 Classification + Dual-Channel L2 Routing
    Clio: k-means on all summaries, k dynamic, all bottom-up
    Audio2Tree: cosine → pre-defined L1, then dual-channel: cos ≥ T → matched, cos < T → deviation

S3: Clio Labeling + Hierarchization → Audio2Tree Dual-Channel Clustering + Contrastive Naming
    Clio: contrastive naming (50+50), neighborhood hierarchy (iterative level merging)
    Audio2Tree: contrastive naming (5+5), conditional neighborhood (only when L2 > 50), fixed 3-level tree
```

**Key adaptations from Clio:**

| Clio technique | Clio implementation | Audio2Tree adaptation | Why changed |
|:---|:---|:---|:---|
| Contrastive naming | 50 IN + 50 OUT samples | 5 IN + 5 OUT samples | CS intents more convergent than AI chats |
| Neighborhood hierarchy | Always enabled, iterative merging | Conditional (> 50 L2 per L1), no iterative merging | L1 is pre-defined, fixed 3 levels, most domains under threshold |
| Prefill trick | "The user's request is to" | "客户的诉求是" | Same mechanism, different language |
| Temp=1.0 naming | Sonnet temp=1.0 | Strong model temp=1.0 | Direct reuse |
| Model tiering | Haiku extraction, Sonnet naming | Small model S1, strong model S3 | Direct reuse |
| Iterative level merging | Mathematical ratio formula | Not used | L1 pre-defined by Doc2Graph |

**Not adapted from Clio:**

| Clio feature | Why not |
|:---|:---|
| 5-layer privacy defense | Internal enterprise data |
| Interactive UI (Map/Tree View) | Consumer is downstream AI, not humans |
| Fully bottom-up L1 discovery | L1 anchored to Doc2Graph taxonomy |
| Temporal trend monitoring | Audio2Tree builds stable tree; Argus handles per-eval scoring |

---

## 2. Dual-Channel L2 Routing (M1)

### Flow

```
Request embedding (bge-m3)
    │
    ├─ Step 1: L1 Classification
    │   Cosine vs L1 descriptions (from L1 intent_manifest.json)
    │   Assign to best-match L1
    │
    └─ Step 2: L2 Routing (within assigned L1)
        Extract L2 descriptions from manifest.json files under this L1
        Cosine vs all L2.description anchors
        │
        ├─ S_max ≥ T (0.60) → MATCHED CHANNEL
        │   Assign to that L2 → L3 clustering under L2 constraint
        │
        └─ S_max < T → DEVIATION CHANNEL
            Enter deviation pool → auto L2 discovery when pool large enough
```

### Key design decisions

- **Two cosine passes, not one.** L1 classification first, then L2 routing within the assigned L1. This reduces noise — a call about 年报 won't be compared against 法人数字证书 L2 descriptions
- **Force-assignment is forbidden.** Below-threshold calls enter the deviation pool. This is a feature, not a bug — deviation rate measures manual taxonomy coverage
- **Threshold T = 0.60 initial.** Human-calibrated after first batch. Not a fixed constant. Stored in pipeline config
- **L2 anchors from manifest.json, not AGENTS.md.** AGENTS.md teaches how to find them. The extraction script reads at runtime

### Collision detection (Decision 2, 2026-07-20)

After embedding L2 descriptions, compute pairwise cosine distances. If any pair exceeds the collision threshold (0.7), freeze the newer L2's anchor — exclude it from cosine matching. Frozen anchors are surfaced via `argus audio2tree audit --collisions` for Curated review. This prevents false positives from weak descriptions without blocking the pipeline for unrelated L2s.

### Deviation centroids (Decision 3, 2026-07-20)

Deviation L2 centroids participate in routing identically to matched L2 centroids. Once a deviation L2 exists, new calls with cosine ≥ 0.65 are assigned to it. request_count grows naturally. The only distinction: `status: pending_review` and absent `top_down`.

### Deviation rate

```
deviation_rate = |D_deviation| / |D_total|
```

Reported on stdout after every run. A management metric — tells Curated whether the manual taxonomy is keeping up with customer needs.

---

## 3. Criteria-Shaped Facets (M2)

### Design principle

Every facet must trace to at least one Item.Signal in the 25-Item rubric. The question is not "what can we extract" but "what does the rubric need to measure."

### Programmatic facets (deterministic, `core/`)

| Facet | Source in .structural.json | Consumed by Item.Signal |
|:---|:---|:---|
| f0_mean, f0_range, intensity_mean, intensity_std | acoustic measurements | 08, 09, 11, 17, 18 |
| speaking_rate, articulation_rate | word count / duration | 09, 11 |
| jitter_local, shimmer_local, hnr | acoustic measurements | 18 |
| voiced_frames_pct | acoustic measurements | Reliability flag for all acoustic consumers |
| turn_count, segment_word_counts | stats | 01-07 |
| between_turn_pauses, turn_response_gap_sec | turns | 04, 09, 11 |
| call_duration_sec | audio metadata | Routing, triage |
| agent_customer_speech_ratio | segment duration sums | 08, 12 |
| marketing_keyword_hits | phrase-keyword lexicon match | 20, 21 |
| script_jaccard_similarity | phrase-keyword marketing-scripts.yaml | 21 |

### Model-based facets (LLM-extracted, `io/`, quarantined to S2)

| Facet | Item.Signal | Gate-Checkable |
|:---|:---|:--:|
| greeting_present | 01 F1 | ✓ lexical |
| address_term_used | 02 F1 | ✓ lexical |
| confirmation_requested | 03 F1 | ✓ lexical |
| hold_announced + hold_recalled | 04 F1/F2 | ✓ lexical |
| closing_present + followup_offered | 05 F1/F2 | ✓ lexical |
| operation_steps_ordered | 06 F1 | ✗ split: lexical + model |
| system_operation_correct | 07 F1 | ✗ model_only |
| filler_word_density | 08 F1 | ✓ lexical |
| speaking_rate_appropriate | 09 F1 | ✓ threshold |
| patience_indicators | 11 F1/F2 | ✗ split |
| tone_friendliness | 12 F1 | ✗ model_only |
| positive_acknowledgment | 13 F1 | ✓ lexical |
| understanding_confirmed | 10 F1 | ✓ lexical |
| solution_provided | 14 F1/F2 | ✗ split |
| explanation_clarity | 15 F1 | ✗ model_only |
| followup_committed | 16 F1 | ✓ lexical |
| emotion_sync_attempt | 17 F1 | ✗ model_only |
| voice_quality_stable | 18 F1 | ✓ programmatic (acoustic) |
| knowledge_accuracy | 19 F1/F2 | ✗ model_only (DKB-grounded) |
| marketing_trigger_detected | 20 F1/E1 | ✓ lexical+phrase |
| script_compliance | 21 F1/E1 | ✓ lexical (Jaccard) |
| customer_emotion_detected | 22 F1 | ✗ model_only |
| escalation_appropriate | 23 F1/F2 | ✗ split |
| closure_confirmed | 24 F1 | ✓ lexical |
| deescalation_technique_used | 26 F1/F2 | ✗ model_only |

### Quarantine boundary (I1)

Programmatic facets live in `core/` — deterministic, no model. Model-based facets live in `io/` — LLM touch point, quarantined to S2 proposer. Same fence as the 9002 runtime pipeline.

### B-F Gate-Checkability audit (Patch-2)

Each model-based facet must pass the Q1/Q2 test:
- Q1: Can a proposer find a transcript span? (all model-based facets pass Q1 by definition — they're extracted from transcript text)
- Q2: Can a gate deterministically verify that span? → `checkable: true`
- Q2 fails → `split` (lexical sibling + model sibling) or `model_only` (no deterministic gate possible)

**Implementation guidance:** Start with procedural accuracy facets (Items 01-07, mostly lexical, gate-checkable). Semantic facets (knowledge_accuracy, emotion_sync, tone_friendliness) default to checkable=false.

### DKB/Cookbook/Errors routing (Decision 5, 2026-07-20)

For facets that need curated expertise (e.g., `knowledge_accuracy` comparing agent claims against DKB facts), resolve files by path convention:

```
For call assigned to L2 under L1:
  1. Check L2 directory: INTENTS/<L1>/<L2>/dkb.*.yaml
  2. If not found, check L1 directory: INTENTS/<L1>/dkb.*.yaml
  3. If multiple L1 DKB files, match by intent relevance
  4. Resolve parent/extends/overrides per expertise-decision-log §6
  5. If no DKB found at any level → checkable=false for that call
```

Same pattern for cookbook.*.yaml and errors.*.yaml. The resolver is a pure function in `core/` — no model calls.

### Phase 1 vs Phase 2 facet availability

Phase 1: Request only + programmatic facets. Phase 2: adds all model-based criteria-shaped facets. Same Request text across phases → same embedding vectors → Phase 1 centroids survive.

---

## 4. Contrastive Naming (M3)

### Prompt structure

```
你是客服意图分析助手。请根据以下一组客户 Request，生成该聚类的名称和描述。
目标是：用一个精确的名称和描述来刻画这组 Request，使其与对比组区分开来。

<同类 Request>  ← 来自该聚类的 5 条 Request (最接近质心)
{in_cluster_requests}
</同类 Request>

<对比 Request>  ← 来自该 L1 下其他 L2 聚类的 5 条 Request
                 (质心最接近但不在本聚类中)
{contrastive_requests}
</对比 Request>

要求:
1. 用一句中文 (2-8 字) 命名 — 描述"客户想要什么", 而非"客户情绪如何"
2. 用两句话描述核心特征
3. 名称应区分于对比组 — 确保独特、有区分力
4. 这是"{L1_name}"业务线下的"{L2_name}"场景中的细分

输出格式:
<name> [名称] </name>
<description> [两句描述] </description>
```

### Key parameters

| Parameter | Value | Rationale |
|:---|:---|:---|
| In-cluster samples | 5 (closest to centroid) | CS intent convergence; enough to represent the cluster |
| Contrastive samples | 5 (closest neighboring centroid, not in this cluster) | Forces model to name what's DISTINCTIVE |
| Temperature | 1.0 | Naming needs diversity, not determinism |
| Model | Strong model (DeepSeek-V4 or equivalent) | Adapted from Clio's Sonnet-for-naming pattern |
| Validation | Name not in generic set {"其他咨询", "综合问题", "其他", "其他业务"} | Minimum quality bar |

### Contrastive selection algorithm

```
For cluster C with centroid V_c:
  1. Find the nearest other cluster C' (by centroid cosine distance)
  2. Take 5 samples from C closest to V_c → in-cluster samples
  3. Take 5 samples from C' closest to V_c but NOT assigned to C → contrastive samples
```

---

## 5. Manifest Schema (M4)

Four shapes, distinguished by directory path (not by a `level` field).

### L1 Manifest

Location: `INTENTS/<L1>/intent_manifest.json`

```json
{
  "intent_id": "corp-digital-cert",
  "title": "法人数字证书业务",
  "description": "法人数字证书全生命周期服务。区别于年报业务和信用修复。",
  "source": "doc2graph",
  "child_intents": ["certificate-renewal", "certificate-replacement"],
  "last_updated": "2026-07-10T14:30:00Z"
}
```

L1 is a directory node. No `top_down`/`bottom_up`. `description` used for L1 classification (M1 Step 1). `child_intents` is an intent_id list.

### L2 Manifest (Matched Channel)

Location: `INTENTS/<L1>/<L2>/intent_manifest.json`

```json
{
  "intent_id": "certificate-renewal",
  "title": "证书延期",
  "description": "客户数字证书到期或过期，申请延期。区别于补办（丢失/损坏）和解锁（被锁定）。",
  "source": "both",

  "top_down": {
    "manual": "证书延期操作手册.docx",
    "operator_count": 12,
    "goal_states": ["T_cert_renewed"],
    "pipeline_version": "doc2graph-v0.3",
    "processed_at": "2026-07-10T14:30:00Z"
  },

  "bottom_up": {
    "channel": "matched",
    "match_confidence": 0.87,
    "request_count": 342,
    "cluster_centroid": [0.12, -0.34, 0.78],
    "representative_requests": ["客户询问延期流程", "客户咨询续费费用"],
    "clustering_run_id": "run-2026-07-19T09-00-00Z",
    "last_clustered_at": "2026-07-19T09:15:22Z"
  },

  "calibration_status": "calibrated",
  "last_updated_by": "audio_to_tree"
}
```

### L2 Manifest (Deviation Channel)

Location: `INTENTS/<L1>/<L2>/intent_manifest.json`

```json
{
  "intent_id": "ukey-driver-failure",
  "title": "UKey驱动故障",
  "description": "客户UKey插入后无法识别，或驱动重装后仍无效。区别于证书解锁（被锁定而非硬件故障）。",
  "source": "audio2tree",

  "top_down": {},

  "bottom_up": {
    "channel": "deviation",
    "deviation_score": 0.82,
    "best_match_intent_id": "certificate-unlock",
    "best_match_similarity": 0.31,
    "request_count": 127,
    "status": "pending_review",
    "discovered_at": "2026-07-19T09:15:22Z"
  },

  "calibration_status": "needs_manual",
  "calibration_detail": "127通通话。与最近手册'证书解锁'余弦距离0.31。无对应操作手册。",
  "last_updated_by": "audio_to_tree"
}
```

### L3 Manifest

Location: `INTENTS/<L1>/<L2>/<L3>/intent_manifest.json`

```json
{
  "intent_id": "certificate-renewal.fee-inquiry",
  "title": "延期费用咨询",
  "description": "客户询问延期费用标准、VIP优惠资格和支付方式",
  "source": "audio2tree",
  "parent_intent_id": "certificate-renewal",

  "bottom_up": {
    "channel": "matched",
    "match_confidence": 0.91,
    "request_count": 89,
    "cluster_centroid": [0.18, -0.29, 0.81],
    "representative_requests": ["客户询问延期费用", "VIP客户确认优惠"],
    "clustering_run_id": "run-2026-07-19T09-00-00Z",
    "last_clustered_at": "2026-07-19T09:15:22Z"
  },

  "calibration_status": "needs_manual",
  "last_updated_by": "audio_to_tree"
}
```

### Field summary

| Field | L1 | L2 (matched) | L2 (deviation) | L3 |
|:---|:--:|:--:|:--:|:--:|
| `intent_id`, `title`, `description` | ✓ | ✓ | ✓ | ✓ |
| `source` (doc2graph/audio2tree/both) | ✓ | ✓ | ✓ | ✓ |
| `child_intents` | ✓ | — | — | — |
| `parent_intent_id` | — | — | — | ✓ |
| `top_down` | — | ✓ | — | — |
| `bottom_up.channel` (matched/deviation) | — | ✓ | ✓ | ✓ |
| `bottom_up.status` (pending_review) | — | — | ✓ | — |
| `calibration_status` | — | ✓ | ✓ | ✓ |
| `last_updated_by` | ✓ | ✓ | ✓ | ✓ |

### Merge rules

- Manifest exists: read → update only `bottom_up` + `last_updated` + `last_updated_by` → write. Never touch `top_down`
- Manifest doesn't exist (deviation channel): create with `source: "audio2tree"`, `status: "pending_review"`
- L3 manifests are always created by audio2tree

---

## 6. Stability Protocol (M5)

### Core algorithm

```
1. Load state from previous run (pipeline_state/clusters.json)
   - Each cluster: {intent_id, centroid, member_count, l1_id (L2) or parent_l2_id (L3)}

2. For each new Request vector V:
   a. Cosine similarity against all existing L2 centroids
   b. If max_sim ≥ 0.65:
      - Assign to that L2
      - Update centroid: new = (old × n + V) / (n + 1)
      - member_count += 1
   c. Else:
      - Append to unassigned_pool

3. When |unassigned_pool| ≥ discovery_threshold (15):
   - k-means on pool only (never full dataset)
   - Contrastive naming for new L2s → status: pending_review
   - Existing clusters unchanged

4. Persist state after run
```

### Parameters

| Parameter | Value | Source |
|:---|:---|:---|
| Assignment threshold | 0.65 | Clio incremental stability |
| Discovery threshold | 15 | Audio2Tree PRD |
| Min cluster size (L2) | 10 | Audio2Tree PRD |
| Min sub-cluster size (L3) | 20 | Audio2Tree PRD |
| Centroid drift alert | 0.95 | Human audit trigger (never auto-merge) |
| Max centroid drift (auto-update) | 0.10 | Audio2Tree PRD |

### What the protocol does NOT handle

- **L1 changes**: Doc2Graph-anchored. New L1 → fresh start for that L1
- **L2 deletion**: intent_id persists as `status: deprecated`
- **Full reclustering**: not supported. Manual Curated operation
- **Auto-merge**: two centroids at cos > 0.95 → `audit` command flags them, Curated decides

### State file location

`pipeline_state/clusters.json` at the pipeline root. Forward-compatible: Phase 2 state files add `phase: 2` and may include `facet_stats` that Phase 1 files lack.

---

## 7. Neighborhood-Based Hierarchy (M6)

### Trigger

Enabled only when L2 count in an L1 exceeds ~50. Below threshold, direct full-list naming suffices.

### Algorithm (Clio G.7 adapted)

```
1. Embed each L2 cluster's name + description (bge-m3) → vectors

2. K-means group vectors into k neighborhoods
   - k chosen so each neighborhood averages ~40 clusters
   - This keeps each neighborhood within the LLM context window

3. Per-neighborhood: Claude proposes parent cluster names
   - Claude sees BOTH the neighborhood's clusters AND the m=5 nearest clusters OUTSIDE the neighborhood
   - The edge samples prevent boundary effects

4. Claude deduplicates across all neighborhood proposals
   - Merges semantically identical parent names
   - Ensures coverage — no L2 left without a parent candidate

5. Assign each L2 to best-fit parent
   - Cosine similarity between L2 description and parent description

6. Rename parents based on their actual assigned children
   - Regenerate name + description after assignment (not before)
   - This is the Clio "rename after assignment" pattern (G.7)
```

### Key parameters

| Parameter | Value |
|:---|:---|
| Neighborhood size | ~40 clusters |
| Edge contrast samples (m) | 5 |
| LLM temperature (proposal) | 1.0 |
| LLM temperature (dedup) | 1.0 |

---

## 8. Boot Sequence: Phase 1 → Phase 2 (M7)

### Phase 1 (`--phase 1`)

- S0: structural transcription (already available)
- S1: Request extraction (small model, temp=0.2) + programmatic facets (acoustic, turn stats)
- S2: L1 classification (cosine to L1 descriptions)
- S3: Basic L2/L3 clustering (semantic only, no signal-level facets)

Delivers immediate value: call clustering, intent discovery, deviation detection. No dependency on 9003 compiler.

### Phase 2 (`--phase 2`)

- S1: Adds criteria-shaped model-based facets to each Request
- S2: Dual-channel L2 routing (was single-channel in Phase 1)
- S3: Full clustering with criteria-shaped L3 + facet_stats enrichment

### Migration guarantee

Request text is identical across phases → embedding vectors identical → Phase 1 centroids survive unchanged in Phase 2. Phase 2 adds metadata, not structural changes. The `--phase` flag gates which facet extractors are loaded at runtime — same pipeline code, different extractor composition.

### State file compatibility

Phase 1 state: `{clusters: [...], run_id: "..."}`
Phase 2 state: `{phase: 2, clusters: [...], facet_stats: {...}, run_id: "..."}`

Phase 2 reads Phase 1 state, enriches, writes Phase 2 state. Forward-compatible — never backward-migrated.
