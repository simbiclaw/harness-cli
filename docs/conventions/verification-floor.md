# Verification Floor

No milestone is done until proof of behavior exists. Every milestone in every ExecPlan has an `Acceptance Test:` line naming a specific runnable test. The test is written first or in the same commit as the implementation. Untested milestones cannot have their checkbox flipped.

## Per-layer test floor

What "test-floor-met" means depends on the layer. The definitions below are the minimum; exceeding them is fine, falling short is not.

### Repo

Every Repo method has a test that **fails before implementation and passes after**. The test exercises the method's external contract: for a read method, assert on the returned shape and null-vs-data discrimination; for a write method, assert on the persisted state being retrievable and correct. Repo never throws on "not found" — returns a typed null-or-not result. Tests assert this.

### Service

Every Service function is exercised by a test that asserts on its **return type** and at least one **specific value transformation** (given known inputs, the output has this specific property). Service is pure with respect to I/O — functions take Types and return Types. Tests exercise that purity: no external calls, no side effects.

### Runtime

Every job has an integration test covering **one happy path and one failure path**. Happy path: the job completes and produces the expected output. Failure path: the job encounters a retryable failure, the retry policy fires, and the job either succeeds or surfaces the failure correctly (no silent hangs, no partial output).

### UI

Every interactive element has a **stable test selector** (data attribute, not CSS class or nth-child) and at least one **click-target test** that asserts the element responds to interaction. Stable selectors use `data-testid` or equivalent; implementation-detail selectors (CSS class, DOM position) are not stable.

## Externally observable property

For a CLI tool, the canonical Acceptance Test invokes the CLI as a subprocess and asserts on the externally observable surface:

```python
import subprocess


def test_convert_handles_csv_input(tmp_path):
    input_file = tmp_path / "input.csv"
    input_file.write_text("a,b\n1,2\n")

    result = subprocess.run(
        ["uv", "run", "argus", "convert", str(input_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "1,2" in result.stdout
    assert result.stderr == ""
```

What counts as "externally observable":

- Exit code (`returncode`).
- Bytes on stdout (parseable by callers; this is a public contract).
- Bytes on stderr (format consistency still matters).
- Files written to disk under paths the CLI claims to write to.
- Side effects on resources the CLI claims to manage.

What does *not* count as the sole acceptance criterion:

- "The function returns the expected dict." Internal-API tests are useful but cannot be the sole proof.
- "Mock was called with these arguments." Mocks prove the inside, not the outside.
- "No exception was raised." Silent success is not proof.

## External integrations require recorded transcripts

If the system calls a third-party API, the Acceptance Test records the exchange (via `vcrpy`, `respx`, or equivalent) and commits the recording to `tests/cassettes/`. Live-network tests do not count toward the verification floor. The recorded fixture is treated as part of the test and reviewed like any other test code.

## Test layout

```
tests/
├── unit/                    # Internal-API tests. Fast. Run on every change.
├── integration/             # Subprocess invocations. The verification floor.
│   └── cassettes/           # Recorded HTTP for tests that need network.
└── conftest.py
```

The Acceptance Test for a milestone almost always lives in `tests/integration/`.

## Flakes are bugs

A flaky test does not pass for milestone purposes. Re-running CI does not flip the milestone checkbox. If a test is flaky because it depends on real time, real network, real filesystem race conditions, or random data, the test itself is wrong; fix the test.

## Adversarial verification

Every ExecPlan is executed by two independent subagents in an adversarial loop. The implementer (subagent A) writes code; the verifier (subagent B) attempts to **falsify** A's delivery — not confirm it. B's job is to find what A missed, not to rubber-stamp A's output.

### Five rules

| # | Rule | Enforced by |
|---|---|---|
| 1 | **Test-first.** Before implementation begins, the core-path test cases for the plan are authored and committed. They start red. | structural test (test files exist before any src/ change in the commit sequence) |
| 2 | **One test per milestone minimum.** Every milestone has at least one test covering its core behavior. The test is written before or in the same commit as the implementation. | milestone flip blocked until test passes |
| 3 | **E2E integration test with real data.** After all milestones complete, a separate end-to-end test runs against real (not mock, not stub) data from the INTENTS tree and/or recorded call transcripts. This test is the final gate before the plan archives. | plan archival blocked until E2E passes |
| 4 | **Adversarial subagents.** All testing and verification steps are executed by subagent B — a different agent than subagent A who implemented the milestone. B receives the spec and the acceptance criteria; B does not receive A's implementation reasoning. B's prompt is adversarial: "prove this doesn't work." | CLAUDE.md harness rule |
| 5 | **Isolation.** A cannot prompt B. B cannot prompt A. The human or the orchestrating agent reads B's output and decides whether to accept, reject, or send back for rework. A fix by A triggers a fresh B verification — no incremental approval. | orchestrator discipline |
| 6 | **Repair feedback.** REJECTED verdicts produce implementation notes entries matching the failure class: `[human-todo]` for semantic failures, `[deviation]` for constraint violations. Mechanical failures require no entry (auto-retry). | structural test (`.claude/tests/test_repair_feedback_gate.py`) |

