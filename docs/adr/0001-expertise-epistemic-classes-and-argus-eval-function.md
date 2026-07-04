# ADR-0001: Expertise Epistemic Classes and Argus Evaluation Function

**Status:** accepted

**Date:** 2026-07-04

## Context

The v1 expertise-library spec listed nine expertise modules in a flat consumer matrix without distinguishing *how* each module knows what it claims. Different modules rest on fundamentally different kinds of evidence — acoustic measurements are machine-extracted features, operational procedures are authored documentation, error cases are accumulated runtime observations — and treating them as uniform "facts" misrepresents their epistemic weight to the scoring engine.

At the same time, the v1 fact-checking spec framed Argus evaluation as a single function: "score every call against active Rules & Criteria." This elides a critical step. Facts are scored against rubric, then the raw score is adjusted by history (precedents, prior overrides, context from the anchored case). These are two distinct operations with different inputs and failure modes.

This ADR establishes the epistemic classification and the two-stage contract as the standing architecture for Argus scoring.

## Decision

### Epistemic classes

The nine expertise modules are classified into three epistemic classes, named by *how the knowledge is obtained and what kind of evidence supports it*:

| Class | Epistemic basis | Modules | Consumer rule |
|---|---|---|---|
| **Versioned rubric** | Authored and versioned by domain experts; the yardstick against which facts are measured. Changes are gated (human review). | Rules & Criteria, Acoustic Feature (indicator framework), Phrase & Keyword (lexicon) | Pinned by rubric version; Argus reads the rubric at the version declared in config |
| **Descriptive facts** | Authored and versioned by domain experts; describe what exists, not what to measure. Changes are gated. | Product Introduction, Operation Manual, Dynamic Knowledge Base | Read at the pinned INTENTS SHA; treated as context, not yardstick |
| **Accumulated history** | Grows at runtime from scored calls; each entry is anchored to a specific L3 case node in the INTENTS tree. Changes are additive (new precedents append; overrides supersede with attribution). | Best Practice Cookbook, Error Case Library | Read at the pinned INTENTS SHA; consumed by `adjust()`, never by `score()` |

**Audio Transcription** (module 9) is not a library module — it is a per-call input artefact produced by the transformation layer and consumed as `facts` by `score()`. It does not belong to any epistemic class.

The key reclassification this ADR makes: **Acoustic Feature** and **Phrase & Keyword** move from "descriptive facts" to "versioned rubric." The acoustic indicator framework (pitch range thresholds, pause-duration buckets, intensity floors) is a measurement instrument, not a measurement. The phrase-keyword lexicon is the list of things to look for, not the things found in a particular call. Per-call acoustic measurements and per-call phrase matches remain facts in the call record; the framework and the lexicon are the yardstick.

### Two-stage Argus evaluation contract

```
raw = score(facts, rubric)
adjusted = adjust(raw, history)
```

- **`score`** receives `facts` (from the call record: structural transcription frames, per-call acoustic measurements, per-call phrase matches) and `rubric` (from the INTENTS `_rubric/` shelf at the pinned version: rules & criteria, acoustic indicator framework, phrase-keyword lexicon). It produces a `raw` verdict per rule — pass, fail, or requires-review — each with evidence citations anchored to specific transcript turns.
- **`adjust`** receives the `raw` verdict and `history` (from the INTENTS tree's L3 case nodes: anchored `cookbook.*` and `errors.*` records). It applies precedents — prior overrides, context-specific adjustments, reviewer-established patterns — and produces the `adjusted` verdict with `applied_precedents[]` attribution on every adjustment.
- **`history` is never an argument to `score()`.** The raw score is pure with respect to history. This preserves the property that `score` only depends on the facts of *this call* and the rubric of *this version* — it is reproducible given the same inputs.
- **`adjusted` carries `applied_precedents[]`** — a list of `{precedent_id, source_node, adjustment, reason}` records — so every deviation from the raw score is auditable.
- **Both stages are pure** with respect to I/O. They receive data and return results. External reads (INTENTS tree, call record) happen in the `io` layer before `core` is invoked.

### Evidence citation

Ambiguity → `requires-review`, never pass/fail by guess. Every verdict must cite the specific transcript turn, tree node, or rubric entry that supports it. This is non-negotiable and is enforced structurally: the `FactCheckVerdict` type has no "no-citation" variant.

## Consequences

- The `score` function signature explicitly separates `facts` from `rubric` — two arguments, not one combined input.
- The `adjust` function signature explicitly receives `history` — which `score` never sees.
- Acoustic Feature and Phrase & Keyword readers move from the facts-input pipeline to the rubric-input pipeline.
- The v1 flat consumer matrix in `expertise-library.md` is replaced by the three-category-reader grouping.
- The `FactCheckVerdict` shape must carry `raw`, `adjusted`, and `applied_precedents` fields.
- Any future Argus scoring implementation must satisfy this contract; it is testable as a structural invariant (see `tests/test_argus_eval_contract.py`).
