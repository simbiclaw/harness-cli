# Harnessing Clio's Three-Stage Pipeline into Audio2Tree — Design Spec

**Date:** 2026-07-19 · updated 2026-07-19
**Status:** draft
**Source:** Clio paper (arxiv 2412.13678) + Audio2Tree PRD patch + adversarial review of INTENTS _demo structure + multi-session cross-referencing with Patch-1/Patch-2 compiler design

---

## 1. Purpose

This document specifies how to harness the three-stage pipeline from Anthropic's Clio paper — **Extracting Facets → Semantic Clustering → Cluster Labeling and Hierarchization** — into audio2tree, the bottom-up intent discovery system. Three Clio techniques are directly adapted: contrastive prompting for cluster naming, neighborhood-based hierarchy building, and prefill output constraint. Two architectural innovations are added: dual-channel L2 routing (matched vs deviation) and criteria-shaped facets driven by QA rubric Items.

---

## 2. Pipeline Architecture

### 2.1 Clio → Audio2Tree Stage Mapping

```
Clio                                Audio2Tree                      Key Adaptation
─────────────────────────────────────────────────────────────────────────────────
S0: (none)                          S0: ASR + Structural            ★ Net-new stage.
                                    Transcription                   Audio input vs text.

S1: Extracting Facets               S1: Request Extraction          ★ Single Request vs
  Multi-facet (summary, lang,         One Chinese sentence per        multi-facet. No PII
  concern score). LLM (Haiku,         call. LLM (small model,         stripping needed.
  temp=0.2). PII omission.            temp=0.2). Prefill trick.

S2: Semantic Clustering             S2: L1 Classification +         ★ L1 pre-defined by
  K-means on all summaries.           L2 Dual-Channel Routing.        Doc2Graph. Dual-channel
  k dynamic, based on dataset         Cosine → pre-defined L1.        routing: matched (cos ≥ T)
  size. All bottom-up.                Deviation: cos < T → auto-L2.   vs deviation (cos < T).

S3: Labeling + Hierarchization      S3: Dual-Channel Clustering     ★ Matched channel:
  Contrastive naming (50 IN +         + Contrastive Naming.           L3 under L2 constraint.
  50 OUT). Neighborhood-based         Matched: L3 within L2.          Deviation channel:
  hierarchy (~40/neighborhood).       Deviation: L2 auto-cluster       L2 auto + L3 sub.
  Iterative level merging.            → L3 sub-cluster.               No iterative merging.
                                      Contrastive: 5 IN + 5 OUT.      Fixed 3-level tree.
```

### 2.2 Full Pipeline Flow

```
Raw audio (WAV/MP3)
    │
    ▼
[S0] speech-swift / call-inspector → .structural.json (segment-centric, speaker-labeled)
    │
    ▼
[S1] LLM (small model, temp=0.2) → single Request (one Chinese sentence)
    │                              + programmatic facets (acoustic, turn stats)
    │
    ▼
[S2] Embed Request → cosine vs L1 descriptions (from manifest.json, discovered via AGENTS.md)
    │
    ├─ L1 classification → assign to best-match L1
    │
    ├─ L2 Dual-Channel Routing (within each L1):
    │   ├─ Matched:  cos(Request, L2.description) ≥ T → assign to existing L2
    │   └─ Deviation: cos(Request, any L2.description) < T → enter deviation pool
    │
    ▼
[S3] Per-L1 clustering:
    │
    ├─ Matched Channel (per L2):
    │   1. Collect Requests assigned to this L2
    │   2. Silhouette-optimal k-means → L3 clusters
    │   3. Contrastive naming (5 IN + 5 OUT samples)
    │   4. Validate: L3 centroid cos(L2.description) ≥ 0.50 (else → deviation pool)
    │   5. Write L3 intent_manifest.json + update L2 manifest bottom_up
    │
    ├─ Deviation Channel (pool across all L2s in this L1):
    │   1. If |pool| < discovery_threshold (15): skip, accumulate
    │   2. Silhouette-optimal k-means → L2 clusters
    │   3. If best_silhouette < 0.25: flag for human review, skip
    │   4. Contrastive naming → status: pending_review
    │   5. For each new L2: recursively run L3 clustering
    │   6. Write new L2 + L3 intent_manifest.json (source: audio2tree)
    │
    └─ Hierarchy Renaming (conditional):
         If L2 count in this L1 > 50:
           Neighborhood-based (Clio G.7 adapted): embed → k-means ~40/neighborhood
           → Claude proposes per-neighborhood (contrast with m=5 nearest outside)
           → cross-neighborhood dedup → assign → rename parents
         Else: direct full-list naming
```

