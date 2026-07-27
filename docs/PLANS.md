# PLANS.md — the ExecPlan rubric

This file defines the shape every ExecPlan in this repository takes. Read it once when you are creating or substantially editing a plan; it does not need to stay in session context for routine implementation work.

ExecPlans are the unit of feature-scale work for this project. Architectural decisions that outlive any single plan live in `docs/adr/`. Experiments referenced by Decision Logs live in `docs/experiments/`. Cross-plan retrospectives live in `docs/retrospectives/`. The plan directory is for plans, not for everything.

## What an ExecPlan is

A living document capturing one unit of feature-scale work. Written *before* execution begins, edited continuously *during* execution, archived *after* shipping. It is the single source of truth for: why this work, what it produces, what was decided along the way, what surprised us, and how it ended up.

ExecPlans are not specs handed down. The agent executing the plan also keeps it current. State that lives only in chat or only in git log cannot survive a fresh session.

## File location and lifecycle

A new ExecPlan lives at `docs/exec-plans/active/NNNN-<slug>.md`, where `NNNN` is the next free four-digit number. When work ships, the file moves to `docs/exec-plans/completed/`. If cancelled or absorbed, it moves to `docs/exec-plans/archived/` with a final entry in Outcomes & Retrospective explaining why.

A plan is created when work is at least feature-sized: more than one commit, more than one logical step, or any work touching a Tier C path. One-line typo fixes do not need a plan. A new subcommand, a config schema change, a refactor across modules, anything user-visible: yes.

## Required sections, in order

Empty sections are kept (with an italic note explaining the absence) rather than omitted, so the structure is recognizable to a fresh reader.

### 1. Purpose

One paragraph. Prose. What user-visible problem does this work solve, and why now? If you cannot write this paragraph without referring to internal architecture, the plan is too low-level — split it.

### 2. Big Picture

The architectural view. Which modules in `src/argus/` are touched. What is in scope. What is *deliberately* out of scope (this matters more than what is in). If the work has natural extensions you are choosing not to do, name them here.

For this CLI, also note: which subcommands the work introduces or modifies, what config surface it adds, what files on the user's filesystem it reads or writes.

### 3. Milestones

A numbered list. Each milestone is a coherent shippable unit, typically one to five commits. Each milestone has:

- A one-sentence description in imperative mood ("Add the `argus convert` subcommand").
- An `Acceptance Test:` line naming a runnable test (`tests/test_X.py::test_name`) that proves the milestone is done. The test exists by the time the milestone's checkbox flips. Untested milestones do not flip.
- An optional `Notes:` block for hints, gotchas, or dependencies on other milestones.

For a CLI, the typical Acceptance Test invokes the CLI as a subprocess via `subprocess.run([...])` and asserts on exit code and stdout/stderr. See `docs/conventions/verification-floor.md` for what counts.

Milestones are sized so the agent can complete one without exhausting context. If a milestone is too big, split it.

### 4. Progress

Checklist. The *only* mandatory-bullet section.

```
- [ ] M1: Add the convert subcommand  (created 2026-05-01)
- [x] M2: Add input format detection  (done 2026-05-02 14:30 PT)
- [ ] M3: Add streaming for large files  (in progress, started 2026-05-02 15:00 PT)
```

Each flip of `[ ]` to `[x]` is its own commit (see `commit-hygiene.md`). The PostToolUse hook will remind you. The Verifier subagent re-runs the Acceptance Test before the flip is final.

### 5. Decision Log

Every consequential decision gets an entry. "Consequential" means another reasonable agent could have made a different call, *and* the call affects something downstream. Naming a private helper is not consequential. Choosing `argparse` vs `typer` vs `click` is.

Entries are H3-headed (`### Decision: <one-line>`) and contain a Rationale shaped according to `docs/conventions/i-dont-know-protocol.md`:

- `Source: <URL or path:line>` — cited
- `Experiment: docs/experiments/<name>/` — empirical
- `Confidence: low` plus `Revisit: <milestone or date>` — explicit guess

Forbidden phrases ("standard approach", "best practice", etc.) are enforced by structural test.

