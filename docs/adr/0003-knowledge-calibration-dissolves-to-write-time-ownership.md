# ADR-0003: Knowledge Calibration Dissolves to Write-Time File Ownership

**Status:** accepted

**Date:** 2026-07-04

## Context

The v1 architecture described "Knowledge Calibration" as a runtime domain where the bottom-up intents tree and the top-down compute graph meet and reconcile — ingesting from both, detecting divergences, and resolving contradictions bottom-up. Calibration was domain #4 in the 10-domain inventory, with a dedicated pipeline, type-level invariants, and test coverage.

The v6 design reframed this: the INTENTS tree is the single source of behavioural truth (ADR-0002), and calibration — the resolution of conflicting knowledge sources — happens at **write time**, not read time. The transformation layer (audio2tree, doc2graph) produces the tree; the tree is already the reconciled output. The consumer (Argus) never sees two conflicting sources. There is nothing to calibrate at read time.

This ADR records the dissolution of Knowledge Calibration as a code domain so that a future reader does not "restore" the missing domain thinking it was lost by accident.

## Decision

### Knowledge Calibration is not a runtime domain

The v1 calibration pipeline (mapping → divergence detection → contradiction resolution → calibrated graph publish) is not implemented in this repo. The work it described is performed by the transformation layer (not this repo — see `docs/references/platform-architecture.md`) at tree-build time:

1. **Mapping** (intent ↔ operator) — performed by the transformation pipeline (audio2tree's clustering stage and doc2graph's tensor-operator DAG construction) during tree generation. The output is the tree's L3 case nodes with `intentMapping` fields.
2. **Divergence detection** (`manual-gap`, `unused-by-customers`) — performed at build time by the pipeline; gaps are annotated in the tree and surfaced to the human operator who resolves them before the tree is committed.
3. **Contradiction resolution** (bottom-up authoritative) — performed at build time: the tree is authoritative by construction. The compute graph is an *input* to the build, not a peer at read time. When the tree and graph disagree, the tree's claim is preserved and the graph's operator is annotated as `superseded-by-calibration`.
4. **CalibratedGraph publish** — the tree *is* the calibrated graph. There is no separate publish step; `git commit` on the tree is the publish.

### Bottom-up authority is enforced by file ownership, not runtime logic

The v1 calibration spec's type-level invariant — the asymmetric `calibrate(intentTree, computeGraph)` signature — was the right instinct but the wrong layer. The authority relationship is structurally encoded in the INTENTS tree:

- The tree is the authoritative artefact. Files in the tree are owned by their producer (tracked in `_meta/ownership.yaml`).
- The compute graph is a build-time input; it does not appear on disk as a separate artefact that consumers read.
- Coverage gaps (intents with no corresponding operator) are emitted producer-side as `manual-gap` annotations in the tree. Argus reads these as metadata on the node — not as a runtime calibration decision.
- Content gaps (operators with no corresponding intent) are `unused-by-customers` annotations, also emitted producer-side.

### The one caveat to verify

ADR-0004 collapses the Expertise Library's nine reader interfaces to one INTENTS Provider. That Provider reads exactly one tree at one SHA. This means Argus never has to reconcile two conflicting knowledge sources at read time — it always reads an already-single, already-calibrated tree.

This is the property that makes the dissolution safe. If a future design introduces a second knowledge source that Argus reads independently, the runtime calibration domain must be re-established. This ADR names that gate explicitly so the decision is reversible with evidence, not accidentally violated.

## Consequences

- Knowledge Calibration is removed from `ARCHITECTURE.md`'s domain inventory. It is not a domain in this repo.
- The calibration spec (`docs/product-specs/shared/calibration.md`) is amended to describe the coverage-axis / content-axis split and the build-time resolution model, rather than a runtime pipeline.
- The v1 structural test `test_calibration_invariants.py` and lint `calibration_asymmetric_signature.py` remain as enforcement of the bottom-up authority principle, but they now apply to the INTENTS Provider's read path, not a separate Calibration domain.
- The `ICalibratedGraphReader` interface is replaced by the INTENTS Provider's typed read methods. There is no separate calibrated graph to read — the tree is the graph.
- If a future design introduces a second independent knowledge source, this ADR must be revisited and a runtime calibration domain re-established.