---

## 3. Criteria-Shaped Facets

### 3.1 Design Principle

Clio extracts generic facets for exploration. Audio2Tree extracts facets that feed into QA evaluation. Every facet must trace to at least one Item/Signal in the 25-Item rubric. The question is not "what can be extracted" but "what does the rubric need to measure."

### 3.2 Facet Taxonomy

**Programmatic facets** (deterministic, computed from .structural.json):

| Facet | Source | Consumers (Item.Signal) |
|:---|:---|:---|
| f0_mean, f0_range, intensity_mean, intensity_std | librosa + parselmouth | Items 08, 09, 11, 17, 18 |
| speaking_rate, articulation_rate | word count / duration | Items 09, 11 |
| jitter_local, shimmer_local, hnr | parselmouth | Item 18 |
| voiced_frames_pct | librosa.pyin | All acoustic consumers (reliability flag) |
| turn_count, segment_word_counts | .structural.json stats | Items 01-07 |
| between_turn_pauses, turn_response_gap_sec | .structural.json turns | Items 04, 09, 11 |
| call_duration_sec | .structural.json audio | Routing, triage |
| agent_customer_speech_ratio | segment duration sums | Items 08, 12 |
| marketing_keyword_hits, script_jaccard_similarity | phrase-keyword lexicon match | Items 20, 21 |

**Model-based facets** (LLM-extracted, quarantined to S2 proposer):

| Facet | Traces to Item.Signal | Gate-Checkable? |
|:---|:---|:--:|
| greeting_present | 01 F1 | ✓ lexical |
| address_term_used | 02 F1 | ✓ lexical |
| confirmation_requested | 03 F1 | ✓ lexical |
| hold_announced + hold_recalled | 04 F1/F2 | ✓ lexical |
| closing_present + followup_offered | 05 F1/F2 | ✓ lexical |
| operation_steps_ordered | 06 F1 | ✗ (split) |
| system_operation_correct | 07 F1 | ✗ model_only |
| filler_word_density | 08 F1 | ✓ lexical |
| speaking_rate_appropriate | 09 F1 | ✓ threshold |
| patience_indicators | 11 F1/F2 | ✗ (split) |
| tone_friendliness | 12 F1 | ✗ model_only |
| positive_acknowledgment | 13 F1 | ✓ lexical |
| understanding_confirmed | 10 F1 | ✓ lexical |
| solution_provided | 14 F1/F2 | ✗ (split) |
| explanation_clarity | 15 F1 | ✗ model_only |
| followup_committed | 16 F1 | ✓ lexical |
| emotion_sync_attempt | 17 F1 | ✗ model_only |
| voice_quality_stable | 18 F1 | ✓ programmatic (acoustic) |
| knowledge_accuracy | 19 F1/F2 | ✗ model_only (DKB-grounded) |
| marketing_trigger_detected | 20 F1/E1 | ✓ lexical+phrase |
| script_compliance | 21 F1/E1 | ✓ lexical (Jaccard) |
| customer_emotion_detected | 22 F1 | ✗ model_only |
| escalation_appropriate | 23 F1/F2 | ✗ (split) |
| closure_confirmed | 24 F1 | ✓ lexical |
| deescalation_technique_used | 26 F1/F2 | ✗ model_only |

### 3.3 Alignment with Patch-1 / Patch-2

| Patch Concept | Facet Extraction Implementation |
|:---|:---|
| **I1 (Quarantine)** | Model-based facets extracted in S2 (proposer), quarantined. Programmatic facets computed in S3 (ground), no model uncertainty. |
| **B-F (Gate-Checkability)** | Each model-based facet tagged `checkable: true\|false\|split`. Lexical facets are gate-verifiable. Semantic facets are model-only or auto-split. |
| **I6 (Independence-weighted corroboration)** | Acoustic facet + phrase facet on same signal = independent (different error sources, weight 1.0). Two model-based facets judging same span = redundant (weight 0.0). |
| **D16 (Lexicon ≠ Corroborator)** | Programmatic facets (acoustic indicators, phrase hits) are measurement instruments, not corroborators. |

