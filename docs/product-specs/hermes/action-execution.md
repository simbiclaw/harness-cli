---
verification-status: proposed
last-reviewed: 2026-07-04
domain: Hermes
layer: Service
---

# Hermes — Action execution

The most safety-critical surface in the platform. This document is the canonical home for the **action-tier classification** referenced in `PRODUCT_SENSE.md § Hermes` and `ARCHITECTURE.md § 5 Service`.

## User job

When the citizen has authorised an action ("yes, please file the annual report"), Hermes executes the corresponding operator(s) in the target system via Playwright MCP / Chrome DevTools Protocol. Execution surfaces are: DOM snapshots and screenshots for evidence; navigation, click, and form-fill for action; per-action confirmation flows for Tier-B actions.

## The action-tier system

Every action descriptor produced by Hermes Service declares its tier. The descriptor type (from `ARCHITECTURE.md § 5 Service`):

```
type ActionDescriptor =
  | { tier: 'A'; kind: 'read'; ... }
  | { tier: 'B'; kind: 'confirmed'; ... }
  | { tier: 'C'; kind: 'autonomous'; ... }
```

### Tier A — read-only

Actions that inspect the target system without committing state. DOM snapshots, screenshots, navigation that does not POST or otherwise mutate, reading the current page's text content.

Tier-A actions are executed without per-action user confirmation. They are still surfaced in the audit log (`PRODUCT_SENSE.md § Hermes Awaiting Steering Q3`) for transparency.

### Tier B — confirmed

Actions that commit state to the target system, where the action requires explicit per-action user confirmation before Runtime executes. Form submissions, button clicks that mutate, navigations that imply commitment (e.g., "submit final filing").

The confirmation flow is a UI surface (`docs/design-docs/hermes/action-confirmation.md`); the flow shows the citizen what is about to happen, captures their acknowledgement, then executes. The user's acknowledgement is captured in the audit log alongside the executed action.

### Tier C — autonomous

Actions executed without per-action user confirmation. **Tier C is initially empty.** The default policy in `PRODUCT_SENSE.md § Hermes` initialises Tier-C as having zero permitted action kinds. Promoting an action to Tier-C requires an ADR with explicit reversibility analysis and an entry in this file naming the action and the reversibility evidence.

The initial-empty default exists because Class-C failures in the RegTech domains may be legally irreversible (`PRODUCT_SENSE.md § Hermes` failure tolerances). The architectural commitment is that Tier-C is *structurally rare* — promoting an action to Tier-C is a deliberate, audited decision, not a default.

## Mechanical enforcement

Three layers, in order of strength:

1. **Type-level**: the three tiers are distinct types, not a string field on a shared type. There is no shared `Action` type that all three inhabit; code that handles "any action" must explicitly handle all three discriminants. (Lint: `hermes-action-tier-required` fails if any action descriptor lacks a tier discriminant.)

2. **Provider-level**: the browser-automation Provider exposes three sets of methods, one per tier. The Tier-C method set is gated on a build-time configuration that lists the permitted Tier-C action kinds; at bootstrap the list is empty and the Tier-C method set is therefore empty. (Lint: `hermes-tier-c-allowlist` fails if Tier-C methods are referenced from anywhere not explicitly named in this file.)

3. **Test-level**: a structural test asserts that no call site outside Hermes Service can invoke a Tier-C method. A second structural test verifies that every `ActionDescriptor` constructor in Hermes Service produces a discriminated value (no untagged unions that could collapse the tier).

## Action-tier classification (initial)

This is the **first cut**, marked `Confidence: low` until the ADR resolving `PRODUCT_SENSE.md § Hermes` Awaiting Steering Q1 lands. Every entry below is `proposed`.

| Action kind | Tier | Reason |
|---|---|---|
| Take screenshot of current page | A | Read-only |
| Capture DOM snapshot | A | Read-only |
| Navigate to URL (GET) | A | Reads the page; does not mutate |
| Read form field value | A | Read-only |
| Click button labelled "Cancel" or "Back" | A | Conventionally non-mutating; but see Open §1 |
| Fill form field | B | Pre-commit step; final submission is a separate Tier-B action |
| Click button labelled "Next" / "Continue" | B | Multi-step forms commit progress |
| Click "Submit" / "Confirm" / "File" | B | Final commitment of state |
| Upload file | B | Commits a file to the target system |
| Pay fee | B | Commits a payment |
| (every action kind not above) | B (default) | The default tier is B; promotion to A requires explicit reasoning here. |

`Tier C is empty.`

## Audit trail

Every Tier-A, Tier-B, and Tier-C action emits an audit record at execution. Records contain: action descriptor, timestamp, target URL, before/after DOM snapshot references, before/after screenshot references, user-confirmation reference (Tier-B only), executed-by identity, source-citation back to the calibrated-graph operator that motivated the action.

The audit log is a Provider, accessed through `IAuditLogWriter`. The audit log is read-only after write — there is no method to redact or modify a record. (Per `PRODUCT_SENSE.md § Hermes` Q3: per-session log visible in UI, persisted session + 30 days, exportable as plain text — these are defaults pending the ADR.)

## Failure modes and tolerances

(See `PRODUCT_SENSE.md § Hermes` for the Class A/B/C failure-tolerance taxonomy. This section names the implementation contract.)

**Class A failure**: retry-with-backoff up to a small bound, then surface to user with the failure reason. Continue.

**Class B failure mid-execution**: capture the post-failure state; surface to the user with explicit before/after; cite the audit record(s); do not retry without re-confirmation. The user-facing surface for this is in `docs/design-docs/hermes/action-confirmation.md` (the "partial commit" panel).

**Class C failure**: this should not happen because Tier-C is empty. If a Tier-C action is added in the future and fails, the failure surfaces with maximum visibility — a session-blocking modal, full audit citation, and an automatic Metis ticket emission with severity `critical`. The architectural goal is that this code path is rarely-executed; if it executes, it indicates a regression in the Tier-C allowlist policy, not just a runtime failure.

## Tiebreaker references

- `PRODUCT_SENSE.md § Hermes` — confirmation outranks convenience; urgency does not promote tier.
- `ARCHITECTURE.md § 5 Service` — type-level tier system.

## Open

> **§1 Cancel/Back classification.** "Click button labelled Cancel or Back" is listed as Tier-A above. In some target systems, "Cancel" actually commits a cancellation (e.g., cancelling an in-flight filing). The classification is `Confidence: low` and may need to be Tier-B per-action depending on context.
> **Default if not decided**: when the action's button label matches a small allowlist of known-non-mutating words AND the post-action page change is verified read-only, treat as Tier-A; otherwise Tier-B.

> **§2 Multi-step form commit.** "Click Next/Continue" in a multi-step form might or might not commit progress depending on the system. Conservative tier-B is the current cut; an ADR may refine.

> **§3 Per-domain Tier-C candidates.** The supported RegTech domains (digital certificates, electronic seals, corporate registration, annual reporting, credit restoration) likely have read-only-but-currently-Tier-B actions that could be Tier-A (status checks, document fetches). These are candidates for promotion to Tier-A in domain-specific ADRs, never for promotion to Tier-C.

This file is the action-tier source of truth. Proposed changes to the table above require an ADR.
