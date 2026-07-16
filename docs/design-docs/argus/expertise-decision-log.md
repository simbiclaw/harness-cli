# Expertise Decision Log — Unified Record

**Date:** 2026-07-16
**Status:** draft — decisions #1-#5 recorded; #6-#9 pending
**Scope:** 9003 compiler · INTENTS tree · Argus + audio2tree dual-consumer architecture

---

## Background

The 9 expertise modules (expertise-library.md, ADR-0004) are organized into three epistemic classes. The 9003 compiler produces `_rubric/rules_criteria/` (expertise #1) and must correctly reference or embed content from expertise #2-#4 and #7-#8. This document records one decision per expertise: embed in compiled Item YAML, or reference as a standalone file in the INTENTS tree.

### Judgment criteria

| Criterion | Embed if | Reference if |
|:---|:---|:---|
| Update frequency | low — recompile on change is acceptable | medium/high — must update without recompile |
| Sharing scope | single Item consumer | multiple Items or audio2tree consumer |
| Content nature | "how to score" (rule logic) | "what to score against" (referent data) |

---

## Architecture: Dual-Consumer Measurement Infrastructure

The expertise data is consumed by TWO systems, not one. This is the load-bearing architectural decision that determines why "reference" dominates the embed-vs-reference analysis.

```
call log (transcript + acoustic)
        │
        ▼
┌───────────────────────────┐
│  Measurement Profiles     │  ← _rubric/profiles/
│  + Phrase & Keyword       │     _rubric/phrase-keyword/
│  + Acoustic Feature       │     _rubric/acoustic/
│                           │     INTENTS tree, pinned git SHA
│  Same data, two consumers │
└───────┬───────────────────┘
        │
   ┌────┴────┐
   ▼         ▼
┌──────┐  ┌──────────────┐
│ Argus│  │ audio2tree   │
│      │  │              │
│Top-  │  │Bottom-up     │
│down  │  │Discovery     │
│      │  │              │
│已知  │  │未知          │
│问题  │  │问题          │
│known │  │unknown       │
│unkn. │  │unknowns      │
└──┬───┘  └──┬───────────┘
   │         │
   │ 25 Item │ 涌现模式:
   │ 评分    │  - coverage_gap 词条高频命中
   │         │  - 未被任何 signal 覆盖的情绪/态度维度
   │         │  - 新词法-声学协同模式
   │         │
   └────┬────┘
        │ 反馈回路 (asymmetric — audio2tree suggests, humans decide)
        ▼
  ┌──────────────────────────────────────────────┐
  │ 词库更新      → _rubric/phrase-keyword/ 新术语│
  │ Item 重编译   → 9003 compiler 重新运行        │
  │ 新建 Item     → rubric 扩展                   │
  │ 人工复审      → coverage_gap 标记通话进入QA队列│
  │ 手册更新      → #5 Operation Manual           │
  └──────────────────────────────────────────────┘
```

### Argus — Top-down, known unknowns

Argus evaluates calls against the 25 compiled rubric Items. Each Item YAML references measurement profiles and lexicons. Evaluator loads profiles once at startup, caches, and all Items consume the same cached data.

Argus detects patterns that match known Items: "Item 22 F1 fired — agent failed to acknowledge customer anger." These are **known unknowns** — failure modes the rubric was explicitly designed to catch.

Argus misses patterns that:
- Have terms not in any lexicon's known coverage (coverage_gap: true)
- Combine signals across dimensions in ways no Item covers
- Emerge from new product lines, policy changes, or evolving customer behavior

### audio2tree — Bottom-up, unknown unknowns

audio2tree loads the SAME profiles and lexicons from the SAME pinned INTENTS SHA. For each call, it:

1. Computes all profile dimensions — emotion timelines, attitude labels, competence scores, interaction quality metrics
2. Matches features against known_item_mapping across all profiles — features WITH coverage → already handled by Argus
3. Identifies features WITHOUT coverage:
   - Terms with `coverage_gap: true` in lexicons
   - Emotion/attitude dimension scores crossing thresholds but not matching any known_item_mapping
   - Lexical-acoustic co-occurrence patterns not described by any Item signal
4. Runs unknown_unknown_gating rules

Example gating rules (defined per profile):

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

### Feedback Loop — Asymmetric, human-gated

```
audio2tree discovery ──────────────────────────────────────────────┐
  │                                                                 │
  ├─ coverage_gap term hits > threshold                            │
  │    → Add term to lexicon, bump INTENTS SHA                     │
  │    → Items referencing that lexicon auto-benefit (no recompile)│
  │                                                                 │
  ├─ suggest_new_item                                              │
  │    → Human review → New Item in rubric → 9003 compiler re-run  │
  │    → New Item YAML references existing profiles                │
  │                                                                 │
  ├─ suggest_lexicon_update                                        │
  │    → New terms added, coverage_gap: false                      │
  │    → Existing Items auto-benefit                               │
  │                                                                 │
  └─ flag_for_human_review                                         │
       → Marked calls enter human QA queue                         │
       → Human confirms pattern → triggers Item recompilation      │
       → or manual update to product/procedure documentation       │
```

The loop is **asymmetric**: audio2tree can suggest; humans decide. Argus never self-modifies. All changes enter through the transformation layer's build pipeline with human approval gates, committed as new INTENTS epochs (ADR-0003).

### Why this architecture forces "reference" for shared expertise

If lexicons were embedded in Item YAML, audio2tree would need to extract them from 25 Item files to build its own copy — two copies of the same lexicon, guaranteed to diverge. With the reference strategy, one file at a predictable INTENTS path is consumed by both systems from the same pinned SHA. No copies. No drift.

This is why the embed-vs-reference judgment criterion weights "sharing scope" and "content nature" heavily: "reference" is the default for any expertise consumed by both systems.

---

---

## #1 Rules & Criteria — N/A (compiler output)

**Epistemic class:** Versioned rubric
**INTENTS location:** `_rubric/rules_criteria/<dimension>/item-XX.yaml`

This IS the compiler's output. It is not embedded or referenced — it is produced.

---

## #2 Acoustic Feature — REFERENCE

**Epistemic class:** Versioned rubric
**INTENTS location:** `_rubric/acoustic/`
**Decision date:** 2026-07-15

### What it is

12 acoustic indicators (f0_mean, f0_range, speaking_rate, intensity_mean, intensity_std, articulation_rate, pause_duration, turn_response_gap, jitter_local, shimmer_local, hnr, voice_quality_sustained) plus emotion/attitude fingerprint profiles. These are the **measurement yardstick** — per-call acoustic measurements are facts; the indicator framework that interprets them is rubric.

### Analysis

| Criterion | Assessment | Direction |
|:---|:---|:--:|
| Update frequency | low (model version changes) | Embed OK |
| Sharing scope | 9 Items (8, 9, 11, 12, 13, 17, 18, 22, 26) + audio2tree | **Reference** |
| Content nature | "what to score against" — measurement yardstick | **Reference** |

### Decision

**Reference.** Indicators and fingerprint profiles live as standalone files:

```
_rubric/acoustic/
  indicators.yaml          # 12 indicators: thresholds, units, descriptions
  emotion-profiles.yaml    # anger, anxiety, confusion, resignation fingerprints
  attitude-profiles.yaml   # impatience, indifference, volatility fingerprints
```

Item YAML references by path:
```yaml
acoustic_framework_ref: "_rubric/acoustic/indicators.yaml"
emotion_profile_ref: "_rubric/acoustic/emotion-profiles.yaml#anger"
```

Evaluator's RubricReader loads once, caches, all Items share.

---

## #3 Phrase & Keyword — TWO-LAYER: REFERENCE (Layer 1) + EMBED (Layer 2)

**Epistemic class:** Versioned rubric
**INTENTS location:** `_rubric/phrase-keyword/` (Layer 1) or inline in Item YAML (Layer 2)
**Decision date:** 2026-07-15 (Layer 1/2 split) · 2026-07-16 (marketing scripts correctly classified)

### What it is

Three kinds of lexical/linguistic reference data:

**Layer 1 — Shared lexicons (REFERENCE).** Multi-Item shared vocabulary organized by measurement dimension:

```
_rubric/phrase-keyword/
  customer-emotion/                    # ~90 terms across 7 files
    escalation-threat.yaml             #   投诉, 曝光, 315, 举报, 消协...
    deception-perception.yaml          #   坑人, 被骗, 忽悠, 套路...
    price-dissatisfaction.yaml         #   太贵, 不划算, 乱收费...
    product-disparagement.yaml         #   垃圾, 烂, 差劲, 不好用...
    resignation.yaml                   #   无语, 郁闷, 算了, 失望...
    repeated-frustration.yaml          #   又来了, 第X次, 反复, 每次...
    confusion-markers.yaml             #   我不太明白, 什么意思, 没听懂...
  agent-attitude/                      # ~60 terms across 3 files
    politeness.yaml                    #   请, 您好, 谢谢, 您/你 ratio
    dismissive.yaml                    #   不知道, 等会回复, 不归我管...
    confrontational.yaml               #   你又没问, 我不是说了吗...
  agent-competence/                    # ~22 terms across 2 files
    knowledge-gaps.yaml                #   不清楚, 可能, 大概, 好像...
    procedural-errors.yaml             #   应该先..., 忘了..., 搞错了...
  interaction-patterns/                # ~18 patterns across 3 files
    turn-taking.yaml                   #   抢话/冷场 thresholds
    objection-handling.yaml            #   否定词+解决方案 配对
    confirmation.yaml                  #   复述确认, 语义相似度 >0.7
```

Each entry carries usage metadata: `intensity`, `acoustic_corroboration`, `co_occurrence_amplifiers`, `coverage_gap`.

| Criterion | Assessment | Direction |
|:---|:---|:--:|
| Update frequency | medium (new terms discovered, policy changes) | Reference |
| Sharing scope | Multiple Items + audio2tree | **Reference** |
| Content nature | "what to score against" — referent data | **Reference** |

**Decision:** Reference. Evaluator loads lexicon files via RubricReader, caches, all Items share.

**Layer 2 — Item-specific vocabulary (EMBED).** Vocabulary used by exactly one Item:

| Vocabulary | Item | Why embed |
|:---|:--:|:---|
| 起接语 "您好" | 1 | Single consumer |
| 称谓语 "先生/小姐/女士/老师" | 2 | Single consumer |
| 候线语 "请稍等/您稍等" + 召回语 | 4 | Single consumer |
| 结束语 "再见" + "还有其他问题" | 5 | Single consumer |
| 口语标记 "的话/那个/的哦" | 8 | Single consumer |
| 资源关键词 "客服系统/业务手册/帮您查" | 18 | Single consumer |
| T01-T11 trigger_keywords (10 triggers × ~5 keywords) | 20 | Single consumer |
| benefit indicators (因为/所以/方便/优势) | 21 | Single consumer |
| dismissive_set (好的那算了/随便你/行吧) | 21 | Single consumer |
| 隐私 regex pattern | 27 | Single consumer |

| Criterion | Assessment | Direction |
|:---|:---|:--:|
| Update frequency | medium (product line changes affect trigger keywords) | Reference preferred |
| Sharing scope | Single Item | **Embed OK** |
| Content nature | "how to score" — used directly by signal triggers | **Embed** |

**Decision:** Embed. Embedded directly in Item YAML. No separate file, no caching overhead. Update requires Item recompilation — acceptable because when item-specific vocabulary changes, the Item's signals likely need review anyway.

**Layer 2 — Reference corpus (REFERENCE).** Full-text marketing scripts used as a comparison baseline:

| Content | Consumer | Why reference |
|:---|:--:|:---|
| 16 marketing scripts (话术 S2-S18, full text) | Item 21 (Jaccard baseline) | Changes with product line, not rubric; recompile on every script edit is unnecessary overhead |

| Criterion | Assessment | Direction |
|:---|:---|:--:|
| Update frequency | medium (product line changes) | Reference |
| Sharing scope | Items 20, 21 (Item 20 uses trigger→script mapping) | Reference |
| Content nature | "what to score against" — referent data | **Reference** |

**Decision:** Reference. Stored as `_rubric/phrase-keyword/marketing-scripts.yaml`. Excluded scripts: S1, S13, S14 (agent identity intros), S7 non-marketing portion (work hours announcement), S8 (platform registration — separate trigger T08).

### Combined embed-vs-reference for #3

```
_rubric/phrase-keyword/
  customer-emotion/          ← Layer 1: REFERENCE (7 files)
  agent-attitude/            ← Layer 1: REFERENCE (3 files)
  agent-competence/          ← Layer 1: REFERENCE (2 files)
  interaction-patterns/      ← Layer 1: REFERENCE (3 files)
  marketing-scripts.yaml     ← Layer 2: REFERENCE (corpus)
Item YAML inline             ← Layer 2: EMBED (item-specific vocabulary)
```

---

## #4 Product Introduction — REFERENCE

**Epistemic class:** Descriptive facts
**INTENTS location:** `<L1>/产品知识/<L3>/index.md`
**Decision date:** 2026-07-16

### What it is

Authoritative product knowledge: what products exist, their features, pricing, applicable scenarios. Evaluators consult this to verify agent claims. Examples from CA hotline domain: 子证书功能与场景, 移动证书优势, 印章定制费用, VIP服务 tiers and pricing.

### Analysis

| Criterion | Assessment | Direction |
|:---|:---|:--:|
| Update frequency | medium (new products, pricing changes) | Reference |
| Sharing scope | Items 19, 20, 21, 25 + audio2tree + human agents | **Reference** |
| Content nature | "what to score against" — referent knowledge | **Reference** |

### Decision

**Reference.** Produced by doc2graph from raw product documentation. Stored in INTENTS tree per Context-Engineering §5. Item YAML declares the INTENTS path; evaluator loads at runtime via INTENTS Provider at pinned SHA.

```yaml
# Item 19 (业务知识) YAML
reference_sources:
  product_intro:
    intents_path: "数字证书客服热线/产品知识/"
    pinned_sha: "<git SHA at compile time>"
```

Compiler does NOT read Product Introduction during compilation. It only records the INTENTS path reference in Item YAML.

---

## #5 Operation Manual — REFERENCE

**Epistemic class:** Descriptive facts
**INTENTS location:** `<L1>/操作规范/<L3>/index.md`
**Decision date:** 2026-07-16

### What it is

Standard operating procedures: how business processes should be executed. Evaluators consult this to verify procedural compliance. Examples: 证书续期流程, 投诉升级处理规范, 远程协助操作规范.

### Analysis

| Criterion | Assessment | Direction |
|:---|:---|:--:|
| Update frequency | medium (policy/system changes) | Reference |
| Sharing scope | Items 3, 4, 6★, 7★, 17, 25 + audio2tree + human agents | **Reference** |
| Content nature | "what to score against" — referent knowledge | **Reference** |

### Decision

**Reference.** Produced by doc2graph. Item YAML declares INTENTS path. Compiler does NOT read content — evaluator loads at runtime.

```yaml
# Item 4 (候线规范) YAML
reference_sources:
  operation_manual:
    intents_path: "数字证书客服热线/操作规范/"
    pinned_sha: "<git SHA at compile time>"
```

---

## #6 Dynamic Knowledge Base — PENDING

**Epistemic class:** Descriptive facts
**INTENTS location:** `<L1>/<L2>/<L3>/index.md` (per Context-Engineering)

### Pending questions

1. What is the scope of DKB content for the CA hotline domain? (FAQ entries, policy updates, known issues?)
2. Does DKB content change frequently enough to require runtime loading vs. compile-time embedding?
3. Which Items consume DKB content?

---

## #7 Best Practice Cookbook — PENDING

**Epistemic class:** Accumulated history
**INTENTS location:** `<domain>/<case>/cookbook.<slug>.yaml`

### Pending questions

1. Is the cookbook consumed exclusively via severity_map references (indirect — no compiler action needed)?
2. Or do Items directly reference cookbook entries for signal calibration?

---

## #8 Error Case Library — PENDING

**Epistemic class:** Accumulated history
**INTENTS location:** `<domain>/<case>/errors.<slug>.yaml`

### Pending questions

1. Same as #7: indirect (via severity_map) or direct reference?
2. Does the Calibration Manifest (independent channel per spec §0.5) draw from Error Case Library?

---

## #9 Audio Transcription — N/A (per-call artefact)

**Epistemic class:** N/A — not in the INTENTS tree
**Location:** Per-call input, produced by audio2tree transformation layer

Not subject to embed-vs-reference. It is the raw input to evaluation, not referent data.

---

## Summary

| # | Expertise | Strategy | INTENTS Location |
|:--|:---|:--:|:---|
| 1 | Rules & Criteria | N/A (output) | `_rubric/rules_criteria/` |
| 2 | Acoustic Feature | **Reference** | `_rubric/acoustic/` |
| 3 | Phrase & Keyword — Layer 1 | **Reference** | `_rubric/phrase-keyword/` |
| 3 | Phrase & Keyword — Layer 2 embed | **Embed** | Item YAML inline |
| 3 | Phrase & Keyword — Layer 2 corpus | **Reference** | `_rubric/phrase-keyword/marketing-scripts.yaml` |
| 4 | Product Introduction | **Reference** | `<L1>/产品知识/<L3>/index.md` |
| 5 | Operation Manual | **Reference** | `<L1>/操作规范/<L3>/index.md` |
| 6 | Dynamic Knowledge Base | PENDING | — |
| 7 | Best Practice Cookbook | PENDING | — |
| 8 | Error Case Library | PENDING | — |
| 9 | Audio Transcription | N/A | — |

---

## Cross-references

- **expertise-library.md**: epistemic classification, consumer matrix
- **ADR-0001**: epistemic classes (versioned rubric, descriptive facts, accumulated history)
- **ADR-0002**: INTENTS path-as-ontology, bottom-up authority
- **ADR-0004**: expertise library dissolution, three category readers
- **Context-Engineering.md §5**: Operation Manual folder structure (L1→L2→L3 with index.md)
- **soft-criteria-authoring-spec-v4-patch-1.md**: D1-D12 (operationalized artifact structure)
- **soft-criteria-authoring-spec-v4-patch-2.md**: S1-S6 (compiler pipeline gaps)
- **measurement-profiles-design.md**: D13-D18 (shared data infrastructure)
- **营销触发-reconciled.yaml**: unified trigger keyword source (11 triggers, 16 marketing scripts)