---

## 4. S3: Contrastive Naming + Hierarchy Building

### 4.1 Contrastive Naming Prompt (adapted from Clio G.5)

**Model:** Strong model (DeepSeek-V4 or equivalent). **Temperature:** 1.0 (naming needs diversity, not determinism).

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

**Adaptation:** Clio uses 50 IN + 50 OUT. Audio2Tree uses 5+5 — customer service intents are more convergent than open-ended AI conversations. The contrastive structure is preserved: the model must identify what is DISTINCTIVE, not just common.

### 4.2 Neighborhood-Based Hierarchy (adapted from Clio G.7)

**Trigger:** Only when an L1 has > 50 L2 clusters.

1. **Embed:** Each L2 name + description → embedding vector
2. **Neighborhood:** K-means into groups of ~40 clusters each
3. **Propose:** Per-neighborhood, Claude proposes parent names (includes nearest m=5 clusters OUTSIDE the neighborhood as contrastive boundary)
4. **Deduplicate:** Claude merges across neighborhoods
5. **Assign:** Each L2 to best-fit parent
6. **Rename:** Regenerate parent names from assigned children

### 4.3 Key Parameters

| Parameter | Value | Source |
|:---|:---|:---|
| Min cluster size (L2) | 10 | Audio2Tree PRD |
| Min sub-cluster size (L3) | 20 | Audio2Tree PRD |
| Discovery threshold (deviation pool) | 15 | Clio |
| Silhouette minimum threshold | 0.25 | Clio |
| Assignment threshold (cosine to existing centroid) | 0.65 | Clio |
| L2 match threshold T | 0.60 (initial, human-calibrated) | Audio2Tree PRD |
| Neighborhood size | ~40 clusters | Clio G.7 |
| Contrastive edge samples (m) | 5 | Clio (reduced for smaller total clusters) |

---

## 5. S3 Output: Writing to intent_manifest.json

### 5.1 Key-Level Isolation

Doc2Graph writes `top_down`. Audio2Tree writes `bottom_up`. Neither reads the other's section during write. Calibration (0017) reads both — its job: compare presence, set `calibration_status`.

### 5.2 Manifest Structure

Each directory node (L1, L2, L3) contains its own `intent_manifest.json`. Level is expressed by directory path, not by a `level` field.

#### L1 Manifest

```json
{
  "intent_id": "corp-digital-cert",
  "title": "法人数字证书业务",
  "description": "法人数字证书全生命周期服务。区别于年报业务和信用修复。客户身份为企业法人代表或经办人。",
  "source": "doc2graph",
  "child_intents": ["certificate-renewal", "certificate-replacement", ...],
  "last_updated": "2026-07-10T14:30:00Z"
}
```

L1 has no `top_down`/`bottom_up` — it's a directory node. `description` is used for audio2tree's L1 classification (cosine match against Request). `child_intents` is `intent_id` list, not paths.

#### L2 Manifest (Matched Channel)

```json
{
  "intent_id": "certificate-renewal",
  "title": "证书延期",
  "description": "客户数字证书到期或过期，申请延期。区别于补办（丢失/损坏）和解锁（被锁定）。涉及费用、VIP优惠、过期恢复。",
  "source": "both",

  "top_down": {
    "manual": "证书延期操作手册.docx",
    "operator_count": 12,
    "goal_states": ["T_cert_renewed", "T_payment_confirmed"],
    "pipeline_version": "doc2graph-v0.3",
    "processed_at": "2026-07-10T14:30:00Z"
  },

  "bottom_up": {
    "channel": "matched",
    "match_confidence": 0.87,
    "request_count": 342,
    "cluster_centroid": [0.12, -0.34, 0.78],
    "representative_requests": ["客户询问延期流程", "客户咨询续费费用", "VIP客户确认优惠"],
    "clustering_run_id": "run-2026-07-19T09-00-00Z",
    "last_clustered_at": "2026-07-19T09:15:22Z"
  },

  "calibration_status": "calibrated",
  "last_updated_by": "audio_to_tree"
}
```

