---
verification-status: proposed
last-reviewed: bootstrap
consumed-by: KnowledgeCalibration, Argus, Metis
---

# Conversation Distillation (shared, bottom-up)

The bottom-up pipeline. Takes structural transcription, deconstructs each customer turn into self-contained atomic claims, and synthesises a 2-to-3 level intents-tree. This is the **authoritative source of behavioural truth** in the system; the architectural invariant in `PRODUCT_SENSE.md § Cross-product` and `ARCHITECTURE.md § 3` rests on the output of this domain.

## User job

Transform 100k non-structured support-call transcriptions into a structured library of **Atomic Claims** and a **Bottom-up Intent Tree** that acts as a buffer and bridge to the Top-down Computation Graph, ultimately eliminating semantic drift between colloquial customer language and official documentation.

The downstream user is Knowledge Calibration; the indirect users are Argus (which uses the intents-tree for fact-checking against rules), Metis (which clusters atomic claims to surface emerging issues), and Hermes (which consumes the *calibrated* graph that this domain's output shapes).

## Acceptance behaviour

Given a corpus of structural transcriptions, the system produces:

**A library of atomic claims**, each satisfying:
- **Single proposition**: one logically complete and independent statement.
- **De-contextualised**: pronouns ("it", "this") replaced with specific business entities ("the U-Key driver", "the SSL certificate"). Each claim must remain factually accurate when isolated from its source conversation.
- **Not a Q&A pair**: claims are propositions, not exchanges. A customer's question becomes a claim about what the customer wanted to know; an agent's answer becomes a claim about what the agent asserted.
- **Source-cited**: every claim links back to its source transcription segment(s). Claims without source citations are forbidden — the entire `PRODUCT_SENSE.md § Argus` evidence-citation requirement collapses if claims float free of their sources.

**A 2-to-3 level intents-tree**, where:
- **Level 1**: broad business categories (e.g., *Annual Report Submission*).
- **Level 2**: process stages or policy types (e.g., *Late Filing Penalties*).
- **Level 3**: specific intent nodes (e.g., *Requirements for evidence of system failure during late filing*).
- The tree is **stable across regenerations**: when new claims arrive, existing intent nodes are preserved when possible; new nodes are added rather than the whole tree being re-clustered. Stability is what makes the intents-tree usable as a calibration target.

A reviewer reading a level-3 intent node can:
1. See the claims that populate it.
2. See the source transcription segments those claims came from.
3. Trust that the same node will exist (with possibly more claims) after the next ingest cycle.

## Pipeline shape

```
StructuralTranscription corpus
  → Atomic Claim Extraction (per-turn, per-call)
  → De-contextualisation (resolve pronouns, expand references)
  → Source-citation linking (every claim → its segment(s))
  → Hierarchical Clustering (semantic, with stability constraints)
  → Intent Tree Construction (2-to-3 levels)
  → IIntentTreeSource published
```

## Interfaces produced

`IIntentTreeSource` — declared in `ConversationDistillation/Types`, consumed by `KnowledgeCalibration`.
`IIntentTreeReader` — read-only view consumed by Argus and Metis.

```
IntentTree = {
  rootNodes: IntentNode[],         // level-1 nodes
  generationId: string,            // monotonic; downstream consumers cache against this
  generatedAt: Timestamp,
}
IntentNode = {
  id: IntentNodeId,                // stable across generations when possible
  label: string,
  level: 1 | 2 | 3,
  children: IntentNode[],          // empty at level 3
  claims: AtomicClaim[],           // populated only at level 3
  parentId: IntentNodeId | null,
}
AtomicClaim = {
  id: ClaimId,
  text: string,                    // de-contextualised
  sources: SegmentRef[],           // back to AudioIntake segments
  extractedAt: Timestamp,
}
```

## The stability constraint

This is the contract that makes the intents-tree useful. Without it, every regeneration would shift node IDs and the calibration step in `KnowledgeCalibration` would be reduced to fuzzy re-matching every cycle.

The constraint: when a regeneration produces a tree that semantically resembles the prior tree, node IDs are preserved. Specifically: if a node's claims set overlaps the prior generation's node by more than a threshold (initial default: Jaccard ≥ 0.5), the prior node's ID is reused; otherwise a new ID is minted and the prior ID is moved to `archived` state in the Repo.

Mechanical enforcement: `intent-tree-stability` test that runs the pipeline twice on the same input and asserts ID preservation; runs the pipeline on input + 10% new claims and asserts that ≥ 90% of prior IDs are preserved. Fails CI on regression.

## Failure modes and tolerances

**Claims with unresolved pronouns**: the de-contextualisation step failed. Flag the claim as `unresolved` and exclude from clustering. Downstream consumers may filter on this flag. Bulk unresolved claims signal a regression in the de-contextualisation logic and trigger a doc-gardener alert.

**Claims clustered into ambiguous level-3 nodes**: a level-3 node containing claims that span multiple distinct intents. Detected by intra-node semantic variance above a threshold; flag the node as `requires-split` for offline review. Hermes refuses to consume `requires-split` nodes; Argus and Metis warn on use.

**A previously stable intent node disappears**: a regeneration in which a node's claims set fell below the stability threshold. The node is moved to `archived` rather than deleted; calibration logic in `KnowledgeCalibration` decides whether the corresponding compute-graph nodes follow.

## Forbidden behaviours

This domain does not interpret claims for product decisions. It produces the structured library; Argus/Metis/Hermes interpret. Adding business logic here (e.g., severity scoring of claims) would couple the bottom-up authority to a specific consumer's needs.

This domain does not consume the compute-graph or the calibrated graph. The dependency direction is one-way: distillation feeds calibration; calibration does not feed distillation. (`ARCHITECTURE.md § 3` dependency matrix enforces this — there is no edge from this domain to Calibration's outputs.)

## Tiebreaker references

- `PRODUCT_SENSE.md § Cross-product` — bottom-up authority.
- `PRODUCT_SENSE.md § Argus` — evidence-citation requirement (claims must link to sources).

## Open questions

> **Question**: What is the threshold for hierarchical clustering's level-1 / level-2 / level-3 split? The bottom-up spec calls for "abstract, intuitive theme clusters" without a quantitative criterion.
> **Default if not decided**: silhouette-coefficient-driven cut at each level, with manual review of the cuts on the bootstrap corpus before they are accepted as the production thresholds. Treat this as `Confidence: low` until empirical results land.
> **Decided by**: M2 of the first Conversation Distillation exec-plan.

> **Question**: How are claims that contradict each other (one customer says X, another says ¬X) handled in the tree? They cluster into the same intent node but disagree on the answer.
> **Default if not decided**: claims are surfaced in the same node with a `contradiction` flag on the node; downstream consumers (Argus most relevantly) decide how to surface the contradiction. Calibration's bottom-up-authoritative rule means contradictions are not resolved by the tree itself — they are evidence that reality diverges from the official compute-graph and the divergence is the signal.
