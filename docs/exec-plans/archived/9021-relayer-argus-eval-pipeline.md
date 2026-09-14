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
| Proposer (S2) | Written from scratch, `anthropic`-only | Imported from `simbiclaw/sim` — **seven** modules, not the original eleven, and `qa_agent` rewired rather than moved verbatim; see `9024-port-and-fences` M7 for the import list and the type-level data flow |
| Scorer (S4a) | Written from scratch | Extracted from B's `core/aggregator.py` — a redesign of the boundary, not a file move |
| Rubric | Assumed to exist in `INTENTS/` | B's 27-item table becomes `SpecificRubric` input, compiled by 9003 into epoch-pinned nodes |
| Layer fences | Asserted in prose; three of four vacuous | Four `forbidden` import-linter contracts, each proved by a planted violation |
| Baseline | Empty `src/argus/` | `simbiclaw/sim@0c2cccd` plus this repo at the 9020 head |
| 9020 relationship | Unstated | Section 2.1 records the inheritance explicitly |

## 2. Big Picture

The layer boundary this repository specifies and `simbiclaw/sim` ignores falls close to where B's
module graph already splits — **close, but not at it, and the difference was initially mistaken for
the boundary itself.** B runs eight stages across four tiers: S0 ingest (stages −1 and 1); the
producer-side decisions it makes for itself (stage 0's call routing and knowledge assembly, stage
3's intent inference); the consumer's proposal (stages 2, 4, 5); and the consumer's arithmetic
(stage 6). Only the last two belong to Argus — the earlier sentence here claimed a "rubric
compiler's derivation" among B's tiers, and B has none: it reads a flat table rather than compiling
one, which is why the compiler is this repository's. The first revision of this plan cut the import along B's module graph
because *"B's module graph splits close to the layer boundary, which is why this is a move rather
than a rewrite"* — a seam chosen for being cheap, then justified by its cheapness. The seam that
matters is not where B's imports separate; it is **does this stage decide something the tree already
records.** A module that re-decides what a producer decides is not the consumer's, wherever it sits.

**The thesis, narrowed and stated honestly.** Moving B's *model-calling* modules into `io/` makes
quarantine a directory move rather than a rewrite — that much holds, and it is what makes this plan
cheap. But it was never true of the pure stages: M10's own Contract says "not a move", M17's says
"not a port", M18's says "neither codebase has any notion of precedent", and M12, M19 and M21 are
new. The thesis describes the S2 half and nothing else.

In scope: the import and re-layering of B's **proposal half** (as delimited in M7); the pure stages
S3, S4a, S4b and S5; epoch pinning; replay; the four layer fences as enforced artifacts; compiling
B's rubric through 9003; and the call-record contract that delimits the seam.

Deliberately out of scope: any change to the 9003 compiler's own design; audio ingest (S0 is
upstream — and this is enforced, not merely declared: M7 no longer imports `asr_preprocessor` or
`preprocessor`, M2 consumes the producer's `speaker_role` rather than re-deriving it, and M3
retires the reliability chain instead of repairing it); routing and per-call intent assignment
(audio2tree's D5 protocol, which alone writes `bottom_up`); Metis and Hermes; multi-language
support — this plan commits Argus to zh-CN customer-service QA at the code level, and a future
multi-language requirement is a rewrite rather than a configuration.

**The three epistemic classes and the eight expertise types** are the consumer's real interface to
the tree, and they are not B's "double knowledge base". ADR-0001 separates Versioned Rubric,
Descriptive Facts and Accumulated History, and PMCA §A.5 assigns each a lane: facts and standards
into the raw lane (`score(facts, rubric)`), accumulated history into the adjust lane
(`adjust(raw, history)`), measurements into none. Argus's three category readers (M13) are that
separation at the code level. B's model — build one KB context blob, inject it into every stage's
prompt, let the model apply it — makes the model the applier of knowledge, which is precisely what
S1–S5 exist to prevent.

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
| `divergence.py:assess_drift` — "provisional detector" | `core/divergence.py` | Kept; **M19.5 (new, 2026-09-14) supplies its missing consumer.** The module's own docstring defers to "9002 M5.5", which was overturned — so this deferral chain terminated in nothing until this milestone existed. M17 is corroboration (I6) and never was the drift detector. |
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
- `build/rubric-staging/**` (new — M16's compiled-node output, a build artifact: never committed, never read at runtime; the epoch commit that lands these nodes is an upstream act)
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
runs: the random tranche's absolute floor (M19) and the role-swap confidence floor (**M2's original
formulation** — superseded 2026-09-14: M2 is now a deletion, not a threshold; see
`9023-b-repairs`). Measure,
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

### M2 — Delete the role re-derivation; consume the producer's `speaker_role`

**Superseded 2026-09-14 — this milestone was "add a confidence floor to `_verify_roles`".** The
floor was the wrong repair: `_verify_roles` re-derives speaker identity from Chinese keyword
heuristics plus an LLM call, and the producer establishes the same fact deterministically. The
tier violation is the defect; a better heuristic at the wrong tier is still at the wrong tier.
audio2tree's 9008 M9 now produces `speakers[].speaker_role` (`agent`/`customer`/`null`),
`speakers[].speaker_role_source` (`voiceprint`/`keywords`/`null`) and `config.voiceprint`
provenance, from an enrolled-agent database with a declared keyword fallback — and **declines
rather than guessing** when either speaker has no eligible segment. The consumer reads that, and
an absent role is an absent input.

Do not repair, port, or import `_verify_roles`, `AGENT_INDICATORS`, `AGENT_OPENING`,
`ROLE_SWAPPED` or the swap application. Delete them with `asr_preprocessor.py` (M7).

**The schema change this milestone needs, and who owns it (added 2026-09-14).** "An absent role is
an absent input" is not representable in the schema M5 landed: `src/argus/types/pipeline.py:142`
is `role: Literal["customer", "agent"]` — non-nullable, a faithful port of upstream's
`CleanTurn.role` (`:61`). Nothing in the plan mentioned `Turn`, and M5 is already flipped and
CONFIRMED, so the change had no owner. **This milestone owns it.** The port gains an explicit
absent state (nullable, or a third member — the shape is M2's to choose), and two consequences
follow that must be handled here rather than discovered later:

1. **It is a declared deviation from a CONFIRMED port.** The plan's own boundary rule is that a
   field the consumer re-derives is a field the contract failed to carry; this is the converse —
   the contract must be able to *say* "not established", which upstream's type cannot. The
   deviation is recorded in the Decision Log with its rationale, not left for the fidelity floor
   to flag as a drift.
2. **It interacts with 9022's floor.** `9022-contract-fidelity-checker` compares the port against
   upstream mechanically, and a deliberate divergence is indistinguishable from an accidental one
   unless a register says so. That plan needs an **intentional-deviation register** as part of its
   scope; this milestone is its first entry. (Filed on 9022 rather than solved here.)

`Acceptance Test:` `tests/test_io_import.py::test_no_role_re_derivation` — no module under
`src/argus/` computes an agent/customer role from transcript text (structural: no keyword list,
no role-detection prompt, no swap path). `tests/test_call_record.py::test_absent_role_defers` —
a call whose role is not established routes to a human rather than being scored.
`tests/test_schemas.py::test_absent_role_is_representable` — the port can express "not
established", and the deviation is registered as intentional rather than surfacing as drift.

**Contract.**
- *Deliverable:* Speaker attribution consumed from the call record; no re-derivation in the consumer.
- *Binding constraint:* I2's posture — an input nobody established is **absent**, not low. A fabricated role is the same class of defect as a fabricated score.
- *Acceptance property:* A correctly-role-labelled call is evaluated against the agent's utterances; a call without a role is routed to a human, and no code path can manufacture one.
- *Known evidence (advisory):* **0 of 718 archived calls carry `speaker_role`** — the corpus predates M9, and the re-run is gated on an archive backup that has not been made. **Consequence, recorded deliberately: until that run happens this milestone makes Argus produce no auto-final verdict at all — every call defers on absent role.** That is the honest state, not a regression to work around; a consumer that keeps its re-derivation to avoid it is keeping the tier violation.

### M3 — Retire the reliability chain (it is not a signal; the timestamps are not lost)

**Superseded 2026-09-14 — this milestone was "repair the ASR-reliability chain".** Two corrections
on contact with the code and with the producer:

1. **The timestamps are not lost.** `calls/*.json` carries `start_sec`/`end_sec` on every turn and
   every segment, on the original wall-clock axis (Q6a). What drops them is simbi's *internal*
   `Session` object — a type this plan does not import. There is nothing to repair on the record
   side; the call-record contract already carries time (M4 tests it).
2. **Path C is retired by decision, not repaired.** `fact_checker.py:33` reads `q.reliability`
   behind a `hasattr` guard that is always false, so the "low-reliability → human review" path has
   never fired. But reviving it would import a **fabricated** signal: `asr_quality` is two text
   regexes turned into a three-valued call-level grade, its consumers are display-level, and the
   recording-trust indicators that would measure the property are unproduced by human direction
   (Q6c). **`asr_quality`, `reliability`, `INCOMPLETE`, `ASR_ERROR` and path C are deleted, not
   ported.** The consequence of a garbled transcript is already caught structurally: its findings
   fail exact-quote verification, land in `ungrounded`, and route to a human (I2).

`Acceptance Test:` `tests/test_grounding.py::test_garbled_transcript_routes_ungrounded` — a
transcript whose quotes cannot be matched produces no auto-final verdict and no fabricated quality
number anywhere in the record.

**Contract.**
- *Deliverable:* No input-quality grade anywhere in the consumer; a bad transcript fails through the anchor gate.
- *Binding constraint:* I2 — an unanchorable finding routes to a human. A text-derived grade standing in for an unmeasured acoustic property is the defect, not the safety net.
- *Acceptance property:* Bad input changes routing through quote failure, never through a fabricated score or grade.
- *Known evidence (advisory):* `asr_quality` has zero effect on any score simbi has produced (its three consumers are a log line, a report field, and display). The repetition half of the phenomenon belongs to audio2tree's M11 (a per-turn 3-gram run-length measurement, in flight) — **Argus waits for that rather than building a second detector.** If an input-triage signal is ever wanted before the hunt pass, the named route is reviving one of Q6c's five indicators as a deliberate act — which would produce a measurement, not a grade. Both are optimisations; I2 catches the consequence regardless.

### M4 — B's first end-to-end test, and the call-record contract's conformance test

**Amended 2026-09-14 — promoted to the definition of the seam.** B has zero integration tests,
which is why M1's two crashes survived; it needs a fake LLM covering 14 call sites and a stub NLI,
since `transformers` cannot be installed in CI. That much is unchanged.

What is added: this test becomes **the call record's executable contract**. The seam between the
perception tier and the consumer currently has no runnable definition on either side — the record
schema exists, the consumer's reader does not, and the boundary was being described in prose in
two repositories. M4 makes it executable in the one place both sides can see it: a real call
record entering the pipeline and producing a report, with every field the consumer depends on
asserted present and typed.

`Acceptance Test:` `tests/test_e2e.py::test_transcript_to_report` — a real transcript from
`data/transcripts/` produces a complete report with no network access.
`::test_call_record_carries_the_consumer_contract` — the record the pipeline consumes carries
`speakers[].speaker_role` + `speaker_role_source` (M2), `start_sec`/`end_sec` on turns and
segments (M3), per-segment acoustic blocks aligned to spans, and per-call `stats`; each asserted
present, with the absent case exercised as a routing input rather than a crash. **Declared-empty
is a third state, not a failure:** 47 of the 718 archived records carry `turns: 0` and
`segments: 0`, so "present" means the field exists and holds a value *or* the record says it holds
nothing — a test that only accepts non-empty would fail on 6.5% of the corpus for the wrong reason.

**Contract.**
- *Deliverable:* An executable end-to-end test over a real transcript, with no network; and the runnable definition of what the consumer may depend on from the producer.
- *Binding constraint:* The verification floor — an externally observable property exercised against real data — plus the boundary rule this review established: a field the consumer re-derives is a field the contract failed to carry.
- *Acceptance property:* The pipeline runs from a real transcript file to a report, deterministically and offline; and every field the consumer reads is present in the record it was promised, or the run defers explicitly.
- *Known evidence (advisory):* B has no integration test, which is why M1's crashes survived. The NLI dependency may not be installable in every environment. **This milestone's baseline is also the reference M7 compares against after the move** — same input, same output.

### M5 — Port B's schemas into `types/`

B's `models/schemas.py` (25 Pydantic models) replaces 9020's stand-ins. The stage decomposition it
encodes — atoms to coverage to questions to verdicts, with `turn_id`/`doc_path` provenance — is
the contract everything else attaches to.

`Acceptance Test:` `tests/test_schemas.py::test_every_contract_roundtrips` — each schema constructs,
serializes and deserializes. `::test_m5_verdict_fields_never_enter_replay_hash` — I5 binds to the
port: `Verdict.score`/`confidence` are excluded from `core/replay.py`'s `_hashable()` allowlist,
the hash is invariant to a model-proposed number, and the liveness stand-in proves the allowlist
is consumed. (The section's originally sketched names — `test_all_schemas_roundtrip`,
`test_replay_payload_excludes_proposed_score` — were the pre-repair sketches; the six-round
verification record in `9021-relayer-argus-eval-pipeline-notes/M5.md` explains the renames.)


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

### M7 — Move B's proposal half into `io/` (import list redrawn along the architecture's seam)

**Amended 2026-09-14 — the original list was cut along B's module graph, and that graph is not the
architecture's seam.** B runs eight stages across four tiers; only the S2 half belongs to the
consumer. The list as first written — *"B's module graph splits close to the layer boundary, which
is why this is a move rather than a rewrite"* — chose the seam because it was cheap and then
justified it by its cheapness. It would have imported S0 ingest, audio2tree's routing decision and
intent interpretation with the model-calling code. The seam that matters is not where B's imports
separate; it is **does this stage decide something the tree already records.**

**Imported unchanged** (re-namespaced, behaviour identical): `llm_client`, `nli`, `prompts`, and
`fact_checker` **path A only** — plus `atomizer` and `question_generator` *once their arguments are
supplied from the sources named below*. `qa_agent` is imported **rewired, not unchanged** (below).

**Not imported, each with the owner named:**
- `asr_preprocessor`, `preprocessor` — S0 ingest; the producer's `calls/*.json` carries the
  structure, and M2/M3 consume it rather than recompute it
- `intent_inferrer` — **as a routing decision**. The call-level placement is audio2tree's D5
  protocol; `bottom_up` is written by exactly one mechanism, and a second decider is how one call
  acquires two intents. Its *within-call* output returns as the consumer's own proposal (below),
  never as a referent.
- `kb_context_builder`, `intent_retriever`, `knowledge/indexer.py` — retired in favour of M13's
  Provider. Both halves of B's "double knowledge base" are empty stubs (an empty `INTENTS/`
  directory, a 0-byte `rubrics.md`); these modules have never run against real input
- `fact_checker` path B — suspended until M13 gives it a real source; its evidence is
  unanchorable under I2 (M12)
- `asr_quality`, `reliability`, `INCOMPLETE`, `ASR_ERROR`, path C — deleted by decision (M3)

**The type-level data flow after the drop — the part the first revision of this list missed.**
Deleting a module deletes its *output type* as well, and the retained modules' signatures name
those types. This table is the executable form of the seam; the import list is not executable
without it.

| Argument type | Consumed by | Was produced by | **Produced by, after this milestone** |
|:---|:---|:---|:---|
| `Session` | `atomizer.atomize`, `atomizer.build_coverage_matrix`, `fact_checker.verify_all` | `preprocessor.build_session` (dropped) | **The consumer, from the call record** (M4's contract): turns, speakers, timestamps and spans already exist in `calls/*.json`. This is the legitimate fixture step, not a re-derivation. |
| `SessionKBContext` | `atomizer` (reads `.domain_knowledge_summary[:1500]` as prompt text), `question_generator` (7 sites), `fact_checker` | `kb_context_builder` + `intent_retriever` (dropped) | **The consumer, from M13's Provider**: `all_rubric_items`/`applicable_rubrics` from the compiled `_rubric/` nodes; the domain summary from the node's capsule and manifest. It goes into the proposer's prompt as **declared exposure** (patch 3's crutch — versioned, and disjoint from the measurement set) and is **never a grounding referent**. |
| `IntentInference` | `question_generator.generate_all` (serialized whole into the implied-question prompt) | `intent_inferrer` (dropped) | **The consumer's own S2 proposal step.** audio2tree ruled within-call intent its own decision and not the producer's ("nothing in the routing protocol speaks to it"), so this is not a duplicated authority — but its output is proposal material, quarantined with the rest of S2, and the *call-level* attribution still comes from the manifest rather than from it. The two display-only fields (`intent_switches`, `unresolved_intents`) are dropped. |
| `CleanTranscript` | nothing retained | `asr_preprocessor` (dropped) | Not needed — the call record replaces it. |

**`qa_agent` is rewired.** Its `run()` currently calls all five dropped modules by name
(`agents/qa_agent.py:53-56, 70-75, 88-92`) and its constructor instantiates them (`:24-28`), so
"moved verbatim" was wrong. The orchestrator's new wiring is: call record → consumer-built
`Session`; Provider → `SessionKBContext`; atoms; the proposer's own intent step; questions;
verification; score. It keeps its shape as the single entry point and loses its ingest stages.

Squashed import commit citing `simbiclaw/sim@0c2cccd` as the **base**, with the local repair
commits recorded alongside: the fixes are local-only and unpushed, and the citation must not imply
they are reachable upstream.

`Acceptance Test:` `tests/test_io_import.py::test_pipeline_runs_from_io` — the moved pipeline
produces the same output as M4's baseline on the same input, **with the arguments supplied from
the sources in the table above**.
`::test_no_producer_logic_in_io` — no imported module re-implements a producer's decision: no role
inference from transcript text, no call-level intent assignment, no knowledge-tree traversal, no
ASR text parsing. (The fifth prohibition — no rubric→question derivation from the flat table — is
**M15's**, because switching `question_generator`'s input from `config/rubric_items.py` to the
compiled nodes is that milestone's work; asserting it here would fail against code this milestone
legitimately imports.)

**Contract.**
- *Deliverable:* Every model-touching module that belongs to the consumer lives under `io/`.
- *Binding constraint:* I1 — model nondeterminism exists only in S2, which lives in `io/`. Plus the boundary this review established: **a module that re-decides what a producer decides is not the consumer's, wherever it sits** — sitting in `io/` violates no import direction, which is why M8's fences cannot express it (new item 8 carries the artifact).
- *Acceptance property:* The pipeline produces the same output after the move as before it; no module outside `io/` reaches a model; and no module inside `io/` re-decides something the tree already records.
- *Known evidence (advisory):* B's original eleven-module list spanned fourteen call sites across nine modules; the amended list names seven modules and the call-site count no longer describes it. Treat the file list above as binding and the count as historical.

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


**Amended 2026-09-14 — the dimension weights are missing, and they were specified all along.**
The formula is `(Empathy×3 + Resolution×3 + Procedure×2 + Proactive×1) ÷ 9`, stated verbatim in
`docs/PRD/eval/skills/evaluator/SKILL.md:221` and `:310`, and it was carried into this line's
design: the legacy v1 node format held the field (`_rubric/rules_criteria/c21-active-flexible-marketing.yaml:50`
still carries `dimension_weight: 1.0`), and patch-1's `AuthoredNode` schema **dropped it** with no
re-adding. **Neither codebase implements it** — simbi's `core/aggregator.py:66-69` and this
repository's shipped `core/score.py:241-242` both sum flat across dimensions, so every score
either has produced weights all dimensions equally. Per-item `deduction` is uniformly 1.0 (the
source rubric is 1/0/NA scored, with no per-item weight column), so the dimension multiplier is
the only weighting that exists.

This milestone therefore carries: `Rubric` gains a dimension-weight map, and `tally()` groups by
dimension before summing. The weights are read from the compiled rubric, never hardcoded (M22's
binding constraint). Their home is `_rubric/gates/{dimension}.yaml`, which gains `dimension_weight`
alongside `hard_fail_rule` — the co-location the authoring spec states at
`soft-criteria-authoring-spec-v4.html:603` (**citation corrected 2026-09-14**: earlier revisions cited
"§3.4", which does not exist, and then "§3.5", which is ResidueManifest). **That is a
compiled-output change: it requires a recompile and republish at a new epoch, and is a Tier C
decision recorded in Awaiting Steering.**

`Acceptance Test:` `tests/test_score.py::test_i3_determinism_canary` — identical inputs give
byte-identical `raw`. `::test_score_receives_no_history`. `::test_weight_comes_from_rubric_not_verdict`.
`::test_core_no_model_client`. `::test_dimension_weights_are_applied` — a call failing item(s) in a
3× dimension scores strictly lower than the same failures in the 1× dimension; the ÷9 normalisation
is asserted against the formula, and the weights are read from the compiled rubric, not a literal.
`::test_purity_assert_fires` — **the runtime purity assert, restored 2026-09-14.** Spec §2.5.3 says
the invariant is *"enforced twice, on purpose … the signature stops it going in; the gate catches it
if it somehow appears"*, and §8 M4's acceptance names the firing case explicitly. The shipped
`core/score.py:11-13` argues the runtime half away — *"a signature that cannot express one is the
cheaper version of the same check"* — which is a reasonable engineering preference and **not the
spec**. This milestone lands the assert: a confirmed finding carrying `cites_precedent=True` reaching
`score()` raises rather than scoring, and the test proves it fires by planting one. If the plan's
authority concludes the signature alone is sufficient, that is a spec deviation to record in the
Decision Log — not a change to make by leaving the test out.

**Contract.**
- *Deliverable:* A pure scoring function taking grounded facts and the rubric, with the dimension weighting the spec specifies actually applied.
- *Binding constraint:* I3 — `raw = score(facts, rubric)`, and `score` never receives history. I1 — `core/` imports no model client. M22 — no verdict-altering value lives as a hardcoded constant.
- *Acceptance property:* Identical grounded findings and rubric version produce an identical raw score; the rubric's weight reaches the arithmetic from `core/` rather than from inside the quarantine; and a failure in a 3× dimension counts three times a failure in the 1× dimension, as the formula says.
- *Known evidence (advisory):* B's aggregator is a report builder with no rubric parameter, and weight and veto are stamped inside modules bound for `io/`. This is a redesign, not a move. **The weighting gap is not B's alone — the shipped M10 has it too**, which is why this milestone's acceptance test names the dimension multiplier explicitly rather than leaving it to the redesign.

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

### M13 — Build `io/intents_provider.py` and the epoch reader (I4) — the sole read surface

**Amended 2026-09-14.** Read-only access to `INTENTS/` at a pinned git SHA from `EPOCH.yaml`, with
three category readers — and it is the **only** path by which anything under `src/argus/` reads the
tree. The three readers are not an implementation detail: they are the consumer's end of the
architecture's three epistemic classes (ADR-0001) — Versioned Rubric, Descriptive Facts,
Accumulated History — which is what B's two-bucket "double knowledge base" was a coarser
approximation of.

The Provider implements the read protocol `INTENTS/AGENTS.md` already specifies, which is
deterministic and by-id: confirm the call's L1/L2/L3 attribution from the manifests, read that
node's `intent_manifest.json` (`top_down`/`bottom_up`), read the `_rubric/` items for the cited
dimension, return `deferred` for signals on a node whose `source == "audio2tree"`, and treat an L2
with no Item as a routing label rather than a scored one. **Discovery is not this milestone's job:**
deciding which node a call belongs to is audio2tree's routing protocol (vectorised request, cosine
over L2 descriptions, 0.60 threshold) and it writes `bottom_up` alone. A second decider is how one
call acquires two intents.

