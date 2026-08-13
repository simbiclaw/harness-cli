# audio2tree ↔ INTENTS ↔ 9003 Compiler — Relationship Map

**Date:** 2026-07-17
**Status:** draft
**Source:** Cross-referencing audio2tree-pipeline.md retrospective, INTENTS/_demo/structure-demonstration.md, soft-criteria-authoring-spec-v4-patch-2.md, ADR-0003

---

## The three actors

```
┌──────────────────────────────────────────────────────────────────┐
│                        INTENTS/ (git-versioned)                   │
│                                                                  │
│  EPOCH.yaml          ← audio2tree writes, both read        │
│  _rubric/rules_criteria/   ← 9003 compiler writes, Argus reads   │
│  _rubric/evidence/         ← audio2tree writes, 9003 reads,      │
│  _rubric/profiles/           Argus reads, audio2tree reads       │
│  _rubric/gates/            ← ??? (no defined producer)           │
│  <domain>/.../calls/       ← audio2tree writes (transcriptions)  │
│  <domain>/product-intro.md ← doc2graph writes                    │
│  <domain>/<case>/<L3>/     ← doc2graph writes (operation manuals)│
│  <domain>/<case>/dkb.*.yaml   ← human writes (DKB)               │
│  <domain>/<case>/cookbook.*   ← human writes (cookbook)          │
│  <domain>/<case>/errors.*     ← human writes (error cases)       │
└──────────────┬───────────────────────────────┬───────────────────┘
               │                               │
    ┌──────────┴──────────┐          ┌─────────┴──────────┐
    │    audio2tree        │          │   9003 Compiler     │
    │                      │          │                     │
    │ Producer: writes     │          │ Producer: writes    │
    │  - calls/*.json      │          │  - rules_criteria/  │
    │  - evidence/         │          │  - residue-manifest │
    │  - epoch.yaml        │          │                     │
    │                      │          │ Consumer: reads     │
    │ Consumer: reads      │          │  - evidence/        │
    │  - profiles/         │          │  - Specific Rubric  │
    │  - evidence/         │          │  - Generic Skill    │
    │  - calls/            │          │  - align.md         │
    │                      │          │                     │
    │ Feedback: suggests   │──────────│→ triggers recompile │
    │  - lexicon updates   │          │                     │
    │  - new Items         │          │                     │
    └──────────────────────┘          └─────────────────────┘
```

---

## Material flow: who writes what, who reads what

| INTENTS path | Written by | Read by | Notes |
|:---|:---|:---|:---|
| `EPOCH.yaml` | audio2tree (at build time) | Argus, audio2tree (consumer), 9003 | Single source of truth for "which SHA is current" |
| `_rubric/rules_criteria/<dim>/item-XX.yaml` | **9003 compiler** | Argus (evaluator) | The ONLY write path into rules_criteria/. ADR-0003 exception |
| `_rubric/evidence/acoustic/` | audio2tree (producer) | Argus, audio2tree (consumer), 9003 (compile-time refs) | 12 indicators + emotion/attitude profiles |
| `_rubric/evidence/phrase-keyword/` | audio2tree (producer) + audio2tree feedback (updates) | Argus, audio2tree (consumer), 9003 (compile-time refs) | Layer 1 shared lexicons. Feedback loop can add terms directly |
| `_rubric/profiles/` | audio2tree (producer) | Argus, audio2tree (consumer) | Measurement profiles with known_item_mapping + unknown_unknown_gating |
| `_rubric/gates/` | **UNKNOWN** | Unclear | No defined producer. Not in any pipeline spec. Ghost artifact |
| `<domain>/<case>/<L3>/calls/*.json` | audio2tree (structural transcription) | Argus (input), audio2tree (consumer) | Per-call data. NOT versioned. NOT expertise |
| `<domain>/product-intro.md` | doc2graph (envisioned) | Argus, audio2tree, human agents | L1 domain-global product knowledge |
| `<domain>/<case>/<L3>/index.md` | doc2graph (envisioned) | Argus, human agents | Operation manuals at L3 granularity |
| `<domain>/<case>/dkb.*.yaml` | Human (product team) | Argus (FactsReader) | Dynamic Knowledge Base — highest authority |
| `<domain>/<case>/cookbook.*.yaml` | Human (QA reviewers) | Argus, 9003 (compile-time calibration) | Best Practice Cookbook — accumulated history |
| `<domain>/<case>/errors.*.yaml` | Human (QA reviewers) | Argus, 9003 (compile-time gap identification) | Error Case Library — accumulated history |
| `_meta/residue-manifest.yaml` | **9003 compiler** | Human (review), Argus (coverage tracking) | Names what the compiler left behind |

