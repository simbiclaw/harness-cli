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

### Hook semantics: authority-bearing, not capability-substituting

The original Verifier skill design said "triggered automatically by the PostToolUse hook." But hooks follow a strict allow/block contract — JSON `{"continue": true|false}` plus output text. A hook cannot invoke a skill; it can only emit an instruction the model *may* follow. The verifier's invocation channel was always **advisory-stochastic**, never deterministic.

This resolves the retrospective's indeterminacy about "either wasn't invoked or too weak": the invocation channel never had blocking semantics. The model could (and apparently did) ignore the instruction to run the verifier.

**The correct architecture** is M4's inversion — **deterministic denial replaces stochastic invocation**:

| Pattern | What it tries to do | What hooks allow |
|---|---|---|
| Capability-substituting | Hook triggers verification | ❌ Not possible — hooks can't summon skills |
| Authority-bearing | Hook blocks flip unless CONFIRMED ledger entry exists | ✅ The hook contract: `{"continue": false}` |

The adversarial verification gate (M6) and repair feedback gate embody this pattern: they don't try to *make* anything happen. They check for evidence and **deny** if absent. This is the general principle for hook design: hooks guard state transitions, they don't initiate work.

### Absolute hook paths pointed at wrong repo

The `.claude/settings.json` hook commands used absolute paths pointing to `/Users/prometheus/workspace/argus/.claude/hooks/...` — a different repository. On any other checkout (CI, worktree, container), hooks would either fail to launch or run against the wrong repo's state. This was likely a contributing cause of the 9004 execution mistakes. Fixed by switching to repo-relative paths and adding a structural test (`test_hook_paths_portable.py`) that prohibits absolute paths in any hook command.

### Missing hook registration

`pre_execution_gate.py` (M2) was implemented and tested, but never registered in `settings.json`. The gate existed on disk but never intercepted any tool calls. Fixed by adding it as a PreToolUse hook for Edit/Write/MultiEdit matchers.

## 7. Awaiting Steering

*Empty — no Tier C questions at plan creation.*

## 8. Outcomes & Retrospective

All 10 milestones shipped. The PEV loop evolved from 80% documentation / 20% enforcement to a structurally enforced control loop:

- **Plan phase** gained machine-readable constraints (Allowed Reads/Writes, Requires, Risk Tier) validated by structural test and enforced by pre-execution gate hook.
- **Execute phase** gained worktree sandboxing (implementation in `/tmp/impl-<sha>/`), implementation notes (per-milestone structured markdown with typed entries and devgrid fields), and test-first gate (structural test verifies tests precede src/ changes).
- **Verify phase** gained adversarial verification gate (structural test verifies CONFIRMED verdict before checkbox flip) and autonomous repair loop (failure classification → retry/human-todo/update-constraints).
- **Orchestration** gained a Dynamic Workflow pipeline script (`pev_orchestrator.js`) that runs milestones through pevPlan → pevExecute → pevVerify → pevRepair.

25 E2E integration tests pass. 10 orchestrator structural tests pass. 11 repair loop tests pass. 7 worktree tests pass. 5 gate tests pass. All backward-compatible: old ExecPlans without constraint fields work as before.

### Post-evolution follow-ups

- **Repair feedback gate** (post-evolution): pushed the repair loop's write operation from documentation to structural test layer. `test_repair_feedback_gate.py` verifies every REJECTED verdict has the required notes entry (`[human-todo]` for semantic, `[deviation]` for constraint-violation). Added `write_notes_entry()` to `pev_repair.py` so agents can persist feedback in one call.

- **Hook path portability fix**: settings.json hook commands used absolute paths to a different repo (`/Users/prometheus/workspace/argus/`). Changed to repo-relative paths; added `test_hook_paths_portable.py` structural test. Registered `pre_execution_gate.py` in settings.json (was implemented but never wired).

### Architectural principle: hooks guard state transitions, they don't initiate work

The original Verifier design tried to use a hook to trigger verification. Hooks return `{"continue": true|false}` — they are **authority-bearing**, not **capability-substituting**. The correct pattern, used by every gate in this plan, is **deterministic denial**: the hook/structural test checks for evidence and denies if absent. It never tries to make something happen. This is captured as a generalizable rule: if you find yourself wanting a hook to *do* something, invert the design — make it *block* until evidence that the something was done exists.
