---
verification-status: proposed
last-reviewed: 2026-07-04
consumed-by: Argus (Metis and Hermes via interface reference)
---

# Calibration — Bottom-Up Authority and Two-Axis Validation

Calibration is the process that ensures the INTENTS tree (from support-call audio, via `audio2tree`) and the compute graph (from operation manuals, via `doc2graph`) produce a single, coherent knowledge artefact. It is performed at **build time** by the transformation layer, not at runtime by Argus. See ADR-0003 for the dissolution of Knowledge Calibration as a runtime domain.

The single most important architectural commitment remains: **the bottom-up intents-tree is authoritative**. When the two inputs disagree, the intents-tree wins; the compute-graph is updated to match. Support calls are the behaviour corpus from human agents performing real work; operation manuals are documentation, which is always partial and frequently stale. Documentation calibrates against reality, not the other way around.

## Where calibration happens

Calibration is a **build-time operation** performed by the transformation layer (not this repo — see `docs/references/platform-architecture.md`). The output is the INTENTS tree itself: a committed, git-versioned, already-reconciled artefact. Argus reads the tree at a pinned SHA; there is no runtime reconciliation step. The tree *is* the calibrated output.

This is why the v1 Knowledge Calibration domain dissolves (ADR-0003): the consumer never sees two conflicting sources. The build pipeline resolves conflicts before commit.

## Two axes of calibration

Calibration operates on two independent axes. They are separated because they have different detection mechanisms, different severities, and different consumers.

### Coverage axis: what exists vs. what is documented

**Question**: does every intent have a matching operator, and does every operator have a matching intent?

| Condition | Flag | Meaning | Consumer |
|---|---|---|---|
| Intent with no operator | `manual-gap` | Customers describe a procedure the manual doesn't document | Metis (documentation gap ticket) |
| Operator with no intent | `unused-by-customers` | The manual describes a procedure no customer ever asks about | Metis (cleanup candidate); not an error |

Detection: structural — walk the intent tree's L3 nodes and the compute graph's operator set; for each intent, check if `intentMapping` resolves; for each operator, check if any intent maps to it.

Threshold: `manual-gap` on >50% of intents is a mass-divergence alert. Do not publish; surface for human review. This guards against ASR/extraction regressions.

### Content axis: when both exist, do they agree?

**Question**: when an intent and an operator describe the same business step, do they agree on prerequisites, terminal state, and platform details?

| Condition | Action |
|---|---|
| Agreement | No flag; operator carries `calibratedFromIntent` reference |
| Disagreement | Intent claims are authoritative. Operator is updated; pre-update operator preserved with `superseded-by-calibration` annotation |

Detection: semantic — for each `intentMapping`, compare the intent's claims against the operator's fields (prerequisites, outputs, terminal state). This is the bottom-up-authority rule in operation.

### The INTENTS representation

The calibrated output is the INTENTS tree. Every divergence, gap, and resolution is recorded in the tree:

- **`manual-gap`** — annotated on the L3 case node's `context.yaml`; the intent is preserved but flagged
- **`unused-by-customers`** — annotated on the operator's definition in the compute graph; surfaced to Metis, not to Argus
- **`superseded-by-calibration`** — the pre-update operator is preserved in the compute graph's history; the updated operator carries a `calibratedFromIntent` reference to the L3 node that drove the change
- **`intentMapping`** — L3 case nodes carry `intentMapping` linking to operator IDs; this is the primary traversal path from tree to graph

## The bottom-up authority invariant

This contract is encoded at four levels:

**1. Type-level.** The calibration function's signature is asymmetric:

```
calibrate(intentTree: IntentTree, computeGraph: ComputeGraph): CalibratedGraph
```

There is no symmetric `reconcile(a, b)` form. The function name, parameter order, and return type all encode that the intent tree is the dominant operand. Type aliases that flatten this asymmetry are forbidden by lint `calibration-asymmetric-signature`.

**2. Logic-level.** When the two inputs disagree, the resolution rule reads the intent-tree's claims and updates the operator; never the inverse. There is no code path where an operator's prior content overrides intent-tree claims.

**3. Test-level.** `tests/test_calibration_invariants.py::test_bottom_up_authority` constructs contradictory inputs and asserts resolution direction.

**4. Architectural-level.** `ARCHITECTURE.md § 3` — the dependency matrix encodes the authority direction. The intents tree is the authoritative source; the compute graph is a build-time input, not a peer at read time.

## Pipeline shape (build time)

```
IIntentTreeSource  ─┐
                    ├→ Coverage-axis check (gap/unused flags)
IComputeGraphSource ┘     │
                          ├→ Content-axis check (agreement/disagreement per mapping)
                          │
                          ├→ Contradiction resolution (intent-authoritative)
                          │
                          └→ INTENTS tree committed (tree IS the calibrated output)
```

## Interfaces

The v1 `ICalibratedGraphReader` is replaced by the INTENTS Provider (`argus.io`). There is no separate calibrated graph to read — the tree is the graph. The Provider exposes typed reads:

- `read_rubric(sha, module, version)` → `RubricModule`
- `read_facts(sha, domain, case)` → `list[FactRecord]`
- `read_history(sha, domain, case)` → `list[HistoryRecord]`

See ADR-0004 for the interface collapse from nine v1 readers to one Provider with three category reads.

## Acceptance behaviour

Given an `IIntentTreeSource` and an `IComputeGraphSource`, the build pipeline produces an INTENTS tree commit with:

- **Mappings preserved** — every L3 intent node carries `intentMapping` linking to operators
- **Divergences logged** — `manual-gap` and `unused-by-customers` flags on affected nodes
- **Contradictions resolved bottom-up** — intent claims authoritative; pre-update operator preserved with `superseded-by-calibration`
- **Generation-stable** — each tree commit carries the SHA as the generation identifier; downstream consumers pin against it

## Failure modes

**Mapping ambiguity**: an intent node maps to multiple plausible operators. Surface all candidates with `confidence: 'medium'`; downstream consumers handle multiplicity (Argus may show both rules; Hermes refuses to act on medium-confidence mappings without disambiguation).

**Circular operator graph**: prerequisites form a cycle. Fail calibration; keep the prior tree generation; log the regression. Cycles indicate a contradiction the bottom-up rule cannot resolve cleanly.

**Mass divergence**: `manual-gap` on >50% of intents. Alert; do not publish. Heuristic guard against ASR/extraction regressions.

## Forbidden behaviours

No runtime writes to the INTENTS tree. No silent fallback to prior generation without surfacing the failure. No publishing of a tree that violates the bottom-up rule.

## Tiebreaker references

- `PRODUCT_SENSE.md § Cross-product` — bottom-up authority.
- ADR-0003 — calibration dissolution; build-time resolution.
- ADR-0002 — INTENTS path-as-ontology; the tree is the calibrated output.
- `ARCHITECTURE.md § 3` — dependency matrix encoding.

## Open questions

> **Question**: What confidence threshold separates `high` / `medium` / `low` mapping confidence?
> **Default if not decided**: derived empirically from the bootstrap corpus; treat as `Confidence: low` until then.
