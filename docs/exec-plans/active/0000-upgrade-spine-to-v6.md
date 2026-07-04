# 0000 — Upgrade the spine to the refined design (v1 → v6)

## Purpose

The knowledge spine in this repository (`ARCHITECTURE.md`, `docs/product-specs/`, `docs/design-docs/`, the four top-level docs) is the *first-generation* spine — the artefacts `0001-bootstrap-the-spine` landed and enforced. Since then the design was refined through a sequence of steering decisions that the repository has not yet absorbed, and one of those decisions reframes the repository itself: **this codebase is Argus-specific.** The other apps (Metis, Hermes) and the pipelines that produce the semantic layer (audio2tree, doc2graph, Navigator) are separate layers, not this repo's code. The refinements this plan absorbs are: the Argus-only rescope and the domain reduction that follows from it; an epistemic classification of the nine expertise modules; a two-stage Argus evaluation contract; a path-as-ontology semantic layer (`INTENTS/`) that is a *runtime artifact* Argus reads, not a build-time domain; the reclassification of Acoustic Feature and Phrase & Keyword from descriptive facts to versioned rubric; the anchoring of history judgements to the intent tree; and the dissolution of Knowledge Calibration as a domain (the filesystem now does that job at write time). This plan rescopes the architecture to Argus, records the architectural decisions as ADRs (the repo currently has none), upgrades the specs, and lands a worked `INTENTS/` example — without disturbing the enforcement layer `0001` already built.

## Big Picture

This is a documentation-and-architecture upgrade, not application code. Nothing in `src/argus/` changes behaviourally; no subcommand, config surface, or on-disk CLI format is touched. The work rescopes the system of record (`docs/` and `ARCHITECTURE.md`) to what this repo actually is, and adds a new top-level `INTENTS/` tree that is reference data Argus reads, not code.

The reframing that drives the plan is three tiers, only one of which is this repo:

- **Transformation layer** (not this repo): audio2tree (Audio Intake + Conversation Distillation) and doc2graph / Navigator (Document Ingestion from human docs; Navigator from live web apps) *produce* `INTENTS/`. In this repo these appear as `.claude/skills/` and subagents, never as `src/argus/` domains.
- **Semantic layer** (data, not code): `INTENTS/` itself — a git-versioned runtime artifact Argus reads at a pinned SHA. It has no place in any layering contract.
- **Consumer layer** (this repo = Argus only): read INTENTS → `score` → `adjust` → emit report/coaching. Metis and Hermes are interface references (Argus emits findings Metis consumes), not code here.

Consequently the repo's own domain set reduces from v1's ten to **five**, mapped directly onto the layers `.importlinter` already enforces (`types → config → io → core → cli`):

- `types` — INTENTS-read result shapes, `FactCheckVerdict` with `raw` / `adjusted` / `applied_precedents`.
- `config` — rubric-version and INTENTS-SHA pinning, thresholds.
- `providers` + `utils` (cross-cutting; the INTENTS reader is a Provider that resolves paths at a pinned SHA — this is where the former "Expertise Library" domain goes, collapsed from nine reader interfaces to one INTENTS provider). Maps onto `io`.
- `core` — `score` (`raw = score(facts, rubric)`), `adjust` (`adjusted = adjust(raw, history)`), and report/coaching emission. All pure; maps onto `core`.
- CLI surface — maps onto `cli`.

In scope: rescoping `ARCHITECTURE.md` to Argus-only (platform-reference split out from repo-enforced) and reconciling it with `.importlinter` by mapping the five domains onto the five enforced layers; four ADRs (the two design ADRs plus two *dissolution* ADRs — Knowledge Calibration and Expertise-Library-as-artifact); edits to `expertise-library.md`, `calibration.md`, `fact-checking.md` to carry the epistemic classes and two-stage contract; a new `intents-semantic-layer.md`; the `INTENTS/` worked tree; and a `QUALITY_SCORE.md` regrade.

Deliberately out of scope, and named so a later plan does not assume otherwise: no new lints (the refined design *names* checks like `argus-eval-purity` and the `intents-*` family; promoting them from `Aspiration:` to code is separate, evidence-driven work under the promotion rule). No population of `INTENTS/` beyond the single worked example. No `references/node_contract.md` (the tree-interior schema gate, owned by the human). No elaboration of `.importlinter` into per-domain sub-contracts — that is option (B) in the rescope ADR, deferred until `src/argus/` actually holds the domains; enforcing structure over near-empty packages now would violate the same discipline that starts QUALITY_SCORE at F.

