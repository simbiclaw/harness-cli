# 9022 — Shared Contract-Fidelity Checker

## 1. Purpose

M5 spent five adversarial rounds past its Contract because the fidelity floor it needed — "the port and upstream cannot differ in any way observable to a caller" — was being built inside one milestone's test file with no written threat model, so every round's survivors were the generalization of the previous round's fix and no round could close. This plan gives that discipline its own home: the raw-fact recording the rounds converged on, a sweep harness with the pyc-taint hazard fixed once for every future sweep, and the threat model written down so the next agent knows what this floor claims and — just as important — what it does not.

## 2. Big Picture

The threat model is the plan's core artifact. It separates two claims that rounds 4 and 5 conflated:

- **Drift** — the port and upstream diverge because a maintainer edited one and not the other. This is the common case, it is what `test_schemas.py`'s floor has caught since round 2, and extending it (raw callables + MRO facts) is this plan's first milestone.
- **Sabotage** — an adversary edits the port to launder a value (`proposed_score`) past the gates, forging `__module__`, smuggling re-exports, hiding behavior in mixins. Rounds 4-5 proved an unbounded adversarial brief against sabotage always succeeds: a sufficiently clever editor wins, which is B succeeding, not failing. This plan writes down which sabotage classes the floor closes (the recorded 21+5), which it watches at boundary grade (`validate_default` family, digest-vs-forgery), and the theorem it aims at — *if two classes differ in any way observable to a caller, some check fires* — plus the known distance to it (properties, `__slots__`, descriptors, metaclass `__call__`).

Inherits from 9021 M5 (committed on `claude/9021-m5-handoff-local`): the round-4/5 floor in `tests/test_schemas.py` and `scripts/build_schema_snapshot.py`, and `scripts/mutate_m5_contract.py` with its 21-row table. Deliberately out of scope: any change to the port (`src/argus/types/pipeline.py` — fidelity is observed, never repaired here), the 9003 compiler's own schemas, CI wiring beyond the shared runner.

