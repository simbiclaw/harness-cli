# 9024 — The Port: Schemas, Proposal Half, and the Four Fences

## 1. Purpose

Argus stops being built from scratch: B's data contracts and its model-calling modules move into
`src/argus/`, where the quarantine becomes a directory rather than a promise. This plan carries the
move, the layer fences that make it real, and the call-record contract that draws the line between
what the producer decides and what the consumer derives. It inherits one finished milestone (M5,
the schema port) and completes the rest.

## 2. Big Picture

**The seam criterion**, established by the architecture review of 2026-09-14 and used throughout
this family: *does this stage decide something the tree already records?* A module that re-decides
what a producer decides is not the consumer's, wherever it sits — `asr_preprocessor`'s role
inference, `intent_inferrer`'s routing, `kb_context_builder`'s knowledge assembly and
`intent_retriever`'s traversal all fail that test and are not imported. The first revision of the
plan cut along B's module graph instead, because it was cheap, and then justified the cut by its
cheapness; §2 of the archive records that finding.

The port is not only a move of modules: deleting a module deletes its **output type**, and the
retained modules' signatures name those types. M7 carries the type-level data-flow table that makes
the import list executable — `Session` from the call record, `SessionKBContext` from the read
surface (9025) as declared exposure, `IntentInference` as the consumer's own quarantine-side
proposal.

**Depends on:** 9023 (B must run and be tested before any of it is imported).

**Layer fences** (M8) are what makes the quarantine real rather than asserted: four `forbidden`
import-linter contracts, each proved by a planted violation. **M9** repoints the I8 provenance
checker at the now-populated tree — the repository's strongest existing artifact, which until now
scanned an empty directory.

**Inherited:** M5 is complete (CONFIRMED 2026-09-14, six adversarial rounds; the round-by-round
record is `docs/exec-plans/archived/9021-relayer-argus-eval-pipeline-notes/M5.md`). Its fidelity
floor is **this plan's**: `9022-contract-fidelity-checker` was absorbed here on 2026-09-14 (the
human's ruling — it had never been executed, half of it hardened a floor that already stands, and
its register was needed by this plan's own port change). Its files, its register and the pyc-taint
hazard it carried came with it, and there is no longer a second plan to negotiate
`tests/test_schemas.py` with.

