# 9005 — PEV Loop Evolution: Governed State Transitions

## 1. Purpose

harness-cli's PEV loop is currently 80% documentation and 20% enforcement. Test-first is not enforced, Execute runs in the working tree (no sandbox), adversarial verification is not checked before checkbox flips, and repair feedback is free-text Surprises. This plan evolves the PEV loop to the paper's model (arXiv 2605.18747 §3.4) of governed state transitions: plans as contracts, execution sandboxed, verification by deterministic sensors, termination governed by verification.

## 2. Big Picture

Four interdependent changes to the PEV loop, built in a single ExecPlan:

1. **Machine-readable milestone constraints** — ExecPlan milestones gain optional `Allowed Reads`, `Allowed Writes`, `Requires`, `Risk Tier` fields. A pre-execution gate enforces them.
2. **Implementation notes** — Per-milestone structured markdown log replacing free-text Surprises for deviation tracking. Entries: plan-confirmed, discovery, deviation, human-todo.
3. **Execute-phase worktree sandbox** — Implementer works in `/tmp/impl-<sha>/`, verified state merges back after B CONFIRMED.
4. **Workflow pipeline orchestrator + autonomous repair loop** — Dynamic Workflow `pipeline()` orchestrates PEV; REJECTED verdicts trigger autonomous repair with structured failure classification.

**Deliberately out of scope:**
- Container/VM sandboxing (git worktree only, per user decision)
- PGE rubric compiler changes (PEV is the general primitive; PGE is a separate specialization)
- Container-level permission tiers (Tier A/B/C escalation already exists)

`Source: docs/conventions/pev-loop.md · docs/conventions/verification-floor.md · arXiv 2605.18747 §3.4`

## 3. Milestones

### M1 — Machine-readable milestone constraints

Extend ExecPlan milestone format with optional constraint fields (`Allowed Reads`, `Allowed Writes`, `Requires`, `Risk Tier`). Backward-compatible: milestones without fields work as before. Structural test validates field values.

`Acceptance Test:` `.claude/tests/test_milestone_constraints.py::test_constraints_parse_and_validate`

### M2 — Pre-execution constraint gate

Hook that reads milestone constraints and blocks Edit/Write outside `Allowed Writes`. Follows existing `pre_tool_use.py` pattern (JSON stdin, JSON stdout, `continue: false` to block).

`Acceptance Test:` `.claude/tests/test_pre_execution_gate.py::test_gate_blocks_overreach`

### M3 — Implementation notes convention

Define per-milestone structured log format at `docs/exec-plans/active/NNNN-notes/M<N>.md`. Entry types: plan-confirmed, discovery, deviation (with devgrid sub-fields), human-todo.

`Acceptance Test:` `tests/test_conventions_exist.py::test_implementation_notes_convention_exists`

### M4 — Implementation notes structural test

Validate notes exist for milestones with deviations and have valid format (entry types, devgrid fields).

`Acceptance Test:` `.claude/tests/test_implementation_notes.py::test_notes_valid_when_deviations_exist`

### M5 — Test-first gate

Structural test verifying test files are committed before src/ changes for each milestone. Uses git log temporal ordering.

`Acceptance Test:` `.claude/tests/test_test_first_gate.py::test_test_first_enforced`

### M6 — Adversarial verification gate

Structural test verifying CONFIRMED verdict exists in Decision Log before checkbox flip, with staleness check.

`Acceptance Test:` `.claude/tests/test_adversarial_verification_gate.py::test_confirmed_before_flip`

### M7 — Execute-phase worktree sandbox

Worktree utilities: `create_worktree`, `run_tests_in_worktree`, `merge_worktree`, `remove_worktree`. Implementer works in isolated `/tmp/impl-<sha>/`.

`Acceptance Test:` `.claude/tests/test_pev_worktree.py::test_worktree_isolation_and_merge`

### M8 — Workflow pipeline orchestrator

