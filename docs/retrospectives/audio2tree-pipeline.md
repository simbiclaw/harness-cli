# audio2tree Pipeline — Retrospective

**Date:** 2026-07-17
**Status:** draft
**Source:** Full-pipeline walkthrough of structural-transcription → conversation-distillation → unknown-unknown gating → feedback loop

---

## What audio2tree is

audio2tree is a dual-role system in the three-tier platform architecture:

```
Transformation layer          Semantic layer           Consumer layer
(produces INTENTS/)           (INTENTS/ tree)          (reads INTENTS/)

audio2tree ────────┐                                  audio2tree ─── unknown-unknowns
  (Producer role)   │                                  (Consumer role)
                    ├──→ INTENTS/ ──→ read by ──→
doc2graph ─────────┘                                  Argus ─── known-unknowns
```

**Producer role** (transformation layer): raw support-call audio → structural transcription → atomic claims → intent tree. Populates the INTENTS tree with behavioural truth.

**Consumer role** (discovery layer): reads the SAME measurement profiles as Argus, but instead of scoring calls against known Items, it detects patterns no Item covers — the unknown unknowns.

---

## Pipeline stages

### Stage 0: Audio intake → Structural Transcription

**Owner:** `.claude/skills/structural-transcription/SKILL.md`
**Script:** `scripts/pipeline.py`
**Backend:** soniqo/speech-swift audio-server (HTTP API) + librosa/parselmouth (acoustic features)

```
raw audio (WAV/MP3/FLAC)
  → [ffmpeg] normalize to 16kHz mono/stereo
  → [audio-server /diarize] VAD + speaker diarization (pyannote 3.0)
  → [audio-server /transcribe] ASR per segment (Qwen3-ASR-0.6B, MLX)
  → [librosa + parselmouth] acoustic feature extraction (parallel with ASR)
  → structural transcription JSON
```

**Key design decisions at this stage:**

| Decision | Rationale |
|:---|:---|
| Stereo per-channel skips diarization | When channels are split-recorded (agent=L, customer=R), the channel IS the speaker label. Diarizing a downmix adds speaker confusion risk for zero gain |
| Acoustic features run in parallel with ASR, not after | ASR is I/O-bound (model inference on GPU/Neural Engine); acoustic features are CPU-bound. Running concurrently maximizes throughput |
| Mono path: VAD and diarization merge | pyannote segmentation 3.0 performs frame-level VAD as part of speaker labeling. Calling `/vad` separately is redundant — the `/diarize` endpoint already returns gated segments |
| Output is file, not stdout | Structural transcriptions are megabytes. stdout corruption on long pipelines is a real failure mode |
| Parallel batch scheduling via Bash `&` + `wait`, not subagents | Subagents run in isolated sandboxes without model cache or env vars (HF_HOME). Bash-level parallelism shares the audio-server connection pool and warm model weights |

**Output shape:** Segment-centric JSON with speaker labels, time intervals, ASR text, acoustic features (F0, intensity, speaking rate, jitter, shimmer, HNR, spectral features), turn structure, and between-turn pauses.

---

### Stage 1: Structural Transcription → Atomic Claims

**Owner:** `.claude/agents/conversation-distillation.md`
**Scripts:** `extract_claims.py`, `embed_claims.py`

```
structural transcription JSON
  → [LLM] per-turn claim extraction (four gates)
  → [LLM] de-contextualisation (resolve pronouns/references)
  → [Deterministic] source-citation linking (every claim → segment IDs)
  → atomic claim library (JSONL, append-only)
```

**The four claim gates** (non-negotiable — candidate claims that fail any gate are discarded):

1. **Single proposition** — one logically complete statement per claim. "The customer ordered a U-Key and it has not arrived" is two claims
2. **De-contextualised** — pronouns and underspecified references resolved to specific business entities. Unresolvable references → drop the claim
3. **Not a Q&A pair** — customer question and agent answer are two separate claims, never one merged exchange
4. **Source-cited** — every claim links to `audio_id` + `segment_ids`. No claim ships without a citation

**Key design decisions:**

