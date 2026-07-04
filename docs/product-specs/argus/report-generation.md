---
verification-status: proposed
last-reviewed: 2026-07-04
domain: Argus
layer: Service
---

# Argus — Report generation

## User job

Aggregate fact-checking verdicts into reports for QA Supervisors (team-level) and individual Call Center Agents (per-agent). Reports surface trends, rule-failure distributions, and improvement candidates without requiring the supervisor to read every call individually.

## Acceptance behaviour

A QA Supervisor reading a team-level report can identify the top three rule failures by frequency, see which agents contributed to each, and click through to representative call examples. Cited evidence requirement (`PRODUCT_SENSE.md § Argus`) propagates: every aggregate statement traces to the underlying verdicts.

A Call Center Agent reading a per-agent report sees their own performance against rule frequencies in a way that respects the agent-privacy policy (`PRODUCT_SENSE.md § Argus Awaiting Steering`).

## Tiebreakers consumed

- `PRODUCT_SENSE.md § Argus` — supervisor outranks agent on UI choices when the two conflict; agent-privacy policy governs visibility.

## Open

This file is a stub. The first Argus exec-plan or a follow-on plan elaborates the report shapes and the aggregation contracts. Per-agent visibility is gated on the agent-privacy ADR.
