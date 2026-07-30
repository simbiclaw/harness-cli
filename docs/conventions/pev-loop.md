# PEV Loop — the control loop primitive

The Plan → Execute → Verify loop is the atomic unit of work in this repository. Every milestone in every ExecPlan runs through it. It is not a suggestion or a pattern — it is the primitive that gates all state transitions. No milestone flips without traversing all three phases.

The loop is derived from the "Code as Agent Harness" survey (arXiv 2605.18747, UIUC/Meta/Stanford, May 2026), which defines PEV as the control mechanism that transforms debugging from an ad-hoc activity into a formal harness-level control process (§3.4.1). The paper decomposes PEV into four components:

1. **Planning as Contract Formation** (§3.4.2) — a plan defines intended changes as a contract; the failing test is the executable form of that contract.
2. **Sandboxed Execution** (§3.4.3) — the contract is fulfilled in an isolated environment.
3. **Permissioned State Transition** (§3.4.3) — no state change (commit, checkbox flip, milestone advance) occurs without verification gating it.
4. **Verification through Deterministic Sensors** (§3.4.4) — objective, repeatable checks (linters, unit tests, static analyzers) gate every state transition.

This repository implements all four components. It also extends the paper's model in one deliberate way: the Verify phase adds an **adversarial verifier** (subagent B) beyond deterministic sensors. The paper treats verification as purely mechanical; we add a second, independent agent whose job is to falsify — designing edge cases no sensor was configured to catch. The deterministic sensors are the floor; adversarial verification is the ceiling.

## The three phases

### 1. Plan — contract formation

The Plan phase is **Planning as Contract Formation** (paper §3.4.2). The milestone's Acceptance Test is the contract: it defines what "done" means in machine-checkable form before any implementation code is written. A plan that cannot be expressed as a failing test is not a plan — it is a wish.

**Who:** The session agent (the agent executing the ExecPlan).

**What happens:**
1. Read the active ExecPlan. Read Surprises & Discoveries first.
2. Identify the next unflipped milestone. Read its Acceptance Test.
3. **Behavioral contract:** If the Acceptance Test does not exist, create it first, in its own commit. The test must fail before implementation begins (red phase of TDD). **The failing test IS the contract.** A behavioral test verifies that the thing being built works correctly — application logic, functional behavior, business rules. For application plans, behavioral tests live in `tests/`. For harness plans (where the harness is the application), behavioral tests live wherever the harness code lives (typically `.claude/tests/`). The distinction is purpose, not directory. **Every milestone must have a behavioral test.** If a milestone genuinely cannot have one (pure structural/convention change with no functional behavior), the milestone must state this explicitly with a reason: `Behavioral Test: none — <justification>`. Absence without justification is a Plan-phase defect.
4. **Structural contract:** If the milestone introduces or modifies a harness rule (new convention, promoted structural test, hook), that structural test must be created and failing before implementation begins. Same red→green discipline as the behavioral test. A structural test enforces a convention about how things are built — commit format, layering, decision log discipline. It does not test application behavior; it tests that the harness rules are followed. A milestone that changes harness behavior without a corresponding structural test is incomplete at Plan phase. If no structural test is needed (the milestone does not touch any harness rule), the milestone must state this explicitly: `Structural Test: none — <justification>`.
5. If the milestone touches a Tier C path, stop and add to Awaiting Steering before proceeding.

**Invariant:** A plan phase is complete when a failing Acceptance Test AND any required structural tests exist for the milestone, AND all Tier C questions are either resolved or parked in Awaiting Steering. Both coverage dimensions must be represented before the first line of implementation code is written.

**Output:** Failing tests — both behavioral and structural — committed. The milestone is now "under implementation."

**Governed by:** `docs/PLANS.md` (ExecPlan rubric), `docs/conventions/ask-threshold.md` (Tier C gate), `docs/conventions/verification-floor.md` (test-first rule).

---

### 2. Execute — implement against the contract

**Who:** Subagent A (the implementer). May be the session agent or a dispatched subagent.