| Decision | Rationale |
|:---|:---|
| Claim library is append-only JSONL | No in-place edits. Append-only means every distillation run is auditable. Duplicate-looking claims across calls are NOT deduped — frequency of intent carries signal |
| Claims are per-turn, not per-call | A single call can contain 5+ distinct intents. Call-level summarization loses this granularity |
| Extraction can be inline (LLM reasoning) or scripted (API call) | Inline for <5 calls (lower overhead), scripted for batches (avoids context burn). Same schema, same gates, same output path |
| Acoustic features are NOT read by the distiller | The distiller works from text only. Acoustic features are metadata for measurement profiles downstream, not for claim extraction |

---

### Stage 2: Atomic Claims → Intent Tree

**Owner:** Same subagent (conversation-distillation)
**Scripts:** `cluster_incremental.py`, `build_intent_tree.py`, `publish_intent_tree.py`

```
claim library (JSONL)
  → [Deterministic] embedding (sentence-transformers, local)
  → [Deterministic + LLM] incremental cluster assignment (stability protocol)
  → [LLM] cluster naming for new nodes only
  → [Deterministic] tree assembly
  → [Deterministic] IIntentTreeSource publish
```

**The stability protocol** — the most consequential design decision in the pipeline:

The core rule: **existing intent nodes are preserved. New nodes are added; the tree is never re-clustered from scratch.**

Concretely:
- New claims matched against existing leaf centroids (cosine similarity > 0.65) → assigned, centroid updated as running mean
- Below threshold → accumulate in `unassigned_pool.jsonl`
- Pool exceeds discovery threshold (50 claims) → k-means cluster the pool, name new clusters, propose parent assignment
- New clusters fit under existing L1/L2 → add. Don't fit → flag for human review. **L1 categories are never auto-created**
- Cluster merges, splits, deletions are never automatic. `--audit` surfaces candidates; human decides

This means the intent tree is stable across runs. It grows additively or stays the same. This stability is what makes it usable as a calibration target for Argus — if the tree shifted on every run, pinned-epoch evaluation would be meaningless.

**Tree shape:** 2-to-3 level hierarchy. L1 = broad business category, L2 = process stage or policy type, L3 = specific intent (when warranted).

---

### Stage 3: audio2tree as Consumer — Unknown-Unknown Detection

**Owner:** Shared measurement infrastructure (`_rubric/profiles/`)
**Consumer:** audio2tree reads the SAME profile files as Argus from the same pinned INTENTS SHA

```
call log (transcript + acoustic)
  → [Deterministic] compute all profile dimensions
      (customer emotion, agent attitude, agent competence, interaction quality)
  → [Deterministic] match features against known_item_mapping
      → Features WITH coverage → already handled by Argus (known-unknowns)
      → Features WITHOUT coverage → unknown-unknown gating
  → [Rule-based] unknown_unknown_gating rules fire
```

**Gating rule examples** (defined per profile):

```yaml
unknown_unknown_gating:
  - trigger: "anger_score > 0.7 AND matched_term NOT IN any known_item_mapping"
    action: "flag_for_human_review"
    label: "potential_novel_anger_pattern"

  - trigger: "resignation == 1.0 AND call NOT flagged by any Item 22 signal"
    action: "flag_for_human_review"
    label: "resignation_missed_by_item_22"

  - trigger: "anxiety_score > 0.6 AND topic_jump_frequent AND call_duration > 600s"
    action: "suggest_new_item"
    label: "high_anxiety_long_call_pattern"

  - trigger: "term_hit_count(coverage_gap_terms) > 5 across 50 calls"
    action: "suggest_lexicon_update"
    label: "emerging_term_pattern"
```

Gating rules are defined per profile and run deterministically. They are the bridge between bottom-up discovery and the human-gated feedback loop.

---

### Stage 4: Feedback Loop — Asymmetric, Human-Gated

```
audio2tree discovery
  │
  ├─ coverage_gap term hits > threshold
  │    → Add term to existing lexicon → bump INTENTS SHA
  │    → Items referencing that lexicon auto-benefit (no recompile)
  │
  ├─ suggest_new_item
  │    → Human review → New Item in rubric → 9003 compiler re-run
  │
  ├─ suggest_lexicon_update
  │    → New terms added, coverage_gap: false
  │    → Existing Items auto-benefit
  │
  └─ flag_for_human_review
       → Marked calls enter human QA queue
       → Human confirms pattern → triggers Item recompilation
       → or manual update to product/procedure documentation
```

