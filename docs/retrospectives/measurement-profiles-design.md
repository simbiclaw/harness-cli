# Measurement Profiles: Shared Data Infrastructure for Argus and audio2tree

**Status:** draft
**Date:** 2026-07-16
**Source:** Patch 1 (D1–D12), Patch 2 (S1–S6), expertise-library.md, ADR-0002 (path-as-ontology), ADR-0004

---

## Architecture

```
call log (transcript + acoustic)
        │
        ▼
┌───────────────────────────┐
│  Measurement Profiles     │  ← 共享数据基础设施
│  _rubric/profiles/        │     INTENTS tree, pinned git SHA
│                           │
│  customer-emotion.yaml    │
│  agent-attitude.yaml      │
│  agent-competence.yaml    │
│  interaction-quality.yaml │
└───────┬───────────────────┘
        │ 同一份 profile 文件，两个消费者
        │
   ┌────┴────┐
   ▼         ▼
┌──────┐  ┌──────────────┐
│ Argus│  │ audio2tree   │
│Top-  │  │Bottom-up     │
│down  │  │Discovery     │
│known │  │unknown       │
│unkn. │  │unknowns      │
└──┬───┘  └──┬───────────┘
   │         │
   │  Item  │ 涌现模式
   │  评分  │
   │         │
   └────┬────┘
        │ 反馈回路
        ▼
  ┌──────────────┐
  │ 词库更新      │ → phrase-keyword/ 新术语
  │ Item 重编译   │ → 9003 compiler 重新运行
  │ 新建 Item     │ → rubric 扩展
  │ 人工复审      │ → coverage_gap 标记通话
  │ 手册更新      │ → Operation Manual
  └──────────────┘
```

## Design Decisions

### D13: Measurement Profiles are the shared data contract

Argus and audio2tree consume the same profile files from the same pinned INTENTS SHA. No per-consumer copies. No drift.

### D14: Profiles are organized by measurement dimension, not by Item

Profile structure follows "what is being measured" (customer emotion, agent attitude, agent competence, interaction quality) — not "which Item needs this." This enables audio2tree to consume profiles without knowing about Items, and enables new Items to be added without restructuring profiles.

### D15: Profiles contain lexicons, acoustic fingerprints, sentence patterns, calculation logic, and gating rules

Each profile is a complete, self-contained measurement unit. It combines lexical patterns, acoustic fingerprints, sentence-structure features, calculation methods, and both known-item mappings and unknown-unknown gating logic.

### D16: Expertise files follow embed-vs-reference rules

| Expertise | Embed or Reference | INTENTS Location |
|:---|:--:|:---|
| #1 Rules & Criteria | N/A — compilation output | `_rubric/rules_criteria/` |
| #2 Acoustic Feature | **Reference** (9 Items share) | `_rubric/acoustic/` |
| #3 Phrase & Keyword — Layer 1 (shared lexicons) | **Reference** (multi-Item) | `_rubric/phrase-keyword/` |
| #3 Phrase & Keyword — Layer 2 (Item-specific vocabulary) | **Embed** in Item YAML | — |
| #4 Product Introduction | **Reference** (marketing scripts are referent data) | `<domain>/<case>/kb.*.yaml` |
| #5 Operation Manual | **Reference** (procedures are referent data) | `<domain>/<case>/kb.*.yaml` |
| #6 Dynamic Knowledge Base | **Reference** | `<domain>/<case>/kb.*.yaml` |
| #7 Best Practice Cookbook | **Reference** (via severity_map) | `<domain>/<case>/cookbook.*.yaml` |
| #8 Error Case Library | **Reference** (via severity_map) | `<domain>/<case>/errors.*.yaml` |
| #9 Audio Transcription | N/A — per-call input artefact | — |

### D17: Profile file structure — the `_rubric/profiles/` directory

