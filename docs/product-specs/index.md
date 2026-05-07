# product-specs/index.md

Per-feature elaboration of `PRODUCT_SENSE.md`. Two kinds of files live under this directory:

**`shared/`** — specs for the foundational pipelines and libraries consumed by multiple apps. Touching any of these has multi-app blast radius; read the relevant file before modifying anything in the corresponding domain.

- `shared/audio-intake.md` — VAD + diarisation + ASR → structural transcription. Consumed by Conversation Distillation.
- `shared/conversation-distillation.md` — bottom-up: structural transcription → atomic claims → intents-tree.
- `shared/document-ingestion.md` — top-down: operation manuals → compute-graph (Tensor-Operator DAG) with visual annotations.
- `shared/calibration.md` — where bottom-up and top-down meet. Encodes the bottom-up-authoritative invariant.
- `shared/expertise-library.md` — the seven expertise modules and their consumer matrix.

**`<app>/`** — per-app feature elaboration. Stubs at bootstrap; Claude Code expands these as exec-plans are written for individual features.

- `argus/fact-checking.md` (stub)
- `argus/report-generation.md` (stub)
- `argus/coaching-tasks.md` (stub)
- `metis/ai-triage.md` (stub)
- `metis/ticket-emission.md` (stub)
- `metis/issue-kanban.md` (stub)
- `hermes/procedural-reasoning.md` (stub)
- `hermes/action-execution.md` (stub — contains the action-tier classification)

Per-feature files all carry a `verification-status:` field at the top: `proposed | implemented | drifted | obsolete`. At bootstrap every per-app feature is `proposed`; the shared pipeline specs are `proposed` until M2–M6 of `0001-bootstrap-the-spine.md` flip them to `implemented`.

Cross-link integrity: every per-feature file links back to the relevant `PRODUCT_SENSE.md` tiebreaker section. Files without that link are flagged by the doc-gardener.
