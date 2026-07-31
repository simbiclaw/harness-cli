---
name: verifier
description: Manually invoked before flipping a milestone checkbox.
  Re-runs the milestone's named Acceptance Test in a clean
  checkout. On pass, writes a 'verified at SHA' Decision Log entry. On
  fail, reverts the checkbox flip and adds a Surprises entry.
---

# Verifier Skill

## When to use this skill

Before flipping a milestone checkbox in an ExecPlan under
`docs/exec-plans/active/`. Invoked by the model, never by a hook.
(Hooks only block/allow — they cannot invoke skills. The adversarial
verification gate enforces the evidence requirement: a `Verdict: CONFIRMED`
entry must exist in the Decision Log before the flip. This skill helps
create that evidence.)

## Pre-condition: adversarial verification

Before a checkbox flip is permitted, subagent B must have completed adversarial
verification of the milestone and returned a verdict of CONFIRMED. The Verifier
checks for this:

1. Read the ExecPlan's Decision Log. Search for the most recent entry matching
   `### M<N> adversarial verification`.
2. If no such entry exists, **refuse the flip**. Report: "Subagent B adversarial
   verification missing for M<N>. See `docs/conventions/verification-floor.md`."
3. If the entry exists but its verdict is REJECTED or the entry is older than
   the latest commit touching files claimed by M<N>, **refuse the flip**.
   Report: "Subagent B verdict was REJECTED (or is stale). Re-run adversarial
   verification before flipping."

The adversarial verification entry must follow this format:

```
### M<N> adversarial verification
Verdict: CONFIRMED
Verified at SHA <sha> on <YYYY-MM-DD HH:MM TZ>.
Subagent B: <agent-id>
Acceptance Test: <test-id> — PASSED
Edge cases exercised: <N>
Failures found: 0
Source: docs/conventions/verification-floor.md#adversarial-verification
```

## Process

1. Read the milestone-N section of the ExecPlan. Extract the
   `Acceptance Test:` line. Parse out the test ID
   (`tests/test_<name>.py::<test_name>` for pytest).
2. Verify the adversarial verification pre-condition (above). If not met, abort.
3. Create a clean worktree of HEAD: `git worktree add /tmp/verify-<sha> HEAD`.
4. In the worktree, install dependencies: `uv sync --dev`.
5. Run only the named Acceptance Test:
   `uv run pytest <test-id> -v --no-header`.
6. Capture exit code, stdout, stderr.
7. Remove the worktree: `git worktree remove /tmp/verify-<sha>`.

## On pass

Append to the ExecPlan's Decision Log:

```
### Milestone N verified
Verified at SHA <git-rev-parse-HEAD> on <YYYY-MM-DD HH:MM TZ>.
Acceptance Test: <test-id>
Source: docs/exec-plans/active/<plan>.md#milestone-N
```

The Source path satisfies the i-don't-know-protocol structural test.

## On fail

Revert the checkbox flip via `git checkout HEAD~1 -- <plan-file>` (then
re-apply any unrelated edits in the same commit). Append to Surprises &
Discoveries:

```
### Milestone N verification failed at <date>
Acceptance Test: <test-id>
Exit code: <N>
Output: <first 50 lines of combined stdout+stderr>
Source: <captured run log path under .claude/verifier-runs/>

Action: do not flip the checkbox until the cause is understood and fixed.
If the test is wrong, fix the test in a separate commit.
```

## What this skill must NOT do

- Modify any source code beyond reverting the ExecPlan file.
- Run the full test suite (CI does that).
- Cache results between runs (every flip gets fresh verification).
- Skip the worktree step (the verifier must run against committed state,
  not the working tree which may have uncommitted changes).

Last reviewed: 2026-07-13