```
_rubric/
  profiles/
    customer-emotion.yaml       # anger, anxiety, resignation, confusion
    agent-attitude.yaml          # politeness, warmth, patience, hostility
    agent-competence.yaml        # knowledge, procedural accuracy
    interaction-quality.yaml     # turn-taking, objection handling, confirmation
  acoustic/
    indicators.yaml              # 12 indicators
    emotion-profiles.yaml        # acoustic fingerprints per emotion
    attitude-profiles.yaml       # acoustic fingerprints per attitude type
  phrase-keyword/
    customer-emotion/            # organized by measurement dimension
      escalation-threat.yaml
      deception-perception.yaml
      price-dissatisfaction.yaml
      product-disparagement.yaml
      resignation.yaml
      repeated-frustration.yaml
    agent-attitude/
      politeness.yaml
      dismissive.yaml
      confrontational.yaml
    agent-competence/
      knowledge-gaps.yaml
      procedural-errors.yaml
    interaction-patterns/
      turn-taking.yaml
      objection-handling.yaml
      confirmation.yaml
  rules_criteria/
    <dimension>/item-XX.yaml     # compiled Item YAMLs (Patch 1)
  evidence/
    ...
  gates/
    ...
```

### D18: Profile schema — `customer-emotion.yaml` as canonical example

```yaml
profile: "customer-emotion"
description: "全通话客户情绪测量——独立于 25 项质检规则"
version: "1.0.0"

dimensions:
  anger:
    lexicons:
      - "_rubric/phrase-keyword/customer-emotion/escalation-threat.yaml"
      - "_rubric/phrase-keyword/customer-emotion/deception-perception.yaml"
      - "_rubric/phrase-keyword/customer-emotion/product-disparagement.yaml"
    acoustic_fingerprint:
      profile_ref: "_rubric/acoustic/emotion-profiles.yaml#anger"
    sentence_patterns:
      negation_density_high:
        threshold: 0.08           # 否定词/总词数 > 8%
        indicator: "对抗性语言密度升高"

    calculation:
      method: "weighted_sum"
      formula: "sum(matched_term.intensity × (1.0 if acoustic_confirmed else 0.4)) / count(matched_terms)"

    output:
      per_turn: "anger_score"
      per_call: "anger_profile"

    known_item_mapping:
      - {item: 22, signal: "F1", role: "客户情绪识别——坐席是否回应"}
      - {item: 26, signal: "F2", role: "沟通氛围——客户情绪是否因坐席升级"}

  anxiety:
    lexicons:
      - "_rubric/phrase-keyword/customer-emotion/repeated-frustration.yaml"
    acoustic_fingerprint:
      profile_ref: "_rubric/acoustic/emotion-profiles.yaml#anxiety"
    sentence_patterns:
      question_ratio_high:
        threshold: 0.25           # 疑问句/总句数 > 25%
      topic_jump_frequent:
        threshold: 3              # 相邻话轮主题跳转 > 3 次

    calculation:
      method: "composite"
      formula: "0.4 × lexical_score + 0.3 × acoustic_score + 0.3 × sentence_pattern_score"

    known_item_mapping:
      - {item: 17, signal: "F1", role: "坐席是否有效引导——降低客户焦虑"}
      - {item: 18, signal: "E1", role: "坐席是否调整策略回应客户焦虑"}

  resignation:
    lexicons:
      - "_rubric/phrase-keyword/customer-emotion/resignation.yaml"
    acoustic_fingerprint:
      profile_ref: "_rubric/acoustic/emotion-profiles.yaml#resignation"

    calculation:
      method: "binary"
      formula: "1.0 if any_term_matched AND acoustic_confirmed else 0.0"

    known_item_mapping:
      - {item: 22, signal: "F1", role: "坐席是否识别客户已放弃——无回应 = 严重失败"}

  confusion:
    lexicons:
      - "_rubric/phrase-keyword/customer-emotion/confusion-markers.yaml"
    acoustic_fingerprint:
      profile_ref: "_rubric/acoustic/emotion-profiles.yaml#confusion"

    calculation:
      method: "count"
      formula: "count(matched_terms)"

    known_item_mapping:
      - {item: 16, signal: "F1", role: "客户困惑——坐席是否重新确认理解"}
      - {item: 18, signal: "E1", role: "客户困惑后坐席是否调整策略"}

# ─── audio2tree 专用：unknown-unknown 门控 ───
unknown_unknown_gating:
  - trigger: "anger_score > 0.7 AND matched_term NOT IN any known_item_mapping"
    action: "flag_for_human_review"
    label: "potential_novel_anger_pattern"

  - trigger: "resignation == 1.0 AND call NOT flagged by any Item 22 signal"
    action: "flag_for_human_review"
    label: "resignation_missed_by_item_22"

  - trigger: "anxiety_score > 0.6 AND topic_jump_frequent == true AND call_duration > 600s"
    action: "suggest_new_item"
    label: "high_anxiety_long_call_pattern"

# ─── Item YAML 消费方式 ───
# Item 18 facets:
#   programmatic:
#     - profile_ref: "_rubric/profiles/customer-emotion.yaml"
#       dimensions_used: [anxiety, confusion]
#       for_signals: [F1, E1]
```

