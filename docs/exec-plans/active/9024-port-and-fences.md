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
- `tests/test_call_record.py` (new — M7's absent-role assertion, the call record's consumer-side conformance inherited from 9023's **M4**, and the arrival-side assertion for the role-type deviation. Declared by no plan's File Scope on either side of the split until 2026-09-14 — same class of gap as the two dependency paths that close this list.)
- `.importlinter` (modify — the four forbidden contracts)
- `docs/conventions/layering.md` (modify — Q16: amend so the convention and the lint agree)
- `tests/test_io_import.py`
- `tests/test_fences.py`
- `tests/test_evidence_anchor.py` (new)
- `tests/test_schemas.py` (modify — M6's anchor assertions, and the fidelity floor's comparison machinery, absorbed from 9022 on 2026-09-14)
- `scripts/build_schema_snapshot.py` (modify — the fidelity oracle; absorbed from 9022)
- `scripts/mutate_m5_contract.py` (modify — the mutation sweep; absorbed from 9022)
- `tests/fixtures/intentional_deviations.yaml` (new — **the register of deliberate divergences**, consumed by the comparison instead of failing on them. Its first entry is `VerdictResult.HUMAN_REVIEW`, retained against a B that deleted it — the register's first genuine use; the absent-role state it was originally reserved for was withdrawn by Q29. See the 2026-09-15 Decision Log entry)
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


### M6 — Extend evidence to an I2 anchor slot

**Reconciled 2026-09-15 against the landed implementation** (`src/argus/types/anchored.py`,
`tests/test_evidence_anchor.py` — 11 passing). The original text below was written before anyone
read M5's landed floor, and following it as written would break a CONFIRMED milestone. Three
corrections, each recorded where it happened rather than smoothed over:

1. **The anchor lives beside the port, not inside it.** The original said "add `span`, `quote`
   and `intents_sha`" to `EvidenceItem`. M5's snapshot test rejects any field upstream does not
   have — adding them there fails the floor, correctly. The landed design is a separate type,
   `types/anchored.py::AnchoredEvidence`, mirroring the ported `EvidenceItem`'s fields and adding
   the three I2 requires; `types/pipeline.py` is untouched, and a test asserts the boundary.
2. **The timestamp re-plumb is retracted.** The original said to re-plumb timestamps through
   stage 1. Stage-1 `Turn` carries no timestamps — and the deeper point is that a timestamp
   cannot satisfy exact-quote verification: seconds locate audio, I2 needs character offsets
   into the text that was read. The landed `Span` is a half-open character range; timestamps
   remain a different provenance axis and a different milestone's problem.
3. **The named acceptance tests exist under different names.** `test_span_roundtrip` is
   `test_the_anchor_survives_a_round_trip`; `test_ambiguous_span_rejected` became
   `test_a_repeated_quote_is_still_unambiguous` — the ambiguity is solved by *storing* the span
   rather than rejecting the record, because short turns repeat (`嗯` occurs twice in the
   fixture) and a stored span is exact where a search would guess. Both plus nine others pass.

The original text, kept as the record of what was written before the floor was read:

> Add `span`, `quote` and `intents_sha`. Re-plumb timestamps through stage 1 so spans are
> recoverable. Verified feasible: B's parser mutates turn text only with `.strip()`, and a
> round-trip on the sample transcript recovered 17/17 turns as exact substrings.
>
> `Acceptance Test:` `tests/test_evidence_anchor.py::test_span_roundtrip` — every evidence item
> recovers an exact character span from the raw transcript. `::test_ambiguous_span_rejected` — a
> turn text occurring twice fails rather than guessing.

`Acceptance Test (current names):` `tests/test_evidence_anchor.py::test_the_anchor_survives_a_round_trip`
— the anchor fields survive a JSON round-trip. `::test_a_resolving_quote_verifies` and
`::test_a_quote_that_does_not_match_its_span_fails` — exact-quote verification, green and red.
`::test_a_repeated_quote_is_still_unambiguous` — a twice-occurring turn text anchors precisely.
Eleven tests in the file; all pass.


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

**M7 also carries the call-record conformance test, inherited from 9023's M4 (2026-09-14).**
`tests/test_call_record.py::test_call_record_carries_the_consumer_contract` asserts that the record
the pipeline consumes carries `speakers[].speaker_role` + `speaker_role_source`, `start_sec`/
`end_sec` on turns and segments, per-segment acoustic blocks aligned to spans, and per-call `stats`
— each present, with the absent case exercised as a routing input rather than a crash.
**Declared-empty is a third state:** 47 of the 718 archived records carry `turns` and `segments` as
empty **lists**, so "present" means the field holds a value *or* the record says it holds nothing.
It is here because the subject is this plan's reader, not B's: B parses labelled transcript text,
and the records carry `turns[].speaker` as `S0`/`S1` with `speakers[].label` null and no
`speaker_role` on any of the 718 — so today the honest form of this test is that the record does
**not** carry a role and the consumer must defer, which is exactly what M7's absent-role state and
`test_absent_role_defers` establish from the other side.

**The role-type deviation is WITHDRAWN (2026-09-15, consequence of Q29).** The block below is the
deviation as planned on 2026-09-14, kept as the record. The human's Q29 ruling — *角色必须确立，
否则 Argus 不处理* — supersedes its premise: role establishment became an **input precondition**,
declined at intake by `argus.io.call_record` (`RolesNotEstablished`), so an unestablished role
never reaches the types at all. A port whose types never see an absent role cannot express one —
and does not need to. Consequences, all three consequences of the original block:

- `pipeline.py`'s `Turn.role` stays exactly upstream's `Literal["customer", "agent"]` — **the
  port's fidelity to upstream is preserved, no longer deliberately broken.**
- The consumer-side assertion is now `tests/test_call_record.py::test_unattributed_call_is_not_processed`
  (decline at intake), which replaces the planned "routes to a human rather than being scored".
- **The register's entry one is no longer the absent-role state — that entry was withdrawn with the
  deviation.** `tests/fixtures/intentional_deviations.yaml` still lands in this milestone, but for a
  different member: `VerdictResult.HUMAN_REVIEW`, retained against a B that deleted it. See the
  2026-09-15 Decision Log entry, "The fidelity target moves with B". The fidelity floor and the port
  no longer fight — which was the register's whole purpose — and the mechanism now has the genuine
  use it was built for rather than a bookkeeping one.

*The original block:*

> **M7 also carries the role-type deviation — the consumer must be able to say "not established."**
> This arrived split across plans and had no executable home (found 2026-09-14 by adversarial
> verification): `9023`'s M2 requires an absent-role state and names the acceptance test, but 9023's
> own out-of-scope excludes this repository and its File Scope lists only its plan file, while no
> milestone here performed the schema change this plan's File Scope already claimed. It belongs
> **here**, because the port is this plan's file and the change is a port property:
>
> - `src/argus/types/pipeline.py` is a faithful port of upstream's `CleanTurn.role`
>   (`Literal["customer", "agent"]`, `:61`/`:142`) — a type that cannot express "nobody established
>   this". The port gains an absent state (nullable, or a third member; the shape is M2's to choose,
>   recorded in 9023).
> - **The consumer-side consequence lives here:** a call whose role is absent routes to a human
>   rather than being scored.
> - **It is a declared deviation from upstream, and it must be registered.** This plan owns the
>   register (`tests/fixtures/intentional_deviations.yaml`), and this milestone's change is its
>   first entry.

