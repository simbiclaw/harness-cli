---
verification-status: proposed
last-reviewed: 2026-07-20
domain: Hermes
---

# Hermes — Citizen chat

The citizen-facing conversational surface. Linear conversation pattern (per `DESIGN.md`); confirmations are inline content, not modal chrome (per `core-beliefs.md` Belief 6).

Conversation cells:
- Citizen turns (text input).
- Hermes turns (text + optional image references for visual-anchor guidance).
- Action-confirmation cards (inline; see `action-confirmation.md`).
- Audit-log entries (subtle, expandable).

## Cross-links

- `PRODUCT_SENSE.md § Hermes`.
- `docs/product-specs/hermes/procedural-reasoning.md`.
- `core-beliefs.md` Belief 4 (action-tier dual-channel), Belief 6 (inline confirmations).

## Stable test selectors

Required: `data-testid="citizen-chat"`, `data-testid="hermes-turn-${turnId}"`, `data-testid="action-card-${actionId}"`.

## Open

Stub. Voice-input affordance, image-zoom-on-anchor, and accessibility-specific screen-reader narration deferred.
