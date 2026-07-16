# Decision Log: Phrase & Keyword Expertise — Organization and Representation

**Date:** 2026-07-16
**Status:** draft
**Scope:** argus/9003 · `_rubric/phrase-keyword/` · `_rubric/acoustic/` · `_rubric/profiles/`

---

## Context

The 9003 compiler transforms human QA rubric items (binary 0/1/NA) into machine-evaluable `_rubric/` nodes. During compilation of Items 18, 20, and 21, it became clear that a large body of shared linguistic and acoustic reference data — negative vocabulary, emotion lexicons, interaction patterns, acoustic fingerprints — is consumed by multiple Items but was being embedded redundantly into each compiled YAML.

This decision log records how `#3 Phrase & Keyword` expertise is organized and represented in the INTENTS tree, how it is consumed by both Argus (top-down, known unknowns) and audio2tree (bottom-up, unknown unknowns), and how the two systems form a feedback loop.

---

## Decision 1: Organize lexicons by measurement dimension, not by Item

**Rationale:** 25 Items consume overlapping subsets of the same vocabulary. Organizing lexicons by "which Item needs this" would create duplicate entries across files (e.g., "投诉" needed by both Item 22 and Item 26 would appear in two lexicons). Organizing by measurement dimension ("what is being measured") creates a single source of truth per concept.

**Measurement dimensions:**

| Dimension | What it measures | Consumer |
|:---|:---|:---|
| `customer-emotion` | 客户在整个通话过程中的情绪状态 | Items 16, 17, 18, 22, 26 · audio2tree |
| `agent-attitude` | 坐席的服务规范性和专业态度 | Items 10, 11, 14, 22, 23, 26 · audio2tree |
| `agent-competence` | 坐席的业务知识和流程准确性 | Items 18, 19, 24, 25 · audio2tree |
| `interaction-patterns` | 坐席-客户交互模式（话轮、异议、确认） | Items 12, 13, 14, 17 · audio2tree |

**Consequence:** Each lexicon file is owned by one measurement dimension. A single term (e.g., "投诉") appears in exactly one file (`escalation-threat.yaml`). Items reference the file path; audio2tree can discover all dimensions without knowing about Items.

---

## Decision 2: Each lexicon entry carries usage metadata — not just the term

**Rationale:** A flat word list enables keyword matching but provides no guidance on *how* a match should be interpreted. A term like "无语" (resignation, intensity 0.4) has very different implications from "投诉" (escalation threat, intensity 0.9). Without metadata, the evaluator treats all matches equally.

**Schema per entry:**

```yaml
entries:
  - term: "<word or phrase>"
    intensity: <0.0-1.0>              # 信号强度
    category: "<sub-dimension>"        # 子类别
    acoustic_corroboration:            # 声学协同验证
      required: [<indicator>, ...]     #   必须确认的声学信号
      weight_without: <0.0-1.0>       #   无协同时的置信度
    co_occurrence_amplifiers:          # 同行词强化
      - pattern: "<regex>"
        intensity_multiplier: <float>
        example: "<natural language>"
    coverage_gap: <true|false>         # 不被任何已知 Item 覆盖 → audio2tree 种子
```

**Consequence:** The evaluator can compute `matched_term.intensity × (1.0 if acoustic_confirmed else weight_without)` per hit — a weighted signal rather than a binary match. audio2tree uses `coverage_gap: true` entries as seeds for unknown-unknown discovery.

---

## Decision 3: Customer emotion = F(acoustic, text) is a composite measurement spanning three data sources

**Rationale:** Customer emotion cannot be reliably detected from text alone (a customer saying "好的" with rising f0 and high intensity is angry, not agreeable) or from acoustics alone (high f0 could be excitement, not anger). The formula combines:

### 3a. Lexical layer (`_rubric/phrase-keyword/customer-emotion/`)

Seven lexicon files organized by emotion sub-type:

**escalation-threat.yaml** — 升级威胁 (~15 terms)