`description` is the semantic anchor — audio2tree embeds it at startup for matching. Must include contrastive boundary: "区别于 X 和 Y." Assigned by Doc2Graph + enhanced by Curated.

#### L2 Manifest (Deviation Channel)

```json
{
  "intent_id": "ukey-driver-failure",
  "title": "UKey驱动故障",
  "description": "客户UKey插入后无法识别，或驱动重装后仍无效。区别于证书解锁（被锁定而非硬件故障）。涉及OS兼容性、驱动版本、设备管理器诊断。",
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

#### L3 Manifest

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
    "representative_requests": ["客户询问延期费用", "VIP客户确认优惠", "客户质疑费用涨价"],
    "clustering_run_id": "run-2026-07-19T09-00-00Z",
    "last_clustered_at": "2026-07-19T09:15:22Z"
  },

  "calibration_status": "needs_manual",
  "last_updated_by": "audio_to_tree"
}
```

L3 has no `top_down` — L3 is always audio2tree-produced. `parent_intent_id` links to parent L2.

#### Field Summary

| Field | L1 | L2 (matched) | L2 (deviation) | L3 |
|:---|:--:|:--:|:--:|:--:|
| `intent_id`, `title`, `description` | ✓ | ✓ | ✓ | ✓ |
| `source` | ✓ | ✓ | ✓ | ✓ |
| `child_intents` | ✓ | — | — | — |
| `parent_intent_id` | — | — | — | ✓ |
| `top_down` | — | ✓ | — | — |
| `bottom_up.channel` | — | matched | deviation | matched |
| `bottom_up.status` | — | — | pending_review | — |
| `calibration_status` | — | ✓ | ✓ | ✓ |
| `last_updated_by` | ✓ | ✓ | ✓ | ✓ |

### 5.3 Feedback Loop

Audio2Tree, Doc2Graph, and 9003 are independent systems. They write different fields into the same INTENTS tree but do not trigger each other. The audio2tree feedback loop closes at Curated confirmation — the L2 exists as a routing tag.

| Output State | Trigger Target | Action |
|:---|:---|:---|
| `channel: deviation, status: pending_review, request_count > 100` | Curated | Confirm L2 as routing tag, or reject as noise, or defer. Confirmation closes the audio2tree loop |
| `channel: deviation, status: pending_review, request_count < 100` | audio2tree | Accumulate until discovery_threshold (15), then cluster |
| `channel: matched, match_confidence < 0.60` | Curated | "Boundary match" — description anchor may need updating |
| `calibration_status: needs_manual` | Curated | Informational. Curated MAY independently commission a manual — not an automatic trigger |
| `calibration_status: needs_calls` | audio2tree | Manual exists but no calls yet |
| `calibration_status: calibrated` | — | Both pipelines populated. Loop complete |

---

## 6. AGENTS.md — Agent Routing Index

### 6.1 Design

AGENTS.md is NOT an exhaustive catalogue. It teaches agents **how to navigate** the tree, not **what is in** it. Every consumer (audio2tree, Argus, Metis, Hermes) can use `find`, `grep`, `cat`, `ls`, `jq` to explore. The file's role is to give them the protocol.

```markdown
# INTENTS — Agent Routing Index

## How to navigate

Path is ontology. Each directory node has an `intent_manifest.json`.
`find INTENTS -name "intent_manifest.json"` finds all.

manifest fields:
  `source`          — doc2graph | audio2tree | both
  `calibration_status` — calibrated | needs_manual | needs_calls | conflict
  `top_down`        — Doc2Graph writes (manual ref, operator count, goal states)
  `bottom_up`       — audio2tree writes (request count, centroid, channel, status)
  `description`     — L1/L2 semantic anchor. Must name contrastive boundary.

## Routing protocol (audio2tree Consumer)

1. Extract call Request (S1)
2. Embed Request
3. Cosine vs all L2.description:
   - L2 descriptions extracted from manifest.json, not repeated here
   - `find INTENTS -path "*/*/intent_manifest.json" -exec jq -r '"\(.intent_id)\t\(.description)"' {} \;`
4. S_max >= 0.60 → matched channel (L3 clustering under this L2)
5. S_max < 0.60  → deviation channel (auto L2 clustering + naming)
6. L2 count > 50 per L1 → enable neighborhood hierarchy

## Reading protocol (Argus Evaluator)

1. From manifest.json, confirm call's L1/L2/L3
2. `cat INTENTS/<L1>/<L2>/<L3>/intent_manifest.json` → top_down + bottom_up
3. `find INTENTS/_rubric/rules_criteria/` → compiled Items
4. manifest.source == "audio2tree": manual-ref signals return deferred
5. manifest exists but no _rubric Item: L2 is routing tag only, not scored

## Writing rules

- Do NOT write directly. All changes through transformation layer (audio2tree, doc2graph)
- Each file owned by exactly one producer (_meta/ownership.yaml)
- Stable intent_id: once assigned, never changed (even if Chinese title is renamed)
```

