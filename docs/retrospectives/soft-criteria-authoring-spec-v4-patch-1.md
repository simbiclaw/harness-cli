# Patch 1 — Evidence Sources, Rubric Structure, and the Item→Node Mapping

**Patches:** `soft-criteria-authoring-spec-v4.html`
**Date:** 2026-07-10
**Status:** accepted
**Source:** 9003 compiler implementation discussion (human↔Claude Code, adversarial review cycle)

---

## 1. Acoustic Feature and Phrase & Keyword are NOT independent rules_criteria

### Original framing (§0.5, §2, §3)

The spec lists three compiler inputs and treats acoustic/phrase as targets:

> A2-ac: author the 12 acoustic indicators into `_rubric/acoustic/`
> A2-ph: author the phrase lexicon into `_rubric/phrase/`

This placement alongside `rules_criteria/` implied they were sibling rule categories — independent criteria the evaluator hunts with.

### Corrected framing

Acoustic Feature and Phrase & Keyword belong to the **Versioned rubric** epistemic class (ADR-0001), but they are **measurement instruments, not rules**. They provide thresholds, baselines, and objective quantitative data to the 25 rules_criteria items — enabling qualitative judgments from structural evidence. They are **evidence sources**, consumed by triggers and corroborators, never evaluated as standalone criteria.

Specifically:

1. **Acoustic Feature** — 12 indicators (f0_mean, f0_range, speaking_rate, intensity_mean, intensity_std, articulation_rate, pause_duration, turn_response_gap, jitter_local, shimmer_local, hnr, voice_quality_sustained). Used to capture agent tone, warmth, and politeness during customer interaction. Beyond the ASR text stream, these 12 acoustic features provide the most direct and effective method for emotion recognition. Primarily serves the Empathy & Tone dimension (6/8 items), secondarily Procedural Accuracy (2/7 items).

2. **Phrase & Keyword** — 4 lexicon groups (recommended, sensitive, negative, filler) plus marketing triggers/scripts. Used to assess agent politeness, emotional state, and service attitude through keyword matching; also enhances customer emotion detection through keyword identification. Serves all four dimensions, with highest concentration in Empathy & Tone and Proactive Value.

**ADR-0001's reclassification is correct but imprecise:** Moving Acoustic/Phrase from "descriptive facts" to "versioned rubric" addressed the epistemic classification, but not the hierarchical relationship with rules_criteria. This patch adds that hierarchy: rules_criteria references evidence sources; evidence sources are not independent rules.

---

## 2. Per-item audit: which items need Acoustic / Phrase evidence

### Summary

| | Acoustic needed | Phrase needed | Both | Neither |
|---|---|---|---|---|
| **Procedural Accuracy** (7) | 2 | 4 | 1 | 2 |
| **Empathy & Tone** (8) | 6 | 6 | 4 | 0 |
| **Problem Resolution** (8) | 1 | 1 | 0 | 6 |
| **Proactive Value** (2) | 0 | 2 | 0 | 0 |
| **Total** (25) | **9** | **13** | **6** | **8** |

### Per-dimension evidence concentration

| Dimension | Acoustic conc. | Phrase conc. | Notes |
|-----------|:------:|:------:|------|
| **Empathy & Tone** | 6/8 (75%) | 6/8 (75%) | Emotion/attitude/atmosphere judgment depends heavily on acoustic signals and keyword detection |
| **Procedural Accuracy** | 2/7 (29%) | 4/7 (57%) | Phrase for script compliance (greeting/title/closing/hold phrases); Acoustic only for speed and hold-time thresholds |
| **Problem Resolution** | 1/8 (12%) | 1/8 (12%) | Almost independent — relies on KB lookup and semantic inference |
| **Proactive Value** | 0/2 | 2/2 (100%) | No acoustic dependency; entirely on marketing trigger keywords and script matching |

### Full per-item detail

See Appendix A at the end of this document.

---

## 3. _rubric/ directory structure

### Before (current compiler output)

```
_rubric/
├── acoustic/indicators.yaml          ← WRONG: sibling to rules_criteria, treated as independent rules
├── phrase-keyword/lexicon.yaml       ← WRONG: same issue
├── procedural_accuracy/              ← CORRECT: per-item nodes
├── empathy_and_tone/
├── problem_resolution/
└── proactive_value/
```

### After (recommended)