---

## Dependency chain

### Forward dependencies (what must exist before X can run)

```
audio2tree (Producer)
  └─ NO upstream INTENTS dependency — it CREATES the initial tree

9003 Compiler
  └─ DEPENDS ON: _rubric/evidence/acoustic/     (audio2tree must have produced these)
  └─ DEPENDS ON: _rubric/evidence/phrase-keyword/ (audio2tree must have produced these)
  └─ DEPENDS ON: Specific QA Rubric               (human-authored, external)
  └─ DEPENDS ON: Generic Evaluator Skill          (AI template, external)
  └─ DEPENDS ON: align.md                         (human-authored, external)
  └─ DEPENDS ON: <domain>/product-intro.md        (doc2graph must have produced)
  └─ DEPENDS ON: <domain>/<case>/dkb.*.yaml       (human must have written)
  └─ DEPENDS ON: <domain>/<case>/cookbook.*.yaml  (human must have written)
  └─ DEPENDS ON: <domain>/<case>/errors.*.yaml    (human must have written)

Argus (Evaluator)
  └─ DEPENDS ON: _rubric/rules_criteria/          (9003 must have compiled)
  └─ DEPENDS ON: _rubric/evidence/                (audio2tree must have produced)
  └─ DEPENDS ON: <domain>/.../calls/              (audio2tree must have transcribed)
  └─ DEPENDS ON: EPOCH.yaml                 (audio2tree must have pinned)

audio2tree (Consumer — unknown-unknown detection)
  └─ DEPENDS ON: _rubric/profiles/                (must exist)
  └─ DEPENDS ON: _rubric/evidence/                (must exist)
  └─ DEPENDS ON: _rubric/rules_criteria/          (for known_item_mapping — 9003 must have compiled)
  └─ DEPENDS ON: <domain>/.../calls/              (its own transcriptions)
```

### The chicken-and-egg problem

```
audio2tree Consumer needs _rubric/rules_criteria/ (for known_item_mapping)
  └─ which needs 9003 Compiler
       └─ which needs _rubric/evidence/
            └─ which needs audio2tree Producer
                 └─ which has NO dependency on rules_criteria/
```

**Resolution:** The boot sequence is:
1. audio2tree Producer runs first → creates `_rubric/evidence/` + `calls/` + `EPOCH.yaml`
2. 9003 Compiler runs second → reads evidence/, writes `_rubric/rules_criteria/`
3. audio2tree Consumer can now run → reads rules_criteria/ for known_item_mapping
4. Argus can now run → reads everything

This is not a deadlock because audio2tree Producer doesn't need the compiler's output.

---

## Versioning and epoch model

```
Timeline:
  Epoch A (SHA-a1b2c3)
  │ audio2tree Producer writes evidence/acoustic/ + phrase-keyword/
  │ audio2tree writes calls/*.json
  │
  Epoch B (SHA-d4e5f6)
  │ 9003 Compiler reads evidence/ at SHA-d4e5f6
  │ 9003 writes rules_criteria/item-XX.yaml
  │ Each Item YAML records pinned_sha: "d4e5f6" for every reference
  │
  Epoch C (SHA-g7h8i9)
  │ audio2tree feedback adds new term to phrase-keyword/escalation-threat.yaml
  │
  Epoch D (SHA-j0k1l2)
  │ Argus evaluator runs at pinned SHA-d4e5f6 (the compile-time epoch)
  │ Item YAML references resolve to evidence/ at SHA-d4e5f6
  │ Item does NOT see the new term added at Epoch C
  │ → This is CORRECT: evaluation is reproducible at the compile-time epoch
```

**The pinned_sha is the linchpin of reproducibility.** Each Item YAML records the git SHA at compile time for every reference (acoustic framework, lexicons, product intro, DKB, cookbook, errors). The evaluator resolves references at that SHA — not at HEAD. This means:

- audio2tree can advance the evidence/ tree independently
- 9003 can recompile Items at a new epoch when ready
- Argus always evaluates against the epoch the Item was compiled at
- Re-running evaluation at the same epoch produces identical results (I5: Replayability)