## Lexicon Entry Schema (per D13-D15)

Each lexicon file under `_rubric/phrase-keyword/` follows this schema:

```yaml
# _rubric/phrase-keyword/customer-emotion/escalation-threat.yaml
file_type: "lexicon"
dimension: "customer-emotion"
sub_dimension: "escalation-threat"
version: "1.0.0"

entries:
  - term: "投诉"
    intensity: 0.9
    category: "escalation-threat"
    co_occurrence_amplifiers:
      - pattern: "已经.*次"
        intensity_multiplier: 1.3
        example: "已经投诉三次了"
      - pattern: "再.*不"
        intensity_multiplier: 1.2
        example: "再不解决我就去投诉"
    coverage_gap: false

  - term: "曝光"
    intensity: 0.85
    category: "escalation-threat"
    coverage_gap: false

  - term: "315"
    intensity: 0.95
    category: "escalation-threat"
    note: "消费者权益日引用——高严重度升级信号"
    coverage_gap: false
```

## Item YAML Changes

Item YAML drops inline lexicon content and calculation code. Instead:

```yaml
# Item 22 — old (embeds everything)
facets:
  programmatic:
    - facet_name: "negative_emotion_hits"
      calculation: "def detect(call_log): ..."   # 大段代码在 Item YAML 中

# Item 22 — new (references profiles)
measurement_profiles:
  - profile_ref: "_rubric/profiles/customer-emotion.yaml"
    dimensions_used: [anger, resignation]
    for_signals: [F1]
  - profile_ref: "_rubric/profiles/interaction-quality.yaml"
    dimensions_used: [turn-taking]
    for_signals: [F1, F2]

facets:
  programmatic:
    - facet_name: "emotion_detection"
      profile_ref: "_rubric/profiles/customer-emotion.yaml"
      dimensions: [anger, resignation]
    - facet_name: "turn_taking_analysis"
      profile_ref: "_rubric/profiles/interaction-quality.yaml"
      dimensions: [turn-taking]
```

## Feedback Loop Paths

| Trigger | Source | Action | Target |
|:---|:---|:---|:---|
| coverage_gap term hits > threshold across N calls | audio2tree | Add term to existing lexicon file | `_rubric/phrase-keyword/` → bump SHA |
| New emotion pattern not covered by any signal | audio2tree `suggest_new_item` | Human review → new Item in rubric → recompile | 9003 compiler |
| Existing Item consistently misses known pattern | Argus κ drift | Update Item signals → recompile | 9003 compiler |
| New product/service launched | Product Introduction update | Update marketing scripts → recompile Items 20/21 | 9003 compiler |
| Manual procedure change | Operation Manual update | Update interaction-patterns lexicon | `_rubric/phrase-keyword/` → bump SHA |

## Conformance Matrix

| Patch 1/2 Decision | Status |
|:---|:--:|
| D2 (pure data) | ⚠️ Profiles contain calculation logic — not pure data. Acceptable because profiles are versioned rubric, not runtime code. Calculation is a deterministic formula, not arbitrary execution. |
| D4 (self-contained nodes) | ✅ Profile refs are explicit paths. Evaluator loads once, caches. |
| D10 (four-layer structure) | ⚠️ facets layer simplified — calculation moves from Item YAML to profile. Item YAML retains signal-level facet declarations but delegates implementation to profiles. |
| D11 (uniform schema) | ✅ All Items use same profile reference pattern. |
| S1 (companion doc manifest) | ✅ Profile refs are SHA-pinned at compile time. |
| S2 (source validation) | ✅ Profile and lexicon files validated pre-compile. |
| S4 (gate-checkability) | ✅ Calculation in profile is independently testable. |
| S6 (compiler self-audit) | ✅ Lexicon completeness checkable against profile's declared lexicons. |
| ADR-0002 (path-as-ontology) | ✅ All files at predictable paths. |
| ADR-0004 (three category readers) | ✅ RubricReader loads `_rubric/profiles/` and `_rubric/phrase-keyword/`. |

## Lexicon File Reference: Layer 1 (Shared Infrastructure)