```
_rubric/
│
├── rules_criteria/                      # 25 items → 25 nodes (主体 — the actual rubric)
│   ├── procedural_accuracy/             # 7 nodes
│   ├── empathy_and_tone/                # 8 nodes
│   ├── problem_resolution/              # 8 nodes
│   └── proactive_value/                 # 2 nodes
│
├── evidence/                            # 从属 — measurement instruments, NOT rules
│   ├── acoustic/
│   │   └── indicators.yaml              # 12 indicators (f0_mean…voice_quality_sustained)
│   └── phrase-keyword/                  # NOTE: deviates from Patch 1 recommendation (phrase/)
│       ├── customer-emotion/            # ~90 terms across 7 files
│       │   ├── escalation-threat.yaml   # 投诉, 曝光, 315, 举报, 消协...
│       │   ├── deception-perception.yaml# 坑人, 被骗, 忽悠, 套路...
│       │   ├── price-dissatisfaction.yaml# 太贵, 不划算, 乱收费...
│       │   ├── product-disparagement.yaml# 垃圾, 烂, 差劲, 不好用...
│       │   ├── resignation.yaml         # 无语, 郁闷, 算了, 失望...
│       │   ├── repeated-frustration.yaml# 又来了, 第X次, 反复, 每次...
│       │   └── confusion-markers.yaml   # 我不太明白, 什么意思, 没听懂...
│       ├── agent-attitude/              # ~60 terms across 3 files
│       │   ├── politeness.yaml          # 请, 您好, 谢谢, 您/你 ratio
│       │   ├── dismissive.yaml          # 不知道, 等会回复, 不归我管...
│       │   └── confrontational.yaml     # 你又没问, 我不是说了吗...
│       ├── agent-competence/            # ~22 terms across 2 files
│       │   ├── knowledge-gaps.yaml      # 不清楚, 可能, 大概, 好像...
│       │   └── procedural-errors.yaml   # 应该先..., 忘了..., 搞错了...
│       ├── interaction-patterns/        # ~18 patterns across 3 files
│       │   ├── turn-taking.yaml         # 抢话/冷场 thresholds
│       │   ├── objection-handling.yaml  # 否定词+解决方案 配对
│       │   └── confirmation.yaml        # 复述确认, 语义相似度 >0.7
│       └── marketing-scripts.yaml       # 18 standard scripts (P33)
│
├── gates/                               # B-C output — per-dimension hard_fail_rules
│   ├── procedural_accuracy.yaml
│   ├── empathy_and_tone.yaml
│   ├── problem_resolution.yaml          # IMMEDIATE FAIL if < 7 gate
│   └── proactive_value.yaml
│
└── _meta/
    └── residue-manifest.yaml
```

### Reference direction (单向，不可逆)

```
rules_criteria/ ──references──▶ evidence/     (via trigger.spec, corroborators[])
rules_criteria/ ──synthesized into──▶ gates/  (B-C: many-to-one)
evidence/       ──NEVER references──▶ rules_criteria/
gates/          ──NEVER references──▶ rules_criteria/
```

Evidence files can be shared-referenced by multiple rules_criteria nodes; they are not bound to a single item.

### Concrete before/after file listing

**Deleted (old `_rubric/`):**

```
acoustic/indicators.yaml                       # 12 AuthoredNode — now EvidenceEntry in evidence/acoustic/
phrase-keyword/lexicon.yaml                     # 4 AuthoredNode — now split into evidence/phrase-keyword/{category}/
rules/late-filing-requirements.yaml             # v1-format residue — superseded by compiler output
procedural_accuracy/item-01.yaml … item-27.yaml # flat under _rubric/ — moved to rules_criteria/
empathy_and_tone/item-08.yaml … item-26.yaml
problem_resolution/item-15.yaml … item-25.yaml
proactive_value/item-20.yaml … item-21.yaml
```

**Added (new `_rubric/`):**

```
rules_criteria/                                 # D1: per-dimension batch-load
  procedural_accuracy/item-01.yaml … item-27.yaml   (7 files, items 1,2,3,4,5,9,27)
  empathy_and_tone/item-08.yaml … item-26.yaml      (8 files, items 8,10,11,12,13,14,22,26)
  problem_resolution/item-15.yaml … item-25.yaml    (8 files, items 15,16,17,18,19,23,24,25)
  proactive_value/item-20.yaml … item-21.yaml       (2 files)
evidence/                                       # D2: pure data, not AuthoredNode
  acoustic/indicators.yaml                          # NOTE: expertise-decision-log.md uses framework format
  phrase-keyword/                                   # NOTE: deviates from Patch 1 (phrase/)
    customer-emotion/                               # ~90 terms across 7 files
    agent-attitude/                                 # ~60 terms across 3 files
    agent-competence/                               # ~22 terms across 2 files
    interaction-patterns/                           # ~18 patterns across 3 files
    marketing-scripts.yaml                          # 18 standard scripts (P33)
gates/                                          # D3: per-dimension, detached from nodes
  procedural_accuracy.yaml
  empathy_and_tone.yaml
  problem_resolution.yaml                       # IMMEDIATE FAIL if < 7 gate
  proactive_value.yaml
_meta/residue-manifest.yaml                     # AUTH-5 required output
```

