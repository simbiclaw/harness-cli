---
verification-status: proposed
last-reviewed: bootstrap
domain: Metis
layer: Service
---

# Metis — AI triage

## User job

Cluster atomic claims and detect emerging issues — product defects, process bottlenecks, market trends, competitive intelligence — that warrant analyst attention. Output is a prioritised list of candidate issues with severity scores derived from claim frequency, recency, and (when available) Argus-finding cross-references.

## Acceptance behaviour

A business analyst reviewing the triage output sees candidate issues ranked by leverage (volume × recency × severity), each issue linked to representative atomic claims and their source transcripts. The triage decision (open ticket / dismiss / merge with prior issue) is made by the analyst; Metis does not auto-open tickets without analyst review.

## Inputs

`IIntentTreeReader` (atomic claims, intents-tree) from `conversation-distillation.md`; `ICalibratedGraphReader` for context on which intents map to which manual-gap flags; `IArgusFindingFeed` (read-only) for systemic-finding candidates; `IProductIntroductionReader` for context.

## Tiebreakers consumed

- `PRODUCT_SENSE.md § Metis` — precision over recall in triage; deduplication preferred over fragmentation.
- `PRODUCT_SENSE.md § Cross-product` — Metis pulls Argus systemic findings; Argus does not push.

## Open

This file is a stub. The first Metis exec-plan elaborates the clustering approach, the severity-score function, and the deduplication algorithm. Deduplication policy gated on the ADR resolving `PRODUCT_SENSE.md § Metis` Awaiting Steering.