The loop is **asymmetric**: audio2tree can suggest; humans decide. Argus never self-modifies. All changes enter through the transformation layer's build pipeline with human approval gates, committed as new INTENTS epochs (ADR-0003).

---

## What's working well

### 1. The producer/consumer separation is clean

audio2tree produces the INTENTS tree (via transcription + distillation) and separately consumes measurement profiles for discovery. These two roles use different code paths, different INTENTS locations, and different output channels. A transcription bug doesn't break discovery; a gating rule bug doesn't corrupt the intent tree.

### 2. The stability protocol is the load-bearing innovation

Re-clustering on every run would make the intent tree useless as a calibration target. The incremental assignment + human-gated L1 creation protocol ensures the tree is stable enough for Argus to pin epochs against, while still growing as new calls arrive.

### 3. Deterministic/LLM boundary is well-drawn

Each stage explicitly labels which steps are deterministic scripts and which require LLM judgment. Scripts encode the stability protocol (which an LLM cannot reproduce consistently turn-to-turn); LLM handles the genuinely judgment-requiring steps (claim extraction, de-contextualization, cluster naming). The boundary is explicit in the pipeline diagram and enforced by the subagent instructions ("do not reimplement the deterministic parts in your context").

### 4. Shared measurement infrastructure prevents drift

Argus and audio2tree consume the same profile files from the same pinned SHA. One lexicon update benefits both systems simultaneously. The dual-consumer architecture (documented in `measurement-profiles-design.md`) eliminates the "two copies, guaranteed to diverge" problem.

### 5. Parallelism is correctly scoped

Batch audio processing uses Bash-level parallelism (`&` + `wait`) for file-splitting because subagents lack the audio-server environment. Subagents are reserved for qualitatively different work (debugging diarization vs debugging ASR). This is a pragmatic, non-dogmatic use of the available concurrency primitives.

---

## Surprises and gaps

### Surprise 1: audio2tree has no dedicated pipeline integration test

The structural-transcription skill has `check_server.py` (preflight diagnostic) and the conversation-distillation subagent has per-stage scripts that can be run individually. But there is no single end-to-end test that runs: audio file → structural JSON → claims → intent tree → verify the tree grew by the expected number of leaves. Each stage is tested in isolation; the integration between stages is tested only by human inspection.

**Gap:** Without an integration test, a schema change in structural transcription output could silently break conversation distillation. The `schema_version` field provides a detection mechanism but not a prevention mechanism.

### Surprise 2: The intent tree's stability depends on a magic number (0.65 cosine threshold)

The assignment threshold that determines whether a claim matches an existing leaf or goes to the unassigned pool is a single hardcoded value. There is no documented calibration procedure for this threshold. Too low → unrelated claims get merged into the same leaf (loss of precision). Too high → every claim creates a new leaf (loss of stability).

**Gap:** The 0.65 threshold is not empirically validated against the actual claim corpus. The `--audit` command surfaces centroid drift but doesn't surface threshold sensitivity — it won't tell you that changing the threshold to 0.60 would merge two leaves that should be separate, or that 0.70 would split a leaf that should be one.

### Surprise 3: The distiller doesn't use acoustic features, but the gating rules do

The conversation-distillation subagent explicitly states: "Acoustic features in the input are for layers above and below you, not for you." This is a clean separation — but it means the intent tree is built from text alone, while the unknown-unknown gating rules can fire on acoustic patterns (e.g., "anger_score > 0.7"). An intent that manifests primarily through acoustic cues (e.g., a customer who sounds resigned but uses polite language) may be undercounted in the tree.

**Gap:** The intent tree's text-only construction means its leaf frequencies are biased toward lexically-expressed intents. Acoustic-only patterns (customer sounds angry but never says an angry word) are invisible to the distiller but visible to the gating rules. This asymmetry is documented nowhere.

### Surprise 4: The feedback loop has no latency SLA

When audio2tree flags a `coverage_gap` term pattern across 50 calls, the term should be added to the lexicon. But there is no defined latency: how quickly must the human reviewer act? What happens to the 51st call while the review is pending — does it fire the same gap again, or is there a suppression mechanism?

**Gap:** Without a suppression mechanism, the same unknown-unknown pattern generates a new flag for every call that matches it, flooding the review queue. The gating rules need a cooldown: "after flagging pattern X, suppress re-flagging for N hours or until human acknowledgment."