**Per-node schema changes (each `item-XX.yaml`):**

| Field | Old (v1) | New (Patch 1) |
|-------|----------|---------------|
| `human_version` | absent | **added** — original rubric context preserved verbatim |
| `trigger` (form, spec, checkable) | present | **removed** (D10) — replaced by `machine_criterion` |
| `hard_fail_rule` | attached to node | **removed** (D3) — moved to `gates/{dimension}.yaml` |
| `w_c`, `w_c_provisional` | present | **removed** (D6) — agreement-module concern |
| `residue_declared` | top-level field | **renamed** to `machine_criterion.residue` (Patch 1 §6) |
| `facets` | absent | **added** (D5) — programmatic + model_based, grouped by extraction method |
| `machine_criterion` | absent | **added** (D10) — scoring_scale, gap_type, deduction_weight, dimension_weight |
| `deduction_weight` | hardcoded 1.0 | **computed** (D6) — `dim_weight × confidence × gap_factor` |

**File count:** 29 → 35 (net +6: 4 gates + evidence split + _meta manifest, minus old flat structure)

---

## 4. 1 item → 1 node (spec §3.6b confirmed)

### Mapping cardinality

| Spec term | Count | Relationship to human items |
|-----------|------|----------------------------|
| **rules_criteria node** (per-item compilation) | 25 (items 6,7 excluded) | **1 item → 1 node** |
| **A2-ac nodes** (12 acoustic indicators) | 12 | **0 items → 12 nodes** (from Generic Evaluator Skill template, NOT from human rubric items) |
| **A2-ph nodes** (4 phrase lexicons) | 4 | **0 items → 4 nodes** (same — from template, not from items) |
| **hard_fail_rule** (B-C, per dimension) | 4 | **N items → 1 rule** (synthesized from item subsets, not 1:1) |

Total node count exceeds 27 because the compiler produces evidence nodes and gate nodes beyond the per-item compilation — these have no corresponding items in the Specific QA Rubric. They are compiled from the Generic Evaluator Skill template's judgment structure.

### Why not 1:many?

Spec §3.6b pseudocode states unambiguously:

```
for each item in specific_rubric (27):
    dim = align.md[item]    # ONE dimension per item
```

"one row per item, not per dimension." Cross-axis items (9, 15, 26) have primary and secondary axis annotations, but the secondary axis is stored in `residue_declared` — it does not generate a separate node. One item influencing multiple dimension scores happens at **runtime**, weighted by the evaluator, not split at compile time.

---

## 5. gates/ role

`gates/` is the output of B-C (hard-threshold synthesis, spec §2.6-C).

### The problem

The Generic Evaluator Skill defines dimension-level hard thresholds (Problem Resolution < 7 → IMMEDIATE FAIL, any other criterion < 6 → SPRINT FAILS), but the compiler does not produce 1–10 scores — only 25 binary triggers. At compile time, the compiler cannot know whether a dimension score will fall below a threshold.

### The solution

`gates/` translates dimension-level thresholds into item-level combination conditions — an **early-warning safety net**:

```yaml
dimension: Problem Resolution
hard_fail_rule:
  subset: [15, 16, 17, 18, 19, 23, 24, 25]   # all 8 items in this dimension
  trips_when: ">= 3 items fail"                # combination condition, not simple majority
  consequence: escalate_to_human_qa             # routing decision, not scoring
  synthesized_from: "Generic Evaluator Skill §Hard Thresholds: Problem Resolution < 7 -> IMMEDIATE FAIL"
```

### gates vs rules_criteria

| | rules_criteria | gates |
|------|------|------|
| **Granularity** | per item | per dimension |
| **Question** | Did this item pass? | Does the collective failure pattern of these items indicate dimension collapse? |
| **Output** | trigger pass/fail → feeds `score()` | escalate to human QA → routing decision, independent of `score()` |
| **Source** | Specific QA Rubric (human binary checklist) | Generic Evaluator Skill hard threshold mechanism |
| **Compilation step** | A1-A7 + B-A, B-B, B-D | B-C (many-to-one synthesis) |

---

## Consequences for the 9003 compiler

1. **Output structure:** `_rubric/` directory restructured per §3 above. `evidence/` and `gates/` separated from the current flat output.

2. **Node enrichment:** The 14 rules_criteria items that need acoustic/phrase evidence should declare explicit references to evidence nodes in their `corroborators[]`, and reference acoustic/phrase thresholds in their `trigger.spec`.

3. **A2-ac / A2-ph output path:** 12 acoustic indicators written to `_rubric/evidence/acoustic/indicators.yaml` (no longer 12 standalone AuthoredNodes under `_rubric/acoustic/`). 4 phrase lexicons written as subdirectories under `_rubric/evidence/phrase-keyword/` (customer-emotion/, agent-attitude/, agent-competence/, interaction-patterns/).