**Also M7's, by the import list's own bindingness: B's aggregation logic is absorbed into
`io/qa_agent.py`, not ported as an eighth module.** B's `qa_agent` Stage 6 assembles the report
through its aggregator; the rewired orchestrator still has to produce that report (the M4-baseline
comparison is field-for-field), but `core/aggregator.py` is not on the seven-module list. The
aggregation is the proposal half's own score assembly — not a producer decision — so it moves as
private functions inside `io/qa_agent.py`, and later milestones replace it with `core/score` per
the two-stage contract. Porting it as a separate `io/aggregator.py` would require amending the
binding list; absorbing it requires nothing but a paragraph.

`Acceptance Test (this plan):` `tests/test_call_record.py::test_absent_role_defers` — a call whose
role is not established routes to a human rather than being scored.
`tests/test_call_record.py::test_call_record_carries_the_consumer_contract` — **inherited from
9023's M4** and now gated here rather than only described here: the record carries
`speakers[].speaker_role` + `speaker_role_source`, `start_sec`/`end_sec` on turns and segments,
per-segment acoustic blocks aligned to spans, and per-call `stats`; each asserted present, with the
absent case exercised as a routing input rather than a crash. Declared-empty is a third state — 47
of the 718 archived records carry `turns` and `segments` as empty **lists** — so "present" means the
field holds a value *or* the record says it holds nothing.
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
- [x] M6: Extend evidence to an I2 anchor slot  (done 2026-09-15 — round-1 CONFIRMED; reconciled 2026-09-15, implementation landed in types/anchored.py)
- [ ] M7: Move B's proposal half into io/ — import list redrawn along the architecture's seam  (amended 2026-09-14)
- [ ] M8: Land the four forbidden import-linter contracts  (created 2026-09-12)
- [ ] M9: Repoint the I8 checker at the populated tree  (created 2026-09-12)

## 5. Decision Log