| Term | Intensity | Acoustic corroboration | Co-occurrence amplifier |
|:---|:--:|:---|:---|
| 投诉 | 0.9 | f0_mean_rising + intensity_mean_rising | `已经.*次` ×1.3 ("已经投诉三次了") |
| 曝光 | 0.85 | f0_mean_rising | — |
| 315 | 0.95 | — (lexical alone sufficient) | — |
| 举报 | 0.85 | f0_mean_rising | — |
| 消协 | 0.9 | — | — |
| 工商 | 0.8 | — | — |
| 媒体 | 0.75 | — | — |
| 曝光台 | 0.85 | — | — |
| 维权 | 0.8 | — | — |
| 起诉 | 0.9 | f0_mean_rising | — |
| 律师函 | 0.95 | — | — |
| 信访 | 0.85 | — | — |
| 市长热线 | 0.9 | — | — |
| 12345 | 0.9 | — | — |
| 上级部门 | 0.75 | — | — |

**deception-perception.yaml** — 被欺骗感 (~12 terms)

| Term | Intensity | Acoustic corroboration |
|:---|:--:|:---|
| 坑人 | 0.9 | — (lexical alone sufficient) |
| 被骗 | 0.9 | — |
| 骗人 | 0.85 | — |
| 欺骗 | 0.85 | — |
| 忽悠 | 0.75 | — |
| 蒙人 | 0.7 | — |
| 套路 | 0.7 | — |
| 虚假宣传 | 0.85 | f0_mean_rising |
| 不实 | 0.6 | — |
| 误导 | 0.7 | — |
| 诈骗 | 0.95 | — |
| 陷阱 | 0.75 | — |

**price-dissatisfaction.yaml** — 价格不满 (~18 terms)

| Term | Intensity | Acoustic corroboration |
|:---|:--:|:---|
| 太贵 | 0.6 | f0_mean_rising |
| 不划算 | 0.55 | — |
| 乱收费 | 0.85 | f0_mean_rising + intensity_mean_rising |
| 收费不合理 | 0.75 | — |
| 贵了 | 0.5 | — |
| 不值得 | 0.55 | — |
| 花冤枉钱 | 0.7 | — |
| 隐形消费 | 0.75 | — |
| 附加费 | 0.7 | — |
| 强制消费 | 0.85 | — |
| 捆绑 | 0.65 | — |
| 加价 | 0.6 | — |
| 涨价 | 0.55 | — |
| 不值 | 0.5 | — |

**product-disparagement.yaml** — 产品贬损 (~15 terms)

| Term | Intensity | Acoustic corroboration |
|:---|:--:|:---|
| 垃圾 | 0.75 | intensity_std_high |
| 烂 | 0.65 | intensity_std_high |
| 差劲 | 0.6 | — |
| 不好用 | 0.5 | — |
| 难用 | 0.5 | — |
| 废物 | 0.7 | — |
| 破玩意 | 0.7 | intensity_std_high |
| 什么破 | 0.7 | — |
| 太差了 | 0.65 | — |
| 质量差 | 0.6 | — |
| 不能用 | 0.7 | — |
| 坏的 | 0.55 | — |
| 有问题 | 0.4 | — |
| 老出问题 | 0.6 | — |

**resignation.yaml** — 疲惫放弃 (~12 terms)

| Term | Intensity | Acoustic corroboration |
|:---|:--:|:---|
| 无语 | 0.4 | f0_mean_low + speaking_rate_low |
| 郁闷 | 0.5 | f0_mean_low |
| 心累 | 0.55 | f0_mean_low |
| 算了 | 0.35 | voice_quality_sustained_low |
| 不指望 | 0.5 | f0_mean_low |
| 失望 | 0.6 | voice_quality_sustained_low |
| 放弃 | 0.55 | — |
| 行吧 | 0.25 | — |
| 随便 | 0.3 | — |
| 爱怎样怎样 | 0.5 | f0_mean_rising (frustration variant) |
| 不想说了 | 0.5 | f0_mean_low |
| 没意思 | 0.4 | — |

**repeated-frustration.yaml** — 重复挫折 (~10 terms)

