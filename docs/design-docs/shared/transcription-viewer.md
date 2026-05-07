---
verification-status: proposed
last-reviewed: bootstrap
consumed-by: Argus, Hermes
---

# Shared — Transcription viewer

Single-call viewer used by Argus (with rule-fired highlights) and Hermes (with action-tier indicators per turn). One component, two presentation profiles.

## Anatomy

- Speaker-attributed turns vertically stacked.
- Time markers per turn.
- Per-turn annotations layer:
  - **Argus profile**: rule-fired highlights, low-confidence-ASR markers.
  - **Hermes profile**: action-tier indicators where a turn motivated an action; visual anchor previews.
- Citation-target affordance: every turn is a click target that surfaces in evidence-citing components elsewhere.

## Stable test selectors

Required: `data-testid="transcription-viewer"`, `data-testid="transcription-turn-${turnId}"`. Per `core-beliefs.md` Belief 3.

## Cross-links

- `docs/product-specs/shared/audio-intake.md` (data shape).
- `docs/design-docs/core-beliefs.md` (Belief 1, Belief 2, Belief 5).

## Open

Design tokens applied, but exact spacing and hierarchy decisions deferred to first design-implementation exec-plan.
