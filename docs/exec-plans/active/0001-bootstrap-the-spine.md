# 0001 — Bootstrap the spine

## Purpose

The four spine artefacts (`PRODUCT_SENSE.md`, `ARCHITECTURE.md`, `DESIGN.md`, `QUALITY_SCORE.md`) and their satellite directories were generated externally and dropped into this repo. They describe invariants and contracts; they cannot enforce themselves. This plan is Claude Code's first concrete task: implement the mechanical checks that turn the spine's prose rules into structural tests, deliver the conventions library the spine references, and tear down the bootstrap scaffolding (`docs/MAP.md`, the `harness-spine-bootstrap` block in `CLAUDE.md`) once the spine is self-supporting.

After this plan ships, the spine is no longer aspiration. Every `Aspiration:` marker in `ARCHITECTURE.md` is replaced by a working linter, every `verification-status: proposed` in shared product-specs has a test floor under it, and `QUALITY_SCORE.md` regrades from "F across the board" to whatever the lints actually find.

## Big Picture

Touched: every domain in `ARCHITECTURE.md § 1`, but only at the Types and Repo layer scaffolding level. No Service or UI implementation in this plan — that is for follow-on plans.

In scope:
- The `docs/conventions/` directory, populated with `verification-floor.md`, `i-dont-know-protocol.md`, `commit-hygiene.md` (the references the spine assumes exist).
- The structural test / lint suite named in `ARCHITECTURE.md` and `PRODUCT_SENSE.md`: `no-backward-layer-import`, `forbidden-cross-domain-edges`, `external-imports-only-in-providers`, `parse-at-boundary`, `utils-purity`, `interface-single-declaration`, `forbidden-phrases`, `stable-test-selectors`, `quality-grade-evidence-required`, `architecture-changes-require-adr`, `hermes-action-tier-required`, `hermes-tier-c-allowlist`, `calibration-asymmetric-signature`, `bottom-up-authority-invariant`, `intent-tree-stability`, `no-hand-edit-generated`, `axe-core` (CI integration, not the lint itself), `rules-version-pinned`, `structured-log-shape`, `no-global-providers`.
- The doc-gardener subagent specification (not yet the implementation; spec only — implementation is M6).
- Tear-down of `docs/MAP.md` and removal of the `harness-spine-bootstrap` sentinel block from `CLAUDE.md`.
- A CI rule that asserts `docs/MAP.md` does not exist on `main` and that no `harness-spine-bootstrap:begin` marker is in `CLAUDE.md` on `main`.