If a decision is large enough to outlive this plan — for example, choosing the project's CLI framework, choosing the config file format, choosing the on-disk schema — promote it to an ADR in `docs/adr/` and reference the ADR from the Decision Log entry. ADRs persist; ExecPlans archive.

### 6. Surprises & Discoveries

Anything the plan did not predict. New constraints surfaced during work. Bugs in dependencies. Misunderstandings about an API. Things the next reader picking up this plan should know that they would not derive from the code.

This is also where the Verifier subagent records milestone-flip failures.

### 7. Awaiting Steering

Empty by default. Populated when the plan hits a Tier C decision and pauses for the human. Each entry names the question, the options under consideration, and the deadline by which a non-decision will be treated as one of the options. When the human resolves it, the entry is updated to start with `Awaiting Steering: resolved` (the PreToolUse hook keys on this string).

### 8. Outcomes & Retrospective

Written at completion or cancellation. What shipped vs. what was planned. What took longer than expected and why. What you would do differently. One paragraph minimum; no upper limit. The garbage-collector and doc-gardener skills periodically read these to learn patterns; treat the section as feedback into the harness.

If the plan surfaces patterns that recur across plans, write a cross-plan retrospective to `docs/retrospectives/YYYY-MM-<theme>.md` and link to it.

## Style rules

- **Prose over lists** outside Progress and Milestones. Bullets fragment thought; prose forces you to articulate the *why*. The two exceptions are sections where structure matters more than reasoning.
- **One fenced markdown block max** per file. ExecPlans are read inside other tools that may not handle nested fences gracefully.
- **Self-contained**. Every term of art used in the plan is defined either in the plan or in a linked file. Assume the next reader is a fresh agent or a fresh human with no chat-transcript memory.
- **Edited during execution**, not just at start and end. The Decision Log and Surprises sections grow as work proceeds. Plans untouched for days are suspicious; the doc-gardener flags them.
- **Filename includes a slug**, not just a number. `0023-add-convert-subcommand.md`, not `0023.md`.

## What an ExecPlan is not

- **Not an ADR**. Architectural decisions that outlive a single feature go in `docs/adr/`. The plan's Decision Log can reference an ADR, but doesn't replace one.
- **Not a substitute for code review**. The plan tracks decisions and progress; the Acceptance Tests prove correctness.
- **Not a status report for the human**. The human reads commit messages and Progress checkboxes for status. The plan's audience is the *next agent that picks it up*, which may be a fresh session of yourself.
- **Not write-once**. If the plan turns out wrong about scope or approach, edit it. Mark the change in Decision Log with rationale. Do not invent a new plan to escape an old one's commitments.

## How a session uses an ExecPlan

The session runs each milestone through the PEV loop (`docs/conventions/pev-loop.md`), the atomic control primitive of this repository:

1. **Plan:** Read the most recent active plan end-to-end. Read Surprises & Discoveries first. Identify the next unflipped milestone. Read its Acceptance Test. If the test does not exist, create it first, in its own commit. If the milestone touches a Tier C path, add to Awaiting Steering and end the session.

2. **Execute:** Implement against the test (subagent A). Commit when the test passes, with `Plan:` and `Decision:` trailers. Run structural tests before proceeding. Add consequential decisions to the Decision Log. If architectural, promote to an ADR.

3. **Verify:** Subagent B runs the Acceptance Test in a clean checkout, designs edge cases, and returns CONFIRMED or REJECTED. On CONFIRMED, the Verifier writes "verified at SHA \<sha\>" and the checkbox flips in its own commit. On REJECTED, the loop returns to Plan with B's findings as input.

No checkbox flips without a CONFIRMED verdict. No implementation begins without a failing test. Every PEV iteration leaves a commit trail.

## When this rubric is wrong

The rubric is itself documentation. If you find that the structure here gets in the way more than it helps, flag it as a Surprise in the affected ExecPlan and propose a rubric change. The doc-gardener will surface the proposal. Subject to the same promotion rule as other rules.

Last reviewed: 2026-07-20
