---
verification-status: proposed
last-reviewed: 2026-07-04
domain: Hermes
layer: Service
---

# Hermes — Procedural reasoning

## User job

Given a citizen request ("I want to file my annual report") and the citizen's current state, plan a sequence of operators from the calibrated graph that achieves the request. The plan is procedural: an ordered sequence of operators, each annotated with platform (PC/Mobile), prerequisites, and visual anchors.

## Acceptance behaviour

When the citizen asks "I want to complete business XX", Hermes responds with the full sequence of operators (path planning per `document-ingestion.md` acceptance behaviour). When the citizen says "I'm stuck — system says no permission", Hermes performs backward chaining (fault diagnosis) and identifies the missing prerequisite tensor or skipped operator. When the citizen says "I already did real-name authentication", Hermes performs dynamic routing and identifies the operators whose prerequisites are now met.

In all three cases, Hermes responds with reference to the visual anchor (`document-ingestion.md` requirement 4): "click the area marked by the red box in this image" rather than text-only instruction.

## Forbidden

Hermes does not extend the calibrated graph at runtime. When the calibrated graph does not cover a procedural state the citizen describes, Hermes refuses to act and logs the gap to `IGapLog`, which feeds Metis as a documentation-gap issue. Speculative graph extension is forbidden by `PRODUCT_SENSE.md § Cross-product` and structurally enforced by the absence of `ICalibratedGraphWriter` in Hermes's dependency surface (`ARCHITECTURE.md § 3`).

## Tiebreakers consumed

- `PRODUCT_SENSE.md § Hermes` — confirmation outranks convenience.
- `PRODUCT_SENSE.md § Cross-product` — Hermes consumes calibrated graph; does not write.

## Open

Stub. The first Hermes exec-plan elaborates the planner contract (forward / backward / dynamic), the visual-anchor surfacing format, and the gap-log shape.