| Term | Intensity | Acoustic corroboration | Co-occurrence amplifier |
|:---|:--:|:---|:---|
| 又来了 | 0.6 | f0_mean_rising | `已经.*次` ×1.5 |
| 第X次 | 0.7 | f0_mean_rising | — |
| 反复 | 0.5 | — | — |
| 每次 | 0.45 | — | — |
| 老是 | 0.5 | — | — |
| 总是 | 0.45 | — | — |
| 一直 | 0.35 | — | — |
| 从开始到现在 | 0.55 | — | — |
| 已经N次 | 0.7 | — | — |
| 没完没了 | 0.6 | f0_mean_rising | — |

**confusion-markers.yaml** — 困惑标记 (~8 terms)

| Term | Intensity | Acoustic corroboration |
|:---|:--:|:---|
| 我不太明白 | 0.4 | pause_duration_high + speaking_rate_low |
| 什么意思 | 0.45 | pause_duration_high |
| 没听懂 | 0.5 | pause_duration_high |
| 能再说一遍吗 | 0.45 | — |
| 不懂 | 0.4 | — |
| 不理解 | 0.35 | — |
| 搞不清楚 | 0.5 | — |
| 到底怎么 | 0.45 | pause_duration_high |

### 3b. Acoustic layer (`_rubric/acoustic/emotion-profiles.yaml`)

Five emotion fingerprints, each a combination of acoustic indicators:

| Emotion | Required indicators | Thresholds |
|:---|:---|:---|
| **Anger** (愤怒) | f0_mean, intensity_mean, speaking_rate | f0_mean > baseline+30%, intensity_mean > baseline+15dB, speaking_rate > baseline+20% |
| | Optional: jitter, shimmer | jitter > 2.0%, shimmer > 0.5dB |
| **Anxiety** (焦虑) | speaking_rate, pause_duration, f0_range | speaking_rate > baseline+25%, pause_duration < 300ms, f0_range > baseline+40% |
| | Optional: hnr, jitter | hnr < 15dB, jitter > 1.8% |
| **Confusion** (困惑) | pause_duration, speaking_rate, turn_response_gap | pause_duration > 800ms, speaking_rate < baseline-15%, turn_response_gap > 1500ms |
| **Resignation** (沮丧) | f0_mean, intensity_mean, speaking_rate | f0_mean < baseline-20%, intensity_mean < baseline-10dB, speaking_rate < baseline-20% |
| | Optional: f0_range, voice_quality_sustained | f0_range < baseline-30%, voice_quality_sustained < 0.6 |
| **Dissatisfaction** (不满/抱怨) | intensity_std, f0_range | intensity_std > 15dB, f0_range > baseline+35% |

### 3c. Sentence-structure layer (within each profile dimension)

| Feature | Formula | Indicates |
|:---|:---|:---|
| 疑问句占比 | count(?) / total_sentences | High (>25%) → customer disoriented/distrustful |
| 否定词密度 | count(不/没/别/无) / total_words | High (>8%) + f0 rising → confrontational |
| 感叹词频率 | count(！/啊/呀/天哪) per turn | High → anxiety/excitement |
| 话题跳转次数 | adjacent-turn topic discontinuity count | High (>3) → confused/impatient |
| 重复提问 | same question asked in non-adjacent turns | >1 → agent failed to resolve |

### 3d. Composite formula

```
emotion_score(dimension, call_log) =
    0.5 × lexical_weighted_sum(matched_terms × intensity × acoustic_confirm)
  + 0.3 × acoustic_fingerprint_match(emotion_profile, call_log.acoustic)
  + 0.2 × sentence_pattern_score(patterns, call_log.transcript)
```

Where `acoustic_confirm` = 1.0 if all `required` indicators exceed thresholds, else `weight_without` (typically 0.4).

---

## Decision 4: Agent attitude = F(script content, interaction mode, acoustics)

Agent attitude is assessed across three complementary data sources:

### 4a. Script content (`_rubric/phrase-keyword/agent-attitude/`)

**politeness.yaml** (~5 entries)

| Pattern | Method |
|:---|:---|
| "请" + "您好" + "谢谢" 三件套覆盖率 | count_three_set / total_agent_turns |
| 您/你 ratio | count(您) / (count(您) + count(你)) — < 0.8 → Item 10 fail |

**dismissive.yaml** — 推诿/敷衍 (~40 terms)