**File Scope:**
- `docs/exec-plans/active/9024-port-and-fences.md` (this plan)
- `src/argus/types/pipeline.py` (modify — M6's anchor slot, and M2's nullable-role deviation)
- `src/argus/types/anchored.py`
- `src/argus/types/proposer_diagnostics.py` (modify)
- `src/argus/io/proposer.py`
- `src/argus/io/atomizer.py`
- `src/argus/io/question_generator.py`
- `src/argus/io/fact_checker.py`
- `src/argus/io/llm_client.py`
- `src/argus/io/nli.py`
- `src/argus/io/prompts.py`
- `src/argus/io/qa_agent.py` (new — the imported proposal half, re-namespaced)
- `src/argus/io/call_record.py` (new — the consumer's half of the seam: builds `Session` from the producer's `calls/*.json` per M7's data-flow table. The archive covered this path with its `src/argus/io/**` glob; the split enumerated files and the glob's coverage was lost with it.)
- `tests/test_call_record.py` (new — M7's absent-role assertion, and the call record's consumer-side conformance. Named as an acceptance test by the archive's M2 and by 9023's M2, and declared by no plan's File Scope on either side of the split — same class of gap as the two dependency paths that close this list.)
- `.importlinter` (modify — the four forbidden contracts)
- `docs/conventions/layering.md` (modify — Q16: amend so the convention and the lint agree)
- `tests/test_io_import.py`
- `tests/test_fences.py`
- `tests/test_evidence_anchor.py` (new)
- `tests/test_schemas.py` (modify — M6's anchor assertions, and the fidelity floor's comparison machinery, absorbed from 9022 on 2026-09-14)
- `scripts/build_schema_snapshot.py` (modify — the fidelity oracle; absorbed from 9022)
- `scripts/mutate_m5_contract.py` (modify — the mutation sweep; absorbed from 9022)
- `tests/fixtures/intentional_deviations.yaml` (new — **the register of deliberate divergences**, consumed by the comparison instead of failing on them; this plan lands it, and its first entry is M7's absent-role state)
- `tests/test_i8_provenance_separation.py` (modify — widen the live scan)
- `pyproject.toml` (modify — dependency changes; the archive declared this path and the split dropped it from every successor until 2026-09-14)
- `docs/decisions/dep-vet-transformers.md` (new — `nli` is imported unchanged and B's `utils/nli.py` imports `transformers`, which is not yet a declared dependency of this repository; deps-and-secrets requires a dep-vet record before the install is allowed)

## 3. Milestones

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
(`agents/qa_agent.py:53, :70, :91` by correct name, and `:66` under the unassigned
`self.kb_builder` M1 repairs; `intent_retriever` is commented out and `indexer` is absent), and its
constructor instantiates them at `:27-38`, so "moved verbatim" was wrong. **Line numbers corrected
2026-09-14** — the first revision's citations were approximate. The orchestrator's new wiring is:
call record → consumer-built `Session`; Provider → `SessionKBContext`; atoms; the proposer's own
intent step; questions;
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

**M7 also carries the role-type deviation — the consumer must be able to say "not established."**
This arrived split across plans and had no executable home (found 2026-09-14 by adversarial
verification): `9023`'s M2 requires an absent-role state and names the acceptance test, but 9023's
own out-of-scope excludes this repository and its File Scope lists only its plan file, while no
milestone here performed the schema change this plan's File Scope already claimed. It belongs
**here**, because the port is this plan's file and the change is a port property:

- `src/argus/types/pipeline.py` is a faithful port of upstream's `CleanTurn.role`
  (`Literal["customer", "agent"]`, `:61`/`:142`) — a type that cannot express "nobody established
  this". The port gains an absent state (nullable, or a third member; the shape is M2's to choose,
  recorded in 9023).
- **The consumer-side consequence lives here:** a call whose role is absent routes to a human
  rather than being scored. That is this plan's assertion, tested here, because 9023 cannot test
  this repository's code.
- **It is a declared deviation from upstream, and it must be registered.** The fidelity floor
  compares the port against upstream mechanically and cannot distinguish a deliberate deviation
  from an accidental drift without a register. **This plan owns that register now** (File Scope,
  `tests/fixtures/intentional_deviations.yaml`), and this milestone's change is its first entry.
  The register is deliberately awkward to add to: an entry must name the decision that authorised
  it, so suppressing a divergence is an act someone signs, never a silence.

`Acceptance Test (this plan):` `tests/test_call_record.py::test_absent_role_defers` — a call whose
role is not established routes to a human rather than being scored.
`tests/test_schemas.py::test_absent_role_is_representable` — the port expresses "not established",
and the deviation is listed in this plan's register rather than surfacing as drift.

**Sequencing within the family, stated because this plan's M7 acceptance names sources later plans
build:** `Session` comes from the call record (9023's M4 defines it), `SessionKBContext` from
9025's Provider, and the compiled rubric from 9026. M7 asserts the import and the fences with those
sources stubbed; each source's own plan closes the loop with its own acceptance test. The
dependency is declared rather than circular: this plan depends on 9023, and 9025 depends on this
one.

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


## 4. Progress

- [x] M5: Port B's schemas into types/  (done 2026-09-14 16:40 PT; round-6 CONFIRMED at `3315bd6`)
- [ ] M6: Extend EvidenceItem to an I2 anchor slot  (created 2026-09-12)
- [ ] M7: Move B's proposal half into io/ — import list redrawn along the architecture's seam  (amended 2026-09-14)
- [ ] M8: Land the four forbidden import-linter contracts  (created 2026-09-12)
- [ ] M9: Repoint the I8 checker at the populated tree  (created 2026-09-12)

## 5. Decision Log

### Decision: The import list is cut by ownership, not by B's module graph (2026-09-14)

**Rationale:** `Source:` the archived plan's entry of the same name — four independent inputs (the
plan's own author, audio2tree, doc2graph, soft-compiler) converged on the finding that M7's original
seam was chosen for being cheap. The type-level data-flow table in M7 is the executable form; the
prose list alone is not executable, as adversarial verification established.

**Confidence:** high on the criterion; the surviving risk is a *producer gap* (something a retained
module needs that no producer emits) — record it, do not import the derivation.

### Decision: The intentional-deviation register lives here, with the port it deviates from (2026-09-14)

**Rationale:** `Source:` M2's nullable-role requirement (see 9023) — the consumer must be able to
say "not established", and upstream's `CleanTurn.role` cannot. The fidelity floor compares the port
against upstream mechanically and cannot tell a deliberate deviation from an accidental drift
without a register. **Updated 2026-09-14:** the register was first filed on
`9022-contract-fidelity-checker`; the human absorbed that plan into this one on the same day,
because the plan that introduces the deviation is the plan that must register it, and the file
consuming the register (`tests/test_schemas.py`) was already this plan's. This plan's schema change
is entry one.

**Confidence:** high — without the register the fidelity floor and the deviation will fight.

### Decision: M5's close criteria (Q23, human ruling 2026-09-14)

**Rationale:** `Source:` the archived plan's Q23 entry — M5 gates on its **Contract's** stated
acceptance property, both clauses bound, with the fidelity work spun out to 9022 rather than
carried. That ruling is why this plan exists in its current shape.

**Confidence:** high; the six-round verification record is the evidence.

## 6. Surprises & Discoveries

**The pyc-taint hazard arrives with the sweep (2026-09-14, absorbed from 9022).** Any sweep that
mutates a source file and re-runs must purge `__pycache__` and set `PYTHONDONTWRITEBYTECODE=1`.
CPython validates a cached `.pyc` on source mtime **and size**, so a mutation that preserves byte
length within the same second is served from the stale cache and the sweep reports green on a
mutation it never applied — and constant-value mutations (`= 0` → `= 1` in a validator) are exactly
that class. The cloud session reproduced it independently on issue #19. `scripts/mutate_m5_contract.py`
already carries the standing rule; whoever next runs a sweep through it inherits it rather than
rediscovering it.

**The old list was executable and wrong; the new list was correct and not executable (2026-09-14).**
Adversarial verification's one-sentence verdict on the first amendment. Every retained module takes
an argument only a dropped module produced — `qa_agent.run()` calls all five by name. The lesson
generalises: **a module-level import list is not a contract; the type-level flow is.** Recorded
because the same mistake is available to anyone who edits an import list by reading filenames.

## 7. Awaiting Steering

**Q16: Does `core/` stop importing `io/`?** — **Awaiting Steering: resolved 2026-09-12.** Forbid
`core → io`; M8 lands the four forbidden contracts with `include_external_packages = True` and
amends `docs/conventions/layering.md` in the same milestone, so convention and lint agree.

*Restored 2026-09-14.* The phrase "Awaiting Steering: resolved" is load-bearing, not decoration:
`.claude/hooks/pre_tool_use.py` grants access to a path in `.claude/sensitive-paths.txt` only when
an **active** plan contains that literal string *and* names the path. The parent carried it and the
split paraphrased the decision without it; the parent then archived out of the hook's scan set, so
M8's edit to `.importlinter` was silently converted from an authorised change into a blocked one.
The text above is the parent's own wording, restored.

## 8. Outcomes & Retrospective

*Written at completion or cancellation.*