### M6 adversarial verification

**Verdict: CONFIRMED** — round 1, no rejection-grade finding.

**The attacks the round ran, and what they found:**

- *Unresolvable evidence passing:* no path. `resolve_quote` returns only after equality with the
  exact span slice; mismatch raises, out-of-bounds raises, NFC-vs-NFD normalised quotes raise,
  negative-index wraparound is impossible (`start >= 0` enforced), empty and 1-char transcripts
  raise.
- *Decoration check:* `resolve_quote` is consumed — `core/grounding.py:75` imports and `:211`
  calls it (deliberately discarding the return: "run rather than trusted"); `Span` feeds
  `core/corroboration.py:90`; `SHA_RE` feeds `core/replay.py:58`. Signature changes break at
  import/call time.
- *Nine mutations:* eight killed by named acceptance tests. The ninth — dropping `Span`'s own
  `frozen=True` — was caught by **nothing** (the existing freeze test mutates through the
  parent). Closed in the flip bundle with `test_span_itself_is_frozen`; the mutation fails closed
  regardless, but the docstring's adjective is now asserted where it is claimed.
- *Pydantic bypass probes:* `model_copy(update=...)` skips validation and `object.__setattr__`
   pierces `frozen` — see §6.
- *Multi-byte:* length validation and slicing are both code-point based; no encode/decode path
  exists in the module; astral characters survive JSON round-trip with spans intact.
- *Suite:* `test_evidence_anchor.py` 11/11 at verification (12 after the flip-bundle test), full
  `tests/` 480 passed / 3 skipped / 4 failed, and all four failures fail identically at the
  pre-M6-landing commit `a03c56b` — pre-existing, not regressions. Tier-1 floor: exactly the
  three known failures, 192 passed.

### Decision: The import list is cut by ownership, not by B's module graph (2026-09-14)

**Rationale:** `Source:` the archived plan's entry of the same name — four independent inputs (the
plan's own author, audio2tree, doc2graph, soft-compiler) converged on the finding that M7's original
seam was chosen for being cheap. The type-level data-flow table in M7 is the executable form; the
prose list alone is not executable, as adversarial verification established.

**Confidence:** high on the criterion; the surviving risk is a *producer gap* (something a retained
module needs that no producer emits) — record it, do not import the derivation.

### Decision: The fidelity target moves with B — and the register's first entry is what stays behind (2026-09-15)

**Rationale:** `Source:` M7's execution, where the port could not satisfy M5's snapshot and M7's golden at once. M5's floor was built against `0c2cccd`; M7's golden was captured from B at HEAD `929d5a7`, where 9023 M3 deleted `asr_quality_warning`, `role_swap_detected`, `ASRQuality`, `TurnFlag`, `reliability` and `flags`. A port that recreates the deleted fields to satisfy the old floor would be faithful to a revision B has moved past — and the field it recreates is exactly the one 9023 retired *for being fabricated*. So **the pin moves to `929d5a7`**: the snapshot is regenerated against today's B, and `pipeline.py` aligns to it. Fidelity means faithful to the current upstream, not to the one the floor happened to be built on.

**One member stays, and it is the register's entry one (the mechanism's first real use).**
`VerdictResult.HUMAN_REVIEW` is absent from today's B — 9023 deleted its only producer with the reliability chain — but it is **not** the class of thing 9023 retired. What 9023 retired were fabricated *measurements* (a quality grade guessed from text). `HUMAN_REVIEW` is a *disposition outcome*, spec §3.4 carries the same concept as `meta_verdict: "escalate"`, and Argus's own `core/score.py` already uses it as a key in `_CREDIT` and `_DEFERRALS`. Deleting it would break `score.py` at import and two tests belonging to 9027, a plan that has not begun — recreating in 9027 exactly the divergence 9030 exists to reconcile. So it is retained, and the retention is **signed**: `tests/fixtures/intentional_deviations.yaml` gains its first entry naming the authorising ruling, and the comparator consults the register before failing. One direction only — a registered member may be *extra*; a member the snapshot has and the port lacks is always a failure.

**Why this is the register's first use and not a loophole.** The register was designed (9022, absorbed here) to be deliberately awkward: an entry must name the decision that authorised it, so suppressing a divergence is an act someone signs, never a silence. This entry is the first thing that genuinely needed one — an intentional difference with an authorising ruling — and the mechanism behaves as designed. `HUMAN_REVIEW`'s long-term fate (retain, rename to spec-native `escalate`, or fold into a wider deferral-model revision) stays open and is 9027's to decide with the spec in hand; the register entry names that revisit so it cannot be forgotten.

