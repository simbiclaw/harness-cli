---
verification-status: proposed
last-reviewed: 2026-07-04
domain: Hermes
---

# Hermes — Action confirmation

The Tier-B confirmation flow. Inline in the citizen chat; not modal.

Per `core-beliefs.md` Belief 4 (dual-channel tier visibility) and Belief 6 (inline confirmations).

## Action card anatomy

- Tier indicator (colour + icon + text label).
- Action description in plain language.
- Cited source: the calibrated-graph operator that motivated the action.
- Visual anchor preview (when the action targets a specific UI element in the target system).
- Before-screenshot reference (the current target-system state Hermes is acting on).
- Two affordances: "Confirm" and "Don't do this".

## Partial-commit panel

When a Class-B failure occurs (action committed partially before failing — per `PRODUCT_SENSE.md § Hermes`), the panel surfaces:
- Exact list of what committed.
- Exact list of what did not commit.
- Audit-record citations for both.
- "What now?" affordance: continue from current state, retry, abandon.

The partial-commit panel is the single most failure-recovery-critical UI surface in Hermes. `verification-status: proposed` initially; flips to `implemented` only after empirical testing of partial-failure scenarios.

## Cross-links

- `PRODUCT_SENSE.md § Hermes`.
- `docs/product-specs/hermes/action-execution.md` (the tier source of truth).
- `core-beliefs.md` Belief 4, Belief 6.

## Stable test selectors

Required: `data-testid="action-confirmation-${actionId}"`, `data-testid="action-confirm-button-${actionId}"`, `data-testid="action-decline-button-${actionId}"`, `data-testid="partial-commit-panel-${sessionId}"`.

## Open

Tier-C visual treatment (high-warning) is specified abstractly but Tier-C is empty initially; the visual treatment ships when the first Tier-C ADR lands.
