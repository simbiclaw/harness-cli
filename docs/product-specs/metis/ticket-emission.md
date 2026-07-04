---
verification-status: proposed
last-reviewed: 2026-07-04
domain: Metis
layer: Runtime
---

# Metis — Ticket emission

## User job

When an analyst opens a triage candidate as an issue, emit a ticket to the configured ticket system (Kanban surface; production target is one of the standard ticket systems with stable API representation, see `ARCHITECTURE.md § 4` boring-tech ledger).

## Acceptance behaviour

A ticket emitted by Metis contains: the issue title, the severity score and its derivation, the representative atomic claims (with source transcript citations), the intents-tree node IDs, and (where applicable) the Argus systemic-finding reference. The ticket is opened in the configured Kanban surface; a human reviews it; subsequent code/process change happens via whatever workflow the team uses.

**Explicit non-goal**: Metis does not invoke Claude Code or any other coding agent as a runtime production dependency (`PRODUCT_SENSE.md § Metis`). The PRD describes a closed loop including `Code Fix → Deploy → Verify`; the current scope ends at ticket emission. The architecture must not preclude later automation, but no part of Metis Service or Runtime currently calls a coding-agent provider.

## Tiebreakers consumed

- `PRODUCT_SENSE.md § Metis` — runtime path is human-driven.

## Open

Stub. The first Metis exec-plan elaborates the ticket-shape contract, the deduplication-on-emission rule, and the closure-feedback channel (when a human closes a ticket, that signal feeds future triage prioritisation).
