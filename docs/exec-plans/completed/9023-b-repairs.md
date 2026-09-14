# 9023 — B's Repairs

## 1. Purpose

B (`simbiclaw/sim`) is the working Chinese-language QA evaluator this architecture is built on, and
it has never run end to end: two crashes sit on its happy path, and its role heuristic inverts
correctly-labelled transcripts. Nothing can be imported from a pipeline that does not execute.
This plan fixes B's defects **in place**, in B's own repository, and gives it the integration test
it has never had — so that each repair lands in its own reviewable diff rather than inside the
large move that follows.

## 2. Big Picture

The work executes in `simbiclaw/sim`, not in this repository. That is deliberate and is the whole
point of the split: when the repairs are mixed into the import commit, a reviewer cannot tell a
behaviour change from a re-namespace. B is also where these defects *matter* — every downstream
consumer of the call record inherits them.

**Constraint, from the human (2026-09-14):** B's repository is edited **locally only**, committed
locally, never pushed. The fixes are real but unpushed, so any import commit that cites
`simbiclaw/sim@0c2cccd` must record that its base is that commit *plus local repairs* and must not
imply the repairs are reachable upstream.

Out of scope: everything in this repository, **with two exceptions**, both of which exist because
this plan's code lives in B's repository and cannot test `src/argus/`:

- **M2's absent-role state.** M2 owns the *decision* (nullable, or a third member) and records it
  here; the two acceptance tests that assert it —
  `tests/test_call_record.py::test_absent_role_defers` and
  `tests/test_schemas.py::test_absent_role_is_representable` — execute **in
  `9024-port-and-fences`**, which owns the port and can run them.
- **M3's garbled-transcript consequence.**
  `tests/test_grounding.py::test_garbled_transcript_routes_ungrounded` executes **in
  `9025-read-and-anchor`**, which owns the grounding gate the assertion exercises. **Added
  2026-09-14:** adversarial verification found this test named here and homed nowhere — this plan
  disclaims the repository it lives in, and 9025 did not name it — which is the same defect, in
  the same section, as the M2 exception above.
- **M4's call-record conformance.**
  `tests/test_call_record.py::test_call_record_carries_the_consumer_contract` executes **in
  `9024-port-and-fences`**, which owns the consumer's reader. **Added 2026-09-14:** the test was
  named here on the premise that B could consume a call record. It cannot — B's parser takes
  labelled transcript text, and the records carry anonymous diarization labels with no role — so
  the premise was wrong rather than the test. See M4.

Splitting either any other way leaves the change claimed by a plan with no milestone for it, which
is the state adversarial verification found on 2026-09-14.

**File Scope:**
- `docs/exec-plans/active/9023-b-repairs.md` (this plan)
- *(all code changes land in `simbiclaw/sim`, whose local checkout is
  `/Users/prometheus/workspace/simbi` — B's repository, not this one; per the rubric this block is
  repo-relative to `harness-cli`, so it lists only the plan itself.)*

## 3. Milestones

### M1 — Fix B's two blocking crashes

In `simbiclaw/sim`. `agents/qa_agent.py:66` calls `self.kb_builder`, never assigned (`:31` assigns
`self.kb_context_builder`). `:125` raises `KeyError: 'grade'`. Both sit on the single happy path.
*Line numbers are as of `0c2cccd`, the commit before the repair; both sites now hold fixed code, so
a reader opening the file at HEAD and finding nothing wrong will have found nothing wrong.*

`Acceptance Test:` `tests/test_qa_agent.py::test_pipeline_reaches_report` — the orchestrator runs
end to end against a fake LLM and returns a report object.



`Structural Test: none —` this milestone repairs B's code. It introduces or modifies no harness rule of *this* repository, so there is no structural test it owes; what `.claude/tests/` owes it is the floor it must not redden, which is a different thing and is recorded in `docs/conventions/pev-loop.md`.

**Contract.**
- *Deliverable:* B's pipeline runs end to end without raising.
- *Binding constraint:* None beyond the verification floor. This is defect repair in B's own repository.
- *Acceptance property:* A transcript entering the orchestrator yields a report object with no unhandled exception on the happy path.
- *Known evidence (advisory):* Two crashes were identified — an unassigned attribute in Stage 0 and a missing key at Stage 6. Treat the cited paths as leads and confirm against the tree you execute in. **2026-09-14: a third defect sits on the same path** — `utils/nli.py` hardcoded `device=0`. It is *not* an instance of the two above and does *not* fail on this machine; §6 states what it actually is, and why the first account of it was wrong.


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
CONFIRMED, so the change had no owner. **9024 owns the edit; this milestone owns the decision.** The port gains an explicit absent
state (nullable, or a third member — the shape is recorded here and applied there), and two
consequences follow:

1. **It is a declared deviation from a CONFIRMED port.** The plan's own boundary rule is that a
   field the consumer re-derives is a field the contract failed to carry; this is the converse —
   the contract must be able to *say* "not established", which upstream's type cannot. The
   deviation is recorded in the Decision Log with its rationale, not left for the fidelity floor
   to flag as a drift.
2. **It interacts with the fidelity floor.** The floor compares the port against upstream
   mechanically, and a deliberate divergence is indistinguishable from an accidental one unless a
   register says so. The **intentional-deviation register** is `9024`'s (it absorbed
   `9022-contract-fidelity-checker` on 2026-09-14), and this milestone is its first entry. (Filed
   there rather than solved here.)

`Acceptance Test:` the B-side tests run here (`tests/test_asr_preprocessor.py` — the swap path is
gone, and no keyword list or role-detection prompt survives). The two **consumer-side** assertions —
`tests/test_call_record.py::test_absent_role_defers` and
`tests/test_schemas.py::test_absent_role_is_representable` — execute in **9024**, which owns the
port and can run them (see its M7, which also records the deviation in its own register).


`Structural Test: none —` the convention this milestone enforces (a consumer never re-decides what a producer decided) is a plan-family rule, and its structural form is `9024`'s M8 import fences, not a test that can be written here. **`test_no_role_re_derivation_survives` is not a structural test and is no longer described as one:** it reads B's source for deleted names, which asserts no convention of this repository and is defeated by renaming — verification demonstrated that twice. It is a tripwire for accidental survival, and it is worth exactly that.

