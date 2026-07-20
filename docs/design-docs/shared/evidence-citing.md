---
verification-status: proposed
last-reviewed: 2026-07-20
consumed-by: Argus, Metis, Hermes
---
**Corresponding product-spec:** [docs/product-specs/shared/conversation-distillation.md](../docs/product-specs/shared/conversation-distillation.md)


# Shared — Evidence-citing component

The component used everywhere the system makes a claim — Argus verdicts, Metis tickets, Hermes audit records, Hermes procedural steps. Renders the claim with one or more clickable citation chips that open the source artefact in context (transcript turn, calibrated-graph operator, prior audit record).

Per `core-beliefs.md` Belief 5, citations are clickable, not footnotes.

## Anatomy

- Claim text.
- Citation-chip strip (1..N chips per claim).
- On chip click: opens the source artefact in a contextual panel without losing the citing surface.

## Stable test selectors

Required: `data-testid="evidence-claim"`, `data-testid="evidence-citation-${sourceType}-${sourceId}"`.

## Cross-links

- `PRODUCT_SENSE.md § Argus` (evidence-citing non-negotiable).
- `core-beliefs.md` Belief 5.

## Open

Source-type taxonomy fixed initially as `transcript-turn | calibrated-operator | audit-record | atomic-claim | manual-image`. Extensions require design-doc update.