4. **B-C output path:** Per-dimension hard_fail_rules from `_add_hard_fail_rules` written to `_rubric/gates/`, no longer attached to individual rules_criteria nodes.

5. **Spec §3 unchanged.** Per-item compilation (1 item → 1 node) is preserved. Evidence nodes and gate nodes are independent outputs outside the per-item loop.

---

## Appendix A: Per-item evidence audit (complete)

### Procedural Accuracy (7 items)

| Item | Acoustic | Phrase | Evidence needed |
|------|:---:|:---:|------|
| 1 起接语 | | x | recommended_phrases: "您好" |
| 2 称谓语 | | x | recommended_phrases: "先生/小姐/女士/老师" |
| 3 信息查询 | | | KB lookup only |
| 4 候线规范 | x | x | pause_duration + recommended_phrases: "请稍等/您稍等" |
| 5 结束语 | | x | recommended_phrases: "再见"; "还有其他问题" check |
| 9 语速语音 | x | | 12 indicators: speaking_rate, f0_mean, intensity_mean, intensity_std… |
| 27 隐私保护 | | | regex: phone_number_pattern NOT IN transcript |

### Empathy & Tone (8 items)

| Item | Acoustic | Phrase | Evidence needed |
|------|:---:|:---:|------|
| 8 清晰流畅 | x | x | hnr, voice_quality_sustained + filler: "的话/那个/的哦" |
| 10 礼貌用语 | | x | recommended: "您" + sensitive: "你" count |
| 11 亲切友善 | x | x | f0_mean, f0_range, voice_quality_sustained + negative: "又不是/怎么可能" |
| 12 无打断 | x | | turn_response_gap (overlap detection) |
| 13 集中倾听 | x | | turn_response_gap + pause_duration |
| 14 表达委婉 | | x | sensitive: "不知道/没办法/无法告诉您" |
| 22 情绪处理 | x | x | f0_mean, intensity_mean + sensitive (complaint patterns) |
| 26 沟通氛围 | x | x | f0_mean, f0_range, intensity_mean + negative + sensitive |

### Problem Resolution (8 items)

| Item | Acoustic | Phrase | Evidence needed |
|------|:---:|:---:|------|
| 15 重点突出 | | | semantic — perceiver gap, not compilable |
| 16 理解需求 | | | pure residue, not compilable |
| 17 主动引导 | x | | pause_duration + speaking_rate (silence detection) |
| 18 思路清晰 | | | lookup: KB proxy, partial |
| 19 业务知识 | | | lookup: KB verification |
| 23 不推诿 | | x | sensitive: "不归我管/去找别人/自己去查" |
| 24 方案准确性 | | | coverage gap, causal inference needed |
| 25 业务办理 | | | lookup: KB fee/documents verification |

### Proactive Value (2 items)

| Item | Acoustic | Phrase | Evidence needed |
|------|:---:|:---:|------|
| 20 营销机会 | | x | marketing/triggers: P31 trigger_keywords (5 product lines) |
| 21 积极营销 | | x | marketing/scripts: P33 18 standard scripts quality check |

---

## 6. Item file structure and runtime contract (added 2026-07-13)

Eight architecture decisions from a spec interview between human and Claude Code, following the adversarial review that produced Patch 1. Each decision is recorded with its rationale and architectural consequence.

### Decision registry

| # | Decision | Rationale | Architectural consequence |
|---|----------|-----------|--------------------------|
| **D1** | Runtime loads rules_criteria by dimension in batch | 9002 evaluator loads all nodes under a dimension directory at once, parses once, holds in memory | Output organized as `rules_criteria/{dimension}/item-XX.yaml`; flat list rejected |
| **D2** | Evidence entries are pure data (dict/list), not AuthoredNode | Acoustic indicators and phrase lexicons are measurement instruments providing thresholds/baselines — they don't need trigger/agreement/gate fields that rules carry | New `EvidenceEntry` type: `{name, type, values}` where values is `{threshold, unit, description}` for acoustic or `[word_list]` for phrase. Runtime loads via separate evidence loader.<br><br>**NOTE:** Final format aligned with `expertise-decision-log.md` — acoustic uses framework format (version + indicators[]), phrase-keyword uses subdir classification (customer-emotion/, agent-attitude/, etc.) |
| **D3** | Gates strictly separated per-dimension, never attached to individual rules_criteria nodes | Per-dimension hard_fail_rule is a routing decision (escalate to human QA), not a per-item score. Attaching it to one node per dimension (the current `break` pattern) is fragile and semantically wrong | `hard_fail_rule` field removed from `AuthoredNode`. Gate files at `gates/{dimension}.yaml`. Runtime loads gates independently for routing decisions |
| **D4** | trigger.spec inlines acoustic/phrase thresholds directly | Nodes should be self-contained for runtime evaluation. The evaluator should not need to chase external references to evaluate a trigger | trigger.spec writes concrete values: `"speaking_rate ∈ [120, 220] wpm AND intensity_std < 15 dB"`. evidence/ directory exists as human-readable documentation reference, not as a runtime dependency |