The `EPOCH.yaml` tracks HEAD. Individual Item YAMLs track their own compile-time SHA. These are different concepts: epoch.yaml says "this is the latest version of the tree"; item-XX.yaml says "I was compiled against this specific version."

---

## The feedback loop: audio2tree → 9003

This is the most important interaction between the two systems:

```
audio2tree Consumer detects unknown-unknown
  │
  ├─ coverage_gap term hits > threshold
  │    → Human approves → term added to phrase-keyword/<lexicon>.yaml
  │    → INTENTS SHA advances
  │    → Items referencing that lexicon AUTO-BENEFIT (no recompile)
  │         because the lexicon path is the same, just at a newer SHA
  │    → Evaluator will pick up new terms when Items are recompiled at new epoch
  │
  ├─ suggest_new_item
  │    → Human reviews pattern → New item added to Specific QA Rubric
  │    → 9003 compiler re-run → new item-XX.yaml written
  │    → INTENTS SHA advances
  │    → Argus re-pins to new epoch
  │
  └─ flag_for_human_review
       → Human confirms pattern is real
       → May trigger: lexicon update, Item update, or new Item
       → All paths eventually flow through 9003 recompile
```

**Critical asymmetry:** Lexicon updates (adding a term) do NOT require recompile — the Item references the lexicon by path, and the evaluator loads at the compile-time SHA. The Item only benefits from the new term after a recompile pins a new SHA. This means there is a window where audio2tree has discovered a gap and the lexicon has been updated, but Argus evaluations still use the old lexicon because Items haven't been recompiled. The feedback loop is human-gated at every step, so this window is bounded by human review latency, not by system design.

---

## What the _demo structure gets right and wrong about this relationship

### What it gets right

1. **The tree shape correctly separates concerns.** `_rubric/` (compiler output + measurement infrastructure) is at the top; domain trees (L1/L2/L3) are below. audio2tree writes to `_rubric/evidence/` and `calls/`; 9003 writes to `_rubric/rules_criteria/`. These paths don't overlap.

2. **The `pinned_sha` pattern is consistently modeled.** The item-20 YAML example shows `pinned_sha` on every reference (acoustic framework, lexicons, product intro, DKB, cookbook, errors). This is the mechanism that decouples audio2tree's write cadence from 9003's compile cadence.

3. **The expertise summary table correctly labels consumers.** It shows which expertise types are consumed by Argus (evaluator) vs audio2tree (discovery) vs human agents. The dual-consumer architecture is visible in the table.

### What it gets wrong (from adversarial review)

1. **`_rubric/gates/` has no producer.** Neither audio2tree nor 9003 writes to this directory. The _demo tree lists `coverage-gates.yaml` and `agreement-gates.yaml` but no pipeline stage produces them. If 9003's ResidueManifest serves this role, the directory shouldn't exist as a separate artifact. If it's human-authored, it should be documented as such.

2. **`_rubric/profiles/` is in the expertise-decision-log architecture diagram but absent from the _demo tree.** The measurement profiles are the shared data contract between Argus and audio2tree Consumer — arguably the most important `_rubric/` subdirectory for the dual-consumer architecture. Its absence from the tree is a significant omission.

3. **The `_rubric/evidence/` directory conflates two producers.** The tree shows `acoustic/`, `phrase-keyword/`, and `marketing-scripts.yaml` all under `_rubric/evidence/`. But `acoustic/` and `phrase-keyword/` are produced by audio2tree, while `marketing-scripts.yaml` is a reference corpus that may come from doc2graph or a human. The tree doesn't distinguish producer ownership at the file level — only at the directory level via `_meta/ownership.yaml`.

4. **Item 20's YAML example lists lexicon refs as `corroborators`.** This violates D16 — lexicons are measurement instruments, not independent corroborating signals. The 9003 compiler's AUTH-4 would reject this. The _demo structure should model the correct pattern: lexicons under `reference_sources`, not `corroborators`.

---

## Operational sequence: from cold start to first evaluation

