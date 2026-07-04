---
verification-status: proposed
last-reviewed: 2026-07-04
domain: argus
layer: core
---

# Argus — Fact-Checking

## Two-stage evaluation contract

Argus fact-checking is a two-stage pipeline. The stages are deliberately separated because they have different inputs, different failure modes, and different purity properties. See ADR-0001 for the full rationale.

```
raw = score(facts, rubric)
adjusted = adjust(raw, history)
```

### Stage 1: `score(facts, rubric)`

`score` receives:

- **`facts`** — the call record: structural transcription frames (per-call, from `audio-intake.md`), per-call acoustic measurements (pitch contour, pause distribution, intensity), and per-call phrase matches. These are measurements taken during a specific call — they are *facts*, not rubric.
- **`rubric`** — the versioned rubric from the INTENTS `_rubric/` shelf at the pinned rubric version: Rules & Criteria (the scoring rules), Acoustic Framework (the indicator thresholds — pitch range floors, pause-duration buckets, intensity minimums), and Phrase Lexicon (the target word/phrase lists). These are the *yardstick* — authored by domain experts, versioned, gated.

`score` produces a **raw verdict** per rule: pass, fail, or requires-review, each with evidence citations anchored to specific transcript turns and rubric entries.

`score` is **pure with respect to history** — it does not receive history as an argument. The raw score depends only on the facts of *this call* and the rubric of *this version*. It is reproducible given the same inputs.

`score` is **pure with respect to I/O** — it receives data and returns a result. The INTENTS tree read and call-record read happen in the `io` layer before `core` is invoked.

### Stage 2: `adjust(raw, history)`

`adjust` receives:

- **`raw`** — the raw verdict from `score`.
- **`history`** — accumulated history records from the INTENTS tree's L3 case nodes: anchored `cookbook.*.yaml` (best practices) and `errors.*.yaml` (error cases). These are precedents — prior overrides, context-specific adjustments, reviewer-established patterns.

`adjust` applies precedents and produces the **adjusted verdict** with `applied_precedents[]` attribution on every adjustment — `{precedent_id, source_node, adjustment, reason}` — so every deviation from the raw score is auditable.

`adjust` is **pure with respect to I/O** — same as `score`, it receives data and returns a result.

### Evidence citation

Ambiguity → `requires-review`, never pass/fail by guess. Every verdict must cite the specific transcript turn, tree node, or rubric entry that supports it. This is non-negotiable and structurally enforced: the `FactCheckVerdict` type has no "no-citation" variant. A verdict with no citation is a release blocker (`PRODUCT_SENSE.md § Argus`).

## Acceptance behaviour

A QA reviewer reading a fact-checking output can:

1. See every rule that was checked.
2. For every fail or requires-review verdict, click through to the transcript turn(s) cited as evidence.
3. For procedural rules, see which operators were expected and which were observed.
4. See every precedent applied by `adjust` — which prior override affected this verdict, and why.
5. Override any verdict; the override feeds the offline error case library update path (accumulated history, `cookbook.*.yaml` / `errors.*.yaml`, anchored to the L3 case node).

## Inputs and outputs

### Inputs to `score`

| Input | Source | Epistemic class |
|---|---|---|
| `StructuralTranscription` | per-call, from `audio-intake.md` | N/A — call artefact |
| `Rubric` (Rules & Criteria, Acoustic Framework, Phrase Lexicon) | INTENTS `_rubric/` shelf, pinned version | Versioned rubric |

### Inputs to `adjust`

| Input | Source | Epistemic class |
|---|---|---|
| `raw` verdict | output of `score` | N/A |
| `History` (Best Practice Cookbook, Error Case Library) | INTENTS tree, L3 case nodes, anchored `cookbook.*.yaml` / `errors.*.yaml` | Accumulated history |

### Output

`FactCheckVerdict` declared in `argus/types`. Required fields:

- `call_id` — unique call identifier
- `rubric_version` — the rubric version `score` ran against
- `intents_sha` — the INTENTS tree SHA
- `per_rule_verdicts[]` — one entry per applicable rule, each with:
  - `rule_id` — which rule from the rubric
  - `raw` — the raw pass/fail/requires-review from `score`
  - `adjusted` — the final pass/fail/requires-review from `adjust` (equals `raw` if no precedents applied)
  - `evidence[]` — citations to transcript spans, rubric entries, and operator IDs
  - `applied_precedents[]` — `{precedent_id, source_node, adjustment, reason}` for each precedent `adjust` applied (empty if none)

## Tiebreakers consumed

- `PRODUCT_SENSE.md § Argus` — evidence-citation is non-negotiable; ambiguity → `requires-review`, never pass-or-fail-by-guess.
- `PRODUCT_SENSE.md § Cross-product` — Argus systemic findings forward to Metis when the threshold is met.
- ADR-0001 — epistemic classification and two-stage `score`→`adjust` contract.
- `docs/product-specs/shared/expertise-library.md` — the three category readers (RubricReader, FactsReader, HistoryReader).

## Open

This file describes the contract `src/argus/core` must satisfy. The actual implementation — the rule-evaluation engine, the precedent-matching logic in `adjust`, and the override pipeline — is deferred to the first Argus exec-plan. Owner: not yet assigned.