**Confidence:** high on the pin move — the alternative recreates a field 9023 retired for cause. `Confidence: medium` on retaining `HUMAN_REVIEW` rather than renaming it now: the rename is cleaner long-term but would touch 9027's files, and doing another plan's work to make one's own test green is the trade this plan has refused everywhere else. `Revisit:` when 9027's Plan phase opens.

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

**Pydantic's invariants are constructor-only, and that is fine here — but say it out loud
(2026-09-15, from M6's verification).** `model_copy(update=...)` skips every validator, and
`object.__setattr__` mutates a `frozen` model in place: both produce an `AnchoredEvidence` whose
`intents_sha` fails the 40-hex check or whose quote no longer matches its span. Nothing downstream
re-checks the *format* — but every axis that routes (quote-vs-transcript, epoch equality,
provenance) is re-verified by M12's gate at run time, so a forged record fails closed. The
general lesson for every frozen type this plan lands: **the type's checks are a constructor
contract, not a runtime guarantee; whatever the gate must re-verify, name it.**

**XOR is enforced at the gate, not the type (2026-09-15).** `AnchoredEvidence`'s docstring says
`turn_id` XOR `doc_path`, but both-set and both-None are accepted at construction;
`core/grounding.py` enforces the stricter half at gate time. Deliberate layering — the type
accepts, the gate disposes — but the docstring's "XOR" overstates what the type does.


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

**Q29: What does Argus do with a call whose speaker roles were never established?**
— **Awaiting Steering: resolved 2026-09-15, human ruling.** **角色必须确立，否则 Argus 不处理.**
Role establishment is an **input precondition, not a routing outcome**: a call record whose
`speakers[].speaker_role` is unestablished is declined at intake — rejected before evaluation, the
same disposition as a malformed record (9021 M1's intake contract). Argus produces no evaluation,
no score, no grade, and no "routed to human" verdict for it. Two consequences M7 carries:

1. **The absent-role state exists to be *recognised and declined*, not scored-around.** The port
   gains the absent state so the consumer can detect "nobody established this" — and the handler
   for that state is decline-at-intake.
2. **`test_absent_role_defers`'s name is historical** (inherited from 9023's M2, where the
   disposition was still phrased as a deferral). When M7 writes the test, the assertion is "not
   processed", and the name should say so. Q28 in 9023 records the same ruling from the
   completed plan's side.

**Q30: When does real corpus data reach M7's consumer-side tests?**
— **Awaiting Steering: resolved 2026-09-15, human assignment.** The speaker_role re-run over the
718 records (9008 M9's pass) and its archive-backup prerequisite are assigned to the **audio2tree
line**; the assignment was delivered to the 9008 session on 2026-09-15. Until it lands, 0/718
records carry a role — so M7's consumer-side assertions run on synthetic records carrying the
field, plus the decline path exercised on records that lack it. Real-data conformance waits for
the re-run and is 9024 M7's or M4-inheritance's to pick up when it lands.

**Updated 2026-09-15, same day — the re-run is gated, not scheduled.** The 9008 session reported
back (correctly asking for the ruling's anchor before acting; `2b36eed` was provided): **M13
carries three open, independently-falsified defects** — segment backfill manufactures roles,
ties resolved by the complement erase 39 numbered under-segmentation signals, and the
`between_turn_pauses` schema invariant breaks on 176/671 calls. Running the pass now would write
wrong roles into the corpus, which Q29's ruling then mass-rejects at intake. Agreed disposition,
both sides: **the archive backup proceeds now** (safe, an independent prerequisite; Argus never
reads the backup); **the re-run gates on M13's CONFIRMED.** M7's consumer-side tests stay on
synthetic records plus the decline path until the re-run lands.

**Updated 2026-09-15, later — the human revised both halves (relayed by 9008).** **(1) No backup.**
The ruling's reasoning: *「只要不重跑，就没人重跑」* — the backup protected the corpus against the
re-run, and the re-run is no longer scheduled. **(2) The re-run itself is deferred; roles are
derived in place.** The Q8 rationale for re-running (*"role identification … needs the audio, and
the audio is not retained"*) belonged to the voiceprint route; role determination is now
text-based, so after M13 CONFIRMS, `speaker_role` (and `normalized_text`) can be derived on the
existing archive **without any re-run** — only the 159 calls over 380s that were never transcribed
need one. 9008 records the accepted cost: the archive is gitignored and single-copy, in-place
derivation is its first write, and the pass only adds fields plus recomputes two derived blocks
(`turns[]`, `between_turn_pauses`), both recomputable from `segments[]` — which the contract
forbids touching. **Net for M7: unchanged wait, shorter wait** — real role-labelled corpus arrives
when M13 confirms, no backup or full re-run in between. Q25's backup item on 9023's side is
withdrawn by the same ruling.


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