### 6.2 Semantic Anchor Extraction

Audio2Tree S2 startup:

```bash
# Extract all L2 descriptions as matching anchors
find INTENTS -name "intent_manifest.json" \
  -exec jq -r 'select(.source != null) | "\(.intent_id)\t\(.description)"' {} \;
```

Embed each unique `description` using `BAAI/bge-large-zh-v1.5`. Cache as `{intent_id: vector, description_hash}`. On incremental runs, only re-embed descriptions whose hash changed.

Description quality determines matching accuracy. Descriptions MUST name what the L2 is NOT — the contrastive boundary — not just what it IS. This is Curated's responsibility, not audio2tree's.

---

## 7. Boot Sequence: Phase 1 → Phase 2

### Phase 1 (no compiled Items)

Audio2Tree runs with basic facets:
- S0: structural transcription
- S1: Request extraction + programmatic facets (acoustic, turn stats)
- S2: L1 classification (cosine to L1 descriptions)
- S3: Basic L2/L3 clustering (semantic only, no signal-level facets)

**Value:** Call clustering, basic intent discovery, deviation detection. No dependency on 9003 compiler.

### Phase 2 (Items compiled)

Audio2Tree re-processes the same corpus:
- S1: Full criteria-shaped facets added to each Request
- S2: Dual-channel L2 routing
- S3: Full clustering + L3 detail

### Migration: Why it's simple

Phase 1 and Phase 2 share the same Request text per call. The vector space doesn't change — Phase 2 only **adds** criteria-shaped facets as metadata. Migration steps:

```
Phase 2 startup:
  1. Load Phase 1 cluster state (l2_clusters.json + l3_clusters.json)
  2. For each call:
     a. Re-extract Request (unchanged) + add criteria-shaped facets
     b. Stability protocol: cos vs existing centroids → assign or pool
  3. For each cluster:
     a. Enrich with facet_stats: avg greeting_present rate, resolution rate, etc.
     b. Write to manifest.json bottom_up.l3_clusters[*].facet_stats (optional)
  4. L2/L3 intent_ids, centroids, names unchanged — stability protocol guarantee
```

No data migration, no re-clustering. Phase 1 centroids survive unchanged. The only new output is `facet_stats` — a per-cluster aggregation that Argus can use for coverage analysis.

---

## 8. Stability Protocol

### 8.1 Core Rule

Existing cluster centroids are preserved. New Requests are assigned to nearest existing centroid. New clusters are created only when unassigned data accumulates above threshold.

### 8.2 Incremental Run Algorithm

```
1. Load existing state:
   - l2_clusters.json: {intent_id: {centroid, member_count, l1_id}}
   - l3_clusters.json: {intent_id: {centroid, member_count, parent_l2_id}}

2. For each new Request vector V:
   a. cos(V, all existing L2 centroids) → max_similarity
   b. If max_similarity >= 0.65: assign to that L2
      - centroid = running_mean(old_centroid, V, member_count)
      - member_count += 1
   c. Else: append to unassigned_pool

3. When |unassigned_pool| >= discovery_threshold (15):
   - k-means on pool only (not full dataset)
   - Contrastive naming for new L2s → status: pending_review
   - No existing L2s modified

4. L3: same protocol, per-L2 constraint

5. Audit (manual trigger only):
   - centroid_drift: two L2 centroids at cos > 0.95 → flag for human merge review
   - Merges/splits/deletions NEVER automatic
```

### 8.3 Parameters