Dynamic Workflow script using `pipeline()` pattern: `pipeline(MILESTONES, pev_plan, pev_execute, pev_verify)`. No new subagent type.

`Acceptance Test:` `.claude/tests/test_pev_orchestrator.py::test_pipeline_runs_pev_phases`

### M9 — Autonomous repair loop

On REJECTED: read B's structured notes, classify failure (mechanical/semantic/constraint-violation), decide next action. Human only for `needs-human-judgment`.

`Acceptance Test:` `.claude/tests/test_pev_repair.py::test_repair_classifies_and_routes`

### M10 — Integration and E2E validation

End-to-end test of complete evolved PEV loop. Update cross-references in pev-loop.md, PLANS.md, CLAUDE.md.

`Acceptance Test:` `tests/integration/test_pev_evolved_e2e.py::test_full_pev_pipeline`

## 4. Progress

```
- [x] M1: Machine-readable milestone constraints  (done 2026-07-28)
- [x] M2: Pre-execution constraint gate  (done 2026-07-28)
- [x] M3: Implementation notes convention  (done 2026-07-28)
- [x] M4: Implementation notes structural test  (done 2026-07-28)
- [x] M5: Test-first gate  (done 2026-07-28)
- [x] M6: Adversarial verification gate  (done 2026-07-28)
- [x] M7: Execute-phase worktree sandbox  (done 2026-07-28)
- [x] M8: Workflow pipeline orchestrator  (done 2026-07-28)
- [x] M9: Autonomous repair loop  (done 2026-07-28)
- [x] M10: Integration and E2E validation  (done 2026-07-28)
```

## 5. Decision Log

### Decision: git worktree for Execute sandbox
`Source: user decision (interview Q1) — lightweight, uses existing git infrastructure, no container runtime needed`

### Decision: markdown implementation notes, HTML template as visual reference
`Source: user decision (interview Q2) — B1 template shows structure (plan-confirmed/discovery/deviation/human-todo + devgrid), output is markdown not HTML`

### Decision: full declarative constraints
`Source: user decision (interview Q3) — Allowed Reads, Allowed Writes, Requires, Risk Tier as machine-readable fields`

### Decision: autonomous repair loop
`Source: user decision (interview Q4) — agent reads B's structured notes, diagnoses, decides; human only for needs-human-judgment`

### Decision: workflow pipeline as orchestrator
`Source: user decision (interview Q5) — Dynamic Workflow pipeline() pattern, no new subagent type`

### Decision: all-at-once single ExecPlan
`Source: user decision (interview Q6) — four changes are interdependent, one coherent system`

## 6. Surprises & Discoveries

*Empty — will be populated during implementation.*

## 7. Awaiting Steering

*Empty — no Tier C questions at plan creation.*

## 8. Outcomes & Retrospective

All 10 milestones shipped. The PEV loop evolved from 80% documentation / 20% enforcement to a structurally enforced control loop:

- **Plan phase** gained machine-readable constraints (Allowed Reads/Writes, Requires, Risk Tier) validated by structural test and enforced by pre-execution gate hook.
- **Execute phase** gained worktree sandboxing (implementation in `/tmp/impl-<sha>/`), implementation notes (per-milestone structured markdown with typed entries and devgrid fields), and test-first gate (structural test verifies tests precede src/ changes).
- **Verify phase** gained adversarial verification gate (structural test verifies CONFIRMED verdict before checkbox flip) and autonomous repair loop (failure classification → retry/human-todo/update-constraints).
- **Orchestration** gained a Dynamic Workflow pipeline script (`pev_orchestrator.js`) that runs milestones through pevPlan → pevExecute → pevVerify → pevRepair.

25 E2E integration tests pass. 10 orchestrator structural tests pass. 11 repair loop tests pass. 7 worktree tests pass. 5 gate tests pass. All backward-compatible: old ExecPlans without constraint fields work as before.
