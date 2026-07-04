---
verification-status: proposed
last-reviewed: 2026-07-04
domain: Argus
---

# Argus — QA review surface

The QA Reviewer's primary workspace. Tabbed inspection (per `DESIGN.md` navigation primitives): a primary tab strip across the call list, with each tab swapping to a per-call review pane.

Per-call pane composes:
- Transcription viewer (Argus profile).
- Per-rule verdict list with evidence-citing components.
- Override affordance per verdict.
- "Mark this call requires-review" escalation.

## Cross-links

- `PRODUCT_SENSE.md § Argus` — Reviewer is the priority user; evidence density wins on UI conflicts.
- `docs/product-specs/argus/fact-checking.md`.

## Stable test selectors

Required: `data-testid="qa-review-surface"`, `data-testid="rule-verdict-${ruleId}"`, `data-testid="verdict-override-${ruleId}"`.

## Open

Stub. Pane layout, density choices, and reviewer-keyboard-shortcut set deferred to design-implementation exec-plan.
