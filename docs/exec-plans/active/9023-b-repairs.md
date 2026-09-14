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

`Acceptance Test:` `tests/test_qa_agent.py::test_pipeline_reaches_report` — the orchestrator runs
end to end against a fake LLM and returns a report object.


**Contract.**
- *Deliverable:* B's pipeline runs end to end without raising.
- *Binding constraint:* None beyond the verification floor. This is defect repair in B's own repository.
- *Acceptance property:* A transcript entering the orchestrator yields a report object with no unhandled exception on the happy path.
- *Known evidence (advisory):* Two crashes were identified — an unassigned attribute in Stage 0 and a missing key at Stage 6. Treat the cited paths as leads and confirm against the tree you execute in. **Confirmed 2026-09-14: there were three.** The third is `utils/nli.py`'s hardcoded `device=0`, which fails in `QAAgent.__init__` before any transcript is read; see §6.


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
number anywhere in the record. **This test executes in `9025-read-and-anchor`** (the grounding gate
is that plan's `core/grounding.py`), not here — see §2's second exception.

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
is a third state, not a failure:** 47 of the 718 archived records carry empty `turns` and
`segments` **lists** (values `[]`, not `0`), so "present" means the field exists and holds a value *or* the record says it holds
nothing — a test that only accepts non-empty would fail on 6.5% of the corpus for the wrong reason.

**Contract.**
- *Deliverable:* An executable end-to-end test over a real transcript, with no network; and the runnable definition of what the consumer may depend on from the producer.
- *Binding constraint:* The verification floor — an externally observable property exercised against real data — plus the boundary rule this review established: a field the consumer re-derives is a field the contract failed to carry.
- *Acceptance property:* The pipeline runs from a real transcript file to a report, deterministically and offline; and every field the consumer reads is present in the record it was promised, or the run defers explicitly.
- *Known evidence (advisory):* B has no integration test, which is why M1's crashes survived. The NLI dependency may not be installable in every environment. **This milestone's baseline is also the reference M7 compares against after the move** — same input, same output.


## 4. Progress

- [ ] M1: Fix B's two blocking crashes  (created 2026-09-12)
- [ ] M2: Delete the role re-derivation; consume the producer's `speaker_role`  (amended 2026-09-14 — was "add a confidence floor")
- [ ] M3: Retire the reliability chain (not a signal; timestamps are not lost)  (amended 2026-09-14 — was "repair the chain")
- [ ] M4: B's first end-to-end test + the call-record contract's conformance test  (amended 2026-09-14)

## 5. Decision Log

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
raising"* — together with its own Known evidence, *"treat the cited paths as leads and confirm
against the tree you execute in."* The NLI device index fails exactly that deliverable, on the
machine B is developed on, so the repair is this milestone's work rather than a new milestone's.
It carries its own test (`tests/test_nli.py`) rather than riding on M1's acceptance test, because
that test replaces `NLIModel` wholesale and cannot observe what the constructor passes to
`transformers` — and a change the milestone's named test cannot see is a change with no acceptance
test, which the verification floor does not allow.

**Confidence:** high on the repair; `Confidence: low` on whether `_resolve_device()` should consult
config rather than torch's own answer — that question belongs to whoever first runs B on a GPU box,
and the explicit `device` argument is what makes the answer cheap to change. `Revisit:` then.

## 6. Surprises & Discoveries

**A third crash sat on the same path, and the plan named two (2026-09-14).** `utils/nli.py`
passed `device=0` — a CUDA device index — and `FactChecker.__init__` constructs the NLI model
eagerly, so the failure lands in `QAAgent.__init__`, before a transcript is read. The milestone's
Contract asks for "B's pipeline runs end to end without raising" and its Known evidence says to
treat the cited paths as leads; the lead list was one short, and only executing the milestone
surfaced it. Repaired at `cdc2a05`.

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

**Q25: Who executes the corpus re-run, and when is the archive backup made?** Not resolved. M2 and
M3 are correct as written but produce no usable input until the producer's pass has been run over
the 718 records. The backup is a prerequisite no agent has been authorised to make. Options: the
audio2tree line owns it; the human does it manually; it waits. Default if not decided: it waits, and
the consumer defers every call — which is honest and recorded, not a regression. — deadline: when
9024 opens.

## 8. Outcomes & Retrospective

*Written at completion or cancellation.*