```
Step 1: audio2tree Producer bootstraps INTENTS/
  └─ structural-transcription runs on call corpus
  └─ conversation-distillation builds initial intent tree
  └─ writes: EPOCH.yaml, _rubric/evidence/, _rubric/profiles/, calls/
  └─ git commit → Epoch A

Step 2: Human authors create compiler inputs
  └─ Specific QA Rubric (25 scored items)
  └─ Generic Evaluator Skill (4 dimensions, 1-10 scale)
  └─ align.md (item → dimension mapping)

Step 3: 9003 Compiler runs
  └─ reads evidence/ at Epoch A
  └─ reads three compiler inputs
  └─ writes: _rubric/rules_criteria/item-XX.yaml (25 files)
  └─ writes: _meta/residue-manifest.yaml
  └─ git commit → Epoch B

Step 4: audio2tree Consumer activates
  └─ reads profiles/ + rules_criteria/ at Epoch B
  └─ known_item_mapping now populated → can distinguish known vs unknown patterns
  └─ unknown_unknown_gating rules become meaningful

Step 5: Argus evaluates
  └─ pins Epoch B
  └─ reads rules_criteria/ (compiled Items)
  └─ reads evidence/ (measurement instruments)
  └─ reads calls/ (transcriptions)
  └─ scores calls, emits findings

Step 6: Feedback loop runs
  └─ audio2tree Consumer discovers unknown patterns
  └─ Human reviews → approves lexicon updates or new Items
  └─ 9003 recompiles affected Items → Epoch C
  └─ Argus re-pins to Epoch C
  └─ Cycle repeats
```

---

## Key insights

### 1. audio2tree is the INTENTS tree's primary producer; 9003 is a specialized sub-producer

audio2tree creates the tree skeleton (evidence, profiles, calls, epoch) and populates the domain hierarchy with behavioural data. 9003 adds exactly one thing: compiled rubric nodes under `_rubric/rules_criteria/`. This means the INTENTS tree can exist without the compiler (it just won't have machine-evaluable criteria), but the compiler cannot run without the tree (it needs evidence/ to reference).

### 2. The pinned_sha is the decoupling mechanism

audio2tree can advance the evidence tree at its own cadence (every new call batch, every lexicon update). 9003 compiles at a specific SHA and Items are frozen at that SHA. Argus evaluates at the compile-time SHA. No system blocks another. The cost is that Items don't automatically benefit from new evidence — recompilation is explicit and human-triggered.

### 3. The feedback loop is a GAN in slow motion

audio2tree (Generator equivalent) produces unknown-unknown discoveries. Human review (Discriminator equivalent) validates or rejects them. 9003 (Generator) incorporates approved discoveries into the rubric. The loop is adversarial in structure but human-paced in tempo — unlike the Patch-2 compiler's automated GAN loop, this one has a human in the critical path.

### 4. The missing link: `_rubric/gates/` and `_rubric/profiles/`

The _demo tree is missing `_rubric/profiles/` (the shared measurement contract between Argus and audio2tree Consumer) and has `_rubric/gates/` with no defined producer. These are the two most important structural fixes needed in the _demo tree to accurately reflect the three-system relationship.

---

## Cross-references

- `docs/retrospectives/audio2tree-pipeline.md` — full audio2tree pipeline walkthrough
- `docs/retrospectives/soft-criteria-authoring-spec-v4-patch-2.md` — 9003 compiler GAN architecture
- `docs/retrospectives/measurement-profiles-design.md` — shared measurement infrastructure (D13-D18)
- `docs/design-docs/argus/expertise-decision-log.md` — dual-consumer architecture, embed-vs-reference decisions
- `docs/references/platform-architecture.md` — three-tier platform (transformation / semantic / consumer)
- `docs/adr/0003-knowledge-calibration-dissolves-to-write-time-ownership.md` — write-time ownership, ADR-0003 exception for compiler
- `INTENTS/_demo/structure-demonstration.md` — the tree blueprint (reviewed adversarially)
- `INTENTS/EPOCH.yaml` — current epoch state (placeholder)

---

## Changelog

| Date | Change | Source |
|------|--------|--------|
| 2026-07-17 | Relationship map created. Material flow table (who writes/reads each INTENTS path). Forward dependency chain with boot sequence. Versioning/epoch model with pinned_sha decoupling. Feedback loop mechanics (audio2tree → 9003). _demo structure audit (what's right, what's wrong). Cold-start-to-first-evaluation operational sequence. Three key insights. | Cross-referencing audio2tree-pipeline.md, structure-demonstration.md adversarial review, patch-2 GAN architecture, expertise-decision-log.md, ADR-0003 |