| Parameter | Value | Source |
|:---|:---|:---|
| Assignment threshold | 0.65 | Clio |
| Discovery threshold | 15 | Audio2Tree PRD |
| Min cluster size (L2) | 10 | Audio2Tree PRD |
| Min sub-cluster size (L3) | 20 | Audio2Tree PRD |
| Centroid drift alert | 0.95 | Human audit, not auto-merge |
| Max centroid drift (auto-update) | 0.10 | Audio2Tree PRD |

### 8.4 What the protocol does NOT handle

- **L1 changes:** L1s are Doc2Graph-anchored. If a new L1 is added, audio2tree starts fresh for that L1
- **L2 deletion:** Even if Curated rejects a deviation L2, its intent_id persists (status: deprecated) for historical evaluation replay
- **Full reclustering:** Not supported. If the taxonomy needs restructuring, it's a manual Curated operation

---

## 9. Techniques Adapted from Clio (with justification)

| Clio Source | Clio Implementation | Audio2Tree Adaptation | Rationale |
|:---|:---|:---|:---|
| G.5 Contrastive naming | 50 IN + 50 OUT, Sonnet temp=1.0 | 5 IN + 5 OUT, strong model temp=1.0 | CS intents more convergent. Smaller sample still provides contrastive signal |
| G.7 Neighborhood hierarchy | ~40 clusters/neighborhood, iterative merging | Conditional: enabled only when L2 > 50 per L1 | Most CS domains have < 50 L2 intents |
| G.4 Prefill trick | Prefill "The user's request is to" | Prefill "客户的诉求是" | Same mechanism, S1 Request extraction |
| G.5 Temp=1.0 for naming | Sonnet temperature=1.0 | Strong model temperature=1.0 | Direct reuse — naming needs diversity |
| G.3-4 Model tiering | Haiku extraction, Sonnet naming | Small model S1, strong model S3 | Direct reuse |
| G.7 Iterative level merging | n_l/n_{l-1} formula | Not used | L1 pre-defined, fixed 3 levels |
| G.7 Per-level rename | Regenerate parents after assignment | Matched L2: names from Doc2Graph. Deviation L2: renamed after L3 | Preserves Doc2Graph authority |

---

## 10. What Is NOT Adapted from Clio (with justification)

| Clio Feature | Why Not Adapted |
|:---|:---|
| 5-layer privacy defense | Internal enterprise call data |
| Interactive UI (Map/Tree View) | Consumer is downstream AI (Argus, Metis, Hermes), not humans |
| Fully bottom-up L1 discovery | L1 must anchor to Doc2Graph's business taxonomy |
| Temporal trend monitoring | Audio2Tree builds stable reference tree; Argus handles per-eval scoring |
| Privacy auditor (Claude-based) | Not needed (see privacy) |
| Synthetic data evaluation | Audio2Tree evaluates against human-annotated samples |

---

## 11. Areas Not Yet Designed

1. **Deviation queue format:** `_meta/deviation-queue.yaml` schema and Curated review workflow (approve/reject/defer mechanics, notification triggers).
2. **facet_stats schema:** Per-cluster aggregation format written to `bottom_up.l3_clusters[*].facet_stats` after Phase 2 enrichment.
3. **DKB/Cookbook/Errors routing:** How audio2tree Consumer reads these curated files at L1/L2 levels to enrich criteria-shaped facets (especially for knowledge_accuracy, escalation_appropriate).

---

## Changelog

| Date | Change | Source |
|------|--------|--------|
| 2026-07-19 | Design spec created: pipeline mapping, criteria-shaped facets, S3 algorithm, output format, AGENTS.md, boot sequence, Clio technique adaptation table. | Clio paper (full PDF incl. Appendices B/C/D/G), Audio2Tree PRD patch, Patch-1/Patch-2, expertise-decision-log |
| 2026-07-19 | Section 5.4 corrected: removed cross-system auto-triggers. Feedback loop clarified as audio2tree-only — closes at Curated confirmation. | Adversarial review of spec logic |
| 2026-07-19 | Sections 6-8 rewritten/added: AGENTS.md as CLAUDE.md-style protocol (not catalogue), intent_manifest.json full 4-level schema (L1/L2 matched/L2 deviation/L3), stability protocol with incremental run algorithm, Phase 1→2 migration (same vector space, no reclustering). Section 10 (Areas Not Yet Designed) updated. | User design session |