## Milestones

### M1 — Rescope ARCHITECTURE.md to Argus, reconcile with .importlinter

Split the architecture into two views. Add a short `docs/references/platform-architecture.md` holding the three-tier map (transformation → semantic → consumer; audio2tree / doc2graph / Navigator produce INTENTS; Argus / Metis / Hermes consume) as *reference*, explicitly non-enforced because it describes systems not all in this repo. Then rewrite `ARCHITECTURE.md` (root) to describe only Argus: the five domains `types`, `config`, `providers`+`utils`, `core`, `cli`, mapped one-to-one onto the layers `.importlinter` already enforces (`types → config → io → core → cli`). The INTENTS reader is a Provider (`io`); `score`, `adjust`, and report/coaching are `core`; the former "Expertise Library" and "Knowledge Calibration" domains are removed as domains (their dispositions are the two ADRs in M2). Choose reconciliation option (A) — keep the five-layer CLI contract, map domains onto it — over option (B) — per-domain sub-contracts — and record the choice in the rescope ADR with the "don't enforce structure over empty packages" rationale.

`Acceptance Test:` `tests/test_architecture_argus_scoped.py::test_five_domains_map_to_importlinter_layers` — parses `ARCHITECTURE.md`, asserts it names exactly the five Argus domains and no Metis/Hermes/Calibration/Expertise-Library *domain*, and that each named layer matches a layer in `.importlinter`; plus `uv run lint-imports` still passes unchanged. (New test.)

`Notes:` `ARCHITECTURE.md` is pinned by `test_prd_spine_drift.py`. Re-run it; a rescope *will* trip a drift pin — that is expected here, and the milestone must update whatever the drift test anchors on, not suppress the test. This milestone lands before the INTENTS milestones so the target architecture is settled before the tree that populates it arrives.

### M2 — Land the four ADRs

Add to `docs/adr/` (currently empty — these are its first entries):
- `0001-expertise-epistemic-classes-and-argus-eval-function.md` — the three epistemic classes, the nine-module assignment, and the two-stage `score`→`adjust` contract.
- `0002-intents-path-as-ontology.md` — the INTENTS semantic layer and git-SHA epoch.
- `0003-knowledge-calibration-dissolves-to-write-time-ownership.md` — Calibration is no longer a runtime domain; bottom-up authority is enforced by file ownership plus demand-minted (customer-language) slugs, and coverage gaps are emitted producer-side. Records the reversal so a future reader does not "restore" the missing domain thinking it was lost by accident. Names the one caveat to verify (M7): that Argus never has to reconcile two conflicting knowledge sources at read time — it always reads an already-single, already-calibrated tree.
- `0004-expertise-library-is-a-runtime-artifact.md` — the Expertise Library is the INTENTS folder read at runtime, not a code domain; the nine v1 reader interfaces collapse to one INTENTS Provider with typed returns.

`Acceptance Test:` `tests/test_adrs_present.py::test_four_foundational_adrs_exist_and_are_wellformed` — asserts all four exist, each has a `**Status**:` line and a `## Decision` section, and `docs/adr/` is no longer empty. (New test.)

`Notes:` all four bodies must pass the existing `test_no_forbidden_phrases.py`. ADR-0003 and ADR-0004 each remove a v1 keystone, so their Context sections must state what they replace and why the removal is safe.

### M3 — Reclassify Acoustic Feature and Phrase & Keyword in the expertise spec

Edit `docs/product-specs/shared/expertise-library.md` to add the epistemic-class table and move Acoustic Feature and Phrase & Keyword from descriptive facts into the versioned-rubric class, with the measurement-versus-yardstick reasoning (per-call measurements remain facts in the call record; the indicator framework and the lexicon are the yardstick). Update the module-reader grouping into the three category readers.

`Acceptance Test:` `tests/test_expertise_classes.py::test_acoustic_and_phrase_are_rubric` — parses the spec, asserts both modules appear under the Versioned-rubric class and not under Facts, and that the three category readers are named. (New test.)