| Category | Terms |
|:---|:---|
| 知识推诿 | 不知道, 不清楚, 我不确定, 可能, 大概, 好像, 也许, 估计, 应该是 |
| 时间推诿 | 等会回复, 再说吧, 稍后联系, 回头再说, 等通知 |
| 权限推诿 | 超出权限, 系统问题, 无法解决, 我也没办法, 这个不归我管, 上面规定的, 我管不了 |
| 转移推诿 | 你去找..., 这个要问..., 不是我们负责的, 你自己看, 你自己查 |
| 消极应答 | 都行, 随便你, 无所谓, 都可以 |

**confrontational.yaml** — 对抗性表达 (~15 terms)

| Terms | Acoustic corroboration |
|:---|:---|
| 你又没问, 我刚刚说了, 你没听清吗, 我不是说了吗 | intensity_mean_high (aggressive tone) |
| 你自己不会看吗, 你听不懂吗, 跟你说不清楚 | f0_mean_high + intensity_std_high |
| 你急什么, 你态度好点, 你这是为难我 | f0_range_wide |

### 4b. Interaction patterns (`_rubric/phrase-keyword/interaction-patterns/`)

**turn-taking.yaml**

| Pattern | Threshold | Applies to |
|:---|:---|:---|
| 抢话 (interruption) | turn_response_gap < 300ms with overlapping speech | Item 12 |
| 冷场 (dead air) | turn_response_gap > 5000ms | Item 13, 17 |
| 单方主导 | agent_turn_count / customer_turn_count > 3.0 or < 0.3 | Item 17 |

**objection-handling.yaml**

| Pattern | Gate check |
|:---|:---|
| 直接否定 (no solution) | negative_word present AND no following solution phrase within 2 turns |
| 建设性否定 (with solution) | negative_word + "不过/但是/您可以" within same turn |
| 否定覆盖率 | count(constructive_negation) / count(all_negation) — < 0.5 → Item 14 fail |

**confirmation.yaml**

| Pattern | Gate check |
|:---|:---|
| 复述确认 | semantic_similarity(agent_turn, customer_previous_turn) > 0.7 |
| 确认用语 | "您的意思是..." / "我确认一下..." / "您说的是..." |

### 4c. Agent acoustic fingerprints (`_rubric/acoustic/attitude-profiles.yaml`)

| Attitude | Required indicators | Thresholds |
|:---|:---|:---|
| **Impatience** (急躁) | speaking_rate, turn_response_gap | speaking_rate > 220 wpm, turn_response_gap < 500ms |
| **Indifference** (冷漠) | voice_quality_sustained, f0_range | voice_quality_sustained < 0.5, f0_range < baseline-40% |
| **Volatility** (情绪不稳) | intensity_std, f0_range | intensity_std > 15dB, f0_range change > ±30% within adjacent turns |

---

## Decision 5: Argus and audio2tree are dual consumers of the same infrastructure

### Argus (Top-down — known unknowns)

Argus evaluates calls against the 25 compiled rubric Items. Each Item YAML references measurement profiles for the dimensions it needs:

```yaml
# Item 22 (情绪处理) YAML
measurement_profiles:
  - profile_ref: "_rubric/profiles/customer-emotion.yaml"
    dimensions_used: [anger, resignation]
    for_signals: [F1]
```

Evaluator loads profiles once at startup via RubricReader. Signals check whether profile dimension scores cross thresholds (e.g., "anger_score > 0.7 AND agent did not acknowledge → F1 activated"). Known Items cover known failure patterns.

Argus misses patterns that:
- Have terms not in any lexicon's `known_item_mapping`
- Involve combinations of signals not covered by any Item
- Emerge from new product lines or policy changes not yet encoded

### audio2tree (Bottom-up — unknown unknowns)

audio2tree loads all profiles under `_rubric/profiles/` and `_rubric/phrase-keyword/`. For each call, it:

1. Computes all profile dimensions — producing emotion timelines, attitude labels, competence scores, interaction quality metrics
2. Matches computed features against `known_item_mapping` across all profiles
3. Identifies features **without** coverage:
   - Terms with `coverage_gap: true` in lexicons
   - Dimension scores crossing thresholds but not matching any `known_item_mapping`
   - Lexical-acoustic co-occurrence patterns not described by any signal
