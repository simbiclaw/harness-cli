# 9010 — Continuous Proposer, Divergence Diagnostic, and Provenance Separation

## 1. Purpose

Argus's proposer currently reports a score the way a person reports a hunch: one sampled token, no resolution, no way to tell a confident judgment from a coin flip. That coarseness is invisible in the shipped verdict — the pure stages re-derive the number anyway (I3/I7) — but it is expensive everywhere the pipeline needs to *decide where to look*: which calls a human should review out of the auto-passed tail, which spans the hunt pass should spend its budget on, and whether the proposer is drifting away from human judgment or toward it. This plan makes the proposer's self-report a real scalar, wires it to the one place it is allowed to matter (the existing drift detector), and fences it so it can never become the shipped number or a routing input. It also splits the escape sampler so that prioritizing human review no longer poisons the escape-rate estimate that review exists to produce.

The user-visible outcome is not a different score. It is that a reviewer's queue is ordered by where the misses probably are, that a widening proposer-vs-derived gap schedules calibration work before κ falls, and that the escape-rate number stays honest while all of that happens.

## 2. Big Picture

This plan is a standalone dependent of 9002, not an amendment to it. 9002 is authored with M0–M7 all unstarted; injecting scope into an open plan is the pattern `docs/retrospectives/9004-execution-mistakes.md` identifies as a root cause of execution failure. 9010 therefore declares its own milestones and executes after the 9002 milestones it names have shipped.

The work lands on both sides of the seam, and the seam is the whole point. On the propose side (`src/argus/io/`), a new local open-weight Provider replaces the hosted-model deployment contract, exposes a batch-shaped interface, reuses the transcript KV cache across scoring passes, and computes a continuous `proposed_score` as the expectation over the distribution of scoring-token logits rather than the argmax of one sampled token. On the dispose side (`src/argus/core/`), exactly one new pure module consumes that number: a divergence aggregator that computes `|proposed_score − derived_score|` per dimension per call and feeds it into the §6 drift detector as an additional input to the existing demotion pathway. A second new pure module splits the escape sampler into a random tranche (the only decorrelated window into auto-passed calls, and the only input `compute_escape_rate()` may consume) and a prioritized tranche ordered by proposer signal, excluded from the estimate.

The invariant this plan adds is **I8 — provenance separation**: logit-derived continuity is proposer-internal and MUST NOT reach any disposer input. Two continuous quantities now exist in Argus and they are not interchangeable. Proposer granularity comes from scoring-token logits and is maximally correlated with model bias — it *is* a model self-report. Verdict granularity (`severity_map`) resolves through the human-annotated Calibration Manifest and is decorrelated by construction. The anticipated failure is a well-meaning simplification — "we already have a continuous signal, use it for severity" — which converts the human anchor into a model self-report and silently re-couples the two. I8 exists to make that a fixture failure rather than a design discussion. It is stated as an I-series invariant rather than a D-series decision because it is architectural, not a choice.

Three things from the source analysis are deliberately **not** adopted. The continuous score as a shipped number: D7/D8 stand unchanged, and quarantine is indifferent to a proposed score's resolution. Repeated evaluation (K) as a routing signal: averaging K evaluations shrinks variance as O(1/K) while bias is unchanged, so low variance can mean confidently wrong; K stays behind a config flag, diagnosis-only, and D12 stands — resample variance never touches routing. Criteria decomposition as a new mechanism: the 9003 compiler already is that axis and does it better.

Also out of scope: any change to `score()` or `adjust()`; any change to the replay contract (`proposed_scores`, logprob distributions, `proposer_id`, and `sampling_params` are non-replay-bearing diagnostics — the stored findings remain the replay-bearing record); the Calibration Manifest row-schema additions and AUTH-11/12/13 prohibitions from the companion patch 3, which are 9003 compiler territory and are parked as a steering question rather than absorbed here; and any write path into `INTENTS/` (D15 stands — the manifest is read, never written, by `src/argus/`).

CLI surface: none. This plan introduces no subcommand and changes no flag. Config surface: the proposer deployment contract (endpoint, model hash, G, K, drafter/mode/cap) and the escape-sampler tranche ratio are new config, and `src/argus/config/**` is a sensitive path — those edits are parked in Awaiting Steering (Q3) and no milestone writes them until resolved. Filesystem surface: the plan reads call records and `INTENTS/` as 9002 already does, and writes one new experiment artifact under `docs/experiments/`.

The four `FindingGraph` schema deltas this work needs — `proposer_id`, `alignment_epoch`, `sampling_params`, and the quarantined `proposed_scores{}` block — are a change to an on-disk format, which is Tier C, and they land in `src/argus/types/schemas.py`, a file 9002 owns. They are parked in Awaiting Steering (Q2) and excluded from the File Scope below; see the Decision Log entry on scope negotiation for why.

**File Scope:**
- `src/argus/io/local_proposer.py` (new)
- `pyproject.toml` (modify — declare the proposer extra)
- `src/argus/io/logprob_scoring.py` (new)
- `src/argus/types/proposer_diagnostics.py` (new)
- `src/argus/core/divergence.py` (new)
- `src/argus/core/escape_sampler.py` (new)
- `tests/test_logprob_capability.py` (new)
- `tests/test_capacity_measurement.py` (new)
- `tests/test_local_proposer.py` (new)
- `tests/test_logprob_scoring.py` (new)
- `tests/test_proposer_diagnostics.py` (new)
- `tests/test_divergence.py` (new)
- `tests/test_escape_sampler.py` (new)
- `tests/test_i8_provenance_separation.py` (new)
- `docs/experiments/9010-logprob-capability/**` (new)
- `docs/retrospectives/process-derivation-pipeline-spec-v5-patch-1.md` (read only)
- `docs/retrospectives/soft-criteria-authoring-spec-v4-patch-3.md` (read only)
- `docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation.md` (modify — this plan)

## 3. Milestones

The source patch labels these N0–N5 to keep them distinct from 9002's M0–M7. This plan renames them M0–M5; see the Decision Log for why. The N-label is carried in each milestone's Notes so the patch and the plan can be read against each other.