**What happens:**
1. Write code that makes the Acceptance Test pass.
2. Run the **deterministic sensors** (paper §3.4.4): structural tests, linters (`ruff check`), and format checkers (`ruff format --check`). Do not proceed if any fail. These are the objective, repeatable floor — they must pass every time, no exceptions.
3. Run the gate scripts (if applicable — e.g., GM1-GM6 for rubric compiler items).
4. Write a Decision Log entry for any consequential choice made during implementation.
5. Commit. The commit message includes the `Plan:` and `Decision:` trailers.

**Invariant:** Implementation is never "done" until the Acceptance Test passes AND all deterministic sensors pass. A structural test or lint failure invalidates the implementation regardless of the Acceptance Test result.

**Output:** Implementation code, committed. Deterministic sensors all green. The milestone is ready for verification.

**Governed by:** `docs/conventions/commit-hygiene.md` (message format, one commit per implementation batch), `docs/conventions/i-dont-know-protocol.md` (Decision Log discipline), `docs/conventions/layering.md` (architecture enforcement).

---

### 3. Verify — deterministic sensors + adversarial falsification

Verification operates on two intersecting axes. **Both axes must pass for CONFIRMED.**

**Axis 1 — How verification happens (paper §3.4.4 + our extension):**

| Tier | Mechanism | Description |
|---|---|---|
| **Tier 1** | Deterministic sensors | Objective, repeatable checks (structural tests, linters, Acceptance Test). No human judgment needed to interpret a failure. The floor. |
| **Tier 2** | Adversarial falsification | Subagent B actively tries to break the implementation, designing edge cases no pre-configured sensor was programmed to catch. Our extension beyond the paper. The ceiling. |

**Axis 2 — What is being tested (purpose, not directory):**

| Coverage | Purpose | Example |
|---|---|---|
| **Structural** | Harness convention compliance — did we build it right? | Commit format, layering rules, decision log discipline, forbidden phrases |
| **Behavioral** | Functional correctness — does it actually work? | CLI exits with code 0, state.json schema validates, tmux script accepts --plan |

A milestone with all structural coverage passing but a failing Acceptance Test is not done — the harness is clean but the feature is broken. A milestone with all behavioral coverage passing but structural tests failing is not done — the feature works but the harness is violated. CONFIRMED requires both coverage dimensions to pass through both verification tiers.

**Who:** Subagent B (the adversarial verifier). B is a different agent than A. B does not receive A's implementation reasoning. B's prompt is adversarial: "prove this doesn't work." A and B never communicate directly.

**What happens:**
1. B checks out A's implementation commit in a clean worktree.
2. **Deterministic sensors — structural coverage:** B runs the structural tests (`.claude/tests/`), linters (`ruff check`), and format checkers (`ruff format --check`). Any failure → REJECTED.
3. **Deterministic sensors — behavioral coverage:** B runs the Acceptance Test. If it fails → REJECTED.
4. **Adversarial — behavioral coverage:** B designs at least one edge case the Acceptance Test does NOT cover and runs it. These are creative probes that no deterministic sensor was configured to catch.
5. B states a verdict: CONFIRMED (both tiers pass, both coverage dimensions pass) or REJECTED (any failure).
6. On CONFIRMED: the Verifier skill writes "verified at SHA \<sha\>" to the Decision Log. The milestone checkbox flips from `[ ]` to `[x]` in its own commit.
7. On REJECTED: the loop returns to Plan phase — B's findings become the input to the next iteration. The checkbox does NOT flip.

**Invariant:** Verification is adversarial, not confirmatory. B's job is to find what A missed, not to rubber-stamp A's output. The deterministic sensors catch what they were configured to catch; B catches what no sensor was configured to catch. Both structural and behavioral coverage are required — neither alone is sufficient.

**Output:** A verdict in the Decision Log. Either CONFIRMED (milestone done, checkbox flipped) or REJECTED (loop restarts at Plan).

**Governed by:** `docs/conventions/verification-floor.md` (adversarial verification rules 1-5, subagent B prompt pattern), `.claude/skills/verifier/` (automated re-run on checkbox flip).

---

## The three agents — persistence is the prerequisite for closure