**Facet definition.** 在对每个 item 进行质检时，需要从原始通话中提取一系列"可度量的视角"——称为 Facet。Facet 是从原始对话中提取出的一个可度量的视角，比如主题、对话轮数、声学特征、客户意图等。提取 Facet 的两种方法：

1. **Programmatic（程序化计算）**：对于结构化的、不需要语义理解的属性，直接用代码算出来。例如对话的轮次、时长等元数据，以及候线时长、声学特征（音高、音量、语速等）等无需语义理解的数据。
2. **Model-based（模型提取）**：对于需要语义理解的属性，用 LLM 来提取。例如对话摘要、客户意图、坐席策略、情绪倾向等。

Facet 不是规则本身，而是规则评估所需的**证据输入**。一个 item 可能依赖 0 个到多个 facet——例如 item 1（起接语）只需要 1 个 programmatic facet（phrase_matching），而 item 18（思路清晰灵活）则需要 1 个 model-based facet（dialogue_semantics）来提取判断"思路清晰"和"灵活适应"所需的语义信号。

| **D5** | Facets grouped by extraction method: `programmatic` vs `model_based` | Programmatic facets (acoustic, phrase, duration, turn counts) can be computed in parallel with no model call. Model-based facets (dialogue summary, customer intent, agent strategy, emotion tendency) need LLM extraction. Grouping by method enables runtime batching | New `FacetGroup` on `AuthoredNode` with two lists: `facets.programmatic` and `facets.model_based`. Each `Facet` has `{name, description, extraction_method, required_data}` |
| **D6** | 1-10 scale anchored at item level via deduction_weight + severity_map | Human rubric items are binary (0/1/NA) but each item contributes weighted evidence to a 1-10 dimension score. The mapping from "this item failed" to "how much this hurts the dimension score" must be visible per item | `deduction_weight` already computed (dim_weight × confidence × gap_factor). `severity_map` references calibration manifest epoch. Both fields live on the item node |
| **D7** | Single self-contained YAML per item (~60-80 lines) | One item = one file = one concept a human reviewer can read end-to-end. Splitting into multiple files (item + facets + scale) adds indirection without benefit since facets are not shared across items | Each `item-XX.yaml` contains four sections: `human_version` (原始人工标准), `machine_version` (trigger/gap/escape/agreement), `scale_1_to_10` (deduction_weight + severity_map), `facets` (programmatic + model_based) |
| **D8** | Evidence and gates are auto-compiled AND human-editable post-compilation | Humans must be able to add evidence indicators, adjust gate thresholds, or enrich facets without re-running the compiler. The compiler must not silently overwrite human edits | Compiler writes evidence/ and gates/ files with an `edited_by_human: false` field. Humans change it to `true`. On re-compile, the compiler reads existing files and skips those with `edited_by_human: true` |
| **D9** | Facets are signal-shaped — each facet is defined against a specific FAIL or EXCELLENCE signal | The operationalization principle "Shape what facets to be extracted against the gradable individual criterion" means facets are not a flat list of generic features. Each facet is bound to the specific signal(s) it enables. A model_based facet for Item 18's "思路混乱" signal has a different extraction prompt than a facet for Item 16's "理解需求" signal — even if both extract "dialogue semantics." | `Facet` schema updated: each facet now carries `enables_signals: [{signal_id, extraction_shape}]`. For model_based facets: `{facet_name, enables_signals, prompt}` — the prompt is a complete extraction prompt with checkpoints and output_schema, authored by the compiler per signal. For programmatic facets: `{facet_name, enables_signals, indicator, calculation, output_schema}` — indicator defines what to measure, calculation defines how to compute it |
| **D10** | Operationalized artifact follows a four-layer chain: human_version → machine_criterion → signals → facets | Each compiled item is structured as a layered transformation from subjective human judgment to computable machine evidence. (1) `human_version`: the original rubric text preserved verbatim. (2) `machine_criterion`: the item restated as a gradable (1-10) machine criterion with gap_type and auto_final policy. (3) `signals`: FAIL and EXCELLENCE signals decomposed from the human rubrics pass/fail standards — these are the observable manifestations of the criterion. (4) `facets`: signal-shaped evidence inputs — programmatic facets carry indicator + calculation method; model_based facets carry facet_name + complete model prompt with checkpoints and output_schema. The chain is unidirectional: facets enable signals; signals evidence the criterion; the criterion operationalizes the human rubric | D7's four-section structure revised: `human_version` (原始人工标准), `machine_criterion` (机器可执行的判定标准 — 1-10, gap_type, auto_final policy), `signals` (FAIL + EXCELLENCE — 可观测信号, each with id, description, severity), `facets` (programmatic: indicator + calculation + output_schema; model_based: facet_name + prompt + output_schema). Each facet explicitly declares `enables_signals` — the reverse mapping from facet to signal. Model_based facet prompts are complete, authored by the compiler, not assembled at runtime. See `item-18-example.yaml` for the full worked example.
| **D11** | Uniform operationalized structure for all 25 items — no explicit tier field | All items share the same schema. YAML keys that do not apply to a given item simply do not appear in that item's file. The evaluator infers assessment mode from which keys exist: `deterministic_checks` present → binary PASS/FAIL (compliance layer, auto-final allowed); `signals` present with `model_based` facets + `gap_type: perceiver` → 1-10 scoring (perceiver layer, auto-final forbidden). An explicit `tier` field is rejected: YAML key presence/absence is the mechanism. | Rejects tiered-schema Direction 2 from `9003-structure-design-directions.html`. Item 1's YAML has only `human_version` + `deterministic_checks`; Item 18's has all four layers. No `null` filler fields. |
| **D12** | Signal Decomposition (B-E): a named compilation step that converts human rubric adjectives into gate-checkable signals | Reference methodology Step 2 ("Replace adjectives with failure signatures") has no corresponding named step in the 9003 compiler procedure. The §2.6 procedure jumps from B-D (value extraction) to gap classification, but the critical transformation — decomposing `pass_standard` and `fail_standard` prose into observable FAIL/EXCELLENCE signals — has no step name, no input/output contract, and no AUTH fixture. Each signal must satisfy the spec's three-layer definition of "computable" (compute → verify → dispose, spec footnote ◆): a signal is gate-checkable iff a proposer can find a transcript span for it AND a gate can deterministically verify that the span satisfies the signal's specification. A signal that still contains an evaluative adjective ("坐席表现混乱") without a concrete referent is rejected per AUTH-1 (extended). | New compilation step **B-E: Signal Decomposition**. Input: `human_version.pass_standard` and `human_version.fail_standard` text. Output: `signals: {fail: [{id, description, severity}], excellence: [{id, description}]}`. Each signal must pass the gate-checkable test: can a ground-truth span in a transcript be pointed to as evidence? B-E is agentic (requires semantic understanding of rubric prose) but its output is deterministic rubric. After B-E, the compiler assigns facets (D5/D9) to each signal. AUTH-1 (no adjective triggers) is extended to cover signals: a signal whose description is still a conclusion rather than an observable pattern is rejected by the validator. |