### M0 — Stack-agnostic logprob capability probe

Split from the original M0 (see Decision Log and M6 for the capacity half). This half answers B2.a, a question about the serving stack's API and not about any weights or hardware: does the stack expose top-k logprobs at a chosen token position, at what k, and by which path. The answer is weight-independent, so it is answerable against whatever stack D21 settles on — implemented here for llama.cpp on x86_64 (swapped from MLX per human direction). The committed artifact `docs/experiments/9010-logprob-capability/output.json` records `topk_available`, the observed `topk_ceiling`, the reliable `ceiling_source`, the `g_used` this plan will therefore use, and an `expectation_demo` proving D19's continuous score is computable and distinct from argmax. If no top-k is exposed at all, D19 reduces to argmax scores, only D20 survives, and M2 is rewritten before it starts.

`Acceptance Test:` `tests/test_logprob_capability.py::test_capability_record_is_complete` — the artifact parses and declares `topk_available` and `g_used`, with a positive `topk_ceiling` when available; a record missing capability fields fails. `tests/test_logprob_capability.py::test_g_used_within_measured_ceiling` — the recorded `g_used` never exceeds the measured top-k ceiling (and is 1 when no top-k is exposed). `tests/test_logprob_capability.py::test_expectation_is_computable` — the artifact demonstrates an expectation over the distribution distinct from the argmax, i.e. D19 is real.