Deliberately out of scope (named so future plans don't confuse themselves):
- Any Service-layer business logic for the three apps. The pipelines do not have to *work* yet — they have to have *types and tests structured to require working*.
- Any UI implementation. Component scaffolds with stable test selectors are in scope; visual styling is not.
- The Error Case Library self-learning pipeline. The reader interface lands here; the offline learning loop is a follow-on plan.

Subcommands or surface introduced: this plan is repo-internal; no end-user surface.

Config surface added: `tools/lint/` directory with one configuration file per lint, plus a `tools/structural-tests/` directory for the tests that are not lints (e.g., `bottom-up-authority-invariant`, which constructs deliberately-contradictory inputs and runs the calibration function).

Files on user filesystem read or written: none beyond the repo itself.

## Milestones

The six milestones are sequenced so each unlocks the next. Each milestone has at least one Acceptance Test runnable in CI. Mid-milestone work commits frequently per `commit-hygiene.md` (delivered in M1).

### M1. Populate the conventions library

Deliver the three convention files the rest of the spine references but does not contain. Without these, `verification-status` flips and Decision Log entries cannot be properly shaped.

Files to deliver:
- `docs/conventions/verification-floor.md` — defines what "test-floor-met" means per layer. For Repo: every method has a failing-before-implementation, passing-after test. For Service: every function is exercised by a test that asserts on its return type and at least one specific value transformation. For Runtime: every job has an integration test covering one happy path and one failure path. For UI: every interactive element has a stable selector and at least one click-target test.
- `docs/conventions/i-dont-know-protocol.md` — defines the Rationale shape: cited source / named experiment / explicit `Confidence: low` + `Revisit:`. Names the forbidden phrase set and the lint that enforces.
- `docs/conventions/commit-hygiene.md` — one logical change per commit; checkbox flips in their own commit; structural tests pass before any flip.

`Acceptance Test:` `tests/test_conventions_exist.py::test_required_convention_files_present` — verifies the three files exist and contain the named sections.

### M2. Implement `forbidden-phrases` and the I-Don't-Know test floor

The smallest, highest-leverage lint. Runs over every `.md` in `docs/` and the four top-level `.md` files; fails CI if any contains "best practice", "industry standard", "clean architecture", "follows convention" without an immediately-following citation, experiment reference, or `Confidence: low` marker.

Also: implement `quality-grade-evidence-required` — fails CI if `QUALITY_SCORE.md` contains a hand-edited grade without inline evidence.

`Acceptance Test:` `tools/lint/tests/test_forbidden_phrases.py::test_phrase_without_citation_fails` and `::test_phrase_with_citation_passes`. Plus `tools/lint/tests/test_quality_grade_evidence.py::test_ungrounded_grade_change_fails`.

### M3. Implement the architectural-edge linters

The four lints that enforce `ARCHITECTURE.md § 2` and `§ 3`:

- `no-backward-layer-import`: parse the import graph; fail on any import from a later layer (within the same domain) into an earlier layer.
- `forbidden-cross-domain-edges`: parse the import graph; fail on any cross-domain edge that is `none` in the dependency matrix.
- `external-imports-only-in-providers`: identify external-package imports; fail unless the importing module is in a Providers domain.
- `parse-at-boundary`: identify cross-domain function calls; fail unless the caller's argument is the result of a typed-schema validator.

These four together are the load-bearing structural enforcement for the entire architecture.

`Acceptance Test:` for each lint, a paired pass/fail fixture: `tools/lint/tests/fixtures/no_backward_layer_import/{passes,fails}/`. CI runs the lint against fixtures and verifies expected pass/fail per fixture.

`Notes:` this milestone depends on the project's chosen language. Implementation is per-language (TypeScript surfaces use AST parsing via `ts-morph` or equivalent; Python via `ast` module). The lint behaviour is the same; the implementation detail is per-language.

### M4. Implement the calibration invariant tests

The bottom-up-authority invariant is the single most important rule in `PRODUCT_SENSE.md § Cross-product`. It needs three layers of enforcement:

- `calibration-asymmetric-signature` (lint): verifies the calibration function's signature is `calibrate(intentTree, computeGraph): CalibratedGraph` — symmetric `reconcile(a, b)` forms fail.
- `bottom-up-authority-invariant` (structural test): constructs a deliberately-contradictory `IntentTree` and `ComputeGraph` pair (intent says X, graph says ¬X), runs `calibrate`, asserts the output reflects intent's claims.
- `intent-tree-stability` (structural test): runs the conversation-distillation pipeline twice on the same input, asserts intent-node ID preservation; runs on input + 10% new claims, asserts ≥ 90% prior-ID preservation.

`Acceptance Test:` `tests/test_calibration_invariants.py::test_bottom_up_authority` and `::test_intent_tree_stability`.

### M5. Implement the Hermes action-tier enforcement

The Hermes safety surface, per `docs/product-specs/hermes/action-execution.md`:

- `hermes-action-tier-required` (lint): every `ActionDescriptor` constructor produces a discriminated value with explicit tier.
- `hermes-tier-c-allowlist` (structural test): the Tier-C method set on the browser-automation Provider is reachable from no call site outside the explicitly-listed allowlist; allowlist starts empty.

This milestone also delivers the `ActionDescriptor` type and the three-method-set browser-automation Provider scaffold (no actual browser automation logic; just the typed boundaries that future Hermes implementation must respect).

`Acceptance Test:` `tests/structural/test_hermes_action_tier.py::test_no_untagged_action_descriptor` and `::test_tier_c_unreachable_from_outside_allowlist`.

### M6. Doc-gardener subagent and tear-down

The doc-gardener subagent specification (in `docs/skills/doc-gardener/SKILL.md` or equivalent location depending on the chosen subagent model). The skill scans `docs/` nightly for:
- Stale `verification-status: proposed` (older than 14 days without movement).
- Drifted `verification-status: implemented` (rendered DOM doesn't match design-doc claimed selectors).
- Cross-link integrity violations (a product-spec without a `PRODUCT_SENSE.md` tiebreaker reference; a design-doc without its product-spec link).
- Forbidden hand-edits to `docs/generated/`.
- Stale grades in `QUALITY_SCORE.md` past `Next regrade` date without a covering active exec-plan.

The skill opens fix-up PRs for what it can fix mechanically; flags what it cannot in a `docs/retrospectives/` weekly summary.

Then, tear-down:
- Delete `docs/MAP.md` (commit message: "Bootstrap complete: removing scaffolding routing aid; spine artefacts now cross-link to each other.").
- Remove the `harness-spine-bootstrap:begin/end` block from `CLAUDE.md`.
- Add the CI rule `bootstrap-scaffolding-absent`: fails CI if `docs/MAP.md` exists or if `harness-spine-bootstrap:begin` is grep-findable in `CLAUDE.md`.

`Acceptance Test:` `tests/test_bootstrap_scaffolding_absent.py::test_map_file_absent` and `::test_no_sentinel_block_in_claude_md`. Plus the doc-gardener skill is exercised against a synthetic `docs/` snapshot containing one of each detected drift class.

After M6, this exec-plan moves from `docs/exec-plans/active/` to `docs/exec-plans/completed/` and `QUALITY_SCORE.md` regrades for the first time against real lint output.

## Progress

- [x] M1: Populate the conventions library  (created `<bootstrap>`)
- [ ] M2: Implement `forbidden-phrases` and the I-Don't-Know test floor
- [ ] M3: Implement the architectural-edge linters
- [ ] M4: Implement the calibration invariant tests
- [ ] M5: Implement the Hermes action-tier enforcement
- [ ] M6: Doc-gardener subagent and tear-down

## Decision Log

### Decision: stub Service-layer business logic rather than implement in this plan

**Rationale**: `Source: ARCHITECTURE.md § 5 Service` — Service layer is testable without mocks because Service is pure with respect to I/O. But the structural tests required (M3, M4, M5) do not depend on Service implementation; they depend on Service *types* and the lint infrastructure that gates future Service implementation. Implementing Service in this plan would expand the surface area beyond what one plan can ship coherently, and would tempt skipping the lints in favour of "we'll add them once the code is working." The order — structural tests before working code — is the load-bearing discipline.

**Date**: bootstrap.

### Decision: Defer language choice for the lint implementations to M3

**Rationale**: `Confidence: low` — the project's primary language is not chosen at bootstrap (`ARCHITECTURE.md § 4` boring-tech ledger has the schema-validator choice marked `Confidence: low` for the same reason). M3 is the first milestone where the language matters; the milestone description includes a per-language note. This is not the same plan inventing the project — it's recognising the gap and naming where it gets resolved.

**Revisit**: M3.

## Surprises & Discoveries

(empty at bootstrap)

## Awaiting Steering

(empty — open questions are tracked in `PRODUCT_SENSE.md`, not here, because they are product decisions rather than execution decisions.)

## Outcomes & Retrospective

(written at completion)
