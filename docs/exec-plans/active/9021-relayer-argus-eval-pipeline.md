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
nothing in this plan writes them (D15). `.claude/tests/test_plan_collisions.py` intersects
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
- `pyproject.toml` (modify — dependency changes)
- `docs/decisions/dep-vet-transformers.md` (new)
- `docs/rubric/specific-rubric-27.yaml` (new — B's table as compiler input)
- `docs/exec-plans/active/9021-relayer-argus-eval-pipeline.md` (modify — this plan)

## 3. Milestones

### M1 — Fix B's two blocking crashes

In `simbiclaw/sim`. `agents/qa_agent.py:66` calls `self.kb_builder`, never assigned (`:31` assigns
`self.kb_context_builder`). `:125` raises `KeyError: 'grade'`. Both sit on the single happy path.

`Acceptance Test:` `tests/test_qa_agent.py::test_pipeline_reaches_report` — the orchestrator runs
end to end against a fake LLM and returns a report object.

### M2 — Fix the role-swap false positive

`_verify_roles` returns `should_swap=True` on a correctly-labelled transcript; `:41-42` then
inverts every role, checking agent criteria against customer utterances. Add a confidence floor
so a low-confidence swap routes to a human rather than silently inverting.

`Acceptance Test:` `tests/test_asr_preprocessor.py::test_timestamp_parsing` — currently failing;
passes without a swap. Plus `::test_low_confidence_swap_defers` — a marginal case routes to human.

### M3 — Repair the ASR-reliability chain

`core/preprocessor.py` drops `timestamp_start`/`timestamp_end` when building `Turn`, and path C's
reliability branch is dead. The atomiser propagates `reliability=low` to no effect.

`Acceptance Test:` `tests/test_fact_checker.py::test_low_reliability_forces_human_review` — a
turn marked low-reliability produces a verdict requiring review.

### M4 — B's first end-to-end test

B has zero integration tests, which is why M1's two crashes survived. Needs a fake LLM covering
14 call sites and a stub NLI, since `transformers` cannot be installed in CI.

`Acceptance Test:` `tests/test_e2e.py::test_transcript_to_report` — a real transcript from
`data/transcripts/` produces a complete report with no network access.

### M5 — Port B's schemas into `types/`

B's `models/schemas.py` (25 Pydantic models) replaces 9020's stand-ins. The stage decomposition it
encodes — atoms to coverage to questions to verdicts, with `turn_id`/`doc_path` provenance — is
the contract everything else attaches to.

`Acceptance Test:` `tests/test_schemas.py::test_all_schemas_roundtrip` — each schema constructs,
serializes and deserializes. `::test_replay_payload_excludes_proposed_score` — 9020's I5 allowlist
survives the port.

### M6 — Extend `EvidenceItem` to an I2 anchor slot

Add `span`, `quote` and `intents_sha`. Re-plumb timestamps through stage 1 so spans are
recoverable. Verified feasible: B's parser mutates turn text only with `.strip()`, and a
round-trip on the sample transcript recovered 17/17 turns as exact substrings.

`Acceptance Test:` `tests/test_evidence_anchor.py::test_span_roundtrip` — every evidence item
recovers an exact character span from the raw transcript. `::test_ambiguous_span_rejected` — a
turn text occurring twice fails rather than guessing.

### M7 — Move B's proposal half into `io/`

Eleven modules re-namespaced, behaviour unchanged: asr_preprocessor, preprocessor, atomizer,
intent_inferrer, question_generator, kb_context_builder, intent_retriever, llm_client, nli,
prompts, qa_agent. Squashed import commit citing `simbiclaw/sim@0c2cccd`.

`Acceptance Test:` `tests/test_io_import.py::test_pipeline_runs_from_io` — the moved pipeline
produces the same output as M4's baseline on the same input.

### M8 — Land the four `forbidden` import-linter contracts

`core ✗ model_client`, `grounding ✗ proposer`, `grounding ✗ matching_model`,
`aggregate ✗ model_client`. Requires `include_external_packages = True`. The existing layers
contract permits `core → io`, which must be reconciled with these — see Q16.

`Acceptance Test:` `tests/test_fences.py::test_planted_violation_fails_lint` — a planted
`from anthropic import Anthropic` in a `core/` module makes `lint-imports` exit non-zero.
`::test_clean_tree_passes`. A contract that has never failed is not enforcement.

### M9 — Repoint the I8 checker at the populated tree

`tests/test_i8_provenance_separation.py` currently scans a nearly-empty `core/`. Its allowlist
assumes two modules exist. Widen the scan, keep the red/green pair.

`Acceptance Test:` `tests/test_i8_provenance_separation.py::test_live_core_tree_clean` — passes
against the populated tree with the allowlist reasoned, not widened to admit violations.

### M10 — Extract `score(facts, rubric)`

Not a move. B's `aggregate()` is an 8-argument report builder taking model-authored prose, with no
rubric argument — weight is stamped onto verdicts by `fact_checker.py:193-196` and `is_veto` by
`question_generator.py:110`, both inside modules now in `io/`. Lift both out so the rubric enters
the arithmetic from `core/`.

`Acceptance Test:` `tests/test_score.py::test_i3_determinism_canary` — identical inputs give
byte-identical `raw`. `::test_score_receives_no_history`. `::test_weight_comes_from_rubric_not_verdict`.
`::test_core_no_model_client`.

### M11 — Re-litigate NEI scoring

B scores NEI at 0.5 and keeps it in the denominator, so an unverifiable item contributes half a
point. This repository's rules route an ungrounded finding to a human and block auto-final. Adopt
the latter; it changes every score B has produced.

`Acceptance Test:` `tests/test_score.py::test_nei_excluded_from_denominator` —
an NEI item neither scores nor counts. `::test_nei_blocks_auto_final`.

### M12 — Build `core/grounding.py` (I2)

Exact-quote verification against the transcript, INTENTS node resolution at a pinned epoch, and
the `ungrounded` bucket. Path B evidence is declared unanchorable and routes to `ungrounded`: its
text is model-authored prose, not a quote from the cited document.

`Acceptance Test:` `tests/test_grounding.py::test_i2_anchor_or_quarantine_red` — a finding citing
a non-existent node moves to `ungrounded`. `::test_quote_fidelity_red`. `::test_path_b_always_ungrounded`.
`::test_grounding_no_model_import`.

### M13 — Build `io/intents_provider.py` and the epoch reader (I4)

Read-only access to `INTENTS/` at a pinned git SHA from `EPOCH.yaml`. Record the model-selected KB
path in the run manifest so referent selection becomes replayable rather than re-guessed — B's
drill-down picks the node by asking the model, with no depth cap and no visited set.

`Acceptance Test:` `tests/test_intents_provider.py::test_reads_at_pinned_epoch`.
`::test_no_write_path` — the provider exposes no mutating method.
`::test_s1_no_write_path_into_intents` — an AST scan confirms no `src/argus/` path opens an INTENTS
file for writing. This is 9002's M7 fixture, which was specified and never written.

### M14 — Fix the polarity-blind FAIL signal before compiling anything

`core/compiler/signals.py:353-361` emits a FAIL signal that does not distinguish polarity. The
compiler's only shipped output carries it. Compiling 27 items through this manufactures 27 wrong
rubrics faster than a human can review them.

`Acceptance Test:` `tests/test_signals.py::test_fail_signal_polarity` — item 18 as the regression
case; an inverted-polarity input no longer produces a passing signal.

### M15 — Land B's 27 items as `SpecificRubric` input

B's `config/rubric_items.py` becomes `docs/rubric/specific-rubric-27.yaml`. Re-verify all 27
against the upstream source where recoverable; B's transcription is lossy in at least two places
(item 18 drops a counter-example, item 1 has an empty fail standard).

`Acceptance Test:` `tests/test_rubric_input.py::test_27_items_parse_as_specific_rubric`.
`::test_no_empty_fail_standard`.

### M16 — Compile the rubric through 9003

Produce epoch-pinned `_rubric/` AuthoredNodes with the align map decided in Q3: item 22 to
Empathy & Tone, items 23–25 to Problem Resolution, item 26 to Empathy & Tone with its Problem
Resolution axis recorded as `within_dimension` residue, item 27 to Procedural Accuracy at the
compliance layer. Compiler output is diffed against B's hand-assigned weight and veto; divergences
are findings, not overrides.

`Acceptance Test:` `tests/test_rubric_compile.py::test_all_27_compile_or_declare_residue`.
`::test_item_27_is_compliance_layer` — the veto item does not depend on the judgment gates.
`::test_hand_assignment_divergences_recorded`.

### M17 — Build `core/corroboration.py` (I6)

Independence-weighted aggregation over verified signals. B's local NLI path is a weight-1.0
independent instrument; another model-judged text criterion on the same span is redundant at 0.0.
Clears `finding_thin`, never `criterion_below_tau`.

`Acceptance Test:` `tests/test_corroboration.py::test_redundant_signals_aggregate_zero`.
`::test_independent_signal_clears_finding_thin`.
`::test_corroboration_never_clears_criterion_below_tau`. `::test_aggregate_no_model_client`.

### M18 — Build `core/adjust.py` (S4b)

`adjust(raw, history)`. Genuinely new — neither codebase has any notion of precedent. Unanchored
precedents are dropped, never applied; empty precedents give `adjusted == raw`.

`Acceptance Test:` `tests/test_adjust.py::test_empty_precedents_adjusted_equals_raw`.
`::test_unanchored_precedent_dropped`. `::test_applied_precedents_recorded`.

### M19 — Build `core/route.py` and reconcile the escape estimator (S5)

The three `defer_reason` values, the two-axis auto-final gate, and `core/escape_rate.py` — which
ends 9020's split between sampler and estimator. B's five-condition escalation rule maps onto
`finding_thin` and human routing; `ungrounded` and `criterion_below_tau` are new.

`Acceptance Test:` `tests/test_route.py::test_auto_final_requires_both_axes`.
`::test_ungrounded_always_routes_to_human`. `::test_escape_rate_consumes_random_tranche_only`.

### M20 — Demote the 9020 proposer to a drift probe, safely

`core/divergence.py:52-56` silently skips dimensions absent on either side. The proposer keys by
its own dimension strings on a `[0,k-1]` scale; the derived side keys by the five rubric categories
on 0–100. Unify keys and units first, or the probe reports "flat" forever.

`Acceptance Test:` `tests/test_divergence.py::test_disjoint_keys_raise` — mismatched vocabularies
raise rather than returning an empty dict. `::test_units_are_comparable`.

### M21 — Persist the replay record (I5)

Store the FindingGraph, `intents_sha` and rubric version. `replay_hash` over grounded inputs only,
never the proposed score. B currently discards every intermediate, so no report is re-derivable.

`Acceptance Test:` `tests/test_replay.py::test_stored_graph_rederives_identical_result`.
`::test_replay_hash_excludes_proposed_score`.

### M22 — Surface: CLI, config, record format

B's three run modes under this repository's entry point; typed configuration in `config/`; the
sidecar run manifest. Each is Tier C and individually gated.

`Acceptance Test:` `tests/test_cli.py::test_eval_subcommand_exits_zero` — invoked as a subprocess
against a real transcript. `::test_json_mode_is_machine_readable`.

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
  from model output. B satisfies I3, I7 and D15 independently.
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

**Q7: Attach `simbiclaw/INTENTS`?** — Deadline: 2026-09-26. Unresolved; blocks M13. The symlink
dangles in every clone. Whether this repository's `_rubric/` subtree and B's L1/L2/L3 business KB
are one tree or two decides whether M13 is one provider or two. Default if not decided: attach and
inspect before M13 opens, treating the two-tree case as a scope increase rather than a surprise.

**Q8: One repository, or a package boundary?** — Awaiting Steering: resolved 2026-09-12. One
repository; B enters as a squashed import commit citing `simbiclaw/sim@0c2cccd`.

**Q9: Accept that fixing the role swap changes evaluation outputs?** — Awaiting Steering: resolved
2026-09-12. Yes — fix the heuristic and add a confidence floor. M2 owns it.

**Q10: Accept the four FindingGraph on-disk schema deltas?** — Deadline: 2026-09-16. Unresolved;
blocks M5. Inherited from 9020's Q2, whose stated default could not execute because the milestone
it gated had already shipped. The fields are `proposer_id`, `alignment_epoch`, `sampling_params`
and the quarantined `proposed_scores{}` block; all four are non-replay-bearing. Tier C — a change
to an on-disk format. Default if not decided: adopt all four as non-replay-bearing diagnostics and
record the adoption in this plan's Decision Log, since M5 cannot port B's schemas without settling
where these fields live.

**Q11: Accept the new config surface?** — Deadline: 2026-09-30. Unresolved; blocks M22. Inherited
from 9020's Q3, unchanged and still unresolved. The surface is the proposer deployment contract,
the escape-sampler split ratio and the random-tranche floor, plus B's thresholds. Tier C —
`src/argus/config/**` is a sensitive path. Default if not decided: none — no milestone writes
config until this resolves.

**Q12: Fix the serving shape, or keep it behind the batch-shaped interface?** — Deadline:
2026-09-30. Unresolved; blocks nothing. Inherited from 9020's Q4. Default if not decided: defer
again; the io boundary makes it a swap rather than a rewrite.

**Q13: Namespace the measurement-profiles D-series?** — Deadline: 2026-09-30. Unresolved; blocks
nothing. Inherited from 9020's Q5. Default if not decided: renumber
`measurement-profiles-design.md` D13–D18 to MP-D1–MP-D6.

**Q14: Is companion patch 3 absorbed here or opened as its own plan?** — Deadline: 2026-09-16.
Unresolved; blocks M16. Inherited from 9020's Q6. It adds CalibrationManifest row fields,
prohibitions AUTH-11 to AUTH-13, and a 27-to-25 item-count correction that contradicts this plan's
27-item rubric. Default if not decided: open as its own plan owned by the 9003 compiler line.

**Q15: Reconcile implementation-notes-during-execution with the checkbox-flip gate.** — Deadline:
2026-09-30. Unresolved; blocks nothing but recurs on every milestone. Inherited from 9020's Q8,
where it was worked around per-milestone. Under the promotion rule a second occurrence moves the
rule into the test. Default if not decided: narrow the test's staleness signal to key on a verdict
badge written at flip time.

**Q16: Does `core/` stop importing `io/`, or do the fences allow indirect imports?** — Deadline:
2026-09-26. Unresolved; blocks M8. `.importlinter` declares layers with `core` above `io`, so
`core → io` passes today, while `docs/conventions/layering.md:41` permits it explicitly. The four
forbidden contracts are weaker than claimed unless this is settled. Tier C — `.importlinter` and a
convention document. Default if not decided: forbid `core → io` and amend the convention, because
a fence that admits indirect imports does not enforce the quarantine it names.

**Q17: Adopt B's CLI surface?** — Deadline: 2026-09-30. Unresolved; blocks M22. B offers three run
modes; this repository has a `version` stub. Tier C — CLI surface and stdout format, and
`src/argus/cli/main.py` is a sensitive path. Default if not decided: adopt the three modes, drop
the index-building mode whose output nothing reads, and add a JSON mode as the machine contract.

**Q18: How do milestones importing `transformers` satisfy the verification floor?** — Deadline:
2026-09-26. Unresolved; blocks M3 and M17. The pinned index is unreachable in the execution
environment, so `transformers` cannot be installed and no acceptance test that imports it can run
here. Default if not decided: stub the NLI behind a protocol so the acceptance tests run against a
fake, and mark the real-model path as covered only where a reachable index exists.

**Q19: What is the on-disk format for the evaluation record?** — Deadline: 2026-09-30. Unresolved;
blocks M21. B writes a report and discards every intermediate, so nothing is replayable. I5
requires persisting the FindingGraph, `intents_sha` and rubric version. Tier C — on-disk format.
Default if not decided: a sidecar run manifest, leaving B's report format intact.

## 8. Outcomes & Retrospective

*Written at completion or cancellation.*
