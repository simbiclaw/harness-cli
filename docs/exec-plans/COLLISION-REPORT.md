# Collision & action report — v6 spine upgrade into harness-cli

Companion to `0000-upgrade-spine-to-v6.md`. Every file the upgrade touches, with its collision status against the repo as it stands, and the action. Nothing here is executed — it is the review surface.

## The core finding

The repository is running **v1 of the spine** — the exact bootstrap artefacts, before the six turns of refinement done this session. `0001-bootstrap-the-spine` already ran (it is in `completed/`), so the *enforcement* layer is live: 8 lints in `tools/lint/`, 14 structural tests in `.claude/tests/`, import-linter, hooks, CI. What is missing is only the *design refinement*. So this is a design-upgrade, not an integration, and the enforcement layer is not touched.

## Path convention note

The repo keeps the four top-level docs in two places: `ARCHITECTURE.md` at **repo root**, and `PRODUCT_SENSE.md` / `DESIGN.md` / `QUALITY_SCORE.md` under **`docs/`**. The v6 bundle put all four at root. The upgrade follows the **repo's** convention: edit `ARCHITECTURE.md` at root; if `PRODUCT_SENSE`/`DESIGN`/`QUALITY_SCORE` need edits they happen under `docs/`. Do not introduce a second copy of any doc.

## File-by-file

### ADRs — pure additions (repo `docs/adr/` is empty)

| File | Repo status | Action |
|---|---|---|
| `docs/adr/0001-expertise-epistemic-classes-and-argus-eval-function.md` | absent | **ADD** (M1) |
| `docs/adr/0002-intents-path-as-ontology.md` | absent | **ADD** (M1) |

No collision. These become the repo's first ADRs.

### Shared + Argus specs — edits to existing files (v1 → v6)

| File | Repo status | Action |
|---|---|---|
| `docs/product-specs/shared/expertise-library.md` | present, v1 (Acoustic/Phrase as facts; 9-module flat list) | **EDIT** (M2) — add epistemic-class table, move Acoustic + Phrase to rubric, add category readers |
| `docs/product-specs/argus/fact-checking.md` | present, v1 (single-function framing, stub) | **EDIT** (M3) — two-stage `score`→`adjust`, per-precedent attribution, updated inputs |
| `docs/product-specs/shared/calibration.md` | present, v1 (bottom-up authority only) | **EDIT** (M4) — add coverage-axis / content-axis split |
| `ARCHITECTURE.md` (root) | present, v1 | **EDIT** (M4) — INTENTS representation paragraph, boring-tech row (filesystem over RAG), Argus two-stage note in Service section, ADR-0002 pointer |

These are edits, not overwrites. The repo versions are the ancestors of the v6 versions, so a merge is clean — apply the v6 deltas onto the repo files (do not blind-copy the v6 files, which were written with root-level sibling assumptions and may carry cross-references the repo lays out differently).

### New shared spec — addition

| File | Repo status | Action |
|---|---|---|
| `docs/product-specs/shared/intents-semantic-layer.md` | absent | **ADD** (M4) |

### INTENTS tree — pure addition, Tier C

| Path | Repo status | Action |
|---|---|---|
| `INTENTS/**` (worked `annual-report-submission` domain + `_rubric/` shelf + `_meta/`) | absent | **ADD** (M5) — location is Awaiting-Steering Q1 (root vs `docs/`) |

### QUALITY_SCORE — regrade

| File | Repo status | Action |
|---|---|---|
| `docs/QUALITY_SCORE.md` | present, v1 | **EDIT** (M6) — regrade only the rows the reclassification and INTENTS representation move |

### Never touched

`CLAUDE.md` — **not edited.** The v6 bundle shipped a `CLAUDE_md_borrow_snippet.md` (a sentinel-block append mechanism for a repo without a routing file). This repo already has a mature `CLAUDE.md` that routes correctly. The borrow snippet is **discarded**; `MAP.md` from the bundle is **discarded** for the same reason (the repo routes via `CLAUDE.md` + active ExecPlan). All of `.claude/`, `tools/lint/`, `.importlinter`, `.github/workflows/`, `pyproject.toml`, `src/` — untouched.

## Bundle files that do NOT apply to this repo

From the v6 output set, these are dropped as redundant or repo-inappropriate:

- `MAP.md`, `CLAUDE_md_borrow_snippet.md` — the repo already has `CLAUDE.md` routing.
- `docs/exec-plans/active/0001-bootstrap-the-spine.md` (v6 copy) — the repo already ran its own; kept in `completed/`.
- The v6 `docs/conventions/*` were never generated (they were `0001`'s job); the repo already has a *richer* `conventions/` set (`ask-threshold`, `layering`, `deps-and-secrets` beyond the three the v6 plan named). Do not overwrite them.

## Two pre-existing conditions the upgrade surfaces

1. **ARCHITECTURE.md vs .importlinter model mismatch — now closed by M1, not deferred.** The doc described 10 domains / 6 layers; `.importlinter` enforces 5 layers (`types→config→io→core→cli`) over one `argus` package. The Argus-only rescope makes the honest domain count five, mapping one-to-one onto the enforced layers, so M1 resolves the divergence directly. Two dissolution ADRs fall out: `0003` (Knowledge Calibration dissolves into write-time file ownership) and `0004` (Expertise Library is the INTENTS runtime artifact, not a code domain).
2. **`references/node_contract.md` is still absent** and is the gate for INTENTS tree-interior schemas (the capsule Bone/Flesh shape). Owned by the human. The M6 worked example uses a provisional shape marked as such; it does not substitute for the contract.

## Suggested execution order for Claude Code

Land `0000` into `docs/exec-plans/active/`, then run its milestones M1→M6 in order. M1–M4 are low-risk doc edits gated by new tests; M5 is the Tier-C tree addition (resolve Q1 first); M6 is the regrade-and-verify that must leave the existing harness suite green. Keep a human review gate before M5.
