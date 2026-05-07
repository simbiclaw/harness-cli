---
verification-status: proposed
last-reviewed: bootstrap
consumed-by: KnowledgeCalibration
---

# Document Ingestion (shared, top-down)

The top-down pipeline. Takes operation manuals and standard operating procedures (SOPs) — Word and PDF documents with mixed text-and-image and visual annotations — and reverse-engineers them into a **Tensor-Operator DAG** (Computational Graph) capable of supporting path planning, fault diagnosis, and dynamic routing.

The output of this domain feeds Knowledge Calibration; the calibrated graph then feeds Argus and Hermes.

## User job

Transform "human-readable" manuals into "AI-readable" structural logical maps. The downstream user is Knowledge Calibration. The indirect user is the citizen Hermes serves: every Hermes procedural step ultimately traces back to an operator in this graph.

## Acceptance behaviour

Given an operation manual (Word, PDF), the system produces a Tensor-Operator DAG with the following observable properties. A successful ingestion enables a downstream agent to answer four questions, each of which becomes a test case:

**1. Path planning (happy path)**: "Complete business XX." Output: the full sequence of operators from initial state to terminal state. Test: every supported business in the corpus has a happy path that ends at a terminal `success` tensor.

**2. Fault diagnosis (backward chaining)**: "Stuck on the last step, system says no permission." Output: a backward traversal naming the missing prerequisite tensor or skipped operator. Test: for a curated set of stuck states, the system identifies the missing prerequisite and matches the ground-truth annotation.

**3. Dynamic routing**: "I already did real-name authentication earlier — where do I start?" Output: the operator(s) whose prerequisites are already met by the user's current state. Test: given a state assertion, the system identifies all valid entry operators.

**4. High-fidelity visual guidance**: when responding, the system can reference the specific image and annotation ("the area marked by the red box in image 3"). Test: every operator that has a UI surface in the manual has a `visualAnchor` linking to image and annotation.

## Pipeline shape

```
Word/PDF → Layout parsing (text + image extraction)
        → Visual annotation extraction (red boxes, arrows)
        → Step segmentation (which text-and-image groups are a single step)
        → Operator extraction (action and constraint per step)
        → Tensor extraction (state and data dependencies)
        → DAG assembly (operators connected via tensor dependencies)
        → Cross-platform tracking (PC ↔ Mobile transitions)
        → Anchor mapping (every operator → its UI step)
        → IComputeGraphSource published
```

## Interfaces produced

`IComputeGraphSource` — declared in `DocumentIngestion/Types`, consumed by `KnowledgeCalibration`.

```
ComputeGraph = {
  graphId: string,
  generatedAt: Timestamp,
  manualSourceId: string,
  tensors: Tensor[],
  operators: Operator[],
  visualAnchors: VisualAnchor[],
}
Tensor = {
  id: TensorId,
  name: string,                  // e.g., "user-authenticated", "QR-code-displayed"
  description: string,
  isTerminal: boolean,           // true for end-of-business states
  isInitial: boolean,
}
Operator = {
  id: OperatorId,
  name: string,                  // e.g., "scan QR code on mobile"
  inputs: TensorId[],            // prerequisite tensors
  outputs: TensorId[],           // tensors produced by this operator
  platform: 'PC' | 'Mobile' | 'Either',
  visualAnchor: VisualAnchorId | null,
  sopText: string,               // the standard operation procedure text
}
VisualAnchor = {
  id: VisualAnchorId,
  imageRef: string,              // path to extracted image
  annotations: Annotation[],     // red boxes, arrows, with bounding regions
  description: string,           // text description of where to look
}
```

## Failure modes and tolerances

**OCR drift on annotated screenshots**: a red box around a button whose label is mistranscribed. The visual anchor is preserved (the agent can still point at the box), but the text description is flagged `low-confidence`. Downstream Hermes prefers the visual anchor over the text in low-confidence cases.

**Step segmentation collapses two steps**: a single screenshot containing multiple sub-steps is parsed as one operator. Detected by post-extraction validation (operators with multiple distinct inputs *and* multiple distinct outputs that don't match a known pattern). Flag as `requires-split`; calibration in `KnowledgeCalibration` may unflag if the intents-tree confirms the steps are de facto a single user-perceived action.

**Cross-platform transition lost**: PC-to-mobile or mobile-to-PC handoff missed in extraction. The graph is technically valid but a Hermes procedural step would fail at runtime when the platform changes unexpectedly. Detected by Hermes at runtime and reported as a graph gap; feeds Metis as a documentation-gap issue.

**Manual is internally contradictory**: two paths to the same terminal tensor with incompatible prerequisites. Preserve both paths; mark the contradiction in graph metadata. Calibration resolves contradictions using the intents-tree (which is authoritative — see `PRODUCT_SENSE.md § Cross-product`).

## Forbidden behaviours

This domain does not edit the source manual. The manual is the artefact; the graph is the derivative. Treating the graph as the source of truth would invert authority a second time (the bottom-up tree is authoritative over the graph; the manual is the derivative of someone's authoring intent at a point in time). When the graph and the manual disagree, the manual is suspect *but not corrected* by this domain — that is Knowledge Calibration's job, with the intents-tree as arbiter.

This domain does not invent operators or tensors not present in the manual. Speculative graph extension is forbidden; the gap is logged for Hermes to refuse-and-report.

## Tiebreaker references

- `PRODUCT_SENSE.md § Cross-product` — graph is downstream of intents-tree authority.
- `PRODUCT_SENSE.md § Hermes` — Hermes refuses to act on speculative graph extensions; this is the upstream contract that supports that refusal.

## Open questions

> **Question**: What is the visual-annotation extraction approach? Computer-vision model, hand-rolled red-box detection, or a multi-modal LLM?
> **Default if not decided**: multi-modal LLM (vision-capable) for both red-box detection and SOP-text linkage, with `Confidence: low` because performance on dense-layout screenshots is unknown until empirical results.
> **Decided by**: M3 of the first Document Ingestion exec-plan.

> **Question**: How fresh must the compute-graph stay relative to manual updates? When operations change quarterly, does the graph regenerate on every change, or on a schedule?
> **Default if not decided**: on every detected manual change (file hash diff), with the regeneration triggering downstream recalibration.