### Updated per-item compilation procedure (insert B-E)

The §3.6b per-item compile pseudocode is revised to include the missing Signal Decomposition step between B-D and gap classification:

```
for each item in specific_rubric (25):
    dim   = align.md[item]                         # bind to dimension (B-A)
    gate  = compile_na(item.na_condition)          # → applicability_gate (B-B)
    form  = extract_values(item.text)              # phrases→lexical, numbers→threshold (B-D)
    signals = decompose_signals(                   # ★ B-E: NEW — replace adjectives with
        item.pass_standard,                        #   gate-checkable signals.
        item.fail_standard,                        #   Each signal must pass the test:
        dim                                       #   "Can a proposer find a transcript span
    )                                              #   for this, and can a gate verify it?"
    gap   = classify_gap(item, dim, signals)       # classify gap considering signal coverage
    tier  = aggressive if gap in {proxy, coverage, perceiver} else standard
    facets = assign_facets(signals, gap)            # signal-shaped facets (D5/D9)
    if no dimension adequately covers item:
        emit lookup + data_dependency; defer_until_source_connected
        write dimension_coverage_gap row
    elif surface_form_sensitive(item) and not calibration.covers(item):
        emit node but forbid auto_final (AUTH-9)
    else:
        emit _rubric/ node + within_dimension residue row if lossy
then: synthesize per-dimension hard_fail_rule from item subsets (B-C)
emit: _rubric/ nodes + ResidueManifest
```

### Signal validity test (validator, AUTH-1 extended)

For each signal emitted by B-E, the validator checks:
1. **No adjectives in signal description.** "混乱," "清晰的," "灵活的" → reject. Signal must name an observable pattern, not a conclusion.
2. **Referent test.** Can a human point to a specific transcript span that satisfies this signal? If no → reject.
3. **Gate-checkable test.** Can the gate deterministically verify: (a) the claimed span exists, (b) it matches the signal's specification? If no → flag as `signal_confidence: low` and route to residue.


### Updated _rubric/ directory structure (with D1-D8 applied)