The PEV loop is not a sequence of function calls. It is a **closed loop** carried by three persistent agents. They are launched once per ExecPlan and remain resident across all milestones and all iterations. Without persistence, there is no loop — there is only a pipeline with no feedback arc.

### P — Planner

P receives the milestone spec and produces the contract: a failing test. On REJECTED, P receives V's findings and **updates the contract** — rewriting or extending the test to cover what V found. P does not implement; P only plans. P is the entry point for every iteration of a milestone.

### E — Executor

E receives the contract from P and produces an implementation commit. On repair, E receives updated instructions from P (after V's REJECTED findings were incorporated) and re-implements. E does not plan; E does not verify. E only executes.

### V — Verifier

V receives E's commit SHA and attempts to falsify it. V writes a verdict to the implementation notes. If REJECTED, V's findings flow **back to P** — not to a log file, not to a human (unless semantic). P reads V's findings, updates the contract, and hands off to E. This is the feedback arc that closes the loop.

### Why persistence matters

If P, E, and V are re-created per milestone or per iteration, the feedback arc breaks:

- A new P has no memory of what contract it wrote last time.
- A new E has no memory of what it implemented and why.
- V's findings land in a notes file that nobody reads because there's no persistent P to consume them.

The notes file is the **persistent state** that survives across agent invocations. But the agents themselves must persist to **consume** that state. A REJECTED verdict written to notes, read by P, incorporated into a new contract, handed to E, and re-verified by V — that is one turn of the closed loop. Without persistent P and E, the loop opens at the V→P arc.

### Enforcement

The orchestrator or arbiter must configure three named, persistent agents per ExecPlan. The agents must remain resident from plan start to plan completion. This requirement is enforced by:

- **Structural test:** `.claude/tests/test_pev_agent_persistence.py` — verifies that the orchestrator defines three persistent agent roles and that the V→P→E feedback arc is described in the orchestrator's instructions.
- **Documentation:** This section.

If an ExecPlan completes milestones without persistent P/E/V agents, the feedback arc was never closed — V's findings were written but never consumed. The structural test detects this by checking for per-milestone agent instantiation patterns (anti-pattern) and the absence of persistent role definitions.

### Commit authority — the Arbiter is the sole committer

**Only the Arbiter commits.** P, E, and V never commit. This is not a convention — it is a structural invariant. The commit graph is the Arbiter's sole responsibility.

P writes the contract (test file). E writes the implementation. V writes the verdict (notes). None of them commit. The Arbiter makes exactly two commits per milestone:

**RED commit — contract before implementation.** After P completes the Plan phase (test file exists, fails), the Arbiter commits the failing test alone. Nothing else. This preserves the TDD red→green discipline and satisfies the test-first gate (`test_test_first_gate.py`).

```
test(m<N>): <milestone title> — RED

Failing acceptance test for M<N>.

Plan: docs/exec-plans/active/<plan-id>.md#milestone-<N>
Decision: test-first
```

**GREEN commit — verdict + implementation + checkbox flip.** After V reaches CONFIRMED, the Arbiter bundles E's implementation, V's verdict notes, and the checkbox flip into a single commit. The test that was RED is now GREEN.

```
flip(m<N>): <milestone title>

CONFIRMED by V at <sha>.

Plan: docs/exec-plans/active/<plan-id>.md#milestone-<N>
Decision: test-first, adversarial-verification-passed
```

**Why two commits, not one:**

- **Preserves TDD discipline.** The test-first gate can verify that the RED commit (test) precedes the GREEN commit (implementation). One monolithic commit would erase the red→green boundary.
- **Reviewable.** The RED commit contains only test changes. The GREEN commit contains implementation + verdict + flip. Each is small enough to review.
- **Rollback safety.** If the implementation is wrong but the contract is right, revert only the GREEN commit and re-execute. If the contract is wrong, revert both.

**Why the Arbiter, not P/E/V:**

- **Accountability.** Every commit traces to the Arbiter. P, E, and V produce working-tree artifacts; the Arbiter decides when they are committed.
- **Consistency.** No risk of P's RED commit and E's GREEN commit diverging — the Arbiter controls the commit sequence from a single working tree.
- **No dangling WIP commits.** If V REJECTS, the Arbiter discards uncommitted changes and restarts. git history stays clean.

**Enforcement.** The pre-tool-use hook blocks `git commit` commands from non-Arbiter sessions. P, E, and V sessions do not have `PEV_ARBITER=true` set, so Guard 5 (harness-branch guard) and a new commit-authority guard block their commits. The structural test `test_commit_authority.py` verifies that no commit in the current branch was authored by a subagent.

---

## Loop boundaries

One PEV iteration is bounded by:

| Boundary | Rule |
|---|---|
| **Start** | An unflipped milestone with a failing Acceptance Test |
| **End** | Subagent B CONFIRMED verdict in the Decision Log, checkbox flipped |
| **Restart** | Subagent B REJECTED verdict — return to Plan with B's findings as input |
| **Block** | Tier C question unresolved — park in Awaiting Steering, end session |

A milestone may take multiple PEV iterations to converge. Each iteration produces a commit (or set of commits). The Decision Log records the reason for each restart.

## Permissioned State Transition

**Permissioned State Transition** (paper §3.4.3) is the principle that no state change in the harness occurs without verification gating it. The paper names this as a first-class architectural component alongside contract formation and deterministic verification. In this repository, it is enforced through four concrete mechanisms:

| Mechanism | What it gates | Where it is enforced |
|---|---|---|
| **Checkbox flip gate** | `[ ]` → `[x]` only on CONFIRMED verdict | `pre_tool_use.py` (Guard 0: single-flip, Guard 1: uncommitted-flip blocker); Verifier skill |
| **Tier C gate** | Plan phase may not proceed past an unresolved Tier C question | `docs/conventions/ask-threshold.md`; session agent must park in Awaiting Steering |
| **Loop closure gate** | M(N+1) may not enter Plan phase until M(N) reaches `confirmed` | `.claude/tests/test_pev_loop_closure.py` (structural test); `.pev-signals/state.json` (runtime checkpoint) |
| **Arbiter autonomy boundary** | Arbiter may auto-execute mechanical actions; semantic failures and Tier C edits pause for human | `pre_tool_use.py` (`PEV_ARBITER` exemption); `pev_subagent_adversarial.sh` Arbiter prompt |

These are not four separate rules — they are four instantiations of the same principle: **state transitions are gated.** A checkbox flip, a milestone advance, a Tier C bypass, an arbiter action — each is a state transition, and each requires a specific permission derived from a verification outcome.

The structural test for loop closure (`.claude/tests/test_pev_loop_closure.py`) was promoted from documentation to structural test on 2026-07-29 under the promotion rule. The other three mechanisms remain at their current enforcement levels until two violations across different ExecPlans trigger further promotion.

## The full ExecPlan is a pipeline of PEV loops

Each milestone is an independent PEV loop. Milestones are topologically ordered by dependency — a milestone depending on another cannot begin its Plan phase until the prerequisite's Verify phase completes (signal ID lock, or checkbox flip).

This maps to the `pipeline()` pattern:

```
pipeline(MILESTONES,
  m => pev(m),                                          // Plan + Execute (subagent A)
  result => pev_verify(result)                          // Verify (subagent B)
)
```

Where `pev(m)` = Plan (create failing test) → Execute (implement until test passes) → hand off to B. And `pev_verify(result)` = B runs the test + edge cases → CONFIRMED or REJECTED.

No barrier exists between stages: milestone 3 can be in verification while milestone 4 is still in implementation. The only constraint is topological — a milestone's Plan phase must wait for its dependency's Verify phase to complete.

## Where the PGE loop fits

The Plan-Generate-Evaluate loop (rubric compiler, `docs/PRD/SPEC-rubric-compiler-harness.md`) is a specialized variant of PEV designed for non-executable artifacts (compiled rubric specifications). It substitutes the Execute phase with Generator proposal (Phase A) and Evaluator adversarial review (§3.3), and adds a deterministic acceptance gate (§3.4) that disposes where the Evaluator authors.

| Phase | PEV (general) | PGE (rubric compiler variant) |
|---|---|---|
| **Plan** | Create failing test, check Tier C | Planner delegation packet, dependency scan, DAG dispatch |
| **Execute** | Implement against test | Generator drafts proposal, runs gate script locally |
| **Verify** | B runs test + edge cases | Evaluator writes review; Gate runs G1-G5+GM; converge or park |

The PGE variant exists because compiled rubric specifications cannot be executed — their quality dimensions (grounding fidelity, checkability honesty, residue coverage) require referent-cited adversarial review rather than execution-based verification. PEV is the general primitive; PGE is the specialization for non-executable artifacts.

## Hard prohibitions

These are the Permissioned State Transition rules in negative form — each prohibition is a state transition that must not occur without its corresponding gate.

- **No checkbox flip without CONFIRMED verdict.** The Verifier skill enforces this automatically.
- **No implementation without a failing test first.** Red commits precede green commits (Contract Formation, §3.4.2).
- **No A-B communication.** The human or orchestrating agent reads B's output and decides.
- **No silent state transitions.** Every PEV iteration leaves a commit trail with Plan and Decision trailers.
- **No Tier C work without Awaiting Steering resolution.** The ask-threshold gate is a Plan-phase invariant.

## Milestone constraint fields (optional, machine-readable)

Milestones may include constraint fields for automated enforcement. These are optional — milestones without them work as before (backward-compatible).

```
Acceptance Test: tests/test_X.py::test_name
Allowed Reads: src/argus/core/**, INTENTS/**
Allowed Writes: src/argus/core/module.py, tests/test_module.py
Requires: M2, M3
Risk Tier: B
```

- **`Allowed Reads`**: Comma-separated glob patterns for paths the milestone may read. Default: any path.
- **`Allowed Writes`**: Comma-separated glob patterns for paths the milestone may modify. Default: any path. Enforced by the pre-execution gate (`.claude/hooks/pre_execution_gate.py`).
- **`Requires`**: Comma-separated milestone IDs (e.g., `M2, M3`) that must complete before this milestone begins its Plan phase. Referenced milestones must have lower numbers.
- **`Risk Tier`**: `A` (proceed silently), `B` (proceed and flag), or `C` (stop and ask). Maps to `docs/conventions/ask-threshold.md` tiers.

Validated by `.claude/tests/test_milestone_constraints.py`.

## Arbiter autonomy

The PEV tmux arbiter (`pev_subagent_adversarial.sh`) runs as a Claude Code session with `PEV_ARBITER=true` set. The hooks (`pre_tool_use.py`) recognize this and grant autonomy for PEV coordination operations.

### Allowed autonomously

- Flip milestone checkboxes in ExecPlan files (`[ ]` → `[x]`)
- Commit verdicts and checkpoint state
- Edit `.pev-signals/` files (state.json, violations/)
- Write and edit milestone implementation notes files
- Send repair instructions to subagent A
- Re-trigger verification after repair

### Blocked (pauses for human)

- Semantic failures (`[human-todo]` entries) — design judgment, subjective quality, or human preference questions
- Tier C paths outside `.pev-signals/` and ExecPlan notes — sensitive path edits still require steering

### How it works

1. The tmux script exports `PEV_ARBITER=true` in the arbiter's environment.
2. `pre_tool_use.py` checks `_is_arbiter()` before applying Guard 0 (single-flip) and Guard 1 (uncommitted-flip blocker).
3. When `PEV_ARBITER=true`, the arbiter can flip checkboxes and edit PEV coordination files without triggering guard blocks.
4. Non-arbiter sessions are still subject to all existing guards.

`Source: docs/exec-plans/active/9006-pev-tmux-convergence.md#milestone-3` · enforced by `.claude/tests/test_arbiter_autonomy.py`.

## When this rubric is wrong

If a milestone consistently takes more than 3 PEV iterations to converge, the milestone is likely too large — split it. If the adversarial verification repeatedly catches the same class of error across different milestones, the Plan phase is missing a structural guard — promote it (documentation → structural test → hook → CI gate).

---
Last reviewed: 2026-07-29.
