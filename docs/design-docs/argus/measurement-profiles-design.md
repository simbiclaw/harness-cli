# Measurement Profiles: Shared Data Infrastructure for Argus and audio2tree

**Status:** draft
**Date:** 2026-07-16
**Source:** soft-criteria-authoring-spec-v4 patch-1 (D1-D12), patch-2 (S1-S6), expertise-library.md, ADR-0002, ADR-0004

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

Each profile is a complete, self-contained measurement unit: lexical patterns + acoustic fingerprints + sentence-structure features + calculation methods + known-item mappings + unknown-unknown gating logic.

### D16: Expertise files follow embed-vs-reference rules

| Expertise | Embed or Reference | INTENTS Location |
|:---|:--:|:---|
| #1 Rules & Criteria | N/A — compilation output | `_rubric/rules_criteria/` |
| #2 Acoustic Feature | **Reference** (9 Items share) | `_rubric/acoustic/` |
| #3 Phrase & Keyword — Layer 1 (shared lexicons) | **Reference** (multi-Item) | `_rubric/phrase-keyword/` |
| #3 Phrase & Keyword — Layer 2 (Item-specific) | **Embed** in Item YAML | — |
| #4 Product Introduction | **Reference** | `<domain>/<case>/kb.*.yaml` |
| #5 Operation Manual | **Reference** | `<domain>/<case>/kb.*.yaml` |
| #6 Dynamic Knowledge Base | **Reference** | `<domain>/<case>/kb.*.yaml` |
| #7 Best Practice Cookbook | **Reference** (via severity_map) | `<domain>/<case>/cookbook.*.yaml` |
| #8 Error Case Library | **Reference** (via severity_map) | `<domain>/<case>/errors.*.yaml` |
| #9 Audio Transcription | N/A — per-call input artefact | — |

### D17: Profile file structure — the `_rubric/profiles/` directory

```
_rubric/
  profiles/
    customer-emotion.yaml
    agent-attitude.yaml
    agent-competence.yaml
    interaction-quality.yaml
  acoustic/
    indicators.yaml
    emotion-profiles.yaml
    attitude-profiles.yaml
  phrase-keyword/
    customer-emotion/
      escalation-threat.yaml
      deception-perception.yaml
      price-dissatisfaction.yaml
      product-disparagement.yaml
      resignation.yaml
      repeated-frustration.yaml
      confusion-markers.yaml
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
    <dimension>/item-XX.yaml
  evidence/
    ...
  gates/
    ...
```

### D18: Profile schema

Each profile follows this canonical structure:

```yaml
profile: "<name>"
description: "<what this profile measures>"
version: "1.0.0"

dimensions:
  <dimension-name>:
    lexicons:
      - "<path to lexicon file>"
    acoustic_fingerprint:
      profile_ref: "<path to acoustic profile>#<fingerprint>"
    sentence_patterns:
      <pattern-name>:
        threshold: <value>
        indicator: "<description>"
    calculation:
      method: "<weighted_sum | composite | binary | count>"
      formula: "<expression>"
    output:
      per_turn: "<field name>"
      per_call: "<field name>"
    known_item_mapping:
      - {item: <N>, signal: "<id>", role: "<description>"}

unknown_unknown_gating:
  - trigger: "<condition>"
    action: "<flag_for_human_review | suggest_new_item>"
    label: "<human-readable label>"
```

## Consumer Contract

### Argus (Top-down)

Item YAML references profiles rather than embedding calculation logic:

```yaml
# Item 22 YAML
measurement_profiles:
  - profile_ref: "_rubric/profiles/customer-emotion.yaml"
    dimensions_used: [anger, resignation]
    for_signals: [F1]
```

Evaluator loads referenced profiles at startup via RubricReader. Calculation logic lives in profiles, not in Item YAML. S3 gate verifies: does the claimed span satisfy the profile dimension's specification?

### audio2tree (Bottom-up)

Loads all profiles under `_rubric/profiles/`. For each call:
1. Computes all profile dimensions (emotion timeline, attitude labels, competence indicators)
2. Matches computed features against `known_item_mapping` — features with coverage → normal Argus path
3. Features without coverage (`coverage_gap: true` in lexicons OR no matching `known_item_mapping`) → unknown-unknown candidates
4. Runs `unknown_unknown_gating` rules — triggers that fire mark calls and patterns for human review

## Feedback Loop

| Trigger | Source | Action | Target |
|:---|:---|:---|:---|
| coverage_gap term hits > threshold across N calls | audio2tree | Add term to lexicon file | `_rubric/phrase-keyword/` → bump SHA |
| New emotion pattern not covered by any signal | audio2tree `suggest_new_item` | Human review → new Item → recompile | 9003 compiler |
| Existing Item consistently misses known pattern | Argus κ drift | Update Item signals → recompile | 9003 compiler |
| New product/service launched | Product Introduction update | Update scripts → recompile Items 20/21 | 9003 compiler |
| Manual procedure change | Operation Manual update | Update interaction-patterns lexicon | `_rubric/phrase-keyword/` → bump SHA |

## Lexicon Inventory

The shared infrastructure comprises:

**Customer Emotion** (7 files, ~90 terms): escalation-threat, deception-perception, price-dissatisfaction, product-disparagement, resignation, repeated-frustration, confusion-markers

**Agent Attitude** (3 files, ~60 terms): politeness, dismissive, confrontational

**Agent Competence** (2 files, ~22 terms): knowledge-gaps, procedural-errors

**Interaction Patterns** (3 files, ~18 patterns): turn-taking, objection-handling, confirmation

**Acoustic** (3 files): 12 indicators, emotion fingerprints (anger/anxiety/confusion/resignation), attitude fingerprints (impatience/indifference/volatility)

## Conformance

| Patch Decision | Status |
|:---|:--:|
| D2 (pure data) | ⚠️ Profiles contain calculation formulas — not pure data. Acceptable because profiles are versioned rubric, formulas are deterministic expressions, not arbitrary code. |
| D4 (self-contained) | ✅ Profile refs are explicit paths. Evaluator loads once, caches. |
| D10 (four-layer structure) | ⚠️ facets layer simplified — calculation moves from Item YAML to profile. Item retains signal-level declarations but delegates implementation. |
| D11 (uniform schema) | ✅ All Items use same profile reference pattern. |
| S1 (companion doc manifest) | ✅ Profile refs SHA-pinned at compile time. |
| ADR-0002 (path-as-ontology) | ✅ All files at predictable paths under `_rubric/`. |
| ADR-0004 (category readers) | ✅ RubricReader loads `_rubric/profiles/` and `_rubric/phrase-keyword/`. |