4. Applies `unknown_unknown_gating` rules from each profile

Example gating rules:

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

### Feedback Loop

```
audio2tree discovery ──────────────────────────────────────────────┐
  │                                                                 │
  ├─ coverage_gap term hits > threshold                            │
  │    → add term to lexicon, bump INTENTS SHA                     │
  │    → Items referencing the updated lexicon auto-benefit        │
  │                                                                 │
  ├─ suggest_new_item                                              │
  │    → human review → new Item in rubric → 9003 compiler re-run  │
  │    → new Item YAML references existing profiles                │
  │                                                                 │
  ├─ suggest_lexicon_update                                        │
  │    → new terms added, coverage_gap: false                      │
  │    → existing Items referencing the lexicon get richer signal  │
  │                                                                 │
  └─ flag_for_human_review                                         │
       → marked calls enter human QA queue                         │
       → human confirms pattern → can trigger Item recompilation   │
       → or manual update                                          │
```

The loop is **asymmetric**: audio2tree can suggest; humans decide. Argus never self-modifies. All changes enter through the transformation layer's build pipeline with human approval gates, committed as new INTENTS epochs (ADR-0003).

---

## Decision 6: Embed-vs-reference rule for Phrase & Keyword content

| Layer | Content | Shared by | Strategy | Rationale |
|:---|:---|:--:|:--:|:---|
| **Layer 1** | Customer emotion lexicons (7 files, ~90 terms) | Items 16, 17, 18, 22, 26 + audio2tree | **Reference** | Multi-Item shared; medium update frequency (new terms discovered) |
| **Layer 1** | Agent attitude lexicons (3 files, ~60 terms) | Items 10, 11, 14, 22, 23, 26 + audio2tree | **Reference** | Multi-Item shared |
| **Layer 1** | Agent competence lexicons (2 files, ~22 terms) | Items 18, 19, 24, 25 + audio2tree | **Reference** | Multi-Item shared |
| **Layer 1** | Interaction patterns (3 files, ~18 patterns) | Items 12, 13, 14, 17 + audio2tree | **Reference** | Multi-Item shared |
| **Layer 1** | Acoustic indicators + fingerprints (3 files) | Items 8, 9, 11, 12, 13, 17, 18, 22, 26 + audio2tree | **Reference** | 9 Items share; update frequency low |
| **Layer 2** | Item-specific trigger keywords (T01-T11, benefit indicators, dismissive_set) | Single Item each | **Embed** in Item YAML | Single consumer; embedding avoids indirection |
| **Layer 2** | Item-specific vocabulary (起接语"您好", 结束语"再见", resource_keywords) | Single Item each | **Embed** in Item YAML | Single consumer |
| **Layer 2 — Reference corpus** | 16 marketing scripts (full text, 话术 S2-S18) | Items 20, 21 | **Reference** to `_rubric/phrase-keyword/marketing-scripts.yaml` | #3 Phrase & Keyword — 话术全文是 Item 21 的 Jaccard 比较基准。排除非营销话术（话术 1/7/8/13/14）。作为独立文件引用，话术变更无需重编译 Item YAML |

Layer 1 files live at predictable paths under `_rubric/phrase-keyword/` and `_rubric/acoustic/`. Item YAML references them by path. The evaluator's RubricReader loads referenced files once, caches them, and all Items share the cached data.

Layer 2 content lives inline in each Item's YAML file. No separate file, no path reference, no caching — the evaluator reads it directly from the Item node.

---

## Cross-references

- **Patch 1** (D1-D12): operationalized artifact structure, Signal Decomposition (B-E)
- **Patch 2** (S1-S6): compiler pipeline gaps — source validation, dependency ordering, gate-checkability audit
- **ADR-0002**: INTENTS path-as-ontology — file paths encode semantic roles
- **ADR-0004**: Expertise Library dissolution — nine modules collapse to three category readers; RubricReader loads `_rubric/`
- **expertise-library.md**: epistemic classification of all nine modules
- **measurement-profiles-design.md**: profile schema and consumer contract for Argus + audio2tree
- **营销触发-reconciled.yaml**: reconciled trigger keyword source for Items 20/21 (11 triggers, 16 scripts)