`Notes:` this is the change most likely to have downstream references. After editing, grep `docs/` for any remaining "Acoustic Feature … fact" or "Phrase & Keyword … fact" framing and fix or flag each.

### M4 — Land the two-stage Argus evaluation contract

Edit `docs/product-specs/argus/fact-checking.md` to replace the single-function framing with the two-stage contract: `raw = score(facts, rubric)` then `adjusted = adjust(raw, history)`, with per-precedent attribution (`applied_precedents[]` on the verdict) and the purity-within-epoch property. Update the Inputs section so `rubric` includes the acoustic framework and phrase lexicon and `facts` no longer does. Reference ADR-0001.

`Acceptance Test:` `tests/test_argus_eval_contract.py::test_two_stage_score_then_adjust` — asserts the spec contains both stage signatures, that `history` is not an argument to `score`, and that the verdict records `raw`, `adjusted`, and `applied_precedents`. (New test.)

### M5 — Land the INTENTS semantic-layer spec and the calibration two-axes amendment

Add `docs/product-specs/shared/intents-semantic-layer.md` (the full layout: path-as-ontology, the single `_rubric/` shelf with three modules, facts anchored by scope, history anchored to the L3 case, the naming grammar, the git-SHA epoch). Amend `docs/product-specs/shared/calibration.md` with the coverage-axis / content-axis split. Add the INTENTS representation paragraph and the boring-tech-ledger row (filesystem+bash over RAG) to `ARCHITECTURE.md`, plus the Argus two-stage note in its Service section.

`Acceptance Test:` `tests/test_intents_spec.py::test_semantic_layer_spec_coherent` — asserts the spec names the `_rubric/` shelf with three modules, states "anchor level = scope", places history at L3, and that `ARCHITECTURE.md` references ADR-0002. (New test.)

`Notes:` `ARCHITECTURE.md` is a sensitive, drift-checked file (`test_prd_spine_drift.py`). Re-run that test after editing; if it fails, the edit changed something the drift test pins — reconcile rather than override.

### M6 — Land the worked INTENTS tree

Add the `INTENTS/` tree for the single worked domain: `AGENTS.md`, `EPOCH.yaml`, `tensors.json`, `_meta/{conventions,ownership}.yaml`, the `_rubric/` shelf (rules, the 12-indicator acoustic framework, the phrase-keyword lexicon + one script), and the `annual-report-submission/` branch with its L2 capsule (Bone top-loaded in `index.md`), L3 case, anchored `kb.*` facts, and anchored `cookbook.*` / `errors.*` history.

`Acceptance Test:` `tests/test_intents_tree_wellformed.py::test_worked_example_parses_and_owns` — walks `INTENTS/`, asserts every `.yaml`/`.json`/`.jsonl` parses, every file matches exactly one producer glob in `_meta/ownership.yaml` (zero multi-owner, zero orphaned), and every operator `ui_binding_ref` in the capsule Bone resolves to a Flesh `ui_step`. (New test; this is the structural invariant the tree must hold.)

`Notes:` the tree is reference data, not `src/` — it is exempt from `.importlinter`. Confirm `INTENTS/` is not swept by the layering test.

### M7 — Regrade and reconcile

Regrade any `QUALITY_SCORE.md` rows the new specs move (the acoustic/phrase reclassification and the INTENTS representation change what "doc-freshness" and "coverage" mean for the Expertise and Calibration rows). Run the full existing harness (`uv run pytest .claude/tests tools/lint/tests tests -q` and `uv run lint-imports`) and confirm nothing the upgrade touched regressed. Write the Outcomes section.

`Acceptance Test:` `tests/test_upgrade_consistency.py::test_no_v1_residue` — greps the tree for stale-classification residue (Acoustic/Phrase framed as facts; any `_facts/` or `_history/` shelf reference outside an explicitly-superseded ADR block) and asserts none remains. Plus: the pre-existing harness suite passes unchanged.

## Progress

- [x] M1: Rescope ARCHITECTURE.md to Argus + reconcile with .importlinter  (done 2026-07-04)
- [ ] M2: Land the four ADRs
- [ ] M3: Reclassify Acoustic + Phrase to rubric
- [ ] M4: Land the two-stage Argus contract
- [ ] M5: Land the INTENTS spec + calibration two-axes amendment
- [ ] M6: Land the worked INTENTS tree
- [ ] M7: Regrade and reconcile

