---
verification-status: proposed
last-reviewed: bootstrap
consumed-by: Argus, Metis, Hermes, ExpertiseLibrary
---

# Knowledge Calibration (shared)

Where the bottom-up intents-tree (from `conversation-distillation.md`) and the top-down compute-graph (from `document-ingestion.md`) meet, reconcile, and produce the **calibrated graph** that Argus, Metis, and Hermes consume.

This domain encodes the single most important architectural commitment in the system: **the bottom-up intents-tree is authoritative**. When the two inputs disagree, the intents-tree wins; the compute-graph is updated to match. The reason is stated in `PRODUCT_SENSE.md § Cross-product` — support calls are the behaviour corpus from human agents performing real work; operation manuals are documentation, which is always partial and frequently stale. Documentation calibrates against reality, not the other way around.

## User job

Produce a single calibrated knowledge artefact that downstream apps can use without choosing between conflicting sources. The user is the platform itself; the indirect users are Argus reviewers (who need fact-checking against a single source), Metis analysts (who need to surface the divergences as documentation gaps), and Hermes citizens (who need procedural steps that match what real people actually do).

## Acceptance behaviour

Given an `IIntentTreeSource` and an `IComputeGraphSource`, the system produces a `CalibratedGraph` with the following observable properties:

**Mappings preserved.** Every level-3 intent node in the intents-tree that corresponds to one or more operators in the compute-graph carries an `intentMapping` linking the two. A reviewer can take a level-3 intent ("Requirements for evidence of system failure during late filing") and traverse to the matching operators.

**Divergences logged.** When an intent node has no corresponding operator (the customer voice describes a procedure the manual does not document), the intent is flagged `manual-gap`. When an operator has no corresponding intent (the manual describes a procedure no customer ever asks about), the operator is flagged `unused-by-customers`. Neither flag is a defect — they are signals fed to Metis.

**Contradictions resolved bottom-up.** When an intent node and a compute-graph operator both exist for the same business step but disagree on prerequisites, terminal state, or platform, the intent's claims set is treated as authoritative. The operator is updated to reflect the claims. The pre-update operator is preserved in graph history with a `superseded-by-calibration` annotation. A reviewer can audit the change.

**Generation-stable.** Each `CalibratedGraph` carries a `generationId` that increases monotonically. Downstream Argus / Metis / Hermes cache against this ID; a new generation invalidates downstream caches. The intent-tree's stability constraint (`conversation-distillation.md`) propagates: when the intents-tree preserves IDs across regenerations, the calibrated graph preserves the corresponding calibrated-operator IDs.

## The bottom-up authority invariant

This is the contract that all three downstream apps depend on. It is encoded at four levels:

**1. Type-level.** The calibration function's signature is asymmetric:

```
calibrate(intentTree: IntentTree, computeGraph: ComputeGraph): CalibratedGraph
```

There is no symmetric `reconcile(a, b)` form. The function name, parameter order, and return type all encode that the intent tree is the dominant operand. Type aliases that flatten this asymmetry are forbidden by lint `calibration-asymmetric-signature`.

**2. Logic-level.** When the two inputs disagree on a fact, the resolution rule reads the intent-tree's claims and updates the operator; never the inverse. There is no code path in this domain where an operator's prior content overrides intent-tree claims.

**3. Test-level.** A structural test (`bottom-up-authority-invariant`) constructs a deliberately contradictory pair of inputs and asserts the resolution direction. The test fails CI on regression. This test is among the highest-priority deliverables in `0001-bootstrap-the-spine.md` (M4).

**4. Architectural-level.** `ARCHITECTURE.md § 3` dependency matrix has no edge from this domain to `ConversationDistillation` (no write-back to the intent tree). The forbidden-edges lint enforces.

## Pipeline shape

```
IIntentTreeSource  ─┐
                    ├→ Mapping (intent ↔ operator)
IComputeGraphSource ┘     │
                          ├→ Divergence detection (gap/unused flags)
                          │
                          ├→ Contradiction resolution (intent-authoritative)
                          │
                          └→ CalibratedGraph published
```