**Contract.**
- *Deliverable:* Speaker attribution consumed from the call record; no re-derivation in the consumer.
- *Binding constraint:* I2's posture — an input nobody established is **absent**, not low. A fabricated role is the same class of defect as a fabricated score.
- *Acceptance property:* A correctly-role-labelled call is evaluated against the agent's utterances; a call without a role is routed to a human, and no code path can manufacture one.
- *Known evidence (advisory):* **0 of 718 archived calls carry `speaker_role`** — the corpus predates M9, and the re-run is gated on an archive backup that has not been made. **Consequence, recorded deliberately: until that run happens this milestone makes Argus produce no auto-final verdict at all — every call defers on absent role.** That is the honest state, not a regression to work around; a consumer that keeps its re-derivation to avoid it is keeping the tier violation. **Clarified 2026-09-14:** that sentence describes **Argus**, where M2's consumer half lands (9024). It does **not** describe B, and B does the opposite — see §6's entry on the 0.0/不合格 report, and Q28.


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
number anywhere in the record. **This test executes in `9025-read-and-anchor`** (the grounding gate
is that plan's `core/grounding.py`), not here — see §2's second exception.


`Structural Test: none —` the work is a deletion in B's repository, and the gate it points at (`tests/test_grounding.py::test_garbled_transcript_routes_ungrounded`) is `9025`'s. `test_no_reliability_machinery_survives` has the same status as its M2 twin: a tripwire, not a structural test.

**Contract.**
- *Deliverable:* No input-quality grade anywhere in the consumer; a bad transcript fails through the anchor gate.
- *Binding constraint:* I2 — an unanchorable finding routes to a human. A text-derived grade standing in for an unmeasured acoustic property is the defect, not the safety net.
- *Acceptance property:* Bad input changes routing through quote failure, never through a fabricated score or grade.
- *Known evidence (advisory):* `asr_quality` has zero effect on any score simbi has produced (its three consumers are a log line, a report field, and display). The repetition half of the phenomenon belongs to audio2tree's M11 (a per-turn 3-gram run-length measurement, in flight) — **Argus waits for that rather than building a second detector.** If an input-triage signal is ever wanted before the hunt pass, the named route is reviving one of Q6c's five indicators as a deliberate act — which would produce a measurement, not a grade. Both are optimisations; I2 catches the consequence regardless.


### M4 — B's first end-to-end test

*The title dropped the conformance half on 2026-09-14, when that half moved to `9024`; the
section body and the Contract block record the move.*

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
`data/transcripts/` produces a complete report with no network access, **and the stages that had
never run together did run**. `::test_the_same_transcript_twice_gives_the_same_report` — the
determinism the consumer's replay depends on.

**The milestone's second named test moved to 9024 (2026-09-14).** It read:
`test_call_record_carries_the_consumer_contract` — the record carries `speakers[].speaker_role` +
`speaker_role_source` (the producer's, 9008 M9), `start_sec`/`end_sec` on turns and segments (9008
M11), per-segment acoustic blocks aligned to spans, and per-call `stats`; each asserted present,
with the absent case exercised as a routing input rather than a crash. **Declared-empty is a third
state, not a failure:** 47 of the 718 archived records carry empty `turns` and `segments` **lists**
(values `[]`, not `0`), so "present" means the field exists and holds a value *or* the record says
it holds nothing — a test that only accepts non-empty would fail on 6.5% of the corpus for the wrong
reason.

**It cannot execute here, and the plan's premise for putting it here was wrong.** This section
originally said B is "the one place both sides can see it: a real call record entering the pipeline
and producing a report". B's pipeline consumes labelled transcript *text* — `_parse_raw` matches
`客户`/`坐席`/`客服` prefixes — while the records under `INTENTS/**/calls/**` carry `turns[].speaker`
as an anonymous diarization label (`S0`, `S1`, …), `speakers[].label` **null**, and no
`speaker_role` on any of the 718. A record is not renderable into B's input without an adapter B
does not have, so "a real call record entering the pipeline" describes something that cannot happen
in this repository. The test's actual subject — whether the record carries what the consumer reads —
is a question about the consumer's reader, `9024-port-and-fences`' `src/argus/io/call_record.py`, and
it executes there in the `tests/test_call_record.py` that plan already declares.


`Structural Test: none —` the milestone adds test infrastructure to B's repository and changes no harness rule of this one.

**Contract.**
- *Deliverable:* An executable end-to-end test over a real transcript, with no network. **The second half — the runnable definition of what the consumer may depend on from the producer — moved to `9024-port-and-fences` on 2026-09-14**, because its subject is the consumer's reader and B cannot consume a record. The Contract names both halves because it was written before that was known; round-2 verification checked it clause by clause and found the second half not met here, which is why this line now says where it went.
- *Binding constraint:* The verification floor — an externally observable property exercised against real data — plus the boundary rule this review established: a field the consumer re-derives is a field the contract failed to carry.
- *Acceptance property:* The pipeline runs from a real transcript file to a report, deterministically and offline. **The second clause — every field the consumer reads is present in the record it was promised, or the run defers explicitly — is `9024`'s**, for the same reason as the Deliverable's second half.
- *Known evidence (advisory):* B has no integration test, which is why M1's crashes survived. The NLI dependency may not be installable in every environment. **This milestone's baseline is also the reference M7 compares against after the move** — same input, same output.


## 4. Progress

- [x] M1: Fix B's two blocking crashes  (done 2026-09-14 — cleared by human ruling at the five-round cap; see the Decision Log)
- [x] M2: Delete the role re-derivation; consume the producer's `speaker_role`  (done 2026-09-14 — verified at 9f0e8b3, round 1 CONFIRMED; amended 2026-09-14, was "add a confidence floor")
- [x] M3: Retire the reliability chain (not a signal; timestamps are not lost)  (done 2026-09-14 — verified at 03be621, round 1 CONFIRMED; amended 2026-09-14, was "repair the chain")
- [x] M4: B's first end-to-end test  (done 2026-09-14 — verified at 929d5a7, round 3 CONFIRMED; the call-record conformance half moved to 9024)

## 5. Decision Log

### M4 adversarial verification

**Verdict: CONFIRMED** — round 3, no rejection-grade finding. Round 2 confirmed `df35f9c` and found
its central weakness; the artifact changed, so round 3 verified `929d5a7`.

**The edge cases the round designed and ran:**

- *Is the new empty-input assertion caused by the input, or by the second run's construction?* Four
  combinations of the two variables (KB tree, `FakeLLM` instance): real⇒98.1, empty⇒0.0, empty with
  run-1's construction⇒0.0, real with run-2's construction⇒98.1. Construction is not a confound.
- *Both runs empty ⇒ the test fails*, so the assertion is not satisfiable without a transcript.
- *A total drop of the caller's text* (the orchestrator ignoring it for a constant) ⇒ 1 failed, the
  e2e test. A **content** drop (every turn's text replaced by a constant) ⇒ 38 passed, which bounds
  the assertion: it proves input-dependence, not content-dependence.
- *The route floor's correction, re-measured.* With the earlier revision's empty payloads reinstated
  against today's thirteen routes: 8 of 13 fire, 5 never — and of `INTERACTING_ROUTES` exactly the
  three the comment names fire. Both counts in the comment are exact, not approximate.
- *The empty-string measurements in the test's comment*: 25 questions, 25 verdicts, 0.0/不合格, and
  6 of 6 required routes firing — so the route list genuinely cannot discriminate that case, as the
  comment says.
- *Determinism*, ten consecutive runs of the file, and `ruff check`/`ruff format --check` clean on
  all three files the milestone touches.
- *The record repairs of the previous commit, checked against measurement* — see §6.

**What the round falsified, and this commit corrects:** a sentence I shipped in `ff86993` said the
suite misses five of eight production mutations "including inverting every dialogue-consistency
verdict". That mutation is **caught** at `ff86993` — by the empty-input assertion the same commit
added. The bound was measured at `df35f9c` and carried into the commit that invalidated it. See §6.

### M3 adversarial verification

**Verdict: CONFIRMED** — round 1, no rejection-grade finding.

**The edge cases the round designed and ran:**

- *Deletion completeness, by two greps.* Tracked files via `git grep` and the working tree
  including untracked, for every deleted name. No live reader survives; the only hits are the new
  tests' own assertions. `models/prompts.py` now offers the model only
  `"internal_policy/external_fact"` — the atomize prompt's offer of the deleted field is gone, and
  `ATOMIZE_AGENT_PROMPT` inherits "格式同上" from it.
- *`_parse_raw` byte-identical.* `sha256` of its body is the same at `0c2cccd`, `9f0e8b3`,
  `5e6f039` and `59f0645`.
- *`process()` differs only in the deleted fields.* A differential over sixteen transcripts — the
  three known formats, the label-less and fullwidth variants, five the parser does not recognise,
  CRLF, empty, whitespace-only, and the repo's own `data/transcripts/sample.txt` — dumps
  `CleanTranscript.model_dump()` with the deleted keys scrubbed: **identical**.
- *Routing is total by construction.* Exhaustive over `applicability ∈ {applicable, NA} × ClaimType`
  (six pairs), every pair yields exactly one verdict. `Subquestion(claim_type='asr_uncertain')`
  raises `ValidationError` and `ClaimType('asr_uncertain')` raises `ValueError`, so the branch the
  deletion orphaned cannot be reached by a value the enum can hold.
- *The behaviour change, measured.* See §6 — it is larger than the commit recorded, and the
  measurement is what corrected the commit's own claim about it.
- *Reintroduction.* The same two regexes reinstated under a new name, as a three-valued grade on
  `CleanTranscript`: all four M3 tests stayed green. That falsified the source-grep test's
  docstring, which is corrected; it is the second occurrence of that class in this file.
- *The `SyntaxWarning`, at both revs.* `python -W error::SyntaxWarning -c "import core.asr_preprocessor"`
  raises at base and imports clean at HEAD.
- *The suite.* 36 collected, `36 passed`, 0 skipped, no xfails — and the inventory is unchanged
  between `5e6f039` and HEAD, so nothing was weakened to reach green.

**What CONFIRMED does not cover.** The round's findings are recorded in §6 and none blocks the flip:
the measured blast radius of the one live behaviour change, two orphans the deletion created and
this milestone then cleared, and the retired concept's survival in the design corpus.

### M2 adversarial verification

**Verdict: CONFIRMED** — round 1, no rejection-grade finding.

**The edge cases the round designed and ran:**

- *Reintroduction by a route the tests do not name.* Added a module-level oracle and routed `role`
  through a new helper, leaving the constructor untouched: **all five acceptance tests stayed
  green**, and the demonstration fired — a correctly-labelled transcript shipped
  `['agent','customer']` for `客户/客服`. The docstring and the commit trailer claiming the
  capability was "unexpressible" are both corrected; what is true is narrower and is what the tests
  actually pin (the route the re-derivation used is closed, and reopening it by the obvious path is
  visible).
- *The parser's third format, and five it does not know.* `_parse_raw` has three labelled branches
  and the acceptance tests exercise two. The round swept all three plus `[00:01 -> 00:20]客户:`,
  `[1.0s -> 20.0s]客户:`, `[1000ms -> 20000ms]客户:`, `[1s]客户:` and `speaker=客户:`, and edge
  cases around them: an unlabelled line among labelled ones, CRLF endings, an empty transcript,
  labels other than 客户/坐席/客服.
- *Repo-wide, not module-wide.* Grepped the whole repository for any path that *decides* a role
  rather than reads one. None does; the module now imports only `re` and `models.schemas`.
- *Red→green.* At `64153da`: `5 failed, 29 passed` — exactly the five acceptance tests. At HEAD:
  `34 passed, 34 collected, 0 skipped`. At base, `test_timestamp_parsing` failed with
  `assert 'agent' == 'customer'`, and base shipped *every* role of a correctly-labelled transcript
  inverted. One test was deleted — `test_role_swap_detection`, in the RED commit — correctly,
  because it asserted the deleted behaviour.
- *The absent-role boundary in B.* `CleanTurn(role=None)` raises `ValidationError`, so the plan's
  "B leaves the role non-nullable" is a fact about the code and not a hope.
- *M3's surface, by hash.* The `asr_quality` / `reliability` / `TurnFlag` surface hashes identically
  at base and at HEAD: the deletion did not reach M3's subject.
- *An unattributable call, end to end.* Labels stripped from `TRANSCRIPT_NORMAL` → 0 turns,
  `overall_score=0.0`, `grade='不合格'`, `veto_triggered=True`. Recorded in §6; what B does today is
  not what the acceptance property's second clause asks for, and that clause is 9024's.

**What CONFIRMED does not cover.** The round's remaining findings are behaviours of the surface M2
leaves behind rather than defects in the deletion. They are recorded in §6, and none blocks the
flip.

### M1 adversarial verification

**Verdict: CONFIRMED** — *cleared by the human's ruling at the five-round cap, not by a round's
verdict. No round returned CONFIRMED; five returned REJECTED.*

Rounds 1 and 2 found defects in the artifact: round 1 a real regression the first repair introduced
— a working MPS pipeline moved silently onto the CPU, fixed at `f7af485` — and round 2 the device
probe asking a weaker question than the pipeline asks, fixed at `067e449`. **Rounds 3, 4 and 5 found
nothing in the artifact at all**, and the artifact did not change between them: every finding was
against the prose describing the work, and each round's repair to that prose became the next round's
finding. The human's ruling of 2026-09-14 closes it — *"这种不是代码出问题的，第三轮结束就应该翻牌了"*
— and the rule is now `docs/conventions/pev-loop.md`, "When the loop changes object". Under that
rule, `Verdict: CONFIRMED` above is the structural gate's only vocabulary for *cleared to flip*; it
is not a claim that a round confirmed.

**The edge cases the rounds designed and ran** — what this milestone is actually confirmed against:

- *Each crash fix reverted on its own* (round 3, clone): Stage 0 alone → `AttributeError: 'QAAgent'
  object has no attribute 'kb_builder'` at `agents/qa_agent.py:66`; Stage 6 alone → `KeyError:
  'grade'` at `:125`. Neither fix carries the other, and both land on the lines M1 cites.
- *Every device case falsified by targeted mutation* (rounds 3 and 4): a deliberately wrong
  `_resolve_device()` per branch kills exactly the test covering it — fallback returns `0`, CUDA
  branch removed, MPS branch removed, `getattr` guard removed, `ImportError` guard removed, explicit
  `device` ignored. The CUDA and MPS cases, the two a badly written version would leave vacuous,
  both die.
- *Host-independence* (round 3): the device tests pass with no `torch` importable at all **and** with
  the real `torch` 2.5.1 + `transformers` 4.48.0 on `sys.path`.
- *The MPS divergence* (rounds 3 and 4): `is_torch_mps_available()` requires `is_available() and
  is_built()` where the probe asked only the first. Chased to `REGISTER_MPS_HOOKS` and the
  `USE_MPS` compile flag and found unreachable, because `is_available() ⟹ is_built()` in every
  torch — then closed by construction at `067e449` anyway.
- *The version boundary* (rounds 3, 4 and 5, independently swept each time): `pipelines/base.py` at
  every release tag from 4.40.0 through 4.49.0 plus 5.0.0 and 5.17.0 — thirty-five tags, of which
  4.40.0–4.46.3 raise and none of the rest does.
- *The acceptance test cannot see a wrong report* — volunteered by the executor, confirmed by rounds
  3, 4 and 5: forcing `overall_score = 0.0` and `grade = "SABOTAGED"` after aggregation still passes
  it. It asserts that a report arrives, which is the Contract; M4 owns the test that asserts the
  numbers are right.
- *Five of the fake LLM's thirteen routes never fire* (confirmed by rounds 3 and 4), role detection
  among them — which is M2's subject, and why M4's end-to-end test is not redundant with this one.

**Residual defects in the written record, carried as an open workstream and not blocking the flip:**
the `git notes` on `f7af485` and `cdc2a05` say "has six" where HEAD has eight device tests; the
five-stand-in enumeration survives in `f7af485`'s message, corrected by its note; `simbi/HANDOFF.md`
(untracked) still carries the unqualified `device=0` claim. None touches the artifact.

### Decision: Repair in place, before the import (inherited from the archive, 2026-09-12)

**Rationale:** `Source:` the archived `9021-relayer-argus-eval-pipeline.md` §2 — *"B's defects are
fixed in place before the import so they surface in their own diffs rather than hidden inside a
1,600-line move"*. Confirmed a second time by the architecture review of 2026-09-14, which found
that two of these milestones (`M2`, `M3`) are **transformation-tier** repairs: the consumer will
not import the modules they touch, but the defects are real and the tier that owns them needs them
fixed.

**Confidence:** high on the ordering; `Confidence: low` on whether all four milestones remain in
this plan once M2/M3's owners (audio2tree for `speaker_role`, the consumer for the contract) have
their own plans — `Revisit:` when 9024 opens, since M2/M3's acceptance tests run here.

### Decision: The third crash is repaired inside M1, with its own acceptance test (2026-09-14)

**Rationale:** `Source:` M1's Contract — *"Deliverable: B's pipeline runs end to end without
raising"* — and the repository's own `HANDOFF.md`, whose critical-bug list names the hardcoded
device. It carries its own test (`tests/test_nli.py`) rather than riding on M1's acceptance test,
because that test replaces `NLIModel` wholesale and cannot observe what the constructor passes to
`transformers` — a change the milestone's named test cannot see is a change with no acceptance
test, which the verification floor does not allow.

**Corrected 2026-09-14 after round 1.** This entry originally justified the in-scope decision by
asserting the device index "fails exactly that deliverable, on the machine B is developed on."
It does not: measured, `device=0` constructs successfully on this machine via MPS. What raises is
`transformers` 4.40.0–4.46.3 on an accelerator-less host — a correction applied twice, since the
first correction named the range one release low. The decision survives, and on a firmer footing
than either wrong statement gave it: `pyproject.toml` admits every raising release, and the probe
was silently wrong for Apple Silicon. It rests on the version range, not on the development
machine. The range's **operative** statement is `utils/nli.py::_resolve_device`'s docstring; this
plan restates the number as the evidence that justified the milestone, and §6 records both how it
was verified and why the count is two rather than one. **Corrected 2026-09-14 by round 5**, which
found this line and §6 answering the same question differently — this one said "stated once".

**Confidence:** high on the repair; `Confidence: low` on whether `_resolve_device()` should consult
config rather than torch's own answer — that question belongs to whoever first runs B on a GPU box,
and the explicit `device` argument is what makes the answer cheap to change. `Revisit:` then.

## 6. Surprises & Discoveries

**M1 hit the five-round verification cap without CONFIRMED (2026-09-14).**
`docs/conventions/pev-loop.md` allows at most five Verify rounds per milestone. M1 used all five,
did not reach CONFIRMED, and is **not flipped** and does not advance. This is the record the cap
requires, written before the question goes to the human.

| Round | Verdict | Rejection-grade | Significant | Minor | What the rejection was about |
|---|---|---|---|---|---|
| 1 | REJECTED | 1 | 3 | 2 | the third defect's written provenance — "fails here", "found by execution" — both false; plus a real regression the repair introduced, MPS downgraded to CPU |
| 2 | REJECTED | 1 | 0 | 1 | the version boundary, stated as 4.45 when it is 4.46.3 |
| 3 | REJECTED | 1 | 0 | 5 | the wrong range surviving in `f7af485`'s commit message, and a wrong test count in the same message |
| 4 | REJECTED | 1 | 1 | 3 | the paragraph written to answer round 3, falsified in every part: no in-place correction channel, an inverted force-push argument, a false "stated once" |
| 5 | REJECTED | 1 | 1 | 2 | the command named as evidence that the `git notes` corrections print — `git log --oneline -1 <sha>` suppresses them — and §5 and §6 disagreeing on how many times the range is stated |

**What changed between rounds, and whether the arc converged.** The code has not been rejected since
round 2 and has not changed since round 2 except for one comment and a tightening of the device
predicate. Rounds 1, 3, 4 and 5 each found the pipeline, the acceptance test, the `git notes`
corrections and the docstring correct — in those words. Every rejection from round 3 onward was a
defect in the prose *describing* the work, and each round's repair introduced the sentence the next
round rejected: round 3's scoping paragraph was falsified by round 4, and round 4's evidence
sentence was falsified by round 5.

The findings narrowed every round — from a defect plus a regression, to one number, to one surviving
copy, to a scoping argument, to a command name — but the class did not go away, because the repairs
were themselves unverified assertions. That is the same failure the rounds were catching, which is
the honest reading of why five rounds did not converge.

**What B does with a call it cannot attribute — and why it is not what the plan asks for (2026-09-14).**
M2's acceptance property has two clauses: a correctly-labelled call is evaluated against the agent's
utterances, and a call without a role is routed to a human. The first is demonstrated in B. The
second is not, and M2's deletion is not what stands in its way. Measured end to end on
`TRANSCRIPT_NORMAL` with its labels stripped: **0 turns, `overall_score=0.0`, `grade='不合格'`,
`veto_triggered=True`.** `requires_human_review` is set, but incidentally — `core/fact_checker.py`
derives it from NEI, low confidence, veto and implied questions, none of which knows that
attribution was absent. So B does not defer an unattributable call; it grades it zero and vetoes
it, and a reader who trusted the plan's sentence about "every call defers" would expect the
opposite. That sentence is about Argus and is now marked as such; the clause itself is 9024's
(T7's absent-role state and `test_absent_role_defers`), and Q28 asks whether a 0.0/不合格 report is
an acceptable *form* of "routed to a human" once Argus does defer.

**`_parse_raw` is now the sole role authority, and it recognises three formats (2026-09-14).**
Pre-existing and unchanged by M2, but the *consequence* changed: with the re-derivation gone,
nothing else can rescue a transcript the parser does not recognise. `[00:01 -> 00:20]客户:`,
`[1.0s -> 20.0s]客户:`, `[1000ms -> 20000ms]客户:`, `[1s]客户:` and `speaker=客户:` all yield
**0 turns** — the label is present and the role is neither consumed nor flagged. Two smaller
artifacts of the same parser: the unnumbered branch keeps the label inside the turn text
(`客户您好，我想咨询一下`), and a transcript mixing formats (`[1s -> 20s]客户: …` followed by
`[T02] 坐席: …`) collapses to a single customer turn containing the agent's words, because the
timestamp branch returns before the numbered branch is tried. None of these is M2's to fix — M2
deletes a decider, it does not repair a parser — and all are recorded because M4's end-to-end test
is where they will surface.

**B's design documents still require the deleted behaviour (2026-09-14).** `design/18_file_checklist.md`
and `design/15_3Demos_expected_output.md:27` carry acceptance items reading
`role_swap_detected: True ← 必须检测到` — a stated expectation for something that can no longer
exist. They are archival design records, not live specification, and are left as written under the
same rule that left the experiment record alone; recorded here so the mismatch is known rather than
discovered.

**The deletion's blast radius was larger than the commit recorded, and measuring it corrected
the commit (2026-09-14).** The accuracy-atom filter in `core/question_generator.py` was
`atom_type in [...] and a.reliability == "high"`, so an atom sourced from a short turn — under four
characters, or a repeated fragment — was excluded from accuracy questioning and therefore from the
score's denominator. Deleting the filter lets it back in. Verification measured one call, same fake
model and fake KB: **`100.0 / 优秀` at `9f0e8b3`, `50.0 / 不合格` at `59f0645`**, with
`requires_human_review` moving too, because the newly generated question carries `rubric_id=None`,
so `_get_weight(None)` gives it full weight 1.0 in the 准确性 dimension.

The change is the unavoidable consequence of the deletion — keeping the filter would mean
re-deriving a turn's trustworthiness from text, which is the defect M3 removes — and it is bounded
to atoms from short or repetitive turns. But the implementation commit said the grade "has never
affected a score", and the same message's next paragraph disproves it; the claim is corrected in a
`git notes` correction on `59f0645`. **The coverage gap is the part that matters:** no test in the
suite names `_atom_driven_literal` at all, so nothing pins either the new behaviour or a regression
back to a short-turn filter. M4's end-to-end test is where that lands, and this entry is the
hand-off. **Closed 2026-09-14 by M4:** `tests/test_e2e.py::test_transcript_to_report` asserts that
the accuracy-question route fires at all — one of the six `INTERACTING_ROUTES` whose firing is the
difference between exercising the pipeline and exercising the fake — so the change is now pinned and
a regression back to a short-turn filter would go red.

**The deletion left two orphans, and clearing them was this milestone's work (2026-09-14).** Path C
was the only producer of `VerdictResult.HUMAN_REVIEW`, so deleting it orphaned both the enum member
and the `requires_review` term that read it — a verdict could carry a result nothing could set.
And `Aggregator.aggregate`'s `clean_transcript` parameter lost its only reader when the
`asr_quality_warning` computation went. Both removed at `03be621`, along with the two call sites and
the test helper and import that removing the parameter orphaned in turn. An orphan created by a
deletion belongs to the milestone that deleted, not to whoever finds it next.

**The retired concept is still readable in eleven `design/` files (2026-09-14).** No code reads
`design/`, and M2's round-1 record already set the archival rule for this class — but M3 widens it,
and the retrievable copies are not marginal: a full expected-output JSON
(`design/20_e2e_example.md`), acceptance items for the deleted behaviour
(`design/18_file_checklist.md`, `design/IMPLEMENTATION_CHECKLIST.md`), and path C's specification
(`design/10_instructions4cc.md`, `design/skill4cc.md`). Read is possible; resurrection is not, by
any live path. Left as written, under the rule that a record of what was designed is corrected by
annotation rather than by editing the record.

**A source grep catches names its author thought of, and this milestone proved it twice
(2026-09-14).** `test_no_reliability_machinery_survives`'s docstring claimed the behavioural tests
would notice a reimplementation. Verification reinstated the same two regexes under a new name, as
a three-valued grade on `CleanTranscript` — all four M3 tests stayed green. M2's round 1 falsified
the twin of that sentence in the same file, so this is the second occurrence of one already
recorded error class, and the docstring now names it rather than repeating the claim.

**The production mutations, listed so the bound is auditable (2026-09-14).** Three rounds measured
what the suite catches; the numbers were described in prose and nowhere recorded, which is the
mechanism that let a stale example survive a round — a bound measured at one commit was carried into
the commit that invalidated it. Both tables below, with the measurement each belongs to:

*Round 2, at `df35f9c`* — eight production mutations, `test_e2e.py` alone catching **none**:

| | mutation | whole suite |
|---|---|---|
| P1 | aggregator: veto no longer zeroes the score | caught |
| P2 | fact_checker: NA weight 0.0 → 1.0 | caught |
| P3 | fact_checker: `best_pos > best_neg` → `<` | **missed** |
| P4 | fact_checker: low-confidence review flag never set | caught |
| P5 | aggregator: `passed_count` counts NEI/FAIL as passed | **missed** |
| P6 | aggregator: grade thresholds shifted | **missed** |
| P7 | aggregator: report summary replaced by a constant | **missed** |
| P8 | qa_agent: unresponded count never counts anything | **missed** |

*Round 3, at `ff86993`, ten mutations of its own*: six caught, four missed, and **none of the four
misses was caught by `test_e2e.py`**. P3 is the one that moved — the empty-input assertion added in
`ff86993` catches the dialogue-consistency inversion, so P3's row above is true of `df35f9c` and
false of everything after it. The conclusion both rounds support is the one the test's docstring
now states: **a smoke test over the orchestrator, not a semantic regression net.**

**What the new assertion establishes, and what it does not (2026-09-14).** It reads only
`overall_score`, so it proves the report depends on the *input* rather than on the second run's
construction — and not that it depends on this transcript's *content*. Measured: `"客服：您好"`,
five characters, no timestamps and unrelated to the call, scores exactly what the real transcript
scores, `98.1`. The assertion is also unsigned, so a pipeline scoring the real transcript *lower*
than the empty one passes it; the suite's direction is pinned elsewhere (`test_aggregator.py`), not
here. Both bounds are in the test's docstring, which now points at this section instead of restating
arithmetic it cannot keep current.

**Four of the floor's checks pass while skipping, repo-wide (2026-09-14).** `test_prd_spine_drift.py`
reports five passes; four emit `UserWarning: SKIP: … PRD symlink does not resolve to a directory`
and pass anyway. The symlink `docs/PRD -> ../../papers/PLAN` resolves to `/Users/prometheus/papers/PLAN`,
which does not exist **in the main checkout either**, not only in a worktree. So four of the
"192 passed" in every Tier-1 run since before this plan family test nothing, and the count should be
read knowing it. Recorded here because the floor's numbers are now quoted in verification briefs.

**A correction note on `ff86993` (2026-09-14).** Its message's ruff bookkeeping does not match the
measurement: the pre-M4 reformat count was 29 rather than 28 (28 is what a different ruff version
reports), the pass cleared three files rather than two, and the denominator 52 is not any
invocation's total. The substantive claims hold — `ruff check` and `ruff format --check` are clean
on all three files and the repo-wide count moved down by three. A `git notes` correction is attached
to the commit.

**The token cost was measurable and I first reported it as unmeasurable (2026-09-15).** The
completion report's cost card shipped reading `—`, justified as "this plan never wired
`.pev-signals/state.json`". The file exists; it belongs to `9006-pev-tmux-convergence`, and the
justification confused *that plan's* record with this one's. Asked for the method, `9008-audio2tree-rebuild`
gave it, and the numbers were there.

**Method, and the two traps.** Sum the per-agent transcripts under
`~/.claude/projects/<cwd>/<session>/subagents/agent-*.jsonl`, **deduplicating by `message.id` and
taking the LAST usage entry per id.** One API call streams as several entries — this session:
2929 entries for 1049 calls, 2.79 per call — and the early ones carry partial usage, almost always
`output_tokens: 0`. Summing entries double-counts; summing the first per id under-counts badly.

**What it measures, which is not everything.** Subagent dispatch tokens, input + output, excluding
cache reads. **The orchestrating session's own consumption is not attributable per milestone and is
not in the number** — `pev-loop.md` says so, and the card states the scope rather than presenting the
figure as the whole cost.

| | calls | in + out |
|---|---|---|
| M1 Plan survey (`map-callsites`) | 41 | 106,004 |
| M1 verify, five rounds | 243 | 576,665 |
| M2 execute + verify | 59 | 130,461 |
| M3 execute + verify | 118 | 208,965 |
| M4 verify, three rounds | 170 | 328,461 |
| **this plan** | **632** | **1,350,556** |
| *(not this plan)* the 9021 split's verification | 169 | 1,096,320 |
| *(not this plan)* the M5 rounds | 203 | 1,197,865 |

**M1's five verification rounds cost 576,665 — more than M2, M3 and M4 together.** That is the cap
rule's clearest evidence, and it is worth noting where the spend went: four of those five rounds
rejected the written record, not the artifact.

**Why it is not in `.pev-signals/state.json`.** That file is per repository and single-plan, and this
repository's is occupied by `9006`, whose own `test_pev_tmux_e2e.py` asserts the file describes
9006's M0–M7 and its p/e/v agent ids — writing 9023 into it fails two tests. Reverted. Until the
convention gains a per-plan store (or `9006`'s assertions are moved with it), this section is 9023's
record and the report is its presentation.

### Entries predating the cap record

**The third defect is real, and the first account of it was wrong (2026-09-14, corrected after
round 1).** THIS ENTRY SAID, until round-1 verification falsified it: that `device=0` "fails in
`QAAgent.__init__` before any transcript is read", "on the machine B is developed on", and that
"only executing the milestone surfaced it". All three parts are false, and the verifier disproved
them by execution rather than by argument:

- **It does not fail here.** On this machine `transformers` 4.48.0 resolves the integer `0`
  against CUDA first and MPS second, finds MPS available, and constructs `mps:0` successfully —
  the original line worked. Measured. With *both* accelerators masked, 4.48.0 still constructs on
  CPU rather than raising.
- **The raising branch belongs to a version range, not to this machine.** Within
  `pyproject.toml` and `requirements.txt` — both of which ask for `transformers>=4.40.0` —
  releases **4.40.0 through 4.46.3** end device resolution with
  `else: raise ValueError(f"{device} unrecognized or not available.")`; **4.47.0** replaces that
  with `self.device = torch.device("cpu")`. A CPU-only install on any of the raising releases dies
  in `QAAgent.__init__` — which is why the repair is worth keeping, and is the *entire* honest case
  for it.

  **This range was wrong twice.** The first version of this entry said the failure was on this
  machine; round 1 disproved that. The second said "4.40 through 4.45 … 4.46 onward", which round
  2 disproved — the boundary is one release later than that, so the sentence *understated* the
  raising set by the four published 4.46.x releases and *overstated* the fallback. **Round 3 then
  swept it properly** — `pipelines/base.py` at every release tag from 4.40.0 through 4.49.0
  (thirty-three tags) plus 5.0.0 and 5.17.0 (thirty-five in all): 4.40.0–4.46.3 raise, 4.47.0
  onward fall back, and no release does neither. **Corrected 2026-09-14 by round 4:** this sentence
  previously said "thirty-three tags" while listing the two extra ones, so it was wrong by two and
  disagreed with the docstring, which names the 4.40.0–4.49.0 range alone. The earlier statement of this paragraph described four tag files, which is what the
  author had read, not what had been verified; the boundary is now pinned by the sweep and not by
  the author's sample.

  **Where the range lives now: two places, and that is the rule (corrected 2026-09-14 by round
  4).** This entry earlier claimed the range was "stated once" and that "no third live copy exists".
  Both were false on this file's own text — the number appeared here three times, at §5's Decision
  Log and twice in this section — which is the same overstatement that rejected rounds 2 and 3,
  surviving inside the paragraph written to remove it. The honest rule is: **the operative statement
  is `utils/nli.py::_resolve_device`'s docstring, and this entry may restate the number as
  evidence, because a plan that cannot state the fact that justified its milestone is not a record.**
  What must not recur is a *third* location — a test docstring, a comment, a second plan — repeating
  it as if it were the authority. `tests/test_nli.py` carries none and points at the code.

  **History is corrected in place, with `git notes` (rewritten 2026-09-14 by round 4).** Round 3
  rejected the milestone because the range survives in `f7af485`'s commit message, still reading
  "4.40-4.45" — and found a second false statement in the same message, an enumeration of five
  device tests where the file has six. `cdc2a05` carries two more of the same kind. This entry's
  first answer to that was **wrong in every part**, and round 4 reproduced the falsifications:

  - It said the statements were "not fixable in place". They are: `git notes add -m "…" <sha>`
    attaches a correction that prints directly beneath the message in `git log` and `git show`,
    with no SHA change, no rewrite and no push.
  - It justified itself with "this repository blocks force-push by hook" — an argument that is not
    merely weak but inverted. These commits are **unpublished** (`origin/main` is still `0c2cccd`),
    so amending them would need no force-push and would trip no hook. The constraint this plan
    placed on B's repository — local-only, never pushed — is what makes correcting them *cheap*,
    not what makes it impossible.
  - It said naming the error in the plan was a correction. Round 4's reader test is right and this
    entry accepts it: a disclosure *about* an error, in a different document, is not a correction
    *at* it. The reader who runs `git show f7af485` and no more formed the wrong belief and
    nothing they saw contradicted it.

  **What was actually done.** Notes are attached to `f7af485` (the wrong range, the five-test
  enumeration) and `cdc2a05` (the "found by execution" provenance, the "a GPU box keeps the old
  behaviour" claim). The messages are left as written — they record what was believed when they
  were written — and each now carries its correction at the point of reading.

  **Verified with commands that actually print it (corrected 2026-09-14 by round 5).** This
  paragraph previously offered `git log --oneline -1 <sha>` as the check. That command *suppresses*
  the note: `--oneline` replaces git's default format, and the notes placeholder lives in the
  default one. Round 5 measured ten invocations and split them — printing: `git log -1 <sha>`,
  `git show -s <sha>`, `git log --notes`, `git log --oneline --notes`; silent: `git log --oneline
  -1 <sha>`, `git log --pretty=oneline -1 <sha>`, `git show --oneline -s <sha>`, `git show -s
  --format=medium <sha>`. The property holds — the notes print under `git log -1 <sha>` and
  `git show -s <sha>` — but the sentence named the one form that does not, and it was the only
  evidence offered for the claim it supported.

  The criterion is therefore **not** scoped to live artifacts: a false statement in a reachable
  record is a defect, corrected where it stands. What *remains* scoped is the experiment record,
  which is the next paragraph's subject.

  **A third class, decided the same way and deliberately left alone.** Round 3 also flagged
  `docs/experiments/9021-ab-investigation/report-B.md:930`, whose dependency audit cites
  `utils/nli.py:2,17`. Line 17 was the `pipeline(` call site when that audit ran; the module
  docstring this milestone added moved it. That citation is an *observation* — what the auditor saw
  at the time — not a live pointer, and correcting it would make the record say the audit saw
  something it did not. Recorded here so the mismatch is known and explained; not edited.
- **It was not found by execution.** B's own `HANDOFF.md` had it, as critical bug #2 and again in
  its Critical TODO list. Whoever wrote the first version of this entry read that audit and then
  described the discovery as the executor's.

**What this machine actually fails on is one level above the device:** `utils/nli.py:2` imports
`transformers` at module scope, and the pipeline cannot be imported by any interpreter the
repository itself provides — because it provides none: there is no `.venv` and no CI. The
`transformers` on this machine belongs to another project's virtualenv and reaches B only through
`PYTHONPATH`, which is how this milestone's own real-library checks were run. The fix does not
touch the import, and the tests only import at all because `tests/conftest.py` installs a
stand-in.

**The probe asked a weaker question than the pipeline does (round 3, repaired at `067e449`).**
`transformers` resolves an integer index with `is_torch_mps_available()`, which is
`is_available() and is_built()` — not `is_available()` alone — so a torch reporting MPS available
but not built would send the pipeline into the branch that raises while the probe answered `0` into
it. `is_available()` does imply `is_built()` in every torch today, so the case is unreachable; the
clause was added anyway, because "unreachable by an argument about PyTorch internals" is a worse
guarantee than "cannot be expressed". `is_torch_cuda_available()` is literally
`torch.cuda.is_available()`, so the CUDA half already matched. Two tests were added for it and for
`torch.backends` being absent entirely.

**The first repair also introduced a regression, which round 1 caught.** It probed
`torch.cuda.is_available()` alone — false on Apple Silicon — so it answered `-1` and moved a
working MPS pipeline onto the CPU, silently. Both accelerators are now probed, and the result is
verified against the real libraries on this machine (`torch` 2.5.1, `transformers` 4.48.0, MPS
available, no CUDA): the probe returns `0`, the same value the original code passed. Repaired at
`f7af485`.

**Two limits of M1's acceptance test, recorded because they bound what a CONFIRMED verdict here
would mean.** It asserts that a report arrives, not that the report is right: a mutation forcing
`overall_score = 0.0` and `grade = "SABOTAGED"` while leaving every stage intact still passes it —
which is inside the Contract as written ("no unhandled exception") but is not a statement about
the numbers. And five of the fake LLM's thirteen routes never fire on this fixture — role
detection, L1 drill-down, NA applicability, implied questions and the WikiChat path — so the test
would not notice role detection breaking, which is precisely M2's subject.

**Crash #2's cause is a duplicate prompt, not a missing keyword (2026-09-14).** `models/prompts.py`
defines `REPORT_SUMMARY_PROMPT` twice, at `:332` and `:350`, and the second shadows the first. The
call site's five keywords match the *first* definition exactly — so the call was written against a
template that stopped being live when the second was added, and the `KeyError` was the symptom of
that shadowing rather than of a forgotten argument. The repair supplies the two keys; the dead
definition is left in place, because pre-existing dead code is not this milestone's to delete.
Recorded because the next editor who changes the summary prompt has an even chance of changing the
wrong definition and seeing nothing happen.

**The summary is written before the number it summarises exists (2026-09-14).** Stage 6 formats the
report prompt with `overall_score="待计算"` and `dimension_scores_json="{}"`, because the LLM call
happens before `aggregate` runs. The repair kept that shape — the two new keys are marked pending
the same way rather than asserted as values — so every summary B produces describes a score that
has not been computed. That is a real defect, but it is a design question (reorder the stage, or
aggregate in two passes) rather than a crash, and it is left for a deliberate decision rather than
folded into a defect repair.

**The corpus predates the capability that fixes it (2026-09-14).** `EXPLAIN: speaker_role` — of the
718 archived call records, **zero** carry a role label; the producer-side pass that establishes one
(9008 M9) landed the same day, and the re-run that would populate the corpus is gated on an archive
backup that has not been made. So M2's deletion is correct and, until that run happens, leaves the
consumer with nothing to consume. Recorded here because this is the plan that owns the repairs, not
the re-run.

## 7. Awaiting Steering

**Q28: Is a 0.0/不合格 report an acceptable form of "routed to a human"?** Raised 2026-09-14 by
M2's verification. When a call cannot be attributed, B currently produces a *confident* negative —
zero, 不合格, vetoed — rather than an absence, and `requires_human_review` happens to be set for
unrelated reasons. Argus is supposed to do the opposite: no auto-final verdict, route to a human.
Once 9024 lands the absent-role state, the question is what the routed verdict *looks like*: a
deferral carrying no score at all, or a scored report flagged for review? The distinction matters
because a zero that reaches a report is indistinguishable from a judgment, and the plan's whole
posture is that an unestablished input is absent rather than low. Options: (a) the routed verdict
carries no score and no grade; (b) it carries them, with the deferral signalled by a separate field;
(c) it is a distinct record type. **Default if not decided: (a)**, which is what "absent, not low"
means when written as a type. — deadline: 9024's M7 Plan phase.

**Q27: A milestone whose code verifies clean but whose prose keeps failing — what closes it?**
— **Awaiting Steering: resolved 2026-09-14.** The human ruled: *"这种不是代码出问题的，第三轮结束就
应该翻牌了"* — when the rounds stop being about the artifact, the milestone flips on the artifact's
evidence, and that line was crossed at round 3, not round 5. M1 is flipped under that ruling. The
general rule is written up in `docs/conventions/pev-loop.md`, "When the loop changes object", where
it applies to M2, M3 and M4 prospectively. *The original question is kept below as the record of
what was asked.*


Raised 2026-09-14, when M1 reached the five-round verification cap without CONFIRMED. Five rounds
rejected it; the code has not been rejected since round 2 and has not changed since then except for
one comment and a tightening of the device predicate. Rounds 3, 4 and 5 found the pipeline, the
acceptance test, the `git notes` corrections and the docstring correct, and rejected the *prose
describing* them — and each round's repair introduced the sentence the next round rejected.

Options. **(a)** Keep repairing the prose and verify again. It has now failed four rounds running,
each fix becoming the next rejection, and the cap exists precisely because that loop can run
without converging. **(b)** Flip M1 on the code's evidence, and treat the written record's residual
defects as an open workstream on this plan. **(c)** Change the practice: write a milestone's record
once, at the end, from artifacts that have already been verified, rather than editing it
continuously while the verification is in flight — the five rounds suggest the continuous-edit
practice is what manufactures falsifiable claims. Understanding which, and whether the cap should
have fired here at all, matters more than M1: it will recur on M2, M3 and M4.

**Default if not decided: (a) is exhausted, so the plan sits at (b)-or-(c) undecided — M1 stays
unflipped and no further verification round is dispatched.** — deadline: when the human next reads
this plan, or before M2's Plan phase, whichever is first.

**Q25: Who executes the corpus re-run, and when is the archive backup made?** Not resolved. M2 and
M3 are correct as written but produce no usable input until the producer's pass has been run over
the 718 records. The backup is a prerequisite no agent has been authorised to make. Options: the
audio2tree line owns it; the human does it manually; it waits. Default if not decided: it waits, and
the consumer defers every call — which is honest and recorded, not a regression. — deadline: when
9024 opens.

## 8. Outcomes & Retrospective

**What shipped.** All four milestones, in B's repository, over ten commits. Three crashes on the
single happy path are fixed — the unassigned `kb_builder`, the Stage-6 prompt formatted with five of
its live template's seven keys, and the CUDA device index that died in `QAAgent.__init__`. The role
re-derivation is deleted, along with the flag and the two schema fields it reported into. The
reliability chain is retired, with path C and a `SyntaxWarning` that had fired on every import since
the pattern was written. And B has its first end-to-end test, over its own `data/transcripts/sample.txt`.
The suite went from **uncollectable** to **38 passed, 0 failed, 0 skipped** — and a failure that had
been red since the role heuristic was written is gone.

**What took longer than planned, and why.** The code was the cheap part. M1 consumed all five of its
verification rounds, and four were about the *written record* rather than the artifact: a provenance
claim I had not checked, a version boundary stated as a number, a surviving copy of that number in a
commit message, and finally a paragraph written to answer the round before. The rule that came out of
it — `docs/conventions/pev-loop.md`, "What a milestone's Verify may be asked" — is this plan's most
durable product after the code, and it cost five rounds to learn. M2, M3 and M4 then confirmed in
one, one and three rounds respectively.

**Where the plan was wrong.** Three of the four milestones named an acceptance test that could not run
where the milestone ran. M2's and M3's consumer-side assertions belong to `9024` and `9025`; M4's
call-record conformance test belongs to `9024` because B cannot consume a call record at all — its
parser takes labelled transcript text, and the records carry `turns[].speaker` as `S0`/`S1` with
`speakers[].label` null and no `speaker_role` on any of the 718. Each was reassigned with the
reasoning written in both directions. The plan's premise for M4 — that B is "the one place both sides
can see it" — assumed a capability B does not have.

**What I would do differently, both now rules.** *Do not edit a milestone's written record while its
verification is in flight.* The edits are themselves unverified assertions, and M1 demonstrated that
each one becomes the next round's finding. *Run the tier-1 floor in every dispatch.* Four milestones
were verified and flipped without it, over a floor that was red throughout; the exception is recorded
rather than waived, and M1–M4's flips are unsound until it is green.

**Technical debt this plan creates or leaves.** The tier-1 floor is still red — six published commits
with a bare `Plan: 9021` trailer, three local flip commits whose scope a regex rejects, and two
overdue regrade dates — and its owner is a decision about published history, not an agent. Four of the
floor's `test_prd_spine_drift.py` passes are vacuous repo-wide. In B: `_parse_raw` is now the sole role
authority and recognises three formats, so five plausible timestamp shapes yield zero turns with the
label in plain sight; `_assess_coverage` compares entities to directory names, so coverage is
structurally near zero; and the suite misses five of the eight production mutations M4's verification
ran — it is a smoke test, not a regression net. `CleanTurn.role` stays non-nullable in B by design;
the absent-role state is `9024`'s. B's own `HANDOFF.md` and `design/` corpus still describe the
deleted behaviours, left as written under the archival rule.

**Method note.** Every claim in this section is drawn from the verification reports in the Decision
Log and Surprises above; where a number appears, the measurement that produced it is named there.

**Report:** [`reports/9023-b-repairs-report.html`](../reports/9023-b-repairs-report.html) — the
dashboard, generated 2026-09-15 from `.claude/templates/plan-execution-report.html`. Its figures come
from this file and from `git`; its token cards carry the measured dispatch cost, whose method and
scope are recorded in §6.