**File Scope:**
- `docs/exec-plans/active/9022-contract-fidelity-checker.md` (this plan)
- `docs/exec-plans/active/9022-contract-fidelity-checker-notes/**` (new)
- `scripts/build_schema_snapshot.py` (modify — F1 extends the oracle; **declared here because this plan is what edits it.** Correction 2026-09-14: the plan previously said `9024-port-and-fences` owned it. 9024's File Scope never named it, and neither did the archived parent, so deferring to 9024 left the file with no owner while F1 edited it)
- `scripts/mutate_m5_contract.py` (modify — F2 grows the sweep to 25+ rows and fixes the grading hole; same correction as the line above)
- `scripts/run_sweep.sh` (new — the shared sweep runner: pyc purge, `PYTHONDONTWRITEBYTECODE=1`, collection-error grading; one way to run a sweep)
- `docs/experiments/9022-fidelity-threat-model/**` (new — the written threat model)
- `tests/fixtures/intentional_deviations.yaml` (new — **the register of deliberate divergences**, consumed by the comparison; F1 lands it, and its first entry is 9024's absent-role state)

**Deferred, not claimed — `tests/test_schemas.py`.** F1's edits land in a file the port plan
declares while it is open. It is named here and **deliberately not declared as scope** —
announcing it would collide with `9024-port-and-fences`, which owns it, and the collision detector
is right to object: two plans editing `tests/test_schemas.py` at once is exactly what it exists to
prevent. F1 opens when 9024 releases the file, and this block is filled in then.

**Corrected 2026-09-14 (adversarial verification).** This block previously named *three* deferred
paths and asserted all three belonged to `9024-port-and-fences`. Only one does: 9024's File Scope
names `tests/test_schemas.py` and neither script, and the archived parent named neither script
either — so the deferral left `scripts/build_schema_snapshot.py` and
`scripts/mutate_m5_contract.py` with no owner at all while F1 and F2 edited them. Both are now
declared above, by this plan.

`src/argus/types/pipeline.py` is deliberately absent: this plan observes the port and never edits
it, and declaring it would collide with 9024's scope for the same file.

## 3. Milestones

### F1 — Raw callable + MRO-base facts, filter dropped (the round-5 repair, carried)

Record every callable on every contract class (name + defining module, descriptor-unwrapped) and every MRO base name, for models and enums alike; diff mechanically with no defining-module filter — same interpreter both sides, so pydantic/enum machinery cancels. Closes the round-5 survivor classes: `model_post_init`, laundered `_missing_`, plain-mixin `__setattr__`. Fixture regenerated; mirrors extended; named regression pins the new forms.

**F1 also lands the intentional-deviation register** (`tests/fixtures/intentional_deviations.yaml`),
because a mechanical comparison cannot tell a deliberate divergence from an accidental one. The
register is a list of `{path, field, expected, reason, decided}` entries the comparator consults
*instead of* failing — and it is deliberately awkward to add to: an entry must name the decision
that authorised it, so suppressing a divergence is an act someone signs, never a silence. **Its
first entry is 9024's absent-role state** (`CleanTurn.role` becomes nullable so the consumer can say
"not established"; upstream's `Literal["customer","agent"]` cannot). Without this, 9024's deviation
and a genuine drift are the same event to this floor.

`Acceptance Test:` `tests/test_schemas.py::test_the_checks_can_fail` extended plants — `model_post_init` zeroing scores, post-class `_missing_` with forged `__module__`, plain mixin `__setattr__` — each red via the new facts. (**Corrected 2026-09-14:** the path is `tests/test_schemas.py`, deferred-not-claimed above until 9024 releases it. The earlier pointer to a "File Scope TBD" dangled — there is no TBD in this plan's File Scope, and the 9021-completion split is a completed event, not a pending one.)

### F2 — Sweep to 25+ rows with honest grading

`mutate_m5_contract.py` grows the round-5 survivor rows (AT1-AT3, AT5) and fixes the grading hole: a collection error is a sweep ERROR, not a catch; "no tests ran" fails the sweep; every red must name its mutated target in its failure text.

`Acceptance Test:` the sweep run reports 25 rows all red with per-row target assertions; a deliberately broken row (collection error) grades as ERROR and exits nonzero.

### F3 — Shared sweep runner (the pyc-taint promotion)

`scripts/run_sweep.sh`: purges `__pycache__`, sets `PYTHONDONTWRITEBYTECODE=1`, invokes the sweep, grades exits. Every mutation sweep in the repo runs through it — the rule becomes "there is one way to run a sweep" rather than "remember to disable bytecode." `mutate_m5_contract.py` is refactored onto it, and its docstring records the hazard (same-second size-preserving edits defeat the pyc validator; constant-value mutations are exactly that class).

`Acceptance Test:` `tests/test_sweep_runner.py::test_runner_disables_bytecode_and_grades` — the runner invoked on a stub sweep produces pyc-free runs and nonzero exit on a planted collection error.

### F4 — The threat model, written

`docs/experiments/9022-fidelity-threat-model/README.md`: the drift/sabotate split, the closed/boundary/watching tables (closed: the recorded 26; boundary: `validate_default` family, digest-vs-forgery; watching: properties, `__slots__`, descriptors, metaclass `__call__`), and the statement of what would close the distance (a structural diff over the live pydantic core schema, or accepting boundary grade with reasons). This document is what the next round-B reads instead of being handed an unbounded brief.

`Acceptance Test:` `tests/test_threat_model_cited.py::test_every_watch_class_has_an_owner` — every class listed in "watching" cites the round or finding that surfaced it; every boundary entry states why it is not closed. A threat model nobody can falsify is not one.

## 4. Progress

- [ ] F1: Raw callable + MRO facts, filter dropped  (created 2026-09-14)
- [ ] F2: Sweep to 25+ rows with honest grading  (created 2026-09-14)
- [ ] F3: Shared sweep runner  (created 2026-09-14)
- [ ] F4: Threat model, written  (created 2026-09-14)

## 5. Decision Log

### Decision: Created by steering split from 9021 M5, not by new discovery

**Rationale:** `Source:` 9021 Awaiting Steering Q23 and its Decision Log entry "M5 close criteria" (2026-09-14, human ruling on the cloud session's handoff) — M5's flip gates on its Contract's stated property; the fidelity discipline this plan carries had five survivals of the same shape across distinct rounds, which is the promotion rule's trigger, and a plan with a written threat model is where the rule moves it. The seed work is 9021's commits on the floor files plus `9021-relayer-argus-eval-pipeline-notes/M5.md` (the five-round record) and `M5-round4-brief.md` (the encoder-duplication rule, restated here as binding for F1).

### Decision: Fidelity tests stay in `tests/test_schemas.py` until its owner releases them

**Rationale:** splitting them now would trip `test_plan_collisions.py` against the plan that owns them and force an amendment to a plan mid-flight — the pattern `9004-execution-mistakes` identifies. The deferred-not-claimed block in File Scope is the negotiation. **Updated 2026-09-14:** 9021 was archived that day and its paths redistributed across `9023`–`9029`; the three this plan needs moved to `9024-port-and-fences`, so F1 opens when 9024 releases them rather than when 9021 archives.

**Confidence:** high on the mechanics; `Confidence: low` on the timeline — 9024 carries five milestones of its own. `Revisit:` when 9024's Progress shows M5–M9 closed.

## 6. Surprises & Discoveries

*None yet — this section grows during execution. Seed note from drafting: the arc this plan inherits (R1-R6) is recorded in 9021's Surprises section and `M5.md`; the pyc-taint hazard's sharpest form — size-preserving constant edits defeating the validator — came from the cloud session's independent reproduction on issue #19, and its promotion target (a shared runner, not a convention paragraph) is adopted here as F3.*

## 7. Awaiting Steering

pre_steering_sha: d1a975a (9021's M5 flip — the branch point this plan shares; rollback target if
any Tier C decision below is rejected)

*Closed by the absorption — neither question outlives this plan. Item 1 (does F1's oracle land in
`build_schema_snapshot.py` or a successor script?) transferred to `9024-port-and-fences`, which now
declares the script and answers it by inspection when it edits it. Item 2 (CI wiring for the shared
runner, a Tier C question about `.github/workflows/**`) does not transfer: the runner was F3, F3 was
absorbed rather than carried, and no plan now proposes invoking a sweep from CI. If one ever does,
that is a fresh Tier C question and belongs to whichever plan asks it.*

## 8. Outcomes & Retrospective

**Cancelled by absorption, 2026-09-14 — one day after it was created.** This plan never executed: F1
through F4 were all unstarted, and its entire commit history was documentation.

**Why it existed, and why that turned out to be wrong.** M5 spent five adversarial rounds past its
Contract because the fidelity discipline was being built inside one milestone's test file with no
written threat model. Splitting it into its own plan was the promotion rule applied correctly — the
same failure shape five times triggers a promotion, and a plan is a legitimate home.

**Why it was absorbed.** Three reasons, in the order they mattered. First, the one part with a live
consumer was the intentional-deviation register, and its consumer is `tests/test_schemas.py` — which
`9024-port-and-fences` already owned. A register in one plan consumed by a comparator in another is
a negotiation, not a design. Second, the plan that introduces the deliberate deviation is the plan
that must register it, and that is 9024's M7 (the absent-role state). Third, roughly half of what
remained — F2's sweep growth, F4's written threat model — hardened a floor that already stands and
would have been executed only after 9024 released the file, so the plan had no path to execution
that did not run through another plan's completion.

**What moved, and where it went.** `scripts/build_schema_snapshot.py` and
`scripts/mutate_m5_contract.py` → 9024's File Scope. The register (F1's second half) → 9024's M7,
declared as `tests/fixtures/intentional_deviations.yaml`. F3's shared sweep runner and its
pyc-taint hazard → the hazard is recorded in 9024's Surprises section; the runner itself was
**dropped**, not carried. F2's 25-row sweep and F4's written threat model were dropped with it.

**What that costs, stated plainly.** The pyc-taint rule survives as a paragraph rather than as a
runner that enforces it, which is the weaker of the two forms the promotion rule names — the next
agent must remember, and a rule that depends on remembering is the one that gets violated. The
six-round M5 record still exists (`9021-relayer-argus-eval-pipeline-notes/M5.md`), but the *next*
round-B now reads 9024's threat model only if someone writes one there. If the fidelity floor
survives a seventh round of the same shape, that is the signal to re-open this decision rather than
to write a third plan.

**What worked.** Writing the register before it was needed meant the deviation had a home the moment
9024 introduced it, so the absorption was a file move rather than a design question.
