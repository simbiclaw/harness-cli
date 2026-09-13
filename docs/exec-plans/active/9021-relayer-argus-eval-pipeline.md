# 9021 — Re-layer the Argus Eval Pipeline onto a Working Engine

## 1. Purpose

This plan **completely supersedes and overturns 9002**
(`docs/exec-plans/archived/9002-implement-argus-eval-pipeline.md`, archived 2026-09-12).

**Why 9002 was overturned.** It never executed — all eleven milestones sat unchecked for
sixty-six days — and while it waited, two things invalidated it. First, an investigation found a
working Chinese-language customer-service QA evaluator in `simbiclaw/sim` (`0c2cccd`) that
already satisfies the hardest invariants 9002 exists to enforce: its model proposes labels,
evidence and questions but never a score, weight, dimension roll-up or grade, and it has no write
path into any intent store. Second, 9020 declared itself a dependent that would execute *after*
9002's milestones shipped, then completed anyway — leaving three of 9002's milestones
contradicted by shipped code. The full reasoning is in the archived plan's Outcomes section.

**What this plan does instead.** Argus stops being built from scratch. The model-facing half of
`simbiclaw/sim` moves into `src/argus/io/` — the quarantine — largely unchanged. The pure stages
that exist in neither codebase (grounding, adjust, route, epoch pinning, replay) are built in the
gap between them. This repository's harness, its 9003 rubric compiler and its I8 provenance
machinery are retained and, for the first time, pointed at real code.

**Key differences from the overturned plan:**

| Aspect | 9002 (overturned) | 9021 (this plan) |
|:---|:---|:---|
| Proposer (S2) | Written from scratch, `anthropic`-only | Imported from `simbiclaw/sim`: 14 call sites, 9 modules, moved verbatim into `io/` |
| Scorer (S4a) | Written from scratch | Extracted from B's `core/aggregator.py` — a redesign of the boundary, not a file move |
| Rubric | Assumed to exist in `INTENTS/` | B's 27-item table becomes `SpecificRubric` input, compiled by 9003 into epoch-pinned nodes |
| Layer fences | Asserted in prose; three of four vacuous | Four `forbidden` import-linter contracts, each proved by a planted violation |
| Baseline | Empty `src/argus/` | `simbiclaw/sim@0c2cccd` plus this repo at the 9020 head |
| 9020 relationship | Unstated | Section 2.1 records the inheritance explicitly |

## 2. Big Picture

The layer boundary this repository specifies and `simbiclaw/sim` ignores falls close to where B's
module graph already splits. B's stages −1 through 5 are *proposal*: they consume a transcript and
emit labels, atoms, questions, evidence pointers and one routing confidence. B's stage 6 is
*derivation*: arithmetic over rubric constants with no model in it. Moving the first group into
`io/` makes quarantine a directory move rather than a rewrite; that is this plan's whole thesis.

In scope: the import and re-layering of B's pipeline; the pure stages S3, S4a, S4b and S5; epoch
pinning; replay; the four layer fences as enforced artifacts; compiling B's rubric through 9003.

Deliberately out of scope: any change to the 9003 compiler's own design; audio ingest (S0 is
upstream); Metis and Hermes; multi-language support — this plan commits Argus to zh-CN
customer-service QA at the code level, and a future multi-language requirement is a rewrite rather
than a configuration.

**Two-repository note.** Milestones M1–M4 execute in `simbiclaw/sim`, not here: B's defects are
fixed in place before the import so they surface in their own diffs rather than hidden inside a
1,600-line move. Their acceptance tests run in that repository. The File Scope block below is
repo-relative to `harness-cli` per the rubric, so it does not list them.

**INTENTS is deliberately absent from File Scope.** M13 reads `INTENTS/` and `EPOCH.yaml`;
no code in `src/argus/` writes them (D15). **M16 is not an exception to this and must not become
one.** M16 runs the 9003 compiler to *produce* `_rubric/` AuthoredNodes, and those nodes' home is
`INTENTS/_rubric/rules_criteria/**` — so the milestone emits them to a staging path and stops
there. Committing them into the tree is an upstream write-time epoch act (S6, ADR-0003), performed
by a human or by the compiler line, never by Argus reaching back into its own referent. An earlier
revision of this plan asserted the D15 rule in this paragraph while M16 read as though it wrote the
nodes directly; an implementer would have had to pick a reading, and neither was recorded as
intended. `.claude/tests/test_plan_collisions.py` intersects
declared paths with no read/write distinction, and 9008 declares `INTENTS/**` (modify), so
declaring a read-only INTENTS path here would fail the collision test and block both plans. Do not
add one.

CLI surface: M21 adopts B's three run modes under this repository's entry point — Tier C, parked
as Q17. Config surface: M22 lands typed configuration in `src/argus/config/**`, a sensitive path —
Tier C, parked as Q11. Filesystem surface: the evaluation record gains a sidecar run manifest —
Tier C, parked as Q19.

### 2.1 Inheritance from 9020

9020 is complete and its deliverable stands, but it was built on provisional structures that named
9002 as their replacement. This plan inherits that debt. Recorded here so it cannot be lost in the
supersession.

| What 9020 left | Where | This plan's disposition |
|:---|:---|:---|
| `types/proposer_diagnostics.py` stand-ins — `QuarantinedFindingGraph`, `EvaluationResult`, `derive_evaluation` | self-declared "placeholders ... which are unstarted" | Retired by M5–M6; `_replay_payload`'s three-key allowlist is kept as the executable form of I5 |
| `divergence.py:assess_drift` — "provisional detector" | `core/divergence.py` | Kept; M17 supplies its missing consumer |
| `escape_sampler.py:compute_escape_rate` — "9002 M5.5 owns the real one" | `core/escape_sampler.py` | Reconciled in M19; the split between sampler and estimator ends there |
| Letter-scale token-id mapping is a first-g placeholder | `local_proposer.py:_scale_slice` | Unresolved; it fails silently on a real model. Gated behind Q11 (config) and the M20 demotion |
| `llama-cpp-python` dep-vet records the downloads check as unverified | `docs/decisions/dep-vet-llama-cpp-python.md` | Carried; a human with unproxied network confirms |
| M6 — pinned capacity measurement | unflipped, deferred | Carried as a live follow-up, not closed. Tracked in issue #15 |
| Six open steering questions: 9020's Q2, Q3, Q4, Q5, Q6, Q8 | 9020 Outcomes names them "the honest inheritance for 9002" | Transcribed to this plan's Q10–Q15 |

One inherited item is incoherent and is repaired rather than transcribed. 9020's Q2 states its
default as "none — M2 does not start", but M2 shipped on 2026-08-27. A deadline cannot fire on a
flipped milestone. Restated as Q10 with a default that can actually execute.