### Execution engine

The adversarial loop is not a manual ritual — it is automated by two Claude Code features working together:

**`/goal` — keeps the session running across turns until all milestones are verified.**

```
/goal M0 through M<N> all have subagent B CONFIRMED verdicts in the
Decision Log, every named Acceptance Test passes in a clean worktree,
and the E2E integration test with real INTENTS data exits 0,
or stop after 40 turns
```

A separate evaluator model reads the conversation transcript after each turn and judges whether the condition holds. It does not run commands itself — it evaluates what Claude's own output has demonstrated. The goal clears automatically when the condition is met. Each turn the evaluator returns a short reason why the condition is or isn't satisfied, which appears in the transcript so the next turn can act on it.

**Dynamic workflow — scripts the A→B→verdict pipeline for all milestones in parallel.**

The implement-verify loop maps to the `pipeline()` pattern: each milestone item flows through A (implement) → B (falsify) independently, with no barrier between stages. Milestone 3 can be in B's verification while milestone 4 is still in A's implementation:

```
pipeline(MILESTONES,
  m => agent(`implement ${m.spec}`, {label: `A:${m.id}`, schema: IMPLEMENT_RESULT}),
  result => agent(`falsify ${result.claim}`, {label: `B:${result.id}`, schema: VERDICT})
)
```

After all milestones complete, a `parallel()` fan-out runs the E2E integration test with real data alongside a completeness critic that asks "what's missing." The workflow ends when every milestone has a CONFIRMED verdict and the E2E test passes.

**The two are complementary.** `/goal` provides the completion condition — *when to stop*. Dynamic workflow provides the execution structure — *how to fan out the work*. Without the workflow, each M is a serial human dispatch; without the goal, each M requires a human to say "continue." Together they make the adversarial loop a single command, not a sequence of prompts.

### E2E test requirements

The end-to-end test must:

- Exercise the full pipeline from CLI entry point to final output (stdout/file).
- Use real INTENTS tree data (the worked domain under `INTENTS/annual-report-submission/`) — no stubs, no mocks.
- Use a real or realistically-structured `CallRecord` fixture — a transcript with turns, spans, and acoustic measurements.
- Assert on the **externally observable surface**: exit code, structured output fields (`raw`, `adjusted`, `routing`, `coverage`, `replay_hash`), and the presence of expected findings.
- Produce a `replay_hash` that is byte-identical on a second run with the same inputs.

### Subagent B prompt pattern

```
You are the adversarial verifier for milestone M<N> of ExecPlan <plan-id>.
Your job is to FALSIFY the claim that this milestone is complete.

SPEC: <relevant spec section>
ACCEPTANCE CRITERIA: <named test functions>
DELIVERABLE: <paths A claims to have completed>

For each criterion:
1. Run the named test. If it fails, report the failure with the exact output.
2. If the test passes, design at least one edge case the test does NOT cover.
   Run that edge case against the implementation. Report the result.
3. State your VERDICT: CONFIRMED (test passes + edge cases hold) or REJECTED
   (test fails OR edge case exposes a defect).

Do NOT read A's commit messages, decision logs, or implementation notes.
Judge the code by its behavior, not its intentions.
```

## The Verifier subagent

When a Progress checkbox flips from `[ ]` to `[x]`, the Verifier subagent re-runs the named Acceptance Test in a clean checkout. On pass: writes "verified at SHA \<sha\>" to the Decision Log. On fail: reverts the checkbox flip and adds an entry to Surprises & Discoveries. See `.claude/skills/verifier/SKILL.md`.

## Structural enforcement

Three gates promote the rules above from documentation to structural test:

- **Test-first gate** (`.claude/tests/test_test_first_gate.py`) — for each commit with a `Plan:` trailer that touches `src/`, the milestone's Acceptance Test file must exist in git history at or before that commit. Red commits precede green commits.
- **Adversarial verification gate** (`.claude/tests/test_adversarial_verification_gate.py`) — for each commit that flips a milestone checkbox, a `### M<N> adversarial verification` entry with `Verdict: CONFIRMED` must exist in the Decision Log, timestamped before the flip and after the last implementation commit.
- **Repair feedback gate** (`.claude/tests/test_repair_feedback_gate.py`) — for every REJECTED adversarial verification verdict in a plan's Decision Log, the milestone's implementation notes file must contain the appropriate entry type: `[human-todo]` for semantic failures, `[deviation]` for constraint violations. Mechanical failures require no entry (auto-retry).

Last reviewed: 2026-07-13.
