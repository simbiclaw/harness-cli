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
- `scripts/run_sweep.sh` (new — the shared sweep runner: pyc purge + `PYTHONDONTWRITEBYTECODE=1` + collection-error grading, one way to run a sweep)
- `docs/experiments/9022-fidelity-threat-model/**` (new — the written threat model)
- `src/argus/types/pipeline.py`, `scripts/build_schema_snapshot.py`, `tests/test_schemas.py`, `scripts/mutate_m5_contract.py` — **TBD — will be filled when 9021 completes and ceases to own these paths** (declaring them now trips `test_plan_collisions.py` against the active 9021; the deferral is the negotiation, and this plan does not open its first milestone until then)

## 3. Milestones

### F1 — Raw callable + MRO-base facts, filter dropped (the round-5 repair, carried)

Record every callable on every contract class (name + defining module, descriptor-unwrapped) and every MRO base name, for models and enums alike; diff mechanically with no defining-module filter — same interpreter both sides, so pydantic/enum machinery cancels. Closes the round-5 survivor classes: `model_post_init`, laundered `_missing_`, plain-mixin `__setattr__`. Fixture regenerated; mirrors extended; named regression pins the new forms.

`Acceptance Test:` `tests/test_schemas.py::test_the_checks_can_fail` extended plants — `model_post_init` zeroing scores, post-class `_missing_` with forged `__module__`, plain mixin `__setattr__` — each red via the new facts. (Test file path defers to the 9021-completion split; see File Scope TBD.)

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

### Decision: Fidelity tests stay in `tests/test_schemas.py` until 9021 completes

**Rationale:** splitting them now would trip `test_plan_collisions.py` against active 9021 and force an amendment to a plan mid-flight — the pattern `9004-execution-mistakes` identifies. The TBD in File Scope is the negotiation; F1 opens only after 9021 archives.

**Confidence:** high on the mechanics; `Confidence: low` on the timeline — 9021 has twenty-one open milestones. `Revisit:` when 9021's Progress shows M7-M22 closed.

## 6. Surprises & Discoveries

*None yet — this section grows during execution. Seed note from drafting: the arc this plan inherits (R1-R6) is recorded in 9021's Surprises section and `M5.md`; the pyc-taint hazard's sharpest form — size-preserving constant edits defeating the validator — came from the cloud session's independent reproduction on issue #19, and its promotion target (a shared runner, not a convention paragraph) is adopted here as F3.*

## 7. Awaiting Steering

1. **Does F1's oracle land in `build_schema_snapshot.py` or a successor script?** The current builder is 9021-owned; F1 opens after 9021 archives, at which point the question answers by inspection. Default if not decided: extend in place. — deadline: 9021 completion.
2. **CI wiring for the shared runner.** Whether `.github/workflows/**` should invoke `run_sweep.sh` on PRs touching contract files is a Tier C question (workflow changes are sensitive-path). Default if not decided: local-only until someone asks for CI. — deadline: F3 completion.

## 8. Outcomes & Retrospective

*Written at completion or cancellation.*