**File Scope:**
- `src/argus/io/**` (new — B's proposal half, re-namespaced)
- `src/argus/core/score.py` (new)
- `src/argus/core/grounding.py` (new)
- `src/argus/core/corroboration.py` (new)
- `src/argus/core/adjust.py` (new)
- `src/argus/core/route.py` (new)
- `src/argus/core/escape_rate.py` (new)
- `src/argus/types/**` (new + modify — B's schemas replace the 9020 stand-ins)
- `src/argus/config/**` (new — gated on Q11)
- `src/argus/cli/main.py` (modify — gated on Q17)
- `tests/test_schemas.py` (new)
- `tests/test_evidence_anchor.py` (new)
- `tests/test_io_import.py` (new)
- `tests/test_fences.py` (new)
- `tests/test_i8_provenance_separation.py` (modify — widen the live scan)
- `tests/test_score.py` (new)
- `tests/test_grounding.py` (new)
- `tests/test_intents_provider.py` (new)
- `tests/test_signals.py` (modify — polarity regression)
- `tests/test_rubric_input.py` (new)
- `tests/test_rubric_compile.py` (new)
- `tests/test_corroboration.py` (new)
- `tests/test_adjust.py` (new)
- `tests/test_route.py` (new)
- `tests/test_divergence.py` (modify — disjoint-key guard)
- `tests/test_replay.py` (new)
- `tests/test_cli.py` (new)
- `.importlinter` (modify — the four forbidden contracts)
- `docs/conventions/layering.md` (modify — Q16: amend :41 so the convention and the lint agree)
- `pyproject.toml` (modify — dependency changes)
- `docs/decisions/dep-vet-transformers.md` (new)
- `docs/rubric/specific-rubric-27.yaml` (new — B's table as compiler input)
- `docs/experiments/9021-ab-investigation/**` (new — the evidence base this plan cites)
- `docs/exec-plans/active/9021-relayer-argus-eval-pipeline.md` (modify — this plan)

## 3. Milestones

**How to read a milestone, and which half binds you.** Every milestone carries a **Contract** block
— Deliverable, Binding constraint, Acceptance property, Known evidence. **The Contract is what
binds.** The prose and the named `Acceptance Test:` functions above it were written in a cloud
session that could not install dependencies, could not read the spec, and could not read INTENTS.
They are a starting sketch, not a specification: treat them as evidence of what was known at
authoring time, and discard any of it that contact with the code contradicts.

This split exists because the alternative failed here, three times in one document. A local review
found that this plan had written `replay_hash` as "grounded inputs only" (dropping the anchored
precedents I5 requires), had named only two of I6's three weight classes (deleting the correlated
class entirely), and had asserted the D15 no-write rule while a milestone produced nodes that live
inside INTENTS. **Each was a paraphrase of an invariant that lost part of the invariant.** An agent
implementing those paraphrases would have built a hash that cannot detect what it exists to detect,
a corroboration aggregator with no home for correlated evidence, and a write path the plan forbids.

So: where a Binding constraint cites an invariant, go read the invariant — do not implement this
plan's summary of it. Where the Acceptance property states a behaviour, prove that behaviour; the
test's name and design are yours. Where Known evidence conflicts with what you find, what you find
wins, and the conflict belongs in Surprises.

Two numbers this plan deliberately does **not** supply, because neither is knowable before the code
runs: the random tranche's absolute floor (M19) and the role-swap confidence floor (M2). Measure,
then declare, then record the basis.

### M1 — Fix B's two blocking crashes

In `simbiclaw/sim`. `agents/qa_agent.py:66` calls `self.kb_builder`, never assigned (`:31` assigns
`self.kb_context_builder`). `:125` raises `KeyError: 'grade'`. Both sit on the single happy path.

`Acceptance Test:` `tests/test_qa_agent.py::test_pipeline_reaches_report` — the orchestrator runs
end to end against a fake LLM and returns a report object.


**Contract.**
- *Deliverable:* B's pipeline runs end to end without raising.
- *Binding constraint:* None beyond the verification floor. This is defect repair in B's own repository.
- *Acceptance property:* A transcript entering the orchestrator yields a report object with no unhandled exception on the happy path.
- *Known evidence (advisory):* Two crashes were identified — an unassigned attribute in Stage 0 and a missing key at Stage 6. Treat the cited paths as leads and confirm against the tree you execute in.

### M2 — Fix the role-swap false positive

`_verify_roles` returns `should_swap=True` on a correctly-labelled transcript; `:41-42` then
inverts every role, checking agent criteria against customer utterances. Add a confidence floor
so a low-confidence swap routes to a human rather than silently inverting.

`Acceptance Test:` `tests/test_asr_preprocessor.py::test_timestamp_parsing` — currently failing;
passes without a swap. Plus `::test_low_confidence_swap_defers` — a marginal case routes to human.


**Contract.**
- *Deliverable:* Speaker-role assignment that does not silently invert a correctly-labelled transcript.
- *Binding constraint:* No numbered invariant, but a wrong role inverts every downstream verdict, so an uncertain swap defers to a human rather than applying.
- *Acceptance property:* A correctly-labelled transcript is left unswapped; an ambiguous one routes to a human instead of guessing.
- *Known evidence (advisory):* The heuristic currently returns swap-true on a correct transcript. **Measure its actual error rate before choosing any threshold — do not adopt a number from this plan.**

### M3 — Repair the ASR-reliability chain

`core/preprocessor.py` drops `timestamp_start`/`timestamp_end` when building `Turn`, and path C's
reliability branch is dead. The atomiser propagates `reliability=low` to no effect.

`Acceptance Test:` `tests/test_fact_checker.py::test_low_reliability_forces_human_review` — a
turn marked low-reliability produces a verdict requiring review.


**Contract.**
- *Deliverable:* The reliability signal the atomiser computes reaches the verdict that consumes it.
- *Binding constraint:* None beyond the floor. A dropped uncertainty signal is a silent-confidence defect.
- *Acceptance property:* A turn marked low-reliability demonstrably changes the routing of a verdict resting on it.
- *Known evidence (advisory):* The chain is reported broken at its last link, and timestamps appear to be dropped when the turn type is built. Confirm both.

### M4 — B's first end-to-end test

B has zero integration tests, which is why M1's two crashes survived. Needs a fake LLM covering
14 call sites and a stub NLI, since `transformers` cannot be installed in CI.

`Acceptance Test:` `tests/test_e2e.py::test_transcript_to_report` — a real transcript from
`data/transcripts/` produces a complete report with no network access.


**Contract.**
- *Deliverable:* An executable end-to-end test over a real transcript, with no network.
- *Binding constraint:* The verification floor: an externally observable property exercised against real data.
- *Acceptance property:* The pipeline runs from a real transcript file to a report, deterministically, offline.
- *Known evidence (advisory):* B has no integration test, which is why M1's crashes survived. The NLI dependency may not be installable in every environment.

### M5 — Port B's schemas into `types/`

B's `models/schemas.py` (25 Pydantic models) replaces 9020's stand-ins. The stage decomposition it
encodes — atoms to coverage to questions to verdicts, with `turn_id`/`doc_path` provenance — is
the contract everything else attaches to.

`Acceptance Test:` `tests/test_schemas.py::test_all_schemas_roundtrip` — each schema constructs,
serializes and deserializes. `::test_replay_payload_excludes_proposed_score` — 9020's I5 allowlist
survives the port.


**Contract.**
- *Deliverable:* The pipeline's data contracts live in `types/`.
- *Binding constraint:* I5 — the replay-bearing record stays separable from diagnostics.
- *Acceptance property:* Every contract round-trips, and a proposed score cannot enter the replay-bearing payload.
- *Known evidence (advisory):* B carries the stage decomposition in its schemas; A's are self-declared placeholders. Q10 adopted four diagnostic fields — where they live is yours to design.

### M6 — Extend `EvidenceItem` to an I2 anchor slot

Add `span`, `quote` and `intents_sha`. Re-plumb timestamps through stage 1 so spans are
recoverable. Verified feasible: B's parser mutates turn text only with `.strip()`, and a
round-trip on the sample transcript recovered 17/17 turns as exact substrings.

`Acceptance Test:` `tests/test_evidence_anchor.py::test_span_roundtrip` — every evidence item
recovers an exact character span from the raw transcript. `::test_ambiguous_span_rejected` — a
turn text occurring twice fails rather than guessing.


**Contract.**
- *Deliverable:* Evidence traceable to an exact location in the source transcript.
- *Binding constraint:* I2 — every finding references a real transcript span, exact-quote verified, or is routed to a human.
- *Acceptance property:* Any stored evidence item resolves to a verbatim substring of the raw transcript; an unresolvable one fails rather than passing.
- *Known evidence (advisory):* A round-trip on the sample transcript recovered every turn exactly. Capturing offsets at parse time was suggested as more robust than recovering them later. Short turns may collide on longer calls — verify.

### M7 — Move B's proposal half into `io/`

Eleven modules re-namespaced, behaviour unchanged: asr_preprocessor, preprocessor, atomizer,
intent_inferrer, question_generator, kb_context_builder, intent_retriever, llm_client, nli,
prompts, qa_agent. Squashed import commit citing `simbiclaw/sim@0c2cccd`.

`Acceptance Test:` `tests/test_io_import.py::test_pipeline_runs_from_io` — the moved pipeline
produces the same output as M4's baseline on the same input.


**Contract.**
- *Deliverable:* Every model-touching module lives under `io/`.
- *Binding constraint:* I1 — model nondeterminism exists only in S2, which lives in `io/`.
- *Acceptance property:* The pipeline produces the same output after the move as before it, and no module outside `io/` reaches a model.
- *Known evidence (advisory):* Fourteen call sites across nine modules. B's module graph splits close to the layer boundary, which is why this is a move rather than a rewrite.

### M8 — Land the four `forbidden` import-linter contracts

`core ✗ model_client`, `grounding ✗ proposer`, `grounding ✗ matching_model`,
`aggregate ✗ model_client`. Requires `include_external_packages = True`. The existing layers
contract permits `core → io`, which must be reconciled with these — see Q16.

`Acceptance Test:` `tests/test_fences.py::test_planted_violation_fails_lint` — a planted
`from anthropic import Anthropic` in a `core/` module makes `lint-imports` exit non-zero.
`::test_clean_tree_passes`. A contract that has never failed is not enforcement.


**Contract.**
- *Deliverable:* The four layer fences enforced by an artifact that can fail.
- *Binding constraint:* The four fences in CLAUDE.md. Q16 forbids `core -> io`.
- *Acceptance property:* A planted violation of each fence fails the lint and a clean tree passes. **A contract that has never failed is not enforcement.**
- *Known evidence (advisory):* The existing layers contract cannot see third-party imports, and the current backstop is a short denylist. External-package visibility may need enabling — confirm how.

### M9 — Repoint the I8 checker at the populated tree

`tests/test_i8_provenance_separation.py` currently scans a nearly-empty `core/`. Its allowlist
assumes two modules exist. Widen the scan, keep the red/green pair.

`Acceptance Test:` `tests/test_i8_provenance_separation.py::test_live_core_tree_clean` — passes
against the populated tree with the allowlist reasoned, not widened to admit violations.


**Contract.**
- *Deliverable:* The provenance checker scans the populated `core/` tree.
- *Binding constraint:* I8 — logit-derived continuity must not reach a disposer input.
- *Acceptance property:* The checker still fails on its planted red case after the tree grows, and its allowlist is reasoned rather than widened to admit violations.
- *Known evidence (advisory):* This is the repo's strongest existing artifact; it currently scans a nearly-empty directory.

### M10 — Extract `score(facts, rubric)`

Not a move. B's `aggregate()` is an 8-argument report builder taking model-authored prose, with no
rubric argument — weight is stamped onto verdicts by `fact_checker.py:193-196` and `is_veto` by
`question_generator.py:110`, both inside modules now in `io/`. Lift both out so the rubric enters
the arithmetic from `core/`.

`Acceptance Test:` `tests/test_score.py::test_i3_determinism_canary` — identical inputs give
byte-identical `raw`. `::test_score_receives_no_history`. `::test_weight_comes_from_rubric_not_verdict`.
`::test_core_no_model_client`.


**Contract.**
- *Deliverable:* A pure scoring function taking grounded facts and the rubric.
- *Binding constraint:* I3 — `raw = score(facts, rubric)`, and `score` never receives history. I1 — `core/` imports no model client.
- *Acceptance property:* Identical grounded findings and rubric version produce an identical raw score, and the rubric's weight reaches the arithmetic from `core/` rather than from inside the quarantine.
- *Known evidence (advisory):* B's aggregator is a report builder with no rubric parameter, and weight and veto are stamped inside modules bound for `io/`. This is a redesign, not a move — the shape of the redesign is yours.

### M11 — Re-litigate NEI scoring

B scores NEI at 0.5 and keeps it in the denominator, so an unverifiable item contributes half a
point. This repository's rules route an ungrounded finding to a human and block auto-final. Adopt
the latter; it changes every score B has produced.

`Acceptance Test:` `tests/test_score.py::test_nei_excluded_from_denominator` —
an NEI item neither scores nor counts. `::test_nei_blocks_auto_final`.


**Contract.**
- *Deliverable:* A scoring policy for unverifiable items consistent with the deferral rules.
- *Binding constraint:* I2 and D10 — an ungrounded finding routes to a human and blocks auto-final.
- *Acceptance property:* An unverifiable item cannot silently contribute to a shipped score.
- *Known evidence (advisory):* B scores the unverifiable case at half a point and keeps it in the denominator; adopting the deferral rule changes every score B has produced. The spec defines no denominator.

### M12 — Build `core/grounding.py` (I2)

Exact-quote verification against the transcript, INTENTS node resolution at a pinned epoch, and
the `ungrounded` bucket. Path B evidence is declared unanchorable and routes to `ungrounded`: its
text is model-authored prose, not a quote from the cited document.

`Acceptance Test:` `tests/test_grounding.py::test_i2_anchor_or_quarantine_red` — a finding citing
a non-existent node moves to `ungrounded`. `::test_quote_fidelity_red`. `::test_path_b_always_ungrounded`.
`::test_grounding_no_model_import`.


**Contract.**
- *Deliverable:* S3, the grounding gate.
- *Binding constraint:* I2, plus the two grounding fences — the gate imports neither the proposer nor a matching model.
- *Acceptance property:* A finding that anchors to nothing real is routed, never dropped, and quote fidelity is verified against the transcript rather than asserted.
- *Known evidence (advisory):* Evidence on B's document-verification path is model-authored prose rather than a quotation, so it is not anchorable in its current form.

### M13 — Build `io/intents_provider.py` and the epoch reader (I4)

Read-only access to `INTENTS/` at a pinned git SHA from `EPOCH.yaml`. Record the model-selected KB
path in the run manifest so referent selection becomes replayable rather than re-guessed — B's
drill-down picks the node by asking the model, with no depth cap and no visited set.

`Acceptance Test:` `tests/test_intents_provider.py::test_reads_at_pinned_epoch`.
`::test_no_write_path` — the provider exposes no mutating method.
`::test_s1_no_write_path_into_intents` — an AST scan confirms no `src/argus/` path opens an INTENTS
file for writing. This is 9002's M7 fixture, which was specified and never written.


**Contract.**
- *Deliverable:* Read-only access to INTENTS at a pinned epoch.
- *Binding constraint:* I4 — pinned referents. D15 — no write path into INTENTS from `src/argus/`.
- *Acceptance property:* Two runs against the same epoch reproduce the same grounding outcomes, and no code path opens an INTENTS file for writing.
- *Known evidence (advisory):* Reported as one tree rather than two. The fork and the local tree sit at different revisions, so the real question is which revision, not which tree.

### M14 — Fix the polarity-blind FAIL signal before compiling anything

`core/compiler/signals.py:353-361` emits a FAIL signal that does not distinguish polarity. The
compiler's only shipped output carries it. Compiling 27 items through this manufactures 27 wrong
rubrics faster than a human can review them.

`Acceptance Test:` `tests/test_signals.py::test_fail_signal_polarity` — item 18 as the regression
case; an inverted-polarity input no longer produces a passing signal.


**Contract.**
- *Deliverable:* A compiler signal that distinguishes polarity.
- *Binding constraint:* None beyond the floor.
- *Acceptance property:* An inverted-polarity input no longer yields a passing signal.
- *Known evidence (advisory):* Reported in the signals module; item 18 is the natural regression case. Compiling many items through an undetected polarity defect manufactures wrong rubrics faster than review can catch them.

### M15 — Land B's 27 items as `SpecificRubric` input

B's `config/rubric_items.py` becomes `docs/rubric/specific-rubric-27.yaml` — all 27 rows, with
items 6 and 7 carrying a permanent inapplicability gate and a `data_dependency` naming the system
they need. Re-verify all 27 against the upstream source where recoverable; B's transcription is
lossy in at least two places (item 18 drops a counter-example, item 1 has an empty fail standard).

`Acceptance Test:` `tests/test_rubric_input.py::test_27_rows_parse_as_specific_rubric`.
`::test_items_6_and_7_are_permanently_inapplicable` — both carry a `data_dependency` and neither
reaches the denominator. `::test_25_items_scored`. `::test_no_empty_fail_standard`.


**Contract.**
- *Deliverable:* The human rubric available as compiler input.
- *Binding constraint:* The rubric is a public artifact. Items excluded for data dependency are recorded with their reason, not deleted.
- *Acceptance property:* The scored set matches the operational scope, and an excluded item never reaches the denominator.
- *Known evidence (advisory):* The item count is contested — settle it by listing the live node ids before starting. B's transcription is lossy in at least two places.

### M16 — Compile the rubric through 9003

Produce epoch-pinned `_rubric/` AuthoredNodes with the align map decided in Q3: item 22 to
Empathy & Tone, items 23–25 to Problem Resolution, item 26 to Empathy & Tone with its Problem
Resolution axis recorded as `within_dimension` residue, item 27 to Procedural Accuracy at the
compliance layer. Compiler output is diffed against B's hand-assigned weight and veto; divergences
are findings, not overrides.

`Acceptance Test:` `tests/test_rubric_compile.py::test_all_27_compile_or_declare_residue`.
`::test_item_27_is_compliance_layer` — the veto item does not depend on the judgment gates.
`::test_hand_assignment_divergences_recorded`.


**Contract.**
- *Deliverable:* Compiled rubric nodes.
- *Binding constraint:* D15 — Argus emits nodes; the epoch commit that lands them is an upstream write-time act. Until compilation, soft criteria correctly return deferred.
- *Acceptance property:* Every item either compiles or declares residue, and the veto criterion does not depend on the judgment gates.
- *Known evidence (advisory):* Q3 fixed the dimension mapping. Assessment mode may be inferred at runtime from key presence rather than stored — verify against the live nodes before assuming either.

### M17 — Build `core/corroboration.py` (I6)

Independence-weighted aggregation over verified signals, across **all three** weight classes:
independent (acoustic measurement, lexical/lookup/ordered-match) at **1.0**; **correlated** (Error
Case, Best Practice — a model-judged match to a confirmed referent) at **W_C = 0.4 PROVISIONAL**,
with the debt logged and the correct value being `1 − corr(matcher_error, proposer_error)` measured
on a human-labelled sample; redundant (another model-judged text criterion on the same span) at
**0.0**. B's local NLI path is an independent instrument. Clears `finding_thin`, never
`criterion_below_tau`.

`Notes:` The correlated class is the hard one and it is **not a port**. B has independent signals
and redundant ones but no concept of a model-judged match to a confirmed referent, because its
aggregator only ever sees model-authored prose. Inventing that class — plus a deterministic test
for "same span, same judgment source" — is what makes soft⊕soft = 0 enforceable rather than
aspirational. An earlier revision of this milestone named only 1.0 and 0.0, which would have left
an implementer to treat a correlated match as either independent (over-confidence) or redundant
(discarding evidence). Both violate I6.

`Acceptance Test:` `tests/test_corroboration.py::test_redundant_signals_aggregate_zero`.
`::test_correlated_signal_weighs_w_c` — a model-judged referent match contributes 0.4, neither 1.0
nor 0.0. `::test_independent_signal_clears_finding_thin`.
`::test_corroboration_never_clears_criterion_below_tau`. `::test_aggregate_no_model_client`.


**Contract.**
- *Deliverable:* The independence-weighted corroboration aggregator.
- *Binding constraint:* I6 — all three weight classes, with W_C provisional and its debt logged. D4 — corroboration clears `finding_thin`, never `criterion_below_tau`.
- *Acceptance property:* Redundant signals manufacture no confidence; a correlated signal weighs as neither independent nor redundant; the two deferral axes stay orthogonal.
- *Known evidence (advisory):* The correlated class has no counterpart in B and must be invented — B's aggregator sees only model-authored prose, so there is nowhere a correlation judgement currently lives. This is the hardest of the three inventions.

### M18 — Build `core/adjust.py` (S4b)

`adjust(raw, history)`. Genuinely new — neither codebase has any notion of precedent. Unanchored
precedents are dropped, never applied; empty precedents give `adjusted == raw`.

`Acceptance Test:` `tests/test_adjust.py::test_empty_precedents_adjusted_equals_raw`.
`::test_unanchored_precedent_dropped`. `::test_applied_precedents_recorded`.


**Contract.**
- *Deliverable:* The precedent-application stage.
- *Binding constraint:* I3 — `adjust(raw, history)` is pure, and unanchored precedents are dropped rather than applied. I5 — anchored precedents enter the replay hash.
- *Acceptance property:* Empty precedents leave the score unchanged; the applied set is recorded and replayable.
- *Known evidence (advisory):* Neither codebase has any notion of precedent. What a precedent is on disk is unconstrained by the spec — it is a design, not a port.

### M19 — Build `core/route.py` and reconcile the escape estimator (S5)

The three `defer_reason` values, the two-axis auto-final gate, and `core/escape_rate.py` — which
ends 9020's split between sampler and estimator. B's five-condition escalation rule maps onto
`finding_thin` and human routing; `ungrounded` and `criterion_below_tau` are new.

`Acceptance Test:` `tests/test_route.py::test_auto_final_requires_both_axes`.
`::test_ungrounded_always_routes_to_human`. `::test_escape_rate_consumes_random_tranche_only`.


**Contract.**
- *Deliverable:* S5 routing, and the escape estimator reconciled with the sampler.
- *Binding constraint:* D10 — auto-final requires both axes clear. The estimator consumes the random tranche only, and that tranche respects its declared floor.
- *Acceptance property:* A call carrying ungrounded findings never auto-finalises; a biased sample cannot reach the estimator; the floor holds whatever the prioritisation asks for.
- *Known evidence (advisory):* 9020 shipped the sampler with a floor test that must survive this reconciliation. **The floor has no declared value anywhere — declare one during execution and record its basis.**

### M20 — Demote the 9020 proposer to a drift probe, safely

`core/divergence.py:52-56` silently skips dimensions absent on either side. The proposer keys by
its own dimension strings on a `[0,k-1]` scale; the derived side keys by the five rubric categories
on 0–100. Unify keys and units first, or the probe reports "flat" forever.

`Notes:` If the proposer runs on MLX rather than llama.cpp (Q21), the cache rewind is **not**
`model.n_tokens = prefix_len` and **not** `trim_prompt_cache`, which is unavailable on both pinned
model families. It is a per-cache-type deep-copy snapshot and restore covering **both** `state` and
`meta_state` — `RotatingKVCache` keeps `offset` and `_idx` in `meta_state`, so restoring `state`
alone rewinds to the wrong position. A snapshot taken by reference is silently wrong rather than
broken: mlx mutates cache buffers in place and its arrays have no `.copy()`, and a measured
reference "snapshot" replayed to `max|Δlogit| = 6.06`, i.e. a different `proposed_score` with no
error raised. Measured in issue #15.

`Acceptance Test:` `tests/test_divergence.py::test_disjoint_keys_raise` — mismatched vocabularies
raise rather than returning an empty dict. `::test_units_are_comparable`. If Q21 brings an MLX
Provider into scope, add `::test_cache_rewind_is_bit_exact` — replaying a suffix after a rewind
gives `max|Δlogit| == 0.0`, with a reference-snapshot red case.


**Contract.**
- *Deliverable:* The existing proposer repurposed as an observable drift probe.
- *Binding constraint:* I7 and D7 — a proposed score is never a verdict. D12 — resample variance never touches routing.
- *Acceptance property:* The probe fails loudly on incomparable inputs rather than reporting stability, and divergence is logged rather than routed.
- *Known evidence (advisory):* Key vocabularies and score units differ between the two sides. On MLX the cache rewind is not the llama.cpp primitive and the obvious implementation is silently wrong — see the milestone notes.

### M21 — Persist the replay record (I5)

Store the FindingGraph, `intents_sha` and rubric version. `replay_hash` is a function of
**grounded inputs *and* anchored precedents** — and never of the proposed score (I5). An earlier
revision of this milestone said "grounded inputs only", which drops the precedent set from the hash
and leaves it unable to detect the change it exists to detect: two runs citing different precedents
would hash identically. B discards every intermediate today, so no report is re-derivable.

`Notes:` The manifest path needs a new exact-filename glob in `INTENTS/_meta/ownership.yaml`
assigned to exactly one producer **before** the file may exist. That ledger requires every file to
match exactly one glob with zero orphans, CI-enforced, and `_meta/` uses exact-filename globs with
no `*.yaml` wildcard. The existing compiler-produced sidecar `_meta/residue-manifest.yaml` —
`schema_version: "1.0.0"`, top-level `compiler_epoch`/`sources`/`rows` — is the precedent to
follow. Reported in issue #16; verify against the live tree before writing.

`Acceptance Test:` `tests/test_replay.py::test_stored_graph_rederives_identical_result`.
`::test_replay_hash_includes_anchored_precedents` — two graphs identical but for their precedent
set must hash differently. `::test_replay_hash_excludes_proposed_score`.


**Contract.**
- *Deliverable:* A stored record that re-derives the verdict.
- *Binding constraint:* I5, as written in CLAUDE.md — quoted, not paraphrased: the hash is a function of grounded inputs and anchored precedents only, never of the proposed score.
- *Acceptance property:* The stored record re-derives an identical result; changing only the precedent set changes the hash; the proposed score never does.
- *Known evidence (advisory):* An ownership ledger governs where such a file may live, and an existing compiler-produced sidecar is the precedent. Shape, name and versioning are yours.

### M22 — Surface: CLI, config, record format

B's three run modes under this repository's entry point; typed configuration in `config/`; the
sidecar run manifest. Each is Tier C and individually gated.

`Acceptance Test:` `tests/test_cli.py::test_eval_subcommand_exits_zero` — invoked as a subprocess
against a real transcript. `::test_json_mode_is_machine_readable`.

**Contract.**
- *Deliverable:* The command, configuration and record surfaces.
- *Binding constraint:* Each is a public contract and Tier C. No value that alters a verdict may live as a hardcoded constant.
- *Acceptance property:* The command runs against a real transcript and exits non-zero on failure; every verdict-affecting value has a declared home.
- *Known evidence (advisory):* B's key set contains dead and silently duplicated values, and at least two floors have no declared number anywhere. Discover the real set by building it.

## 4. Progress

- [ ] M1: Fix B's two blocking crashes  (created 2026-09-12)
- [ ] M2: Fix the role-swap false positive  (created 2026-09-12)
- [ ] M3: Repair the ASR-reliability chain  (created 2026-09-12)
- [ ] M4: B's first end-to-end test  (created 2026-09-12)
- [ ] M5: Port B's schemas into types/  (created 2026-09-12)
- [ ] M6: Extend EvidenceItem to an I2 anchor slot  (created 2026-09-12)
- [ ] M7: Move B's proposal half into io/  (created 2026-09-12)
- [ ] M8: Land the four forbidden import-linter contracts  (created 2026-09-12)
- [ ] M9: Repoint the I8 checker at the populated tree  (created 2026-09-12)
- [ ] M10: Extract score(facts, rubric)  (created 2026-09-12)
- [ ] M11: Re-litigate NEI scoring  (created 2026-09-12)
- [ ] M12: Build core/grounding.py (I2)  (created 2026-09-12)
- [ ] M13: Build io/intents_provider.py and the epoch reader (I4)  (created 2026-09-12)
- [ ] M14: Fix the polarity-blind FAIL signal  (created 2026-09-12)
- [ ] M15: Land B's 27 items as SpecificRubric input  (created 2026-09-12)
- [ ] M16: Compile the rubric through 9003  (created 2026-09-12)
- [ ] M17: Build core/corroboration.py (I6)  (created 2026-09-12)
- [ ] M18: Build core/adjust.py (S4b)  (created 2026-09-12)
- [ ] M19: Build core/route.py and reconcile the escape estimator (S5)  (created 2026-09-12)
- [ ] M20: Demote the 9020 proposer to a drift probe, safely  (created 2026-09-12)
- [ ] M21: Persist the replay record (I5)  (created 2026-09-12)
- [ ] M22: Surface — CLI, config, record format  (created 2026-09-12)

## 5. Decision Log

### Decision: Overturn 9002 and re-layer onto simbiclaw/sim

**Rationale:**
- Source: `docs/exec-plans/archived/9002-implement-argus-eval-pipeline.md` §8 — all eleven
  milestones unchecked from 2026-07-08 to 2026-09-12; every module the plan declares is absent
  from `src/argus/`.
- Source: `simbiclaw/sim@0c2cccd` `core/aggregator.py` — 118 lines, no model import, 4/4 tests
  passing; `core/fact_checker.py:184-186` derives the per-verdict score from an enum rather than
  from model output. B satisfies **I7 and D15** independently. On **I3 it satisfies the purity half
  only**: no model touches the arithmetic, but `aggregate()` takes no rubric parameter, so it is
  not `score(facts, rubric)` and M10 is a redesign rather than a move. Stating this as "B satisfies
  I3" without that qualifier — as an earlier revision did here, and as the archived 9002 Outcomes
  still does — overstates it against this plan's own evidence two hundred lines below.
- Source: 9020 Big Picture — "executes after the 9002 milestones it names have shipped"; 9020
  Progress shows M0–M5 flipped 2026-08-27 while 9002 shipped nothing.

**Confidence:** high — the overturn rests on file-existence checks and on two plans' own recorded
state, both independently re-verified.

**Consequences:**
- 9002 is archived; this plan is its sole successor
- B's 1,600-line proposal half is imported rather than rewritten; its defects are fixed in place
  first (M1–M4) so they surface in their own diffs
- 9020's deliverable is retained but its proposer is demoted to a drift probe (M20)
- Argus is committed to zh-CN customer-service QA at the code level

### Decision: 准确性 is a rubric column, not a dimension

The four-dimension template stands. Items 22–27 split by primary failure axis: 22 to Empathy &
Tone, 23–25 to Problem Resolution, 26 to Empathy & Tone, 27 to Procedural Accuracy.
**Rationale:**
- Source: human direction, 2026-09-12, recorded in Q3 below.
- Source: `docs/exec-plans/active/9003-pilot-item18/generic-skill.yaml:4-16` — the four dimension
  names match exactly.
- Routing item 27 to Procedural Accuracy places the veto criterion at the **compliance** layer
  (`src/argus/types/compiler_schemas.py:204`), where it does not depend on the κ/τ agreement gates.
  A fifth dimension would have left it in the judgment layer.

**Confidence:** high for 22–25 and 27; see the next entry for 26.

### Decision: item 26's secondary axis is recorded as within_dimension residue

`AlignMap.entries` is typed `dict[str, str | None]` — one item, one dimension. Cross-axis is not
representable. Item 26 maps to Empathy & Tone and its Problem Resolution aspect is declared as a
`within_dimension` residue row.
**Rationale:**
- Source: `src/argus/types/compiler_schemas.py:126` — the entries type admits no second dimension.
- Source: human direction, 2026-09-12, selecting option (a) over a schema change.
- The residue manifest exists to record a lossy projection rather than drop it silently, so the
  secondary axis is preserved as evidence without a Tier C on-disk format change.

**Confidence:** high that it is expressible; `Confidence: low` that residue is the right *semantic*
home if the intent is that item 26 deduct in both dimensions. `Revisit: M16`.

### Decision: deviate knowingly from the spec's build order

The spec fixes the build order M0→M7 as written and states that **the proposer is built last**.
This plan imports B's proposal half at M7 and builds the INTENTS Provider at M13, which inverts
that.
**Rationale:**
- Source: reported in issue #16 as a standing disagreement with the spec (`:976`, `:1074`).
- The spec's order is correct for building S2 from scratch, where a proposer written before its
  consumers has nothing to check it. This plan is not building S2 — it is importing a proposer that
  already exists and already runs, and the reason to move it early is that quarantining it is a
  directory move that everything downstream depends on.
- The property the spec's order protects — that no proposer output reaches a verdict ungrounded —
  is held here by M12's grounding gate and the M8 fences, not by ordering.

**Confidence:** medium. `Revisit: M12` — if the grounding gate cannot be built against imported
proposer output without reaching back into `io/`, the spec's order was right and this plan's
phasing is wrong.

### Decision: 25 scored items — 6 and 7 excluded for data dependency, not deleted

The rubric keeps all 27 rows. Items 6 (`服务记录规范`) and 7 (`问题升级流程操作完整且规范`) are
marked permanently inapplicable, because both require reading systems Argus cannot reach — a
service-record store and a workflow/escalation system. Twenty-five items are scored.
**Rationale:**
- Source: human direction, 2026-09-12. Neither criterion is checkable from a transcript alone.
- Source: `simbiclaw/sim` `config/rubric_items.py` — both items already carry `na_criteria`
  (`系统问题不能做记录/通话时长<1分30秒`; `电话中未涉及到问题升级`), so they are already known to the
  NA machinery and need no new mechanism.
- Implemented as an `applicability_gate` backed by `AuthoredNode.data_dependency` rather than by
  removing the rows. Three reasons: the compiled rubric stays faithful to the real scoring sheet;
  the *reason* for exclusion is recorded and auditable instead of being a silent absence; and if
  the upstream integration ever lands, restoring them is a gate change rather than a rubric edit.
  B's aggregator already excludes NA items from the denominator, so no scoring change is needed.

**Confidence:** high.

**Consequences:**
- Under the Q3 dimension mapping, Procedural Accuracy drops from 7 scored items to 5, plus item 27,
  giving 6. The other three dimensions are unaffected.
- **Items 6 and 7 are the only two weighted 2.0.** Excluding them takes the rubric's total weight
  from 29.0 to 25.0 and leaves every scored item at weight 1.0, so no scored item exercises the
  weighted path. M10's `test_weight_comes_from_rubric_not_verdict` still proves the plumbing, but
  it needs a synthetic weight ≠ 1.0 fixture or it passes vacuously.
- This 25 is **not** patch 3's 25. See Q14.

### Decision: retain transformers; drop openai and chromadb

**Rationale:**
- Experiment: import trace over `simbiclaw/sim` — `openai` has zero import sites; `chromadb` has
  one (`knowledge/indexer.py`) whose output nothing reads; `torch` has zero direct imports and is
  transitive under `transformers`; `transformers` has one site, `utils/nli.py`.
- The local NLI path reaches a verdict with the API model not called at all, asserted by
  `tests/test_fact_checker.py:78`. Under I6 that is an independent signal at weight 1.0. Replacing
  it with a model call would collapse corroboration toward soft⊕soft = 0 (D5).

**Confidence:** high for the removals; high for retention on the invariant argument.

### Decision: B's aggregator is not score(facts, rubric); M10 is a redesign

**Rationale:**
- Source: `simbiclaw/sim` `core/aggregator.py:17-27` — an 8-argument signature taking
  model-authored `summary` and `suggestions`, with no rubric parameter.
- Source: `core/fact_checker.py:193-196` and `core/question_generator.py:110` — weight and veto are
  stamped onto verdicts inside modules that M7 moves to `io/`, so without M10 the deduction weight
  would be applied inside the quarantine.
- Source: `tests/test_aggregator.py:68-73` — all four tests construct all eight arguments and break
  on the signature change. They are rewritten, not inherited.

**Confidence:** high — established by an adversarial verification pass that set out to falsify the
opposite claim.

### Decision: path B evidence is unanchorable under I2

**Rationale:**
- Source: `simbiclaw/sim` `core/fact_checker.py:119-125` — `EvidenceItem.text` is model-authored
  prose from the verification prompt, while `doc_path` names a single node and the text was
  generated from a concatenation over cascade-loaded nodes.
- Exact-quote verification against `doc_path` would fail for essentially every path-B finding, and
  path B is the accuracy lane containing veto item 27.

**Confidence:** high. Path B routes to `ungrounded` until the verification prompt returns a
verbatim span. `Revisit: M12`.

### Decision: INTENTS paths are omitted from File Scope

**Rationale:**
- Source: `.claude/tests/test_plan_collisions.py` — `_paths_overlap` intersects declared patterns
  with no read/write distinction, and checks every active pair.
- 9008 declares `INTENTS/**` (modify). This plan only reads INTENTS, so declaring a read-only path
  would fail the collision test and block both plans for a dependency that does not exist.

**Confidence:** high.

## 6. Surprises & Discoveries

**The two codebases transcribed the same rubric.** `9003-pilot-item18/specific-rubric.yaml` cites
`docs/PRD/eval/rubric_com_hotline.md`; B's `config/rubric_items.py` has the same 27 items with the
same ids. Item 18 matches clause-for-clause across both. Neither investigation found this alone —
it surfaced only when the two reports were compared. It is the reason this plan merges rather than
chooses.

**Three of four layer fences were vacuous.** `grounding ✗ proposer`, `grounding ✗ matching_model`
and `aggregate ✗ model_client` were satisfied only because the code they guard did not exist. They
become live, unguarded surfaces the moment M12 and M17 land, which is why M8 ships the contracts
before them rather than after.

**I3 was enforced by a grep over a Markdown file.** `tests/test_argus_eval_contract.py:22-58`
searches `docs/product-specs/argus/fact-checking.md` for the string `score(facts, rubric)` and
imports no code. M10 replaces it with an executable fence.

**The `LogitModel` protocol is not portable.** Its docstring promises "a different stack implements
the same five members", but `local_proposer.py:157` calls a sixth, `model.scores`. Latent today
because only one implementation exists. Relevant to the Apple Silicon spike in issue #15.

**Neither the spec nor the memory is readable in a fresh clone.** `docs/PRD` and `INTENTS` are
both dangling symlinks — the first to a path outside the repository, the second to an absolute path
on one developer's machine. Every conclusion in this plan was reached from CLAUDE.md's operating
summary rather than from the spec it defers to.

**Planning and implementation were split across environments, deliberately (2026-09-12).** This
plan was written in a cloud session that could not install dependencies or read either symlink.
Implementation was handed to a local session by human direction, for both reasons — see Q18. Two
consequences the implementing session should act on before opening M1:

- **Re-check this plan's invariant claims against the spec itself.** `docs/PRD` resolves locally.
  Everything in section 2.1 and in the Decision Log was derived from CLAUDE.md's summary; where the
  spec disagrees, the spec governs and this plan is wrong.
- **Q7 may dissolve on contact.** `INTENTS` resolves locally too, so whether `_rubric/` and the
  L1/L2/L3 business KB are one tree or two is answerable by looking rather than by steering. If
  they are one tree, M13 is one provider and the estimate holds; if two, M13 grows by 2–3
  milestones.

**The Apple Silicon gap closed, and D19 is viable on real weights (issue #15, 2026-09-12).** The
MLX spike ran the M0 probe against three real checkpoints on the M3 Ultra. MLX returns the whole
logit vector at a position — 248,320 and 262,144 wide — and requested-k equals returned-k exactly
(20→20, 256→256), so it does not have llama.cpp's distribution-dependent cap that forced the
low-level path there. All twenty letters A–T are single tokens, so G=20 is satisfied rather than
falling back, and the expectation differs from the argmax in all twelve measurements. Throughput is
`throughput_representative: true` on real weights. Three consequences for this plan:

- **The cache-rewind contract is a new requirement nobody had written down.** See M20's Notes. The
  naive implementation is silently wrong, which is the failure class this repository's fixtures
  exist to convert into parse-time or test-time failures.
- **The `LogitModel` Protocol gap is confirmed by a second, independent attempt.** It blocks any
  MLX adapter: the Protocol declares five members and `local_proposer.py:157` calls a sixth.
- **9020's M6 may now be satisfiable.** It was deferred for want of a throughput run against a
  production model on target hardware, and its acceptance test rejects
  `throughput_representative: false`. The spike produced exactly that artifact. Whether it
  *satisfies* M6 depends on whether M6 requires batched numbers — the spike reports
  `batched_tok_s: null`. Check before assuming; do not flip M6 on this text alone.

Scoring is not the capacity problem. The score pass costs ~0.14 s on the 27B against a hunt pass of
~45–60 s — roughly 0.3% of the call. The hunt pass is where capacity is decided, which is Q12.

**A local review found three defects in this plan that would have shipped into implementation
(issue #16, 2026-09-12).** All three were introduced here and all three are now fixed: `replay_hash`
was written as "grounded inputs only", dropping the anchored precedents I5 requires (M21); M17 named
only the 1.0 and 0.0 weight classes, deleting I6's `correlated` class at `W_C = 0.4` entirely; and
§2's D15 claim contradicted M16's production of `_rubric/` nodes. The pattern in all three is the
same and worth naming: **each dropped the harder half of an invariant and kept the half that was a
port.** Precedents, correlation, and the write boundary are the three places this plan cannot copy
B and must invent, and all three were quietly narrowed to what B already does.

**Two claims in that review did not verify here, and are recorded so they are not propagated.**
The review states 9020 "has no notes at all, at any path, and all eight milestones are unflipped";
this tree has seven notes files under
`docs/exec-plans/completed/9020-continuous-proposer-and-provenance-separation-notes/` and six
flipped milestones. It also calls B's `self.kb_builder` `AttributeError` a *third* blocking crash;
it is the first of the two M1 already covers — `qa_agent.py:31` assigns `kb_context_builder` and
`:66` calls `kb_builder`, which is exactly the blocker M1 names. Both misreadings are the same
class the review itself warns about, and neither changes its conclusions.

**This entire line of work is unmerged.** `origin/main` contains none of it: not `local_proposer.py`,
not the 9020 experiment artifacts, not the patch-1 spec, not 9020 or 9021 themselves. As of
2026-09-12 `main` has zero commits this branch lacks and the branch is eighteen ahead, so it is a
clean fast-forward. Until that happens, any acceptance test pointed at `main` cannot find the files
it needs.

The evidence base for every claim in this plan is committed at
`docs/experiments/9021-ab-investigation/`. Read its README first — in particular, `adversarial.md`
falsified five mechanism claims in `synthesis.md`, and the corrected versions are what this plan
encodes.

**M5 was REJECTED by adversarial verification, 2026-09-12 — and the whole defect class was
invention rather than porting.** Subagent B ran ten field-deletion mutations against the ported
types; eight passed the acceptance test cleanly, including deleting `Verdict.weight` and
`Atom.source_turn_ids`. Pydantic v2 ignores unknown keyword arguments, so a round-trip test built
by constructing with kwargs cannot see a field disappear. The full application suite was equally
blind: identical pass/fail counts with a field removed.

Two enums had been silently rewritten. `TurnFlag` is `INCOMPLETE/ASR_ERROR/ROLE_SWAPPED/NORMAL`
upstream; the port wrote `INCOMPLETE/UNCERTAIN/STUTTER`, inventing two members and deleting three —
two of which (`ASR_ERROR`, `ROLE_SWAPPED`) are produced by live code at
`core/asr_preprocessor.py:46,54`. `CoverageStatus` was likewise substituted. **The port could not
read the upstream system's own output**, which is an undeclared on-disk format change with no
steering entry. Losing `ROLE_SWAPPED` also deletes the turn-level provenance M2 needs.

Three fields went required to optional, including `Atom.source_turn_ids` — the atom's anchor — in
the same module whose docstring argues that evidence naming no source must be rejected at
construction. The guard was applied to `EvidenceItem` and the opposite to `Atom`.

**The lesson is narrower and sharper than "check your work".** The acceptance test carried
`hasattr(TurnFlag, "UNCERTAIN")` guards, written because the author was unsure the member existed.
That uncertainty was the signal to open the source file; instead it was encoded as a fallback that
resolves to a passing value. **A guard that degrades to green is a skip, and it will mask precisely
the thing its author was unsure about.** Any structural test in this plan that cannot be shown to
fail on a planted defect is not evidence.

**The polarity-blind compiler signal was item 18's *only* gate-checkable signal (M14,
2026-09-13).** `decompose_signals` emitted one FAIL signal from the flat `named_phrases` list
without consulting which standard named each phrase. A FAIL signal fires on presence, so any phrase
drawn from the *pass* standard deducted for the behaviour the rubric rewards. Item 18 shipped that
signal as its sole gate-checkable output — every other signal was `model_only` — so this was not
one wrong voice among several, it was the entire deterministic verdict, and it deducted for
consulting the business manual that `善于使用资源` explicitly rewards. Measured directly: the item
and the item with its two standards swapped produced byte-identical output. The compiler could not
see polarity at all.

**And the flattening starts upstream of the compiler, which M15 and M16 must address.** The pilot's
`named_phrases` mixes pass-standard vocabulary (`客服系统`, `业务手册`) with fail-standard
vocabulary (`思路混乱`, `引导延期`) in one undifferentiated list, with no field recording which is
which. M14's fix recovers polarity by substring-matching each phrase against the two standards,
because that is the only place the compiler has the information — it works on every fixture in the
suite, but it is **inference, not data**. If the rubric input grows an explicit polarity field, the
helper should read it and fall back to inference only when absent. A phrase appearing in both
standards, as `客服系统` does in item 18, is genuinely ambiguous and stays in the FAIL lane where
the existing entanglement check routes it to model judgment.

**Signal ids shifted as a consequence.** Item 18 now emits `18-S01` (fail lexical), `18-S02`
(excellence lexical), `18-S03`, `18-S04`, where it previously emitted `18-S01..S03`. Nothing in the
suite pins these, but any node compiled before this change, and any downstream reference to
`18-S02` or `18-S03`, now points at a different signal.

## 7. Awaiting Steering

**Q1: Approve the RE-LAYER strategy?** — Awaiting Steering: resolved 2026-09-12. Approved.
Transplant and Absorb are closed. The decision rests on invariant integrity and domain-asset
preservation; the effort axis was withdrawn after an adversarial recount moved the estimate from
9–10 milestones to 19–22.

**Q2: Amend 9002 or supersede it?** — Awaiting Steering: resolved 2026-09-12. Supersede, with a
formal 9020 inheritance table required in the successor. Section 2.1 carries it.

**Q3: Does the dimension taxonomy grow to five?** — Awaiting Steering: resolved 2026-09-12. No.
准确性 is a rubric column, not a dimension. Mapping recorded in the Decision Log.

**Q4: How is item 26's cross-axis mapping represented?** — Awaiting Steering: resolved 2026-09-12.
Option (a): scored in Empathy & Tone, with the Problem Resolution axis recorded as
`within_dimension` residue.

**Q5: Do B's hand-assigned weights and veto ship as runtime truth?** — Awaiting Steering: resolved
2026-09-12. Compile, then diff against B's assignments and treat divergences as findings.

**Q6: Is NEI scored 0.5 and kept in the denominator?** — Awaiting Steering: resolved 2026-09-12.
No — adopt the deferral rule. M11 owns the change.

**Q7: Attach `simbiclaw/INTENTS`?** — Awaiting Steering: resolved 2026-09-12. The local `INTENTS` directory will be attached, so M13 reads a real tree. Whether `_rubric/` and the L1/L2/L3 business KB are one tree or two is now answered by inspection at M13 rather than by steering. If two, record it in Surprises as a scope increase of 2-3 milestones rather than absorbing it silently. Originally blocked M13. The symlink
dangles in every clone. Whether this repository's `_rubric/` subtree and B's L1/L2/L3 business KB
are one tree or two decides whether M13 is one provider or two. Default if not decided: attach and
inspect before M13 opens, treating the two-tree case as a scope increase rather than a surprise.

**Q8: One repository, or a package boundary?** — Awaiting Steering: resolved 2026-09-12. One
repository; B enters as a squashed import commit citing `simbiclaw/sim@0c2cccd`.

**Q9: Accept that fixing the role swap changes evaluation outputs?** — Awaiting Steering: resolved
2026-09-12. Yes — fix the heuristic and add a confidence floor. M2 owns it.

**Q10: Accept the four FindingGraph on-disk schema deltas?** — Awaiting Steering: resolved 2026-09-12. Adopt all four as non-replay-bearing diagnostics. M5 lands them in the ported schemas and records the adoption in the Decision Log. This also repairs 9020's Q2, whose stated default could not fire because the milestone it gated had already shipped. Originally blocked M5. Inherited from 9020's Q2, whose stated default could not execute because the milestone
it gated had already shipped. The fields are `proposer_id`, `alignment_epoch`, `sampling_params`
and the quarantined `proposed_scores{}` block; all four are non-replay-bearing. Tier C — a change
to an on-disk format. Default if not decided: adopt all four as non-replay-bearing diagnostics and
record the adoption in this plan's Decision Log, since M5 cannot port B's schemas without settling
where these fields live.

**Q11: Accept the new config surface?** — Awaiting Steering: resolved 2026-09-12. Accepted, and **the scope includes the drift probe's values**: M20 keeps the probe alive in this plan, and leaving it on hardcoded constants reproduces the silent-failure shape already on the debt list. **No key list is fixed here.** The contents are discovered at M22 under its binding constraint — no value that alters a verdict may live as a hardcoded constant — and the two floors that have no declared value anywhere are measured before they are declared, not guessed here. Note the mechanical consequence of this resolution: `src/argus/config/**` is a sensitive path, so the PreToolUse hook would have blocked M22 from touching config at all while this entry read unresolved, whatever it said. Originally blocked M22.


**Q12: Fix the serving shape, or keep it behind the batch-shaped interface?** — Awaiting Steering: resolved 2026-09-12. **Deferred**, and not for 9020's reason. The measurement needs a stack that is not installed and weights that are not present, and issue #15 established that the score pass is roughly 0.3% of a call — so the capacity question is about the hunt pass, not about D19's granularity. The io boundary keeps this a swap rather than a rewrite whenever it is taken up. Blocked nothing in this plan.


**Q13: Namespace the measurement-profiles D-series?** — Awaiting Steering: resolved 2026-09-12. **Moved out of this plan** to [#17](https://github.com/simbiclaw/harness-cli/issues/17), owned by the 9003 compiler line. It sat here only because 9020 handed it over, and it is not this plan's deliverable: the citation weight is in `core/compiler/**` and its tests. The evidence gathered for it — that there are three colliding series rather than two, that the collision starts at D1 rather than D13, and that the recorded basis for 9020's default was wrong because the ADRs cite zero D-numbers — travels with the issue. Blocked nothing in this plan.


**Q14: Is companion patch 3 absorbed here or opened as its own plan?** — Awaiting Steering: resolved 2026-09-12. Patch 3 is opened as its own plan owned by the 9003 compiler line, not absorbed here. The 25-vs-25 warning below stands and must travel with it. Originally blocked M16. Inherited from 9020's Q6. It adds CalibrationManifest row fields,
prohibitions AUTH-11 to AUTH-13, an F4 tranche-balance check, and a 27-to-25 item-count correction.
Default if not decided: open as its own plan owned by the 9003 compiler line.

> **Do not confuse patch 3's 25 with this plan's 25.** They are different counts reached for
> unrelated reasons and they happen to be the same number. Patch 3 corrects an **ontology node
> count**: it holds that Acoustic Feature and Phrase & Keyword are evidence sources rather than
> rule categories, so the rules_criteria count is 25 (Procedural 7, Empathy 8, Resolution 8,
> Proactive 2). This plan's 25 is an **operational scope**: B's 27 scoring rows minus items 6 and 7,
> excluded because they need systems Argus cannot read. Neither of B's excluded items is an
> acoustic or phrase-lexicon criterion, and B's sheet contains no such category at all — so patch
> 3's correction does not apply to it. Applying patch 3's arithmetic to B's sheet would push out
> items 26 and 27 instead, and item 27 is the privacy veto. Whoever resolves Q14 must keep the two
> counts apart.
>
> **Contested, and only the local session can settle it.** Issue #16 reports that the live INTENTS
> tree holds **25 nodes at ids 1–5 and 8–27** — i.e. 6 and 7 already excluded — which if true means
> the two counts are the same 25 and this warning is wrong. The supporting citation given for it
> (`patch-1:194` as "25 (items 6,7 excluded)") does **not** verify in this tree: line 194 is a
> milestone-table row, and patch-1 contains no mention of items 6 or 7 anywhere. The tree evidence
> cannot be checked from a clone where `INTENTS` dangles. **Settle it by listing the node ids in
> the live tree before M15**, and delete or keep this warning on that basis rather than on either
> document.

**Q15: Reconcile implementation-notes-during-execution with the checkbox-flip gate.** — Awaiting Steering: resolved 2026-09-12. **Moved out of this plan** to [#18](https://github.com/simbiclaw/harness-cli/issues/18). It is a harness defect in `.claude/tests/**`, not a deliverable of re-layering Argus. The finding that travels with it: the gate derives a notes directory that does not match 9008's, so 9008's seven flipped milestones are never checked and the unflipped-milestone test passes vacuously — and 9008's directory name is the one the convention document actually specifies. It is **not** violation two under the promotion rule; the single historical trip predates the test by a day. Blocked nothing in this plan.


**Q16: Does `core/` stop importing `io/`, or do the fences allow indirect imports?** — Awaiting Steering: resolved 2026-09-12. Forbid `core -> io`. M8 lands the four forbidden contracts with `include_external_packages = True` and amends `docs/conventions/layering.md:41` in the same milestone, so the convention and the lint agree rather than contradicting each other. Originally blocked M8. `.importlinter` declares layers with `core` above `io`, so
`core → io` passes today, while `docs/conventions/layering.md:41` permits it explicitly. The four
forbidden contracts are weaker than claimed unless this is settled. Tier C — `.importlinter` and a
convention document. Default if not decided: forbid `core → io` and amend the convention, because
a fence that admits indirect imports does not enforce the quarantine it names.

**Q17: Adopt B's CLI surface?** — Deadline: 2026-09-30. Unresolved; blocks M22. B offers three run
modes; this repository has a `version` stub. Tier C — CLI surface and stdout format, and
`src/argus/cli/main.py` is a sensitive path. Default if not decided: adopt the three modes, drop
the index-building mode whose output nothing reads, and add a JSON mode as the machine contract.

**Q18: How do milestones importing `transformers` satisfy the verification floor?** — Awaiting Steering: resolved 2026-09-12. **Implementation moves to a local Claude Code session**, for the referent reason rather than the tooling one. `docs/PRD` and `INTENTS` resolve locally and dangle in a fresh clone, so the local session is the first that can check this plan against the spec it defers to and against the tree it reads.

> **Correction, 2026-09-12.** An earlier revision of this entry claimed the cloud environment made the whole plan unexecutable. That was measured and is false. `pytest` runs, `argus` imports with `PYTHONPATH=src`, and **287 application tests pass** there; the failures are dependency-bound or routed through `uv`, which cannot reach the pinned index. Thirteen of the twenty-two milestones — M5, M6, M9, M10, M11, M12, M14, M15, M17, M18, M19, M20, M21 — have acceptance tests that are runnable in a dependency-free environment, because `core/` is pure by construction. Only M7, M8 and M22 are dependency-blocked, and M13 and M16 are blocked on the INTENTS tree rather than on tooling. The generalisation from two milestones to all of them was made without testing it. **A plan that says a milestone cannot be verified should name the milestone and the import that blocks it, never the environment.**


**Q20: Which definition of D19's expectation is pinned?** — Awaiting Steering: resolved 2026-09-12. Pin the expectation as the softmax renormalized over the twenty letter positions. The full-vocabulary-softmax-over-the-letter-set reading is recorded here as rejected, so a later implementer does not silently switch definitions on a probe whose value is comparability. Originally blocked M20 and any future proposer work. Two readings exist: the softmax renormalized over the
twenty letter positions, or the full-vocabulary softmax renormalized over the letter set. Issue #15
measured both and found they agree in ordering on its prompt, which is not a guarantee they agree
on a real scoring prompt. Only one can be the definition, because `proposed_score` feeds a drift
probe whose whole value is comparability across runs. Default if not decided: pin the
renormalization over the twenty letter positions, and record the other as the rejected reading so a
later implementer does not silently switch.

**Q21: Is an MLX Provider in this plan's scope, or a successor's?** — Awaiting Steering: resolved 2026-09-12. Option (b) - an MLX Provider is a successor plan's scope, owned by the proposer line. M20 demotes the llama.cpp proposer that exists; the deep-copy rewind contract in its Notes is the successor's starting requirement, not this plan's work. Originally blocked M20's Notes. Issue #15 settles that MLX is a viable proposer engine and
recommends `mlx-vlm` stay the engine, but this plan assumed the proposer was demoted to a drift
probe on its existing llama.cpp stack and contains no milestone for writing a second Provider. That
work is real: extend the `LogitModel` Protocol, write the adapter, implement the deep-copy rewind,
and add the bit-exactness regression test. Options: (a) add it to this plan as two milestones; (b)
open a successor owned by the proposer line, leaving this plan's M20 to demote what exists; (c)
defer until the drift probe is running and has something to compare. Default if not decided: (b) —
this plan is already at twenty-two milestones, and the Provider is orthogonal to re-layering B.

**Q19: What is the on-disk format for the evaluation record?** — Awaiting Steering: resolved 2026-09-12. Accepted: Argus writes an on-disk record sufficient to re-derive the verdict, because I5 requires one. This is a Tier C surface **mandated by an invariant rather than chosen**, so the decision is an acknowledgement and not a design. **Its shape, name and versioning are M21's to design** under I5 and under the `_meta/` ownership ledger, which requires a new exact-filename glob assigned to exactly one producer before the file may exist. Originally blocked M21.


## 8. Outcomes & Retrospective

*Written at completion or cancellation.*
