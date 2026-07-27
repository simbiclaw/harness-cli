# PEV Loop — the control loop primitive

The Plan → Execute → Verify loop is the atomic unit of work in this repository. Every milestone in every ExecPlan runs through it. It is not a suggestion or a pattern — it is the primitive that gates all state transitions. No milestone flips without traversing all three phases.

The loop is derived from the "Code as Agent Harness" survey (arXiv 2605.18747, UIUC/Meta/Stanford, May 2026), which identifies PEV as the core control mechanism for code-harnessed agent systems: code is planned as a contract, executed in a sandbox, and verified by deterministic sensors before any state transition is permitted.

## The three phases

### 1. Plan — contract before code

**Who:** The session agent (the agent executing the ExecPlan).

**What happens:**
1. Read the active ExecPlan. Read Surprises & Discoveries first.
2. Identify the next unflipped milestone. Read its Acceptance Test.
3. If the test does not exist, create it first, in its own commit. The test must fail before implementation begins (red phase of TDD).
4. If the milestone touches a Tier C path, stop and add to Awaiting Steering before proceeding.

**Invariant:** A plan phase is complete when a failing Acceptance Test exists for the milestone AND all Tier C questions are either resolved or parked in Awaiting Steering.

**Output:** A failing test, committed. The milestone is now "under implementation."

**Governed by:** `docs/PLANS.md` (ExecPlan rubric), `docs/conventions/ask-threshold.md` (Tier C gate), `docs/conventions/verification-floor.md` (test-first rule).

---

### 2. Execute — implement against the contract

**Who:** Subagent A (the implementer). May be the session agent or a dispatched subagent.

**What happens:**
1. Write code that makes the Acceptance Test pass.
2. Run the structural tests. Do not proceed if they fail.
3. Run the gate scripts (if applicable — e.g., GM1-GM6 for rubric compiler items).
4. Write a Decision Log entry for any consequential choice made during implementation.
5. Commit. The commit message includes the `Plan:` and `Decision:` trailers.

**Invariant:** Implementation is never "done" until the Acceptance Test passes AND all structural tests pass. A structural test failure invalidates the implementation.

**Output:** Implementation code, committed. Tests pass when run locally. The milestone is ready for verification.

**Governed by:** `docs/conventions/commit-hygiene.md` (message format, one commit per implementation batch), `docs/conventions/i-dont-know-protocol.md` (Decision Log discipline), `docs/conventions/layering.md` (architecture enforcement).

---

### 3. Verify — falsify, don't confirm

**Who:** Subagent B (the adversarial verifier). B is a different agent than A. B does not receive A's implementation reasoning. B's prompt is adversarial: "prove this doesn't work."

**What happens:**
1. B runs the Acceptance Test in a clean checkout. If it fails, B reports the failure.
2. B designs at least one edge case the test does NOT cover and runs it.
3. B states a verdict: CONFIRMED (test passes + edge cases hold) or REJECTED (test fails OR edge case exposes a defect).
4. On CONFIRMED: the Verifier skill writes "verified at SHA \<sha\>" to the Decision Log. The milestone checkbox flips from `[ ]` to `[x]` in its own commit.
5. On REJECTED: the loop returns to Plan phase — B's findings become the input to the next iteration. The checkbox does NOT flip.

**Invariant:** Verification is adversarial, not confirmatory. B's job is to find what A missed, not to rubber-stamp A's output. A and B never communicate directly.

**Output:** A verdict in the Decision Log. Either CONFIRMED (milestone done, checkbox flipped) or REJECTED (loop restarts at Plan).

**Governed by:** `docs/conventions/verification-floor.md` (adversarial verification rules 1-5, subagent B prompt pattern), `.claude/skills/verifier/` (automated re-run on checkbox flip).

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

- **No checkbox flip without CONFIRMED verdict.** The Verifier skill enforces this automatically.
- **No implementation without a failing test first.** Red commits precede green commits.
- **No A-B communication.** The human or orchestrating agent reads B's output and decides.
- **No silent state transitions.** Every PEV iteration leaves a commit trail with Plan and Decision trailers.
- **No Tier C work without Awaiting Steering resolution.** The ask-threshold gate is a Plan-phase invariant.

## When this rubric is wrong

If a milestone consistently takes more than 3 PEV iterations to converge, the milestone is likely too large — split it. If the adversarial verification repeatedly catches the same class of error across different milestones, the Plan phase is missing a structural guard — promote it (documentation → structural test → hook → CI gate).

---
Last reviewed: 2026-07-23.
