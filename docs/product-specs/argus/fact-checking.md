---
verification-status: proposed
last-reviewed: bootstrap
domain: Argus
layer: Service
---

# Argus — Fact-checking

## User job

Score every call against the active Rules & Criteria, citing evidence from the structural transcription and the calibrated graph. Output is a per-call verdict with rule-by-rule pass/fail/requires-review status, each rule's verdict carrying citations to the transcript turns and (where applicable) the operator(s) in the calibrated graph that should have been followed.

## Acceptance behaviour

A QA Reviewer reading a fact-checking output can:

1. See every rule that was checked.
2. For every fail or requires-review verdict, click through to the transcript turn(s) cited as evidence.
3. For procedural rules, see which operators in the calibrated graph were expected and which were observed.
4. Override any verdict; the override feeds the offline Error Case Library update path.

A verdict with no citation is a release blocker (`PRODUCT_SENSE.md § Argus`).

## Inputs and outputs

Inputs: `StructuralTranscription` (per-call, from `audio-intake.md`); `CalibratedGraph` (latest generation, from `calibration.md`); `IRulesAndCriteriaReader`, `IPhraseKeywordReader`, `IAcousticFeatureReader`, `IDynamicKnowledgeBaseReader`, `IBestPracticeCookbookReader`, `IErrorCaseLibraryReader` (all from `expertise-library.md`).

Outputs: `FactCheckVerdict` declared in `Argus/Types`. Shape TBD by the first Argus exec-plan; required fields include `callId`, `rulesVersion`, `perRuleVerdicts[]`, each with `evidence[]` linking to transcript spans and operator IDs.

## Tiebreakers consumed

- `PRODUCT_SENSE.md § Argus` — evidence-citation is non-negotiable; ambiguity → `requires-review`, never `pass-or-fail-by-guess`.
- `PRODUCT_SENSE.md § Cross-product` — Argus systemic findings forward to Metis when the threshold is met (initial default N=5 agents in window).

## Open

This file is a stub. The first Argus exec-plan elaborates the rule-evaluation engine, the verdict shape, and the override pipeline. Owner: not yet assigned.