## Interfaces produced

`ICalibratedGraphReader` — declared in `KnowledgeCalibration/Types`, consumed by Argus, Metis, Hermes, and the Expertise Library Repo.

```
CalibratedGraph = {
  generationId: string,                // monotonic
  generatedAt: Timestamp,
  intentTreeRef: { generationId: string },
  computeGraphRef: { graphId: string },
  calibratedOperators: CalibratedOperator[],
  intentMappings: IntentMapping[],
  manualGaps: ManualGap[],             // intents with no operator
  unusedOperators: UnusedOperator[],   // operators with no intent
}
CalibratedOperator = {
  baseOperatorId: OperatorId,
  calibratedFromIntent: IntentNodeId | null,
  prerequisites: TensorId[],           // possibly updated from base
  outputs: TensorId[],                 // possibly updated from base
  visualAnchor: VisualAnchorId | null,
  supersededOperator: OperatorId | null,
}
IntentMapping = {
  intentNodeId: IntentNodeId,
  operatorIds: OperatorId[],           // empty → manual-gap
  confidence: 'high' | 'medium' | 'low',
}
ManualGap = {
  intentNodeId: IntentNodeId,
  claimSampleIds: ClaimId[],           // representative claims
  description: string,
}
UnusedOperator = {
  operatorId: OperatorId,
  description: string,
}
```

There is no `ICalibratedGraphWriter` exposed to anything other than this domain itself. Downstream apps cannot write back. Hermes specifically cannot extend the graph at runtime — see `hermes/action-execution.md` for the refuse-and-log behaviour.

## Failure modes and tolerances

**Mapping ambiguity**: an intent node maps to multiple plausible operators with similar confidence. Surface all candidates with `confidence: 'medium'` rather than picking; let downstream consumers handle the multiplicity (Argus may show both rules; Hermes refuses to act on `medium`-confidence mappings without user disambiguation).

**Calibration produces a circular operator graph**: a graph where prerequisites form a cycle. Detected as a structural property of the output. Fail the calibration; emit the prior `CalibratedGraph` as the published artefact and log the regression. Cycles indicate a contradiction the bottom-up rule cannot resolve cleanly (the intent claims X requires Y *and* Y requires X), which is a signal for human review, not a state to ship.

**Mass divergence**: a calibration cycle that produces `manual-gap` flags on more than 50% of intent nodes (configurable threshold). Surface as a system-level alert; do not publish the new generation. This is a heuristic guard against ASR / extraction regressions cascading into bad calibration.

## Forbidden behaviours

No write to the intent tree. No write to the compute graph (the *source* compute graph; the calibrated operators are this domain's own output). No publishing of a calibrated graph that violates the bottom-up rule (the lint and test prevent this; the line here documents the intent for human readers).

No silent fallback to the old generation. If a new generation fails to publish, the failure is surfaced; downstream apps continue using the prior generation but the failure is logged and feeds Metis.

## Tiebreaker references

- `PRODUCT_SENSE.md § Cross-product` — bottom-up authority. This file is the implementation contract for that rule.
- `ARCHITECTURE.md § 3 Three invariants` — the dependency matrix encoding.

## Open questions

> **Question**: What confidence threshold separates `high` / `medium` / `low` mapping confidence?
> **Default if not decided**: derived empirically from the bootstrap corpus during M4 of the first Calibration exec-plan; treat as `Confidence: low` until then.

> **Question**: When a calibration update changes an operator's prerequisites, does Hermes immediately use the updated operator, or wait for an explicit human review of the change?
> **Default if not decided**: Hermes uses the new generation immediately for Tier-A (read-only) actions; for Tier-B (confirmed) actions, the user-facing confirmation surfaces the change ("This step's prerequisites were updated based on customer behaviour — review and confirm"); Tier-C is empty initially per `PRODUCT_SENSE.md § Hermes`.