```
INTENTS/_rubric/
│
├── rules_criteria/                      # D1: per-dimension, D7: single file per item
│   ├── procedural_accuracy/
│   │   ├── item-01.yaml                 # D7: human_version + machine_version
│   │   ├── item-02.yaml                 #      + scale_1_to_10 + facets
│   │   ├── item-03.yaml
│   │   ├── item-04.yaml
│   │   ├── item-05.yaml
│   │   ├── item-09.yaml
│   │   └── item-27.yaml
│   ├── empathy_and_tone/
│   │   ├── item-08.yaml
│   │   ├── item-10.yaml
│   │   ├── item-11.yaml
│   │   ├── item-12.yaml
│   │   ├── item-13.yaml
│   │   ├── item-14.yaml
│   │   ├── item-22.yaml
│   │   └── item-26.yaml
│   ├── problem_resolution/
│   │   ├── item-15.yaml
│   │   ├── item-16.yaml
│   │   ├── item-17.yaml
│   │   ├── item-18.yaml
│   │   ├── item-19.yaml
│   │   ├── item-23.yaml
│   │   ├── item-24.yaml
│   │   └── item-25.yaml
│   └── proactive_value/
│       ├── item-20.yaml
│       └── item-21.yaml
│
├── evidence/                            # D2: pure data, D4: human-readable doc
│   ├── acoustic/
│   │   └── indicators.yaml              # NOTE: aligned with expertise-decision-log.md (framework format)
│   └── phrase-keyword/                  # NOTE: deviates from Patch 1 (phrase/)
│       ├── customer-emotion/            # ~90 terms across 7 files
│       ├── agent-attitude/              # ~60 terms across 3 files
│       ├── agent-competence/            # ~22 terms across 2 files
│       ├── interaction-patterns/        # ~18 patterns across 3 files
│       └── marketing-scripts.yaml       # 18 standard scripts (P33)
│
├── gates/                               # D3: per-dimension, detached from nodes
│   ├── procedural_accuracy.yaml
│   ├── empathy_and_tone.yaml
│   ├── problem_resolution.yaml
│   └── proactive_value.yaml
│
└── _meta/
    └── residue-manifest.yaml
```

### Updated AuthoredNode schema (D1-D8 conformance)

| Field | Status | Rationale |
|-------|--------|-----------|
| `human_version: HumanRubricItem` | **NEW** | D7/D10: preserves original rubric context verbatim — the original text is the authority |
| `machine_criterion` | **NEW** | D10: the item restated as a gradable (1-10) machine criterion — includes `criterion_id`, `description`, `scoring_scale`, `gap_type`, `auto_final_allowed`, `escape_tier` |
| `signals: {fail, excellence}` | **NEW** | D10: FAIL and EXCELLENCE signals decomposed from human rubric standards. Each signal has `{id, description, severity}`. Signals are the bridge between machine_criterion and facets |
| `facets: FacetGroup` | **ENRICHED** | D5/D9/D10: facets are signal-shaped — each facet declares `enables_signals: [{signal_id, extraction_shape}]`. Programmatic: `{facet_name, enables_signals, indicator, calculation, output_schema}`. Model_based: `{facet_name, enables_signals, prompt, output_schema}`. The prompt for model_based facets is a complete extraction prompt authored by the compiler |
| `hard_fail_rule` | **REMOVED** | D3: moved to gates/ per-dimension |
| `w_c`, `w_c_provisional` | **REMOVED** | D6: these are agreement-module concerns, not per-item fields |
| `trigger.spec` | **REMOVED** | D10: replaced by `machine_criterion` + `signals` — the criterion defines what to judge, signals define what to observe, facets define how to extract the observations |
| `corroborators[]` | **ENRICHED** | D4/D5: populated with evidence references for 14 items per Appendix A audit |
| `deduction_weight` | **PRESERVED** | D6: item-level 1-10 scale contribution |
| `severity_map` | **PRESERVED** | D6: calibration manifest reference |
| All other §3 fields | **PRESERVED** | agreement, applicability_gate, gap_type, escape_tier, data_dependency, iteration_policy |

---

## 7. Updated consequences for the 9003 compiler (replaces original §Consequences)

1. **Output structure:** `_rubric/` restructured per §6 table. `rules_criteria/` per-dimension (D1), `evidence/` pure data (D2), `gates/` detached (D3).

2. **AuthoredNode schema updated:** `human_version` and `facets` added; `hard_fail_rule` and `w_c` removed. trigger.spec enriched with inline thresholds (D4).

3. **A2-ac / A2-ph output simplified:** Return `list[EvidenceEntry]` (pure data) instead of `list[AuthoredNode]`. Written to `evidence/` with human-edit guard (D8).

4. **B-C output detached:** `_compile_gates()` returns `dict[str, HardFailRule]` per-dimension. Written to `gates/` with human-edit guard (D8). No longer mutates individual nodes.

