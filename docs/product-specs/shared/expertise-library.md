---
verification-status: proposed
last-reviewed: 2026-07-04
consumed-by: Argus (Metis and Hermes via interface reference)
---

# Expertise Library (shared)

The expertise content consumed by Argus during fact-checking. The library is a **runtime artefact** — the on-disk INTENTS tree read by the INTENTS Provider (`argus.io`) at a pinned git SHA. It is not a code domain. See ADR-0004 for the dissolution of the v1 Expertise Library domain and ADR-0001 for the epistemic classification.

The library is **read-only at runtime**. Argus reads; no application writes. Updates to expertise content happen through the transformation layer's build pipeline (`audio2tree`, `doc2graph`), with human approval gates, and are committed to the INTENTS tree as git history.

## Epistemic classes

The expertise modules are classified into three epistemic classes, named by *how the knowledge is obtained and what kind of evidence supports it*. See ADR-0001 for the full rationale.

| Class | Epistemic basis | Modules | Consumer rule |
|---|---|---|---|
| **Versioned rubric** | Authored and versioned by domain experts; the yardstick against which facts are measured. Changes are gated (human review). | Rules & Criteria, Acoustic Feature (indicator framework), Phrase & Keyword (lexicon) | Pinned by rubric version; `score()` reads the rubric at the version declared in config |
| **Descriptive facts** | Authored and versioned by domain experts; describe what exists, not what to measure. Changes are gated. | Product Introduction, Operation Manual, Dynamic Knowledge Base | Read at the pinned INTENTS SHA; `score()` reads facts as context, not yardstick |
| **Accumulated history** | Grows at runtime from scored calls; each entry is anchored to a specific L3 case node in the INTENTS tree. Changes are additive (new precedents append; overrides supersede with attribution). | Best Practice Cookbook, Error Case Library | Read at the pinned INTENTS SHA; consumed by `adjust()`, never by `score()` |

**Audio Transcription** is not a library module — it is a per-call input artefact produced by the transformation layer and consumed as `facts` by `score()`. It belongs to no epistemic class.

### The reclassification

Acoustic Feature and Phrase & Keyword move from "descriptive facts" (v1 framing) to **versioned rubric**. The reasoning:

- The **acoustic indicator framework** (pitch range thresholds, pause-duration buckets, intensity floors, voice-quality metrics) is a measurement instrument — it defines *what to measure and how to interpret the measurement*. Per-call acoustic measurements (this call's mean pitch, this call's pause distribution) remain facts in the call record. The framework is the yardstick; the per-call measurements are the thing measured.
- The **phrase & keyword lexicon** (sensitive-word lists, negative-phrase patterns, recommended-phrase alternatives, ASR biasing terms) is a list of *what to look for* — it defines the target set. Per-call phrase matches ("word X appeared 3 times at turns 5, 12, 47") remain facts in the call record. The lexicon is the yardstick; the per-call matches are the thing measured.

This is the measurement-versus-yardstick distinction: facts are measurements taken during a specific call; rubric is the framework that gives those measurements meaning. Confusing the two would mean changing the yardstick changes history — but changing the yardstick should change *future scoring*, not past facts.

## Consumer matrix

| Module | Argus | Epistemic class | INTENTS location | Update cadence |
|---|---|---|---|---|
| Rules & Criteria | ✓ | Versioned rubric | `_rubric/rules/` | low (rules ship in policy releases) |
| Acoustic Feature (framework) | ✓ | Versioned rubric | `_rubric/acoustic/` | low (model versions) |
| Phrase & Keyword (lexicon) | ✓ | Versioned rubric | `_rubric/phrase-keyword/` | medium (sensitive/negative word lists; ASR lexicon biasing) |
| Product Introduction | ✓ | Descriptive facts | `<domain>/<case>/kb.*.yaml` | medium (product changes) |
| Operation Manual | ✓ | Descriptive facts | `<domain>/<case>/kb.*.yaml` | medium (manual updates) |
| Dynamic Knowledge Base | ✓ | Descriptive facts | `<domain>/<case>/kb.*.yaml` | high (FAQ, current policies) |
| Best Practice Cookbook | ✓ | Accumulated history | `<domain>/<case>/cookbook.*.yaml` | medium (curated examples) |
| Error Case Library | ✓ | Accumulated history | `<domain>/<case>/errors.*.yaml` | high (self-learning loop from reviewer overrides) |
| Audio Transcription | ✓ | N/A — per-call artefact | N/A | per-call (output of `audio-intake.md`) |