## Decision Log

### Decision: upgrade the spine in place rather than re-bootstrap

**Rationale:** `Source: docs/exec-plans/completed/0001-bootstrap-the-spine.md` — the bootstrap already ran; the enforcement layer (8 lints in `tools/lint/`, 14 tests in `.claude/tests/`, import-linter, hooks, CI) exists and passes. Re-running a bootstrap would tear down and rebuild working machinery. The refined design is a *delta* on the landed spine — new ADRs, edited specs, an added `INTENTS/` tree — so the plan edits and adds, and touches no enforcement code.


### Decision: this repository is Argus-only; reduce ten domains to five and map onto the enforced layers

**Rationale:** `Source: steering 2026-07-04` — the three products are three tiers, and only the consumer tier's Argus app is this repo's code. Transformation (audio2tree, doc2graph, Navigator) produces INTENTS and lives in `.claude/skills/` and subagents or separate services; the semantic layer (INTENTS) is a runtime data artifact, not code; Metis and Hermes are interface references, not domains here. What remains is `types`, `config`, `providers`+`utils`, `core`, `cli` — five domains that map one-to-one onto the `.importlinter` layers `types→config→io→core→cli`. This dissolves the pre-existing doc-vs-linter divergence rather than deferring it. Promoted to the rescope ADR (M1) because it outlives this plan.

### Decision: reconciliation option (A) — map domains onto the five-layer CLI contract, not per-domain sub-contracts

**Rationale:** `Source: CLAUDE.md § Simplicity First` — `src/argus/` is near-empty scaffolding; elaborating `.importlinter` into per-container sub-contracts (option B) would enforce structure over packages that do not yet hold code. Option (A) matches what Argus actually is (read → compute → emit) and changes nothing in the enforcement layer. `Confidence: low` on whether (B) becomes worth it later; `Revisit:` when `src/argus/core` holds real `score`/`adjust` modules.

### Decision: promote the two design decisions to ADRs, not Decision-Log entries

**Rationale:** `Source: docs/PLANS.md § 5` — "If a decision is large enough to outlive this plan … promote it to an ADR." The epistemic classification and the path-as-ontology layer both outlive this plan and constrain all future Argus/Metis/Hermes work. `docs/adr/` being currently empty is itself a signal the repo has been carrying architectural decisions in prose without records.

### Decision: no new lints in this plan

**Rationale:** `Source: CLAUDE.md § The promotion rule` — a rule becomes a structural test/hook/CI gate only after it has demonstrated need (typically two violations). The refined-design checks are named as `Aspiration:` in the specs; promoting them is separate, evidence-driven work. Landing the documents first is the correct order. `Confidence: low` on whether `argus-eval-purity` should be fast-tracked given its safety weight; `Revisit:` after M3.

## Surprises & Discoveries

### The v1 doc-vs-linter divergence is closed by M1, not deferred

The original framing of this plan treated the `ARCHITECTURE.md` (10 domains / 6 layers) vs `.importlinter` (5 layers / 1 `argus` package) mismatch as out-of-scope. The Argus-only rescope makes it in-scope and tractable: the honest domain count for an Argus consumer is five, and it maps directly onto the enforced layers, so M1 resolves the divergence instead of leaving it for a later plan.

*No other surprises yet — this section grows during execution. The Verifier records milestone-flip failures here.*

## Awaiting Steering

The following are Tier C under `docs/conventions/ask-threshold.md` (on-disk format changes / new top-level structure). Defaults act if not resolved by the named milestone.

> **Awaiting Steering: resolved — Q1.** INTENTS location is configurable. The tree lands at repo root as the default (`INTENTS/`), but the path is configurable via `argus.config.intents_path`. The spec (M5) documents this configurability; the actual config mechanism is deferred to the first Argus exec-plan.

> **Awaiting Steering: resolved — Q2.** Reclassification of Acoustic Feature and Phrase & Keyword to rubric is accepted as the standing contract for `src/argus/`.


> **Awaiting Steering: resolved — Q3.** Proceed as planned: rescope to five Argus domains (`types`, `config`, `providers`+`utils`, `core`, `cli`), dissolve Knowledge Calibration and Expertise Library as domains, record dissolutions as ADR-0003 and ADR-0004.

## Outcomes & Retrospective

*Empty — written at completion.*