**The evaluation record carries the attributed node (restored 2026-09-14).** The first revision of
this milestone deleted the original's *"record the model-selected KB path in the run manifest so
referent selection becomes replayable rather than re-guessed"* and replaced it with read-by-id —
correct about *how* the node is chosen, silent about *whether the choice is recorded*. Nothing now
records which L1/L2/L3 node a call was attributed to, and **532 of 718 calls sit in `_unassigned`**,
so that is not a corner case. The run manifest records the attributed node id (or its explicit
absence) for every evaluation: I4 pins *which revision* of the tree was read, and this records
*which node* was read from it — without both, two runs against the same epoch with different
attributions replay identically, which is the failure I5's hash exists to make detectable.

**The capsule parsing contract** (doc2graph's, one page, M13's reader implements it directly): a
leaf is `index.md` + `assets/` + optional `intent_manifest.json`; **`ui_steps.yaml` does not exist** (0 of 48 capsules carry one — the Flesh steps are embedded in `index.md`. **Discrepancy recorded 2026-09-14:** `INTENTS/PRODUCERS.md` — human-ratified 2026-08-18, and named by this plan as the producer-footprint authority — still lists `ui_steps.yaml` in doc2graph's footprint twice, in §1 and §2. This plan follows the tree, not the ledger, and records the divergence rather than silently overriding a declared authority)
— PRODUCERS.md's name is legacy, and the Flesh steps are embedded in `index.md` as one fenced JSON
block per routine after the `## Part 1: Bone` / `## Part 2: Flesh` sections; `ui_binding_ref` is
`<routine_id>#<step_order>`, and the Operation Manual's ordered-match sequence is a routine's
`step_instruction` values ascending by `step_order`. Read by id and pin the epoch; do not read
`.pipeline/`. Parent-capsule cascade loading and model-compressed summaries are **not** part of the
contract — capsules are authored per-leaf self-sufficient, and hierarchy is carried by the manifest
chain.

`Acceptance Test:` `tests/test_intents_provider.py::test_reads_at_pinned_epoch`.
`::test_no_write_path` — the provider exposes no mutating method.
`::test_s1_no_write_path_into_intents` — an AST scan confirms no `src/argus/` path opens an INTENTS
file for writing. This is 9002's M7 fixture, which was specified and never written.
`::test_sole_read_surface` — no module outside the Provider reads `INTENTS/` (structural).
`::test_capsule_parse_by_id` — a routine's step sequence resolves from `index.md` by id, with
`step_order` ascending, and no traversal by content.
`::test_audio2tree_source_defers` and `::test_manifest_without_item_is_routing_only` — the
protocol's two routing rules, which the plan previously did not implement.

**Contract.**
- *Deliverable:* Read-only access to INTENTS at a pinned epoch, implementing the documented read protocol, as the sole read surface.
- *Binding constraint:* I4 — pinned referents. D15 — no write path into INTENTS from `src/argus/`. **One reader, one epoch:** an unpinned second reader means part of an evaluation reads whatever the working tree says, which is an I4 hole rather than an untidiness.
- *Acceptance property:* Two runs against the same epoch reproduce the same grounding outcomes; no code path opens an INTENTS file for writing; and no module outside this Provider reads the tree.
- *Known evidence (advisory):* One tree, confirmed by inspection (Q7): `_rubric/` and the L1/L2/L3 business KB are co-located, so this is one provider, not two.

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


**Amended 2026-09-14 — the item count is settled, the `(*)` reading is not, and the diff re-points.**
The live tree settles the count: `_rubric/rules_criteria/` holds **25 item nodes, ids 1–5 and 8–27**;
items 6 and 7 are already excluded, so this plan's operational 25 and patch 3's ontology 25 are the
same 25. (Recorded where the contest lived, at Q14.) B's transcription remains lossy in at least two
places.

**`(*)` is undefined in the source and read two ways.** `docs/PRD/eval/rubric_com_hotline.md`
contains the marker exactly twice — on items 6 and 7 — with no legend anywhere in the document.
B reads it as weight 2.0 (`config/rubric_items.py:80-94`, comment `# (*) 项`); this line's
compiler reads it as data-dependency/deferred, and that reading has the content support: both
marked items are precisely the ones whose criteria need external systems (the service-record store;
the escalation workflow). Under either reading the shipped number is identical — 25 items at weight
1.0, total 25.0 — **because the only two weighted items are the two excluded ones.** The plan's
earlier "total weight 29.0 → 25.0" line was numerically correct and rhetorically misleading: it
presented the weights as load-bearing when they cancel.

**The diff re-points.** M15 was framed as diffing B's hand-assigned **weights** against the
compiler's; weights are uniform across the shipped set, so there is nothing to diff there. The
interesting divergence is **which items are excluded and on what grounds** — data-dependency versus
weight — and that is what this milestone's divergence record covers.

**The `question_generator` input switch lives here** — this is the "input changed" M7 refers to.
`core/question_generator.py:14` imports `RUBRIC_ITEMS, RUBRIC_BY_ID` from `config/rubric_items.py`
and `_rubric_driven` (`:53-96`) iterates `kb_context.applicable_rubrics`, which
`kb_context_builder.py:65` sets from that flat table. That is a second, model-mediated derivation
path from rubric to machine-checkable question, running in parallel with the compiler's
deterministic one — the two cannot even be checked for agreement. This milestone re-points the
read at `_rubric/` through M13's Provider: the questions come from the compiled nodes
(`signals[].description`, the `facets` split into programmatic and model_based), and the flat YAML
becomes compile input only, never a runtime source. The prohibition M7 defers here — *no
rubric→question derivation from the flat table* — is asserted in this milestone's tests.

`Acceptance Test (additions):` `tests/test_rubric_input.py::test_question_generator_reads_compiled_nodes`
— no module under `src/argus/` imports `config/rubric_items.py` or reads the flat table at
runtime; the generated questions resolve to compiled node ids.
`::test_no_second_rubric_path` — the compiled nodes are the only runtime source of
machine-checkable questions.

`Acceptance Test:` `tests/test_rubric_input.py::test_27_rows_parse_as_specific_rubric`.
`::test_items_6_and_7_are_permanently_inapplicable` — both carry a `data_dependency` and neither
reaches the denominator. `::test_25_items_scored` — asserted against the live node ids, and
**without encoding a per-item weight semantics**: the scored set is uniform at 1.0 and the
dimension multiplier lives in M10. `::test_no_empty_fail_standard`.
`::test_star_marker_divergence_recorded` — where B's transcription and the compiler disagree on the
`(*)` items, the disagreement is recorded as a finding rather than resolved by importing B's
reading.

**Contract.**
- *Deliverable:* The human rubric available as compiler input, with the `(*)` ambiguity recorded rather than silently resolved.
- *Binding constraint:* The rubric is a public artifact. Items excluded for data dependency are recorded with their reason, not deleted. **A contested reading in the source is a finding, not a value to import** — and the shipped arithmetic must not depend on which reading wins.
- *Acceptance property:* The scored set matches the operational scope, an excluded item never reaches the denominator, and the `(*)` divergence is visible in the record.
- *Known evidence (advisory):* The count is settled by the live tree (25, ids 1–5 and 8–27). B's transcription is lossy in at least two places. Do not let `test_25_items_scored` acquire weight semantics it does not have.

### M16 — Compile the rubric through 9003

Produce epoch-pinned `_rubric/` AuthoredNodes with the align map decided in Q3: item 22 to
Empathy & Tone, items 23–25 to Problem Resolution, item 26 to Empathy & Tone with its Problem
Resolution axis recorded as `within_dimension` residue, item 27 to Procedural Accuracy at the
compliance layer. Compiler output is diffed against B's hand-assigned weight and veto; divergences
are findings, not overrides.

**Where the output goes (declared 2026-09-14 — it was named nowhere).** §2 asserts that this
milestone *"emits them to a staging path and stops there"*, and neither the Contract nor the File
Scope said what that path is. It is **`build/rubric-staging/`** (repo-relative, gitignored, not
under `INTENTS/`): the compiled nodes are emitted there, and committing them into
`INTENTS/_rubric/rules_criteria/**` is an upstream write-time epoch act performed by the compiler
line or a human — never by this repository reaching into its own referent (D15, ADR-0003). The
path is a build artifact, so it must not be committed and must not be read by anything at runtime;
the plan's File Scope carries it as the one path this milestone writes.

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
- *Binding constraint:* D10 — auto-final requires both axes clear. **patch-1 D22** — the escape sampler splits into a random floor and a prioritized tranche, and the estimator consumes the **random tranche only** (the prioritized tranche is excluded from the escape-rate computation); that tranche respects its declared floor. **patch-1 I8** bounds what may reach routing at all.
- *Acceptance property:* A call carrying ungrounded findings never auto-finalises; a biased sample cannot reach the estimator; the floor holds whatever the prioritisation asks for.
- *Known evidence (advisory):* 9020 shipped the sampler with a floor test that must survive this reconciliation. **The floor has no declared value anywhere — declare one during execution and record its basis.**

### M19.5 — The §6 agreement instrument and `CriterionHealth` (added 2026-09-14)

**This milestone was missing entirely, and two shipped acceptance tests depended on it.** M19's
`test_auto_final_requires_both_axes` and M17's `test_corroboration_never_clears_criterion_below_tau`
both assert over a two-axis gate whose **criterion axis had no producer**. `core/divergence.py`'s
docstring defers the real detector to "9002 M5.5" — overturned — so the chain terminated in
nothing; the plan inherited the deferral without noticing that its addressee no longer existed.
The spec requires it in §8 M5 (*"Argus-vs-human κ store; τ gate; drift detector; per-call coverage
computation and the two-axis auto-final gate"*) and §8 M5.5 (*"Escape-rate sampler +
CriterionHealth"*), and §3.6 defines the type.

Land, in `core/` (pure computation) and `io/` (persistence):
- **`compute_kappa(argus_verdicts, human_verdicts)`** — Cohen's κ per criterion. Argus-vs-human,
  **never** Argus-vs-Argus (§6.4): the instrument measures agreement with the human label, and a
  second model sample is not a second opinion.
- **The τ gate** — a criterion at κ < τ is `untrusted`, and a finding resting on it defers with
  `criterion_below_tau`. τ defaults to 0.8.
- **`check_drift(criterion_id, windowed_kappas)`** — the falling-κ detector. This is the consumer
  `assess_drift` was written for; the two must be reconciled rather than allowed to coexist as two
  notions of drift.
- **`CriterionHealth`** — computation in `core/`, persistence in `io/`. `types/compiler_schemas.py`
  already declares the field as *"filled by rolling sample at runtime"*; this is what fills it.
- **Per-call coverage** — the fraction of the verdict resting on grounded findings (D10's first
  axis), computable per call, never a per-call *residue* gate (the hard prohibition).

`Acceptance Test:` `tests/test_agreement_instrument.py::test_kappa_is_argus_vs_human` — the
instrument takes a human-labelled sample and refuses a model-only one.
`::test_criterion_below_tau_defers` — κ < τ defers the finding and no corroboration clears it (D4).
`::test_falling_kappa_demotes` — drift moves the criterion's health, and only the κ pathway writes
health.
`::test_criterion_health_is_populated` — the CriterionHealth the two-axis gate reads has a
producer, asserted end to end rather than by construction.
`::test_coverage_is_per_call` — coverage is computable for a single call; nothing attempts a
per-call residue figure.

**Contract.**
- *Deliverable:* The agreement instrument, the τ gate, the drift detector and the criterion-health store — the producer of the two-axis gate's second axis.
- *Binding constraint:* §6.4 — agreement is Argus-vs-human, never model self-agreement. D10 — the two axes are orthogonal: corroboration clears `finding_thin` and never `criterion_below_tau`. D12 — resample variance measures difficulty, and never touches routing.
- *Acceptance property:* A criterion cited by a verdict has a health state produced from a human-labelled sample; an untrusted criterion defers regardless of how well corroborated the finding is; and drift demotes through κ alone.
- *Known evidence (advisory):* `core/divergence.py` already exists with a provisional detector and no consumer — reconcile rather than reimplement. 9020's escape sampler carries the floor; 9020's agreement seed is in `tests/test_agreement_seed.py` and `core/compiler/agreement.py` (9003's authoring-side κ, a **different** instrument at a different layer — do not conflate them).

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
- [ ] M2: Delete the role re-derivation; consume the producer's `speaker_role`  (amended 2026-09-14 — was "add a confidence floor")
- [ ] M3: Retire the reliability chain (not a signal; timestamps are not lost)  (amended 2026-09-14 — was "repair the chain")
- [ ] M4: B's first end-to-end test + the call-record contract's conformance test  (amended 2026-09-14)
- [x] M5: Port B's schemas into types/  (done 2026-09-14 16:40 PT; round-6 CONFIRMED at `3315bd6`)
- [ ] M6: Extend EvidenceItem to an I2 anchor slot  (created 2026-09-12)
- [ ] M7: Move B's proposal half into io/ — import list redrawn along the architecture's seam  (amended 2026-09-14)
- [ ] M8: Land the four forbidden import-linter contracts  (created 2026-09-12)
- [ ] M9: Repoint the I8 checker at the populated tree  (created 2026-09-12)
- [ ] M10: Extract score(facts, rubric) + apply the dimension weights  (amended 2026-09-14)
- [ ] M11: Re-litigate NEI scoring  (created 2026-09-12)
- [ ] M12: Build core/grounding.py (I2)  (created 2026-09-12)
- [ ] M13: Build io/intents_provider.py and the epoch reader (I4) — sole read surface  (amended 2026-09-14)
- [ ] M14: Fix the polarity-blind FAIL signal  (created 2026-09-12)
- [ ] M15: Land B's 27 items as SpecificRubric input — `(*)` divergence recorded  (amended 2026-09-14)
- [ ] M16: Compile the rubric through 9003  (created 2026-09-12)
- [ ] M17: Build core/corroboration.py (I6)  (created 2026-09-12)
- [ ] M18: Build core/adjust.py (S4b)  (created 2026-09-12)
- [ ] M19: Build core/route.py and reconcile the escape estimator (S5)  (created 2026-09-12)
- [ ] M19.5: The §6 agreement instrument and CriterionHealth  (added 2026-09-14 — was missing entirely; two tests depended on it)
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

### Decision: M5 close criteria — the Contract's stated property, with fidelity work spun out (steering, 2026-09-14)

**Rationale:** the human ruling, on the cloud session's explicit handoff of the question. Five
adversarial rounds produced a floor whose surviving defects were each the generalization of the
previous fix (the arc: hand-written tables → generated oracle → nine facts → perimeter → raw
callables + MRO), while the Contract's own second acceptance clause — *a proposed score cannot
enter the replay-bearing payload* — was green the whole time against the wrong artifact
(`test_replay_payload_still_excludes_proposed_score` exercises 9020's `proposer_diagnostics`
module, never `pipeline.py`; its docstring says so). That is the rounds-1-3 disease sitting in the
Contract's named test.

Resolved in three parts:
1. **M5's flip gates on the Contract's stated acceptance property, both clauses bound.** Clause 2
   is repaired by binding the port's model-produced fields (`Verdict.score`, `Verdict.confidence`)
   to `core/replay.py`'s `_hashable()` allowlist: the names exist on the port, appear nowhere in
   the hash's recursive keys, the hash is invariant to a model-proposed number riding along, and a
   stand-in allowlist that admits the field moves the hash (liveness). Rounds 4 and 5 are
   recorded as **REJECTED** verdicts with their defect lists below, per the cloud session's
   request that the arc survive in the record rather than as "eventually passed."
2. **Every round-4/5 fidelity fix is retained** in this plan's floor (aliases, constraints,
   model_config, validators, enum bases/order/aliases/methods, freshness and identity probes,
   exact class sets, namespace-smuggling audit, verified provenance, 21-row mutation sweep).
3. **The unfinished fidelity work moves to a successor plan** — `9022-contract-fidelity-checker`:
   raw callable + MRO-base facts with the defining-module filter dropped, the 25-row sweep, a
   shared sweep runner (the pyc-taint promotion: one way to run a sweep, not a convention
   paragraph), and — the part that makes it a plan rather than a round — a written threat model
   separating **drift** (what this floor catches) from **sabotage** (what an unbounded
   adversarial brief always finds, rounds 4-5 having demonstrated it). Five survivals of the same
   shape across distinct rounds is the promotion rule's trigger, and the successor is where the
   rule moves it.

**Confidence:** high that this closes M5 honestly — the Contract is the binding document, and for
the first time both its clauses will be tested against the artifact they name.

### M5 adversarial verification (round 6) — Verdict: CONFIRMED

Verified at SHA `3315bd6` (implementation: the round-4/5 acceptance floor plus the I5 binding
test, `tests/test_schemas.py` 26 passed pyc-disabled; 21-row sweep all red with target-naming
failures). Subagent B, cold-briefed under the bounded mandate: clause 1's coverage generated over
all 16 models; clause 2's binding test survived three attacks — nested evidence-level score
insertion, record-shape drift carrying real `Verdict` objects, traversal-completeness audit — and
the liveness stand-in was independently confirmed wired. No wrong-reason checks among the named
acceptance tests; B's three probes produced nothing to forward to 9022. Round verdicts for the
record: R1 REJECTED, R2 REJECTED, R3 REJECTED (cloud; hand-written tables, then generated oracle,
then freshness — each "a check that passes for a reason other than the property it names"), R4
REJECTED (#20 namespace smuggling, #21 enum behavior hooks, pyc-taint hazard), R5 REJECTED
(model-hook/MRO recording gap, attacker-writable module cut, plain mixins), R6 **CONFIRMED**
under the Q23 bounded mandate. Full defect lists: `9021-relayer-argus-eval-pipeline-notes/M5.md`.

### Decision: The import seam is drawn by ownership, not by B's module graph (2026-09-14)

**Rationale:** `Source:` the human's architecture review of 2026-09-14, run against
`docs/PRD/PMCA.txt` (the perception/memory/cognition/action mapping), spec v5's stage table, and
`INTENTS/PRODUCERS.md` §1 — each consulted after the seam had already been chosen by M7's original
text. B runs eight stages across four tiers (S0 ingest, audio2tree's routing, the rubric compiler's
derivation, the consumer's proposal-plus-derivation) and only the last is this repository's. The
original list would have imported `asr_preprocessor` and `preprocessor` — whose work is structural
transcription, which spec v5 assigns to S0, "Transformation tier — not this repo" — while §2 of
this same plan declared audio ingest out of scope — and the two statements sat four lines apart,
because nothing in this repository compares a plan's stated exclusions against its milestone
contents. That missing check is itself a finding, filed alongside the M5 pattern as promotable.
Four independent inputs converged: the plan's author (who wrote M7's seam and confirmed the error
was choosing the cheap boundary and justifying it by its cheapness), audio2tree, doc2graph and
soft-compiler, each ruling on its own rows and each ruling "obsolete" or "not mine". The new
criterion is stated once and used throughout: **does this stage decide something the tree already
records.**

**Confidence:** high — the boundary was checked four ways and every one of B's eight stages now has
a named owner. `Revisit:` M7's execution, if any imported module turns out to need something the
producers do not emit — which would be a producer gap to record, not a reason to import the
derivation.

### Decision: The `(*)` marker is contested in the source and neither reading ships as data (2026-09-14)

**Rationale:** `Source:` `docs/PRD/eval/rubric_com_hotline.md` — the marker appears exactly twice
(items 6 and 7) and the document defines it nowhere. B reads it as weight 2.0
(`config/rubric_items.py:80-94`); the compiler reads it as data-dependency, which the items'
content supports (both need external systems). Under either reading the shipped arithmetic is
identical — 25 items at 1.0, total 25.0 — because the only two weighted items are the two excluded
ones. The contested value never reaches a shipped number, so the plan neither adopts B's reading
nor silently discards it: it records the divergence (M15) and states that the shipped set does not
depend on the resolution.

**Confidence:** high on the arithmetic (recomputed from the live table under both readings);
`Confidence: low` on which reading the source sheet intended — `Revisit:` when someone can consult
the rubric's author, which is the only authority that can settle it.

### Decision: Dimension weights are specified, unimplemented on both sides, and belong in the compiled gate (2026-09-14)

**Rationale:** `Source:` `docs/PRD/eval/skills/evaluator/SKILL.md:221,310` states the formula
verbatim — `(Empathy×3 + Resolution×3 + Procedure×2 + Proactive×1) ÷ 9`; the legacy v1 node format
carried the field (`_rubric/rules_criteria/c21-active-flexible-marketing.yaml:50`,
`dimension_weight: 1.0`); and soft-compiler confirmed no dimension weight exists anywhere in the
current compiled tree (nodes carry no weight field, the four `gates/*.yaml` carry only
`hard_fail_rule`, the manifest carries none — re-verified against the current epoch). Meanwhile
`Source:` `simbiclaw/sim core/aggregator.py:66-69` and this repository's shipped
`src/argus/core/score.py:241-242` both sum flat across dimensions — **so every score either
codebase has produced weights all dimensions equally**, and the gap is not B's alone.

*On the field's history, corrected 2026-09-14 by adversarial verification:* an earlier revision of
this entry asserted that patch-1's `AuthoredNode` schema "dropped" the field. The companion
`soft-criteria-authoring-spec-v4-patch-1.md:181` says the opposite — `dimension_weight` was
**added** to `machine_criterion` by that patch's D10, and `:182` has `deduction_weight` becoming
*computed* as `dim_weight × confidence × gap_factor`. That same file contradicts itself later
(`:438` enumerates `machine_criterion` without the field), and the live tree carries it nowhere.
So the **observed gap is real and verified**; the **cause is unresolved**, and the "reverses the
direction patch-1 moved" argument below rested on the wrong half of an internally inconsistent
document. The decision stands on the co-location argument, not on that one.

Human ruling (2026-09-14): the weight is compiled into `_rubric/gates/{dimension}.yaml` alongside
`hard_fail_rule` — the location the authoring spec describes where a synthesized gate is *"stored
alongside the dimension's weight in the rubric table"* (§3.5; earlier revisions of this plan cited
"§3.4", which does not exist in that document). That is a compiled-output change → recompile and
republish at a new epoch (Tier C, Awaiting Steering).

**Confidence:** high on the specification and on the implementation gap (both verified in code);
`Confidence: medium` that the gate file is the better of the two candidate homes — the alternative
was re-adding the field to the node schema, rejected because it denormalises a dimension-level fact
across 25 nodes. `Revisit:` at recompile, if the gate file turns out not to be where the scorer
wants to read from.

### Decision: No input-quality signal in the consumer; the repetition phenomenon is the producer's (2026-09-14)

**Rationale:** `Source:` `simbiclaw/sim core/asr_preprocessor.py:68-76` — `asr_quality` is two text
regexes turned into a three-valued call-level grade (GOOD/FAIR/POOR from the ratio of
`reliability == "low"` turns), and its three consumers are a log line, a report field and a display
(`qa_agent.py:56`, `aggregator.py:108`, `cli.py:41`). The one place it was intended to affect a
verdict, path C, is dead behind a `hasattr` guard (`fact_checker.py:33`) — **so the grade has had
zero effect on any score simbi has produced.** audio2tree, consulted at the human's direction:
the conclusion is right but the reason must not be "the producer has no input-trust signal" —
`_is_incomplete`'s phenomenon is **M11's**, arriving as a per-turn 3-gram run-length *measurement*,
and Argus should wait for that rather than build a second detector. `_has_asr_error` is genuinely
unowned. Q6c's five recording-trust indicators stay defined-but-unproduced, so the route to a real
triage signal (a measurement, never a grade) stays named. The consequence of a garbled transcript
is already caught structurally: unanchored quotes → `ungrounded` → human (I2).

**Confidence:** high — the dead-code claim and the zero-effect claim are both verified in the
source; the sequencing claim (M11 owns it) is the producer's own.

## 6. Surprises & Discoveries

**The import seam was a module graph, and the module graph is not the architecture (2026-09-14).**
M7's original "Known evidence" line — *"B's module graph splits close to the layer boundary, which
is why this is a move rather than a rewrite"* — is the defect in one sentence: the seam was chosen
because it was cheap and then justified by its cheapness. Its import list would have carried S0
ingest, audio2tree's routing decision and intent interpretation into the consumer, while §2 four
lines above declared ingest out of scope. Four parties converged independently on the error; the
plan's own author confirmed it and named the missing artifact: **nothing in this repository checks a
plan's stated exclusions against its milestone contents.** A File Scope collision detector and four
import-linter fences exist; none of them reads a plan against itself.

**simbi's knowledge-base integration is two empty stubs (2026-09-14).** `data/knowledge_base/INTENTS/`
is an empty directory and `QA_RUBRICS/rubrics.md` is 0 bytes; `data/` holds only
`transcripts/sample.txt`. Every KB-consuming stage — Stage 0's context, Stage 5 path B's
fact-checking — has run against nothing, which is *why* path-B evidence is unanchorable (M12):
there was never a document to anchor to. This does not sink the plan's thesis, because B's S2 units
are fixture-tested (`tests/test_fact_checker.py` builds `MagicMock`/`AsyncMock` and inline
`KBContent`), which is how a quarantined stage should be tested. What it does retire is the KB
*readers*, which the amendment already retired.

**The "double knowledge base" is a superseded decomposition (2026-09-14).** B's two buckets are
business knowledge and rubric text. The architecture that supersedes them separates knowledge by
**epistemic class** (ADR-0001: Versioned Rubric / Descriptive Facts / Accumulated History) and by
**expertise type** (eight of them), because the class decides *which lane* a piece of knowledge
reaches — the raw lane, the adjust lane, or no lane — and the type decides where it lives and
whether it is embedded or referenced. Argus's three category readers are that separation at the
code level. B's model injects one undifferentiated context blob into every stage's prompt and lets
the model apply it, which makes the model the applier of knowledge — the thing S1–S5 exist to
prevent. The two-bucket split is recorded as history, not migrated.

**The dimension weights were specified, then dropped in a schema migration, then missed by both
implementations (2026-09-14).** The formula `(Empathy×3 + Resolution×3 + Procedure×2 + Proactive×1)
÷ 9` is stated verbatim in the evaluator skill; v1 nodes carried `dimension_weight`; patch-1's
`AuthoredNode` schema removed the field and nothing re-added it; and neither simbi's aggregator nor
this repository's shipped `core/score.py` groups by dimension before summing. So every score either
codebase has produced has weighted Empathy & Tone and Proactive Value equally. A three-week-old
field drop survived two reviews and a shipped milestone because no test asserts what the score
*should* be, only that it re-derives.

**`(*)` has no definition and two readings (2026-09-14).** The source rubric marks items 6 and 7
with a glyph it never defines. B read it as double weight; the compiler read it as data dependency.
Both agree on the affected items, and — because the only two weighted items are the two excluded
ones — both readings give the same shipped total. The plan's "29.0 → 25.0" line was numerically
right and rhetorically misleading, presenting a cancelling weight as load-bearing.

**The consumer's contract with the producers has no executable definition (2026-09-14).** Role
attribution (`speaker_role` — 0 of 718 calls carry it; the capability landed the same day, the
re-run is gated on an archive backup), intent placement (532 of 718 calls sit in `_unassigned`),
and the capsule read protocol (`ui_steps.yaml` does not exist; the Flesh steps are embedded in
`index.md`) were each being described in prose across two repositories with nothing that fails when
the descriptions diverge. M2, M4 and M13 now carry the executable form.

**My own first scan of the corpus was invalid (2026-09-14).** I read `speakers[].label` and
concluded the corpus carries no role information. `label` is the *stereo-per-channel* field and is
null on every mono call **by design** — a check pointed at it would keep reporting "no role
information" forever, including after the fix. The role lives in the parallel `speaker_role`/
`speaker_role_source`/`config.voiceprint` fields. The audio2tree session corrected this; the lesson
generalises to every probe in this repository: **ask what the field you are reading is for before
concluding from its silence.**

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

**The plan's path-B reason was wrong, and the real one is worse (M12, 2026-09-13).** The advisory
called upstream's path-B evidence "model-authored prose rather than a quotation". The prompt asks
for one: `models/prompts.py:328` requests `"key_evidence": "最关键的证据原文片段"` — the most critical
*verbatim source fragment*. What makes it unanchorable is narrower. The returned string is whatever
came out of `json.loads` (`core/fact_checker.py:98-99`) and nothing upstream checks it against a
source, unlike path A where the text is `turn.text` copied verbatim (`:66-72`). It is filed under
`kb_context.primary_intent_path` — `matched_paths[0]` (`knowledge/intent_retriever.py:110`) — while
the text the model read is every primary node concatenated (`:99-103`) and truncated to 3000
characters (`fact_checker.py:102`). So with more than one primary node, a *faithful* quote is
attributed to the wrong document. A plan that had been right about the cause would have suggested
"verify the quote against the doc"; the actual cause means there is no document to verify against.

**The correlated corroboration class already existed here (M17, 2026-09-13).** The advisory says it
"has no counterpart and must be invented". True of upstream — its aggregator sums `v.score *
v.weight` with no notion of where a verdict's error came from (`core/aggregator.py:52-56`) — but
9003 landed the class on the authoring side months ago: `core/compiler/classify.py:43-58`
classifies an exemplar/case match as correlated, and `core/compiler/agreement.py:36-46` already
holds `_W_C = 0.4` with the same provisional note. M17 invented the runtime aggregator, not the
class. The constant now lives in two places, deliberately — a 9003-compiler private is not a
runtime contract — and that is new debt for M22, whose binding constraint is that no
verdict-altering value lives as a hardcoded constant.

**The I8 checker was passing on a docstring (M9, 2026-09-13).** `test_divergence_is_the_only_
permitted_reader` asserted that `divergence.py` reads the proposed score. It does — but under the
parameter name `proposed`, which was never in `LOGIT_DERIVED`. The assertion was satisfied by the
module's *prose*, matched by a raw `"proposed_score" in code` substring scan. So the repo's
strongest existing artifact was reporting the right answer for the wrong reason, and
`severity = proposed` written inside the drift probe — the one module that legitimately holds the
quantity — would have passed clean. Two fixes: the reader test is now structural (identifiers,
string subscripts, `getattr`-style access, no prose), and `LOGIT_DERIVED` carries the names the
quantity is actually spelled with. Verified by planting `deduction = proposed_score` in a live
core module. This is the second time a check has been found to be satisfied by something other
than the property it names — the first was M5's hand-transcribed schema table. Both were fixed by
making the check derive its expectation instead of stating it.

**The escape floor was a parameter, never a commitment (M19, 2026-09-13).** 9020 shipped
`split_tranches(..., absolute_floor: int = 0)`, and every test passed its own number. So the floor
was enforced in four test bodies and in no call site, and the plan's own note — "the floor has no
declared value anywhere" — understated it: a default of zero means a caller who forgets gets no
floor and no warning. Declared at `ESCAPE_RATE_FLOOR = 60`, derived rather than chosen: the rule of
three against the 0.05 escape ceiling this repo already carries at `agreement.py:49`, so 3/0.05 =
60 is the smallest clean sample that distinguishes "below the ceiling" from "too few looks to
tell". The relation is asserted in the test, so changing either number alone fails.

**`compute_escape_rate` returned 0.0 for an empty sample (M19, 2026-09-13).** The most reassuring
number the function can produce, returned for having reviewed nobody. Latent because nothing called
it. An estimate and the absence of one now have different shapes.

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

**"INTENTS is a dangling symlink" was true of one environment, stated as if true of the repo
(2026-09-14, local session).** The Surprises entry above — and the docstring in
`src/argus/core/replay.py` — say INTENTS cannot be read. It dangles in every *fresh clone*; it
resolves on the local machine, where M13 and M16 are therefore executable. Recorded explicitly
rather than quietly fixed, because the dangling reading is currently steering other milestones'
estimates.

**M5's five-round adversarial arc (2026-09-12 → 2026-09-14).** Recorded here because each round's
survivors were the *generalization* of the previous round's fix, one altitude up — the most
valuable thing the milestone produced, kept in the record rather than summarized as "eventually
passed": R1-R3 (cloud) REJECTED — hand-written tables → generated oracle → freshness; every
rejection "a check that passes for a reason other than the property it names." R4 (local) REJECTED
— #20 namespace smuggling (re-export defeats the ownership filter and the exact-set test), #21
enum `_missing_` coercion, plus the pyc-taint hazard (same-second size-preserving mutations —
exactly constant edits, the mutations most worth running — defeat CPython's pyc validator; all
sweeps now pyc-disabled). R5 REJECTED — `model_post_init` unrecorded, the defining-module cut
attacker-writable, plain mixins invisible; terminal repair direction: raw callable + MRO facts,
filter dropped. R6 pending with a bounded brief. The full defect lists live in
`9021-relayer-argus-eval-pipeline-notes/M5.md`.

## 7. Awaiting Steering

**Q24: Recompile for the dimension weights — accept the compiled-output change?** (**Citation corrected twice, 2026-09-14:** this entry and the M10 amendment first cited "§3.4" of the authoring spec, which does not exist; the first correction replaced it with "§3.5", which is ResidueManifest. The co-location sentence is at `soft-criteria-authoring-spec-v4.html:603`. The substance is unchanged.) **Resolved
2026-09-14 (human ruling):** the weight is compiled into `_rubric/gates/{dimension}.yaml` alongside
`hard_fail_rule`; the compiler line recompiles and republishes at a new epoch. Tier C because a
compiled output changes on disk. Recorded here rather than in the Decision Log alone because the
recompile is an act by another line at a moment this plan does not control — M10's
`test_dimension_weights_are_applied` cannot pass until it lands. The alternative considered and
rejected: re-adding `dimension_weight` to the `AuthoredNode` schema (denormalises a dimension-level
fact across 25 nodes, and reverses the direction patch-1 moved). **Blocked by this entry:** M10's
weighted-scoring assertion only; the rest of M10 (extracting `score()` from B's report builder) is
unblocked.

**Q23: What does M5's flip gate on?** — Awaiting Steering: resolved 2026-09-14 (human ruling, on
the cloud session's handoff of the question). The Contract's stated acceptance property, both
clauses bound: clause 2 repaired by tying the port's `Verdict.score`/`confidence` to
`core/replay.py`'s `_hashable()` allowlist (the #22 defect — five rounds of fidelity hardening
while the stated clause tested a different module); rounds 4/5 fidelity fixes retained; the
unfinished sabotage-resistance work (raw callables + MRO facts, 25-row sweep, shared sweep
runner) moves to `9022-contract-fidelity-checker` with its threat model written down. Originally
blocked M5's flip. See the Decision Log entry of the same date for the full disposition.

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
dangles in every clone. **Answered by inspection, 2026-09-14 (earlier than M13 — the tree was mapped while writing M0-foundation fixtures): ONE tree.** Local `INTENTS` is a symlink to `/Users/prometheus/workspace/INTENTS`, holding `_rubric/` and the L1/L2/L3 business KB together; M13 is one provider, no scope increase.
dangles in every clone. Whether this repository's `_rubric/` subtree and B's L1/L2/L3 business KB
are one tree or two decides whether M13 is one provider or two. Default if not decided: attach and
inspect before M13 opens, treating the two-tree case as a scope increase rather than a surprise.

**Q8: One repository, or a package boundary?** — Awaiting Steering: resolved 2026-09-12. One
repository; B enters as a squashed import commit citing `simbiclaw/sim@0c2cccd`.

**Q9: Accept that fixing the role swap changes evaluation outputs?** — Awaiting Steering: resolved
2026-09-12. Yes — fix the heuristic and add a confidence floor. M2 owns it.
**Superseded 2026-09-14:** the ruling above answered "should we fix the heuristic?"; the review of
that date established the heuristic should not exist at all. M2 is a deletion
(`9023-b-repairs`), and this entry is retained as the record of what was decided before the
tier argument was made.

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
> the two counts are the same 25 and this warning is wrong. **Settled 2026-09-14 by listing the live
> node ids: 25 nodes, ids 1–5 and 8–27 — issue #16's report verifies and this warning is wrong on
> the live tree.**
>
> **Correction to the record of how it was closed (2026-09-14).** An earlier revision of this entry
> stated that the citation offered for issue #16's claim — `patch-1:194` as "25 (items 6,7
> excluded)" — *"does not verify in this tree: line 194 is a milestone-table row, and patch-1
> contains no mention of items 6 or 7 anywhere."* **That was my error, and it is exactly the
> collision this plan's Q13 exists to track: there are two files named patch-1.**
> `process-derivation-pipeline-spec-v5-patch-1.md:194` is the `N0` milestone-table row — what I
> read. `soft-criteria-authoring-spec-v4-patch-1.md:194` is `| **rules_criteria node** (per-item
> compilation) | **25 (items 6,7 excluded)** | **1 item → 1 node** |` — exactly what the citation
> said, in the other document. The citation was correct and the rebuttal was wrong.
>
> The tree evidence could not be checked from a clone where `INTENTS` dangles, and the instruction
> document.
>
> **Settled, 2026-09-14, by listing the live tree (the instruction this entry gives)** — the same
> result the citation pointed at all along. The two 25s coincide; the warning above is retained only
> as the record of what was contested. (M16 note that travels with it: item 9 and item 27 sit in
> Procedural Accuracy in the live tree — item 27 matching the Q3 compliance-layer routing.)

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

## 9. Archive note (2026-09-14)

**Status: split — superseded by seven focused plans.** The human's ruling: *"9021 计划过于庞大，
为避免失焦，对这个计划进行分拆，每个子计划都有且只有一个焦点"*. Nothing was cancelled; every
milestone this plan carried now lives in exactly one successor, with its text moved verbatim and
its Progress checkbox carried across:

| Successor | Focus | Milestones |
|---|---|---|
| `9023-b-repairs` | B runs, and is tested | M1–M4 |
| `9024-port-and-fences` | the port, the seam, the layer fences | M5 (done)–M9 |
| `9025-read-and-anchor` | the read surface and the grounding gate | M12, M13 |
| `9026-rubric-line` | 27 rows → epoch-pinned compiled nodes | M14–M16 |
| `9027-pure-arithmetic` | score, corroborate, adjust, replay | M10, M11, M17, M18, M21 |
| `9028-disposition` | routing, the two axes, the agreement instrument | M19, M19.5 |
| `9029-surface` | proposer demotion, CLI, config, record | M20, M22 |

**What stays here, and why this file is worth reading.** The shared record that no single successor
should carry seven times over: §2's architecture review and the seam criterion it established
(*does this stage decide something the tree already records?*); the complete Decision Log, including
the entries whose subject matter crosses plans; the full Surprises section, whose findings — the
empty knowledge base, the undocumented `(*)` marker, the missing dimension weights, the corpus that
predates its own fix — are shared context rather than any one plan's property; and the M5
verification record. Successors cite this file by number where they rely on a decision it holds.

**M5 is complete.** Six adversarial rounds, flip at `d1a975a`, verified at `3315bd6`; the
round-by-round record is in `9021-relayer-argus-eval-pipeline-notes/M5.md` beside this file. Its
fidelity floor lives on as `9022-contract-fidelity-checker`.

**Why split rather than continue.** The plan had grown to 23 milestones spanning four repositories'
worth of concerns — B's repairs, a schema port, a compiler line, four pure stages, a disposition
layer and a CLI. A milestone whose neighbours are unrelated is a milestone nobody can hold in mind,
and the recurring defect this plan produced (M5's six rounds; the import seam drawn along the wrong
boundary; a §6 milestone missing entirely) shares one shape: **nobody was looking at the whole**.
Splitting does not fix that by itself, but it makes each part small enough that someone can.