### Acoustic: `_rubric/acoustic/`

| File | Content |
|:---|:---|
| `indicators.yaml` | 12 indicators: f0_mean, f0_range, speaking_rate, intensity_mean, intensity_std, articulation_rate, pause_duration, turn_response_gap, jitter_local, shimmer_local, hnr, voice_quality_sustained |
| `emotion-profiles.yaml` | Acoustic fingerprints for anger, anxiety, confusion, resignation/despair, dissatisfaction/complaint |
| `attitude-profiles.yaml` | Acoustic fingerprints for impatience/rush, indifference/coldness, instability/volatility |

### Phrase & Keyword: `_rubric/phrase-keyword/`

**Customer Emotion:**

| File | Approx. Size | Content |
|:---|:--:|:---|
| `customer-emotion/escalation-threat.yaml` | ~15 | 投诉, 曝光, 315, 举报, 消协, 工商, 媒体, 曝光台, 维权, 起诉, 律师函, 信访, 市长热线, 12345, 上级部门 |
| `customer-emotion/deception-perception.yaml` | ~12 | 坑人, 被骗, 骗人, 欺骗, 忽悠, 蒙人, 套路, 虚假宣传, 不实, 误导, 诈骗, 陷阱 |
| `customer-emotion/price-dissatisfaction.yaml` | ~18 | 太贵, 不划算, 乱收费, 收费不合理, 贵了, 不值得, 花冤枉钱, 隐形消费, 附加费, 强制消费, 捆绑, 加价, 涨价, 不值 |
| `customer-emotion/product-disparagement.yaml` | ~15 | 垃圾, 烂, 差劲, 不好用, 难用, 废物, 破玩意, 什么破, 太差了, 质量差, 不能用, 坏的, 有问题, 老出问题 |
| `customer-emotion/resignation.yaml` | ~12 | 无语, 郁闷, 心累, 算了, 不指望, 失望, 放弃, 行吧, 随便, 爱怎样怎样, 不想说了, 没意思 |
| `customer-emotion/repeated-frustration.yaml` | ~10 | 又来了, 第X次, 反复, 每次, 老是, 总是, 一直, 从开始到现在, 已经N次, 没完没了 |
| `customer-emotion/confusion-markers.yaml` | ~8 | 我不太明白, 什么意思, 没听懂, 能再说一遍吗, 不懂, 不理解, 搞不清楚, 到底怎么 |

**Agent Attitude:**

| File | Approx. Size | Content |
|:---|:--:|:---|
| `agent-attitude/politeness.yaml` | 5 | 请, 您好, 谢谢, 感谢, 麻烦您 — plus 您/你 ratio |
| `agent-attitude/dismissive.yaml` | ~40 | 不知道, 不清楚, 等会回复, 再说吧, 超出权限, 系统问题, 无法解决, 我也没办法, 这不是我的问题, 你去找..., 这个不归我管, 你自己看, 上面规定的, 我管不了, 随便你, 都行 |
| `agent-attitude/confrontational.yaml` | ~15 | 你又没问, 我刚刚说了, 你没听清吗, 我不是说了吗, 你自己不会看吗, 你听不懂吗, 跟你说不清楚, 你急什么, 你态度好点 |

**Agent Competence:**

| File | Approx. Size | Content |
|:---|:--:|:---|
| `agent-competence/knowledge-gaps.yaml` | ~12 | 不清楚, 可能, 大概, 好像, 也许, 估计, 应该是, 我不确定, 我查一下, 我问一下, 这个我不太了解, 你需要问其他人 |
| `agent-competence/procedural-errors.yaml` | ~10 | 应该先..., 忘了..., 漏了..., 不好意思我搞错了, 我之前说错了, 需要重新..., 这个步骤跳过了 |

**Interaction Patterns:**

| File | Approx. Size | Content |
|:---|:--:|:---|
| `interaction-patterns/turn-taking.yaml` | 5 | 抢话阈值 (<300ms 话轮间隔), 冷场阈值 (>5000ms), 重叠计数 |
| `interaction-patterns/objection-handling.yaml` | 8 | 否定词+解决方案 配对模式, 直接否定 (无方案), 建设性否定 (有方案) |
| `interaction-patterns/confirmation.yaml` | 5 | 复述客户问题模式, 确认理解用语, 语义相似度阈值 >0.7 |
