# Handoff: Expertise Decision Log — #6-#8

**From:** Session 2026-07-16
**To:** Next session
**Pick up at:** `docs/design-docs/argus/expertise-decision-log.md`

---

## Where we are

Recording one decision per expertise type: embed in compiled Item YAML, or reference as a standalone file in the INTENTS tree. Three judgment criteria: update frequency, sharing scope, content nature.

## What's been decided (#1-#5)

| # | Expertise | Strategy | INTENTS Location |
|:--|:---|:--:|:---|
| 1 | Rules & Criteria | N/A (compiler output) | `_rubric/rules_criteria/` |
| 2 | Acoustic Feature | **Reference** | `_rubric/acoustic/` |
| 3 | Phrase & Keyword — Layer 1 (shared lexicons) | **Reference** | `_rubric/phrase-keyword/` |
| 3 | Phrase & Keyword — Layer 2 (Item-specific vocab) | **Embed** | Item YAML inline |
| 3 | Phrase & Keyword — Layer 2 (reference corpus) | **Reference** | `_rubric/phrase-keyword/marketing-scripts.yaml` |
| 4 | Product Introduction | **Reference** | `<L1>/产品知识/<L3>/index.md` |
| 5 | Operation Manual | **Reference** | `<L1>/操作规范/<L3>/index.md` |

## What remains (#6-#8)

| # | Expertise | Epistemic class | INTENTS location (per ADR-0004) |
|:--|:---|:---|:---|
| 6 | Dynamic Knowledge Base | Descriptive facts | `<domain>/<case>/kb.*.yaml` (but may be Context-Engineering `index.md`) |
| 7 | Best Practice Cookbook | Accumulated history | `<domain>/<case>/cookbook.*.yaml` |
| 8 | Error Case Library | Accumulated history | `<domain>/<case>/errors.*.yaml` |

#7 and #8 are most likely **reference** — they are consumed via severity_map by the Calibration Manifest (independent channel per spec §0.5), possibly by both Argus and audio2tree. But this needs verification against the actual data flow.

Key question for #7/#8: are they consumed **indirectly** (severity_map references from Calibration Manifest → no compiler action needed) or **directly** (Item YAML contains a path reference)?

## Key files in harness-cli

```
docs/design-docs/argus/
  expertise-decision-log.md          ← canonical record (read this first)
  measurement-profiles-design.md     ← D13-D18, profile schema, dual-consumer architecture
  phrase-keyword-decision-log.md     ← superseded by expertise-decision-log.md (#3)
  product-intro-op-manual-decision-log.md ← superseded

docs/PRD/
  Context-Engineering.md             ← §5: Operation Manual L1→L2→L3 hierarchy

docs/adr/
  0001-*.md                          ← epistemic classification
  0002-intents-path-as-ontology.md   ← path-as-ontology, bottom-up authority
  0004-expertise-library-*.md        ← 9→3 category readers

docs/retrospectives/                ← (in argus repo — read-only reference)
  soft-criteria-authoring-spec-v4-patch-1.md   ← D1-D12
  soft-criteria-authoring-spec-v4-patch-2.md   ← S1-S6
  营销触发-reconciled.yaml                     ← 11 unified triggers, 16 marketing scripts
```

## Architecture to keep in mind

Two consumers of the same INTENTS data:
- **Argus** (top-down): 25 rubric Items → known unknowns
- **audio2tree** (bottom-up): data emergence → unknown unknowns → feedback to Argus

This is why "reference" dominates — shared data must not be copied.

## Per CLAUDE.md

First action on next session: read the most recent ExecPlan. Read Surprises & Discoveries first. Read `docs/PLANS.md` rubric. Read `docs/conventions/` files before any non-trivial work.