`Notes:` Patch label N0 (capability half). Resolves carried-open B2.a. The declared fallback is not "give up": set G to whatever k the stack exposes and **record G per evaluation**, so the number stays interpretable across a capability change. This half is stack-agnostic in the QUESTION, not the harness — `run.py` is the llama.cpp implementation of the probe, and a different stack swaps the loader behind the same artifact schema. Nothing here depends on the production model or the target hardware, so this milestone completed in the authoring environment.
Allowed Reads: docs/retrospectives/**, src/argus/io/**
Allowed Writes: docs/experiments/9010-logprob-capability/**, tests/test_logprob_capability.py, docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation-notes/M0.md, docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation.md
Risk Tier: B

### M1 — Batch-shaped local Provider with KV-cache reuse

Land `src/argus/io/local_proposer.py`: a Provider for the local open-weight model served on Apple Silicon. Two properties are load-bearing. The interface accepts a **set** of calls and returns a set of finding-sets, even when the set has size one — this is what keeps batched-vs-single-stream a swap behind the io boundary, and it is why the serving-shape question (Q4) is safe to defer. And scoring passes MUST reuse the transcript KV cache: without it, per-dimension scoring re-prefills thousands of tokens four times and M2's per-dimension resolution is unaffordable at volume. Hunt and score are distinct call types with distinct configs, not one setting — the hunt pass runs at task temperature, the score pass greedy and seeded, and all sampling parameters are recorded. Any speculative-decoding layer is a pinned dependency of this Provider and nothing more: the target verifies every drafted token, so output is identical to plain decoding except at floating-point ties, and it may not appear in any layer fence, epoch treatment, or rubric adjacency.

`Acceptance Test:` `tests/test_local_proposer.py::test_accepts_singleton_set` — a set of one call returns a set of one finding-set, same code path as a batch. `tests/test_local_proposer.py::test_kv_cache_reused_across_scoring_passes` — four per-dimension scoring passes over one transcript prefill the transcript exactly once (hard criterion; a failure here falls M2 back to a single call-level score). `tests/test_local_proposer.py::test_sampling_params_recorded` — temperature, seed, drafter, mode, cap, and G appear in the returned record. `tests/test_local_proposer.py::test_provider_is_io_not_core` — structural check confirms `core ✗ model_client` still holds with this Provider present.

`Notes:` Patch label N1. Depends on 9002 M6 (the proposer boundary this Provider implements) having shipped; that dependency is cross-plan and so is stated here rather than in the machine-readable `Requires` field, which addresses only in-plan milestones. Blocked on Q1 (the serving dependencies are new top-level deps) and Q3 (endpoint and model hash are config). Proposer identity is part of the evaluation record, not an ambient setting.
Requires: M0
Allowed Reads: src/argus/io/**, src/argus/types/**, docs/retrospectives/**
Allowed Writes: src/argus/io/local_proposer.py, tests/test_local_proposer.py, pyproject.toml, docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation-notes/M1.md, docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation.md
Risk Tier: C

### M2 — Continuous per-dimension proposed_score, quarantined

Land `src/argus/io/logprob_scoring.py`, which computes a `proposed_score` as the expectation over the distribution of scoring-token logits rather than the argmax of the sampled token, and `src/argus/types/proposer_diagnostics.py`, which types the quarantined block that carries it. The scale is a single-token letter scale at G=20 — integers multi-tokenize and break extraction. Resolution is per-dimension, four per call, matching the derived scores it will be diffed against; per-criterion is a later refinement if divergence localization proves too coarse. K=1 at launch, with K>1 available behind a config flag, diagnosis-only, never routing. The result is stored as a quarantined block and `EvaluationResult` gains nothing from it.

`Acceptance Test:` `tests/test_logprob_scoring.py::test_expectation_not_argmax` — a distribution whose argmax and expectation differ yields the expectation. `tests/test_logprob_scoring.py::test_g_recorded_per_evaluation` — the G actually used is written into every record, not assumed from config. `tests/test_proposer_diagnostics.py::test_d19_quarantine` — a continuous `proposed_score` reaches neither shipped `raw` nor `adjusted` nor the replay hash. `tests/test_proposer_diagnostics.py::test_proposed_scores_non_replay_bearing` — a `FindingGraph` carrying `proposed_scores` and one with the field absent re-derive an identical `EvaluationResult`.

`Notes:` Patch label N2. Contingent on M0: if the stack exposes no top-k, this milestone is rewritten to argmax-only before it starts. Blocked on Q2 — the quarantined block is an on-disk format change, and the `FindingGraph` field additions land in a 9002-owned file. The reason to adopt a number that never ships is threefold, in descending value: it makes the M3 divergence diagnostic a real scalar rather than a tie-saturated near-binary; it lets the hunt pass order its budget toward likely violation mass; and it prioritizes escape sampling within the constraint of M4.
Requires: M0, M1
Allowed Reads: src/argus/io/**, src/argus/types/**, docs/retrospectives/**
Allowed Writes: src/argus/io/logprob_scoring.py, src/argus/types/proposer_diagnostics.py, src/argus/io/local_proposer.py, tests/test_logprob_scoring.py, tests/test_proposer_diagnostics.py, docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation-notes/M2.md, docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation.md
Risk Tier: C

### M3 — Divergence diagnostic into the §6 drift detector

Land `src/argus/core/divergence.py`: a pure function computing `|proposed_score − derived_score|` per dimension per call, aggregated over the same windows as κ — one drift clock, two instruments. It feeds the existing §6 drift detector as an additional input, not a separate channel, so there remains exactly one demotion pathway. A widening divergence flags for calibration injection, which is human-side work (manifest minting); it changes no machine decision. Divergence is the observable meaning of "the proposer became more aligned with human" as curated anchors land: shrinking divergence across manifest epochs, confirmed by rising κ. The module imports no model client, reads no clock, and uses no RNG.

`Acceptance Test:` `tests/test_divergence.py::test_divergence_is_pure` — same inputs produce byte-identical output across two calls. `tests/test_divergence.py::test_feeds_existing_detector` — divergence enters the §6 drift detector's existing input set; a second demotion pathway would fail the test. `tests/test_divergence.py::test_widening_divergence_flags_calibration_only` — a widening series raises a calibration-injection flag and changes no routing decision, coverage value, or auto-final right. `tests/test_divergence.py::test_core_no_model_client` — `divergence ✗ model_client`.

`Notes:` Patch label N3. Depends on 9002 M5.5 (the §6 drift detector and CriterionHealth) having shipped — cross-plan, stated here rather than in `Requires`. This is the one place a logit-derived quantity is permitted to be read at all, and M5 is the fixture that proves it is the only one.
Requires: M2
Allowed Reads: src/argus/core/**, src/argus/types/**, docs/retrospectives/**
Allowed Writes: src/argus/core/divergence.py, tests/test_divergence.py, docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation-notes/M3.md, docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation.md
Risk Tier: B

### M4 — Escape sampler tranche split

Land `src/argus/core/escape_sampler.py`. The escape-rate estimator requires an unbiased sample of auto-passed calls; the continuous proposed score makes it possible to prioritize which auto-passed calls humans review (low proposed score, no grounded finding — the recall problem wearing a flag). Prioritizing the whole sample would bias the very number the estimator depends on. So the sampler splits: a **random tranche**, 50% at launch and never below a declared absolute minimum, which feeds the escape-rate estimator and is the only decorrelated window into auto-passed calls; and a **prioritized tranche**, 50%, ordered by proposer signal, feeding recall recovery and calibration minting, and excluded from the escape-rate computation. `compute_escape_rate()` consumes only the random tranche, enforced by type rather than by convention.

`Acceptance Test:` `tests/test_escape_sampler.py::test_d22_red` — `compute_escape_rate()` fed a prioritized-tranche sample is rejected. `tests/test_escape_sampler.py::test_d22_green` — random tranche only; the estimator is unbiased over a synthetic stream with a known miss rate. `tests/test_escape_sampler.py::test_random_tranche_floor_holds` — the random tranche never falls below the declared absolute minimum, whatever the prioritization asks for. `tests/test_escape_sampler.py::test_prioritized_tranche_excluded_from_rate` — a prioritized case entering the pool leaves the computed rate unchanged.

`Notes:` Patch label N4. Depends on 9002 M5.5 (`compute_escape_rate()`) having shipped — cross-plan, stated here rather than in `Requires`, and note that enforcing the random-tranche-only rule by type means a signature change in a 9002-owned file, which is why this milestone cannot start before 9002 completes. Blocked on Q3: the split ratio and the absolute floor are config. The companion patch 3 makes `escape-random` cases the scarce, load-bearing provenance for manifest curation — the value of this milestone is mostly downstream of this plan.
Allowed Reads: src/argus/core/**, src/argus/types/**, docs/retrospectives/**
Allowed Writes: src/argus/core/escape_sampler.py, tests/test_escape_sampler.py, docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation-notes/M4.md, docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation.md
Risk Tier: C

### M5 — I8 fixture: provenance separation, standing red and green

No new application code. A standing fixture pair that makes the anticipated failure a test failure rather than a design discussion. The red case wires a logit-derived quantity into `severity_map` and must be structurally rejected. The green case confirms `severity_map` resolves only through the Calibration Manifest. The same fixture extends to the other disposer inputs I8 names: `deduction`, coverage, criterion health, and routing. This is the enforcement point that pairs with the companion patch's Gate-Checkability Audit — both hold that a quantity is only gate-checkable if a deterministic check can confirm its referent, observed once in compiled item signals and once in proposer scores.

`Acceptance Test:` `tests/test_i8_provenance_separation.py::test_i8_red` — a logit-derived quantity reaching `severity_map` is structurally rejected. `tests/test_i8_provenance_separation.py::test_i8_green` — `severity_map` resolves only through the calibration manifest. `tests/test_i8_provenance_separation.py::test_i8_covers_all_disposer_inputs` — the same rejection holds for `deduction`, coverage, criterion health, and routing. `tests/test_i8_provenance_separation.py::test_divergence_is_the_only_permitted_reader` — `src/argus/core/divergence.py` is the sole core module that reads a logit-derived quantity.

`Notes:` Patch label N5. The fixture lives in `tests/`, not `.claude/tests/` — see the Decision Log. Written after M2 because it needs a real quarantined block to point at, and it must pass before M3's reader is trusted.
Requires: M2
Allowed Reads: src/argus/**, docs/retrospectives/**
Allowed Writes: tests/test_i8_provenance_separation.py, docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation-notes/M5.md, docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation.md
Risk Tier: B

### M6 — Pinned capacity measurement

The capacity half split from the original M0. Where M0 asked a weight-independent API question, this milestone asks a hardware- and model-pinned one: what is the actual decode throughput, per call type (a long hunt pass and a single-token score pass), for the production model on the target serving hardware, single-stream and batched, with and without speculative decoding. This is the number that replaces the patch's capacity arithmetic (3000 calls/day ≈ 28.8 s/call; an 8-bit 27B at ~20–25 tok/s single-stream; a hunt pass of 1500–2000 output tokens) — an estimate the patch explicitly flags as not evidence. It is deliberately separate from M0 because it cannot be answered from a synthetic model or the authoring box: the same `run.py` harness produces the numbers, but only a run against the pinned model on the target hardware, with `--synthetic` omitted, yields a `throughput_representative: true` artifact.

`Acceptance Test:` `tests/test_capacity_measurement.py::test_capacity_is_representative` — the artifact's `throughput_representative` is true and `throughput_caveat` is null; a synthetic run fails here, which is the point. `tests/test_capacity_measurement.py::test_per_call_type_throughput_present` — hunt and score each carry a positive `single_stream_tok_s` over at least two samples and a `batched_tok_s` (a number, or null with a reason). `tests/test_capacity_measurement.py::test_stack_and_model_pinned` — the artifact records the production `model_id`, a real `model_hash` (not `unrecorded`), and `synthetic_weights: false`.

`Notes:` Patch label N0 (capacity half). Blocked on model access and target hardware, not on code — real GGUF hosts are proxy-blocked in the authoring environment, so this milestone stays red until a run on the target box against the pinned model. It has no code dependents: it informs Q4's serving-shape decision (already deferred) and confirms M2's per-dimension resolution is affordable at volume, but no other milestone's implementation waits on it. That is why the plan proceeds M0 → M2..M5 on the capability result while this milestone is pending.
Requires: M0
Allowed Reads: docs/retrospectives/**, src/argus/io/**
Allowed Writes: docs/experiments/9010-logprob-capability/**, tests/test_capacity_measurement.py, docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation-notes/M6.md, docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation.md
Risk Tier: B

## 4. Progress

- [x] M0: Stack-agnostic logprob capability probe  (done 2026-08-27, verified at output.json; MLX→llama.cpp swap)
- [x] M1: Batch-shaped local Provider with KV-cache reuse  (done 2026-08-27, verified; KV reuse proven against real llama.cpp)
- [x] M2: Continuous per-dimension proposed_score, quarantined  (done 2026-08-27, verified; quarantine + replay invariants)
- [x] M3: Divergence diagnostic into the §6 drift detector  (done 2026-08-27, verified; one demotion pathway, I8-safe)
- [ ] M4: Escape sampler tranche split  (created 2026-08-26)
- [ ] M5: I8 fixture: provenance separation, standing red and green  (created 2026-08-26)
- [ ] M6: Pinned capacity measurement  (created 2026-08-27, split from M0; blocked on model access)

## 5. Decision Log

### Decision: adopt D19 — the proposer MAY emit a continuous proposed_score

Where S2 emits a `proposed_score`, it is computed as the expectation over the distribution of scoring-token logits rather than the argmax of the sampled token, on a single-token letter scale at G=20, per-dimension, K=1 at launch. The number never ships; it is adopted for the three uses named in M2's Notes.
Rationale: adopting a finer proposed score costs nothing past the seam — quarantine is indifferent to its resolution — while a tie-saturated near-binary makes the M3 divergence diagnostic unusable as a scalar.
Source: docs/retrospectives/process-derivation-pipeline-spec-v5-patch-1.md:37-58

### Decision: do not adopt repeated evaluation (K) as a routing signal

K>1 stays behind a config flag, diagnosis-only. D12 is unchanged: resample variance never touches routing.
Rationale: averaging K evaluations shrinks variance as O(1/K) while bias is unchanged, with diminishing returns from correlated biases on hard examples — so low variance can mean confidently wrong, and self-disagreement measures difficulty rather than residue.
Source: docs/retrospectives/process-derivation-pipeline-spec-v5-patch-1.md:28-30

### Decision: adopt D20 — divergence feeds the existing drift detector, not a new channel

`|proposed_score − derived_score|` is computed per dimension per call and aggregated over the same windows as κ, entering the §6 drift detector as an additional input.
Rationale: two demotion pathways would need a tiebreak rule nobody has evidence to write, and the aggregation windows already exist for κ — one drift clock with two instruments is cheaper to reason about than two clocks.
Source: docs/retrospectives/process-derivation-pipeline-spec-v5-patch-1.md:61-76

### Decision: state provenance separation as I8, an invariant, not a D-series entry

Logit-derived continuity is proposer-internal and may not feed `severity_map`, `deduction`, coverage, criterion health, or routing.
Rationale: the distinction is architectural rather than a choice between options — proposer granularity is maximally correlated with model bias because it is a model self-report, while `severity_map` granularity is decorrelated by construction through the human-annotated manifest, and a D-series framing would invite re-litigation of a boundary that has no second option.
Source: docs/retrospectives/process-derivation-pipeline-spec-v5-patch-1.md:78-97

### Decision: adopt D21 — local open-weight proposer, with KV-cache reuse as a hard M1 criterion

A single canonical local model with a declared swap path, endpoint and model hash pinned in config, hunt at task temperature and score greedy-and-seeded, and a Provider interface that takes a set of calls and returns a set of finding-sets even at size one.
Rationale: KV-cache reuse is what makes per-dimension scoring affordable at volume — without it a scoring pass re-prefills the transcript four times — so it is an acceptance criterion rather than an optimization, and D19 falls back to one call-level score if it cannot be met.
Source: docs/retrospectives/process-derivation-pipeline-spec-v5-patch-1.md:101-117

### Decision: split M0 into a stack-agnostic capability probe (M0) and a pinned capacity measurement (M6)

The original M0 bundled two questions with different natures: an API-capability question (does the stack expose top-k logprobs) that depends on neither weights nor hardware, and a throughput question that depends on both. The first was answerable in the authoring environment and gated the code milestones; the second needs the production model on target hardware, which is unreachable here.
Rationale: bundling them meant either blocking the whole plan on hardware access or flipping M0 on a non-representative throughput number — the split lets the capability result unblock M1–M5 immediately while the capacity measurement stays honestly pending as M6, whose acceptance test fails on any `throughput_representative: false` artifact. M6 is appended rather than inserted as M0.5 because the milestone and flip-gate parsers match only integer milestone numbers, and renumbering M1–M5 would corrupt the many prose cross-references to them.
Source: .claude/tests/test_milestone_constraints.py:44

### Decision: swap D21's serving stack from Apple Silicon/MLX to llama.cpp on x86_64 (human-directed)

D21 as authored pinned the proposer to a local open-weight model on Apple Silicon served via MLX. The execution environment is x86_64 Linux without MLX, so M0 could not run and the plan stalled at its first milestone. The human directed swapping the stack to llama.cpp (`llama-cpp-python`), which runs on x86_64 and exposes per-token logits. M0 was then run for real against it.
Rationale: the swap is a human decision recorded here for provenance, not one this plan made on its own; llama.cpp answers B2.a (top-k exposure is an API property) and the capacity questions on the available hardware, and the io-boundary interface (M1) keeps the specific runtime a swap behind the Provider so the plan's architecture is unchanged by which local engine serves it.
Source: docs/decisions/dep-vet-llama-cpp-python.md

### Decision: M3 enforces the single-demotion-pathway property structurally, via a three-field assessment type

D20 says divergence "feeds the existing §6 drift detector as an additional input, not a separate channel", and I8 forbids it touching routing, coverage, auto-final, or score/adjust. The provisional `DriftAssessment` carries exactly three fields — `demote`, `calibration_injection`, `reason` — and `assess_drift` sets `demote` from κ alone; a widening divergence sets only `calibration_injection`.
Rationale: making the type carry no disposer field means divergence has nothing it could write to change a machine decision, so I8 holds by construction rather than by a reviewer noticing — the test asserts both the behavior (widening divergence never demotes) and the structure (no forbidden field). 9002 M5.5 lands the real detector; the durable part here is the divergence math, and the stand-in is replaced then.
Source: docs/retrospectives/process-derivation-pipeline-spec-v5-patch-1.md:61

### Decision: the proposed_score is the expectation over the ORDERED letter scale, correcting M1's capture

M2's first implementation, and M1's `_top_g`, both truncated the per-dimension logits by magnitude. That is wrong for a letter scale: position i is score-letter i, so the score axis is ordered and sorting destroys it. `continuous_proposed_score` now takes the first g logits in scale order, and M1's capture was changed from `_top_g` (sorted) to `_scale_slice` (first g in order). The acceptance test `test_expectation_not_argmax` caught the discrepancy before the flip.
Rationale: D19 defines the score as the expectation over the distribution of scoring-token logits on a single-token letter scale — the letters are the scale and their order is the score, so an expectation over magnitude-ranked positions would be a meaningless quantity. The real deployment maps the specific letter-token vocab ids; that mapping is a config concern (Q3), so the first-g slice is the provisional ordered scale until then. This is why `src/argus/io/local_proposer.py` (an M1 file) is in M2's Allowed Writes.
Source: docs/experiments/9010-logprob-capability/output.json

### Decision: M1 injects the model and defines provisional local types, since 9002's schemas do not exist yet

M1 depends cross-plan on 9002's proposer boundary and `Finding`/`FindingGraph` schemas, which are unstarted. Rather than block, the Provider takes its model by a `LogitModel` protocol (dependency injection) and returns a provisional `FindingSet` with an empty `findings` list; the g-wide per-dimension logit slice it captures is the raw material M2 scores. `ProposerConfig` lives in `io/` as a parameter object, not in `config/`.
Rationale: injection makes the KV-cache contract observable against a fake model with no GGUF in CI and keeps the specific stack swappable, and an empty `findings` list is honest — extraction against the real schema is 9002 M6's job, not M1's. The `config/` landing is Tier C (Q3) and deferred, so a frozen dataclass passed at construction avoids touching a sensitive layer before that resolves. `findings` and `ProposerConfig` are replaced/relocated when 9002 lands.
Source: docs/exec-plans/active/9002-implement-argus-eval-pipeline.md

### Decision: source D19's continuous score from the low-level full-logit vector, not the high-level logprobs API

M0 measured that llama.cpp exposes logprobs two ways, and they differ sharply. The high-level `create_completion(logprobs=N)` caps below N and returns a distribution-dependent count (requested 20 → 12; requested 256 → 129). The low-level logit vector (`Llama.scores`, `logits_all=True`) exposes the full vocabulary. D19's per-dimension expectation must be computed from the low-level vector.
Rationale: the high-level API cannot reliably deliver G=20 distinct entries, so building D19 on it would silently truncate the distribution the expectation is taken over; the low-level path is measured to expose the full width and the artifact demonstrates the expectation is a real scalar distinct from argmax.
Source: docs/experiments/9010-logprob-capability/output.json

### Decision: treat the speculative-decoding layer as throughput, not judgment

Any EAGLE-family speculative decoder is a pinned dependency of the io Provider, logged alongside `sampling_params`, and appears in no layer fence, epoch treatment, or rubric adjacency.
Rationale: the target verifies every drafted token, so output is identical to plain decoding and diverges only at floating-point ties where the logit margin is approximately zero — it cannot alter judgment, and it accelerates the hunt pass while being irrelevant to a scoring pass that has a single token to amortize.
Source: docs/retrospectives/process-derivation-pipeline-spec-v5-patch-1.md:119-134

### Decision: adopt D22 — the escape sampler splits into a random floor and a prioritized tranche

`compute_escape_rate()` consumes only the random tranche; the prioritized tranche feeds recall recovery and calibration minting and is excluded from the estimate.
Rationale: prioritizing the whole sample would bias the very estimator the sample exists to produce, and the random tranche is the only decorrelated window into auto-passed calls — which the companion patch also identifies as the scarce, load-bearing provenance for manifest curation.
Source: docs/retrospectives/soft-criteria-authoring-spec-v4-patch-3.md:93-103

### Decision: launch the tranche split at 50/50 with a declared absolute floor

Fifty percent random, fifty percent prioritized, with the random tranche never falling below an absolute minimum count regardless of what prioritization asks for.
Rationale: the split is the patch author's launch choice, not a number derived from a measured variance budget, and the right ratio depends on an escape-rate distribution that does not exist yet. Confidence: low.
Revisit: by 2026-11-30

### Decision: rename the patch's N0–N5 milestone labels to M0–M5

The source patch labels these milestones N0–N5 to keep them visually distinct from 9002's M0–M7. This plan uses M0–M5 and carries the N-label in each milestone's Notes.
Rationale: the milestone parser matches `### M(\d+)` only, so N-labelled milestones are silently skipped — including by the check that every milestone has an Acceptance Test — which would leave this plan unenforced by exactly the harness it is written for.
Source: .claude/tests/test_milestone_constraints.py:37

### Decision: declare only files 9010 creates; shared 9002 files enter scope on 9002's completion

`src/argus/types/schemas.py`, `src/argus/io/proposer.py`, and `src/argus/core/escape_rate.py` all need edits from this work and are all declared by 9002. They are described in the Big Picture and in milestone Notes but excluded from the File Scope block.
Rationale: the collision detector compares active plans statically and would fail on the overlap, but the dependency here is temporal rather than contended — every milestone that touches a 9002-owned file is gated on that 9002 milestone having shipped, at which point 9002 moves to completed/ and the paths are uncontended.
Source: .claude/tests/test_plan_collisions.py:93-100

### Decision: the I8 and replay fixtures live in tests/, not .claude/tests/

M5's fixtures are ordinary pytest files under `tests/`, following the placement 9002 uses for its own structural fixtures such as the no-write-path test.
Rationale: `.claude/tests/**` is a sensitive path whose edits are Tier C automatic, and these fixtures assert properties of application code rather than of the harness, so the harness directory would be the wrong home even without the gate.
Source: .claude/sensitive-paths.txt:16

### Decision: file the two patch documents into docs/retrospectives/ rather than folding them into the spec HTML

`process-derivation-pipeline-spec-v5-patch-1.md` and `soft-criteria-authoring-spec-v4-patch-3.md` are committed next to the specs they patch, matching how patches 1 and 2 of the companion spec are already stored.
Rationale: the existing sibling patch files establish the layout, and this plan cites them by path and line — folding them into the HTML would break every citation in this Decision Log and was not part of the requested scope.
Source: docs/retrospectives/soft-criteria-authoring-spec-v4-patch-2.md:1

### Decision: every milestone's Allowed Writes carries its own notes file and the plan

The six `Allowed Writes` lines as first authored listed only the milestone's product files. Each now also lists `docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation-notes/M<N>.md` and the plan file itself.
Rationale: the pre-execution gate blocks any write outside the current milestone's declared patterns, and every milestone is required by convention to log implementation notes and keep the plan current — so as authored, each milestone forbade the two writes it is obliged to make. Fixed across all six rather than only M0, because the next five sessions would each hit the same wall.
Source: .claude/hooks/pre_execution_gate.py:126-146

## 6. Surprises & Discoveries

**M0 was split after it ran, once the two halves proved to have different blockers.** The capability question (top-k exposure) came back answerable in this environment and gated the code milestones; the capacity question (production throughput) needs a model host the proxy blocks. Rather than hold the whole plan on hardware access or flip a milestone on a synthetic decode rate, M0 became the stack-agnostic capability probe (done) and M6 became the pinned capacity measurement (pending). M6's acceptance test fails on any `throughput_representative: false` artifact, so the synthetic run cannot satisfy it — the milestone stays red until a real model is measured. Appended as M6 rather than inserted as M0.5 because the milestone and flip-gate parsers match only integer numbers (the same reason 9002's own M3.5/M4.5/M5.5 are invisible to those gates).

**Implementation notes for an in-flight milestone trip the checkbox-flip gate.** `docs/conventions/implementation-notes.md` requires notes to be written *during* execution, as deviations happen, and `pev-loop.md`'s Execute phase says the same. But `.claude/tests/test_pev_checkbox_flip_gate.py::test_unflipped_milestones_should_not_have_confirmed_notes` treats a notes file for an unflipped milestone as stale leftovers from a dead run — and its `VERDICT_BADGES` pattern matches all four badge types, not just `[plan-confirmed]`, so *any* well-formed entry trips it. The two rules cannot both be satisfied while a milestone is in progress. M0's notes were written, hit the gate, and were relocated into this plan's Surprises and Awaiting Steering sections rather than deleted, per the gate's own remediation text. The structural test outranks the convention doc under the promotion rule, so the test was left untouched — it is a sensitive path and a Tier C edit either way. Parked as Q8. This is the first of the two violations the promotion rule counts.

**M0's deviation, in devgrid form, since it has no notes file to live in.** *What the plan said:* M0 measures top-k exposure and per-call-type throughput on the target box, producing a committed `output.json`. *What the code revealed:* the execution environment is x86_64 Linux with no MLX (`uname -m` → `x86_64`; `import mlx` → `ModuleNotFoundError`), while the target is an Apple Silicon M3 Ultra; neither probe can run here, and no CI runner in this repo can run them either. The plan named a target box but never named which executor has it. *Conservative choice (superseded):* originally, implement the harness but produce no artifact and leave M0 unflipped, rather than fabricate numbers. Superseded when the human directed the llama.cpp swap; the harness was re-targeted and a real artifact produced. The discipline held in the interim — no synthetic numbers were ever committed — hand-authoring plausible numbers from the patch's capacity arithmetic would invert the milestone's purpose, since that arithmetic is precisely the estimate M0 exists to replace. `run.py` exits non-zero and writes nothing when the stack is unimportable, so a re-run in the wrong environment cannot leave a synthetic artifact behind. *Revisit:* when the spike runs on the target box (Q7, deadline 2026-09-16); if the box is unavailable past that date, M0 is re-scoped rather than left waiting, because M1 and M2 are both gated on it.

**The acceptance test was verified against nine synthetic artifacts, none committed.** A test that only ever fails on a missing file proves nothing about the artifact it will eventually validate. It was exercised against one well-formed artifact (3 passed) and eight mutations, each rejected by the intended assertion: `g_used` above the ceiling, `topk_available: false` with `g_used: 20`, a missing `score` call type, a null `batched_tok_s` without a reason, a future-dated `measured_at`, an empty `stack.model_id`, an absent `batched_tok_s` key, and `samples: 0`. All nine were deleted afterwards and the working tree confirmed clean before commit.

**Logprob exposure is probed, not asserted, and the high-level API proved lossy.** `probe_topk()` requests a ladder of k from llama.cpp's high-level `create_completion(logprobs=N)` and records what actually returns, then reads the low-level full-logit width separately. The high-level path caps unpredictably (20→12, 256→129, count varies with the distribution); the low-level vector exposes the full vocabulary. This is exactly why the probe measures rather than trusts a documented signature. B2.a is open precisely because the exposure is unverified on this stack, so a harness written against an assumed signature would answer the question with its own assumption. The probe records which entry point answered, the observed width, and the tokenizer's vocab size, so a reader can tell a genuine top-k ceiling from a full-vocabulary distribution. Absence of exposure is recorded as a result (`topk_available: false`, `g_used: 1`) rather than as a script failure — that is the D19-reduces-to-argmax branch, and it is a real answer to the milestone's question.

**M0 ran after a human-directed stack swap: MLX/Apple Silicon → llama.cpp/x86_64.** As first authored M0's two questions were both properties of an Apple Silicon box running MLX, and this environment is x86_64 Linux without MLX, so the spike was implemented but not run. The human then directed swapping the serving stack to llama.cpp (`llama-cpp-python`), which runs here. The spike now produces a real `output.json`: top-k logprobs are exposed (ceiling 256 = full vocab via the low-level logit vector), `g_used` = 20, and the expectation over the softmax (9.38) is genuinely distinct from the argmax (13), so D19 is computable. The acceptance test passes against the real artifact. Real HuggingFace models are proxy-blocked, so the measurement used a synthetic random-weight tiny llama-arch GGUF — valid for the two questions M0 asks, since top-k exposure is an API property and decode rate is a size property, neither depending on weight values. Throughput is therefore flagged `throughput_representative: false`: it is a real rate for this model size but must be re-measured on a production model before the capacity arithmetic (Q4) is trusted.

**The experiments README and the structural test disagree about artifact layout.** `docs/experiments/README.md` specifies `run.sh` plus a `results/` directory; `.claude/tests/test_experiment_dirs_real.py` accepts `run.py` or `run.sh` and `output.txt`, `output.json`, or `results`. This plan's M0 names `run.py` plus `output.json`, which the structural test accepts and the README does not describe. Nothing is broken — the test is the enforcement and the README is the older prose — but the README is worth reconciling with the test before another experiment is authored against it.

**File-scope collision with 9002 is temporal, not contended.** Writing the File Scope block surfaced that three files this work must edit — `src/argus/types/schemas.py`, `src/argus/io/proposer.py`, `src/argus/core/escape_rate.py` — are declared by 9002, which is still active. The collision detector is static and would fail on the overlap even though no milestone of either plan can execute against those files at the same time. The resolution recorded in the Decision Log keeps the detector green and the dependency honest, but it does mean this plan's declared scope understates its eventual footprint: a reader picking it up after 9002 completes should add those three paths and their tests before starting M2 or M4.

**The D-series numbers collide across two documents.** `docs/retrospectives/measurement-profiles-design.md` defines D13–D18 for measurement profiles, profile organization, profile schema, embed-vs-reference, and `_rubric/profiles/`. The pipeline spec already uses D13–D18 for the v6 conformance decisions — scope, referent, confirmation, acoustic/phrase, two-stage, pins-and-layers. These are two unrelated series sharing numbers. This plan continues the pipeline series at D19 and parks the namespacing fix as a steering question (Q5) rather than renaming another document's decisions unilaterally.

**The spec path in CLAUDE.md and in 9002 §1 is stale.** Both reference `docs/PRD/process-derivation-pipeline-spec-v5.html`. There is no `docs/PRD/` directory; the spec lives at `docs/retrospectives/process-derivation-pipeline-spec-v5.html`. This plan cites the correct path throughout and does not fix the two stale references, which sit in a sensitive path and in another plan's prose.

**The item count is wrong in both specs.** The pipeline spec body and §10 handoff say 27 items; the companion spec body, §3.6b, and §7 say the same. Patch 1 to the companion establishes 25 rules_criteria items — Procedural Accuracy 7, Empathy & Tone 8, Problem Resolution 8, Proactive Value 2. The 27 figure appears to have originated in the sampled-gaps analysis, which itself used both "27 items" and "25 independent binary verdicts" in one document; Acoustic Feature and Phrase & Keyword are evidence sources consumed by the 25, not two additional rule items. The find-and-replace is parked as part of Q6 because it touches the companion spec that 9003 owns.

**Whether per-dimension divergence localizes well enough is unknown.** Four dimensions per call is chosen to match the derived scores it is diffed against, not because anything has been measured about how coarse that is. If divergence widens without pointing at a criterion, per-criterion resolution is the declared next refinement — and it multiplies the scoring-pass count, which is why M1's KV-cache criterion is hard rather than aspirational.

**Revisit 2026-11-30 — the 50/50 tranche split.** Mirror of the Marked-as-guess Decision Log entry above. By that date there should be enough escape-rate history to say whether the random floor is over- or under-provisioned. The companion patch flags its own tranche-balance numbers (a 40-case threshold, a 20% `escape-random` floor in the exposure set) with the same caveat: authored, not derived.

## 7. Awaiting Steering

**Q1: Adopt the local serving stack as a new top-level dependency?** — Awaiting Steering: resolved 2026-08-27. The human directed swapping MLX for llama.cpp on x86_64; `llama-cpp-python` was dep-vetted (`docs/decisions/dep-vet-llama-cpp-python.md`, APPROVED with the downloads check unverifiable behind the proxy) and installed. Speculative decoding is deferred to M1/Q4 as a Provider-internal concern. Originally blocked M1. Options: (a) adopt both, each through the dep-vetter skill first, with the speculative layer pinned as a Provider-internal dependency; (b) adopt the serving runtime only and defer speculative decoding until M0's capacity measurement shows the hunt pass needs it; (c) reject the local deployment contract and keep a hosted proposer, which makes D19 contingent on that provider's logprob exposure instead. Tier C — new top-level dependencies from maintainers not already trusted by the project, and `pyproject.toml` is a sensitive path. Default if not decided by the deadline: (b), because M0's measurement is the input that distinguishes (a) from (b) and it will exist by then.

**Q2: Accept the four FindingGraph on-disk schema deltas?** — Deadline: 2026-09-16. Unresolved; blocks M2. The fields are `proposer_id` (model identity and hash, for drift attribution), `alignment_epoch` (derived as `align@<manifest-epoch>`, not an independent counter), `sampling_params` (temperature, seed, drafter/mode/cap, G, K), and the quarantined `proposed_scores{}` block carrying per-dimension continuous scores plus the G actually used. All four are non-replay-bearing: the stored findings remain the replay-bearing record, and `EvaluationResult` re-derives from surviving anchored findings regardless of which proposer produced them. Tier C — a change to an on-disk format Argus reads and writes, landing in a 9002-owned file. Default if not decided by the deadline: none — M2 does not start.

**Q3: Accept the new config surface for the proposer deployment contract and the tranche split?** — Deadline: 2026-09-16. Unresolved; blocks M1 and M4. The surface is the proposer endpoint and pinned model hash, G, the K flag, drafter/mode/cap, the escape-sampler split ratio, and the random-tranche absolute floor. Tier C — config schema change, and `src/argus/config/**` is a sensitive path. Default if not decided by the deadline: none — no milestone writes config until this resolves.

**Q4: Fix the serving shape now, or keep it behind the batch-shaped interface?** — Deadline: 2026-09-30. Unresolved; does not block M1. Options: (a) batched production path with the speculative layer idle and reserved for interactive and dev work; (b) single-stream plus speculative decoding with a longer processing window or a second box. The patch records this as deferred by the owner, and it is safe to defer only because M1 mandates the batch-shaped interface — the two shapes pull against each other, and at 3000 calls/day batch throughput is the binding constraint. Default if not decided by the deadline: defer again; the interface makes the choice a swap behind the io boundary rather than a rewrite.

**Q5: Namespace the measurement-profiles D-series before either series is cited elsewhere?** — Deadline: 2026-09-30. Unresolved; blocks nothing in this plan. Options: (a) renumber `measurement-profiles-design.md` D13–D18 to MP-D1–MP-D6 and update its citers; (b) renumber the pipeline series instead, which is worse because ADRs and CLAUDE.md already cite pipeline D-numbers; (c) leave both and rely on context, accepting that a bare "D15" is ambiguous. Default if not decided by the deadline: (a).

**Q6: Is the companion patch 3 scope absorbed here or opened as its own plan?** — Deadline: 2026-09-16. Unresolved; blocks nothing in this plan. The companion adds `used_for`, `provenance`, `blind`, and `reason` to CalibrationManifest rows, adds prohibitions AUTH-11 through AUTH-13, adds the F4 tranche-balance check, relocates the manifest to `INTENTS/_meta/calibration-manifest.<epoch>.yaml` with independent epoch versioning, supersedes the §3.6b compile pattern, and applies the 27→25 item-count correction across both specs. Options: (a) a separate 9011 owned by the 9003 compiler line, which is where the schema and the compiler already live; (b) absorb into this plan, which widens it across the seam it exists to defend. Default if not decided by the deadline: (a).

**Q7: Who runs the M0 spike, on which model, and by when?** — Awaiting Steering: resolved 2026-08-27. Run in this session against a synthetic tiny llama-arch GGUF (real HF models are proxy-blocked); capability and throughput are weight-independent, so the answer is valid, with throughput flagged non-representative of a production model. Originally blocked M1 and M2. The harness is committed and the acceptance test is waiting for its artifact; what is missing is one run on an M3 Ultra with MLX installed, invoked as documented in `docs/experiments/9010-logprob-capability/README.md`, plus a second run with `--drafter`/`--spec-mode`/`--spec-cap` to get the speculative-decoding delta. Running the spike is exploratory and does not itself adopt a dependency into `pyproject.toml`, so it does not presuppose Q1 — it informs it. Three decisions wait on the result: M2's scale (the value of G, and whether a continuous proposed score exists at all), Q4's serving shape (the batched-versus-single-stream numbers), and M1's KV-cache criterion (the score-pass cost is what makes per-dimension scoring affordable). Do not hand-author the artifact: the acceptance test rejects a future-dated `measured_at` and requires the stack identity, but no check can detect plausible fabricated throughput. Default if not decided by the deadline: re-scope M0 to a capability probe only, dropping the capacity half, so M2 is not blocked indefinitely by a box nobody has scheduled.

**Q8: Reconcile implementation-notes-during-execution with the checkbox-flip gate.** — Deadline: 2026-09-30. Unresolved; blocks nothing, but it will recur on every milestone of every plan. `implementation-notes.md` and `pev-loop.md` require notes written during execution; `test_pev_checkbox_flip_gate.py::test_unflipped_milestones_should_not_have_confirmed_notes` rejects notes for any unflipped milestone, matching all four badge types. Options: (a) narrow the test's staleness signal so in-flight notes are legal — for instance keying on a verdict badge the PEV verifier writes at flip time rather than on any entry, which is the distinction the test's own docstring describes; (b) amend the conventions to say notes are written at flip time, which loses the during-execution deviation log the convention exists to provide; (c) leave both and let each milestone relocate its notes as M0 did. Tier C — `.claude/tests/**` is a sensitive path. Default if not decided by the deadline: (a).

## 8. Outcomes & Retrospective

*(written at completion)*