5. **Facet assignment (revised per D9/D10):** New `_assign_facets()` assigns programmatic/model-based facets per item based on Appendix A audit table. Each facet is signal-shaped: the compiler identifies which FAIL/EXCELLENCE signals need extraction support, then authors a facet with the appropriate extraction method. Programmatic facets carry indicator + calculation + output_schema. Model_based facets carry a complete extraction prompt (checkpoints + output_schema) authored by the compiler — not assembled at runtime. See `item-18-example.yaml` for the full worked example of the four-layer operationalized artifact.

6. **Auto-compile + human-editable contract (D8):** When writing evidence/ or gates/ files, compiler sets `edited_by_human: false`. On re-compile, reads existing file; skips overwrite if flag is `true`.

7. **Per-item compilation (1 item → 1 node) unchanged.** Evidence and gate nodes are independent outputs outside the per-item loop.

8. **Signal Decomposition (B-E, per D12):** New `_decompose_signals()` step inserted between B-D (value extraction) and gap classification. For each item, the compiler reads `pass_standard` and `fail_standard` text and decomposes them into FAIL/EXCELLENCE signals. Each signal must pass the gate-checkable test (spec footnote ◆): a proposer can find a transcript span for it; a gate can deterministically verify that the span satisfies the signal's specification. Signals that remain adjectives ("混乱") without concrete referents are rejected per AUTH-1 (extended). This step is agentic (requires semantic understanding) but produces deterministic rubric. It fills the gap between reference methodology Step 2 ("Replace adjectives with failure signatures") and the 9003 compiler procedure — a step that previously had output format (D10's `signals` field) but no named step defining how to produce it.

---

## Changelog

| Date | Change | Source |
|------|--------|--------|
| 2026-07-10 | Initial patch. Sections 1–5: evidence sources, per-item audit, directory structure, item→node mapping, gates/ role. Sections 6–7 (D1–D8, schema, consequences) added after first spec interview (round 1). | Adversarial review of `soft-criteria-authoring-spec-v4.html` |
| 2026-07-13 | D1–D8 decisions recorded from round-1 spec interview. Facet definition and D5 (programmatic vs model_based) added. AuthoredNode schema table, updated directory structure, and consequences for 9003 compiler written. | Round-1 interview: `9003-ambiguities-interview.html` |
| 2026-07-15 | **D9** added: Facets are signal-shaped. Each facet is defined against specific FAIL/EXCELLENCE signals, not as a flat generic feature list. Programmatic facet structure: `{facet_name, enables_signals, indicator, calculation, output_schema}`. Model_based facet structure: `{facet_name, enables_signals, prompt, output_schema}`. | Round-2 interview Q4 (operationalization principle: "Shape what facets to be extracted against the gradable individual criterion") |
| 2026-07-15 | **D10** added: Four-layer operationalized artifact structure — `human_version → machine_criterion → signals → facets`. `trigger.spec` removed from AuthoredNode schema; replaced by `machine_criterion` + `signals`. `human_version` and `facets` schemas enriched. Facet assignment consequence revised to reflect D9/D10 signal-shaped authoring. | Round-2 interview Q5 (operationalized artifact structure) |
| 2026-07-15 | `item-18-example.yaml` created as full worked example of the four-layer operationalized artifact (Item 18: 思路清晰灵活处理, perceiver gap, 4 FAIL + 3 EXCELLENCE signals, 3 programmatic + 3 model_based facets). | Round-2 interview Q5 deliverable |
| 2026-07-15 | **D11** added: Uniform operationalized structure for all 25 items. All items share the same schema; YAML keys that do not apply to a given item simply do not appear in that item's file (no `null` filler, no explicit `tier` field). The evaluator infers assessment mode from which keys exist: `deterministic_checks` present → compliance layer (binary PASS/FAIL, auto-final allowed); `signals` present with `model_based` facets + `gap_type: perceiver` → perceiver layer (1-10, auto-final forbidden). Rejects explicit tiered schema (Direction 2). | `9003-structure-design-directions.html` (user selected Direction 1) |
| 2026-07-16 | **D12** added: Signal Decomposition (B-E) — a named compilation step that converts human rubric adjectives into gate-checkable FAIL/EXCELLENCE signals. Closes the gap between reference methodology Step 2 ("Replace adjectives with failure signatures") and the 9003 compiler procedure, which had signal output format (D10) but no step defining how to produce it. B-E is agentic (semantic understanding of rubric prose) but produces deterministic output. Each signal must pass the gate-checkable test: can a proposer find a transcript span AND can a gate verify it? AUTH-1 extended to reject signals that are still adjectives. Per-item compile pseudocode (§3.6b) updated. Consequence #8 added. | Gap identified during round-2 Q7 discussion: missing step between B-D and gap classification in §2.6 procedure |
