# design-docs/index.md

Per-surface design elaboration. The top-level `DESIGN.md` is the lookup; this directory is the deep reference.

**Read first**: `core-beliefs.md` — the agent-first design principles. These shape every choice below.

**Shared surfaces** (consumed by multiple apps):
- `shared/transcription-viewer.md` — single-call viewer with rule-fired highlights (Argus) and action-tier indicators (Hermes).
- `shared/expertise-browser.md` — read-only browser for the seven expertise modules.
- `shared/evidence-citing.md` — citation component used everywhere a verdict, finding, or step is shown.

**Per-app surfaces**:
- `argus/qa-review-surface.md` — the QA Reviewer's primary workspace.
- `argus/coaching-task-list.md` — the agent-facing coaching task list.
- `metis/triage-kanban.md` — the analyst-facing Kanban.
- `hermes/citizen-chat.md` — the citizen-facing conversational surface.
- `hermes/action-confirmation.md` — the Tier-B confirmation flow and the partial-commit panel.

Every file in this directory carries a `verification-status:` field. Status meanings are documented in `DESIGN.md`. At bootstrap every file is `proposed`.

## Cross-link integrity

Every design-doc must reference the `PRODUCT_SENSE.md` section for its app and the `product-specs/<app>/` feature it elaborates. Files without those links are flagged by the doc-gardener.