Metis and Hermes are not domains in this repo; they consume Argus findings via interface references, not expertise modules directly. The v1 consumer matrix's Metis and Hermes columns are removed.

## Category readers

The v1 design exposed each module through a dedicated typed reader interface (seven readers plus a facade). In the v6 design, there are **three category readers** — one per epistemic class — implemented as methods on the INTENTS Provider (`argus.io`):

```
RubricReader    → reads the _rubric/ shelf at the pinned rubric version
                  Returns: RulesAndCriteria, AcousticFramework, PhraseLexicon
FactsReader     → reads anchored kb.*.yaml files at the pinned INTENTS SHA
                  Returns: list[FactRecord] (product intro, manual, knowledge base)
HistoryReader   → reads anchored cookbook.*.yaml and errors.*.yaml at the pinned INTENTS SHA
                  Returns: list[HistoryRecord] (best practices, error cases)
```

The three readers map to the three epistemic classes, not the nine modules. The granularity of the v1 interfaces was an artefact of the flat module list; the v6 design groups by epistemic class because that is what `score()` and `adjust()` actually consume. See ADR-0004.

## Update mechanisms

Each epistemic class has a different update path because each has different consequences:

**Versioned rubric** (Rules & Criteria, Acoustic Framework, Phrase Lexicon): human-authored, gated. Updates ship as versioned releases; the rubric version is pinned in Argus config. Changing the rubric version changes future scoring only — past verdicts cite the rubric version they were scored against.

**Descriptive facts** (Product Introduction, Operation Manual, Dynamic Knowledge Base): human-authored, gated. Updates are committed to the INTENTS tree. The INTENTS SHA is pinned in Argus config; a SHA bump picks up new facts. Facts do not change scoring logic — they change the context `score()` evaluates against.

**Accumulated history** (Best Practice Cookbook, Error Case Library): additive, with human approval gate. New best-practice entries and error-case entries append to the tree; overrides supersede with `superseded-by` attribution. The Error Case Library's runtime-fed update path (reviewer overrides → batched → human-approved → committed to tree) is preserved from v1. The approval gate prevents a runtime feedback loop.

## Failure modes and tolerances

**Tree read fails at runtime**: Argus fails closed — do not score; mark the call `requires-review`. The INTENTS Provider returns typed null-or-result; no exceptions for control flow.

**Rubric version not found**: the Provider returns an error shape. Argus refuses to score — scoring without a pinned rubric version is forbidden.

**History not found for a case**: `adjust()` receives an empty history list. This is not an error — new cases have no history by definition. The raw score stands unadjusted.

## Forbidden behaviours

No runtime writes. No silent merging of conflicting expertise versions. No stripping of version metadata from reader returns (every read carries the version of the source it came from; downstream uses that for evidence-citing in audit trails). No scoring without a pinned rubric version.

## Tiebreaker references

- ADR-0001 — epistemic classification and two-stage `score`→`adjust` contract.
- ADR-0002 — INTENTS path-as-ontology and git-SHA epoch.
- ADR-0004 — Expertise Library dissolution; nine interfaces collapse to one Provider with three category readers.
- `PRODUCT_SENSE.md § Argus` — failure tolerance "score without traceable evidence is a release blocker."
- `docs/product-specs/argus/fact-checking.md` — the two-stage evaluation contract.
- `docs/product-specs/shared/intents-semantic-layer.md` — the INTENTS tree layout and naming grammar.