### Surprise 5: No drift detection between Argus κ and audio2tree discovery rate

Argus tracks κ (criterion trust) and signals when it drifts. audio2tree tracks discovery rate (new patterns found per N calls). But there is no cross-system correlation: if Argus κ rises (criteria becoming more trusted) while audio2tree discovery rate stays flat, that's a healthy system. If Argus κ drops while audio2tree discovery rate rises, that's a signal that known Items are losing coverage and new patterns are emerging faster than the rubric can absorb them. This cross-system signal exists in the data but is not computed.

---

## Pipeline complexity assessment

| Stage | Complexity | Why |
|:---|:--:|:---|
| S0: Audio → Structural Transcription | **Medium** | Three external dependencies (ffmpeg, audio-server, Python acoustic libs). Mono/stereo branching adds conditional logic. Parallel ASR+acoustic dispatch requires careful process management |
| S1: Transcription → Claims | **Medium-High** | LLM extraction with four non-negotiable gates. De-contextualization requires cross-segment reasoning. Inline vs scripted extraction is two code paths to keep in sync |
| S2: Claims → Intent Tree | **High** | Stability protocol with five states (assigned, pooled, clustered, named, flagged). Multiple scripts with sequential dependencies. Human-review gates for L1 creation |
| S3: Unknown-Unknown Detection | **Low-Medium** | Deterministic rule evaluation against profile outputs. No LLM. Gating rules are YAML, not code |
| S4: Feedback Loop | **Medium** | Asymmetric (suggest vs decide). Multiple action paths (lexicon update, item recompile, human review). Human-gated with no SLA |

**Total: Medium-High complexity.** The pipeline has 5 stages, 3 external systems, 2 LLM-judgment boundaries, and a human-gated feedback loop. The complexity is in the integration contracts, not in any single stage.

---

## What the pipeline gets right vs what's missing

| Dimension | Status | Notes |
|:---|:--:|:---|
| Deterministic/LLM boundary | ✅ Clean | Every stage labels which steps are scripts vs LLM judgment |
| Stability across runs | ✅ Strong | Incremental clustering protocol; tree never re-clustered |
| Shared infrastructure | ✅ Clean | Single profile copy, two consumers, same SHA |
| Parallelism model | ✅ Pragmatic | Bash-level for file batching; subagents for qualitatively different work |
| Integration testing | ❌ Missing | No end-to-end test across all stages |
| Threshold calibration | ❌ Missing | 0.65 cosine similarity is a magic number |
| Text-only vs acoustic bias | ❌ Undocumented | Intent tree built from text; acoustic-only intents undercounted |
| Feedback loop SLA | ❌ Undefined | No cooldown/suppression for repeated unknown-unknown flags |
| Cross-system correlation | ❌ Not computed | Argus κ vs audio2tree discovery rate not tracked |

---

## Cross-references

- `.claude/skills/structural-transcription/SKILL.md` — S0 implementation
- `.claude/agents/conversation-distillation.md` — S1-S2 implementation
- `docs/retrospectives/measurement-profiles-design.md` — S3 shared infrastructure
- `docs/design-docs/argus/expertise-decision-log.md` — dual-consumer architecture, feedback loop
- `docs/references/platform-architecture.md` — three-tier platform context
- `docs/adr/0003-knowledge-calibration-dissolves-to-write-time-ownership.md` — write-time ownership
- `docs/product-specs/shared/intents-semantic-layer.md` — path-as-ontology grammar
- `INTENTS/EPOCH.yaml` — current epoch state
- `soft-criteria-authoring-spec-v4-patch-2.md` — compiler pipeline GAN architecture (for comparison)

---

## Changelog

| Date | Change | Source |
|------|--------|--------|
| 2026-07-17 | Retrospective created. Full pipeline walkthrough (S0–S4). Five surprises documented: missing integration test, uncalibrated cosine threshold, text-only intent tree bias, undefined feedback loop SLA, missing Argus κ ↔ audio2tree discovery cross-correlation. Complexity assessment and what's-right-vs-missing matrix. | Walkthrough of structural-transcription SKILL.md, conversation-distillation agent, measurement-profiles-design.md, expertise-decision-log.md |
