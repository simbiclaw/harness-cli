---
name: verifier
description: Triggered when an ExecPlan progress checkbox flips from `[ ]`
  to `[x]`. Re-runs the milestone's named Acceptance Test in a clean
  checkout. On pass, writes a 'verified at SHA' Decision Log entry. On
  fail, reverts the checkbox flip and adds a Surprises entry.
---

# Verifier Skill

## When to use this skill

Automatically, by the PostToolUse hook on Edit/Write to a file under
`docs/exec-plans/active/`, when the diff includes a checkbox flip from `[ ]`
to `[x]`.

## Process

1. Read the milestone-N section of the ExecPlan. Extract the
   `Acceptance Test:` line. Parse out the test ID
   (`tests/test_<name>.py::<test_name>` for pytest).
2. Create a clean worktree of HEAD: `git worktree add /tmp/verify-<sha> HEAD`.
3. In the worktree, install dependencies: `uv sync --dev`.
4. Run only the named Acceptance Test:
   `uv run pytest <test-id> -v --no-header`.
5. Capture exit code, stdout, stderr.
6. Remove the worktree: `git worktree remove /tmp/verify-<sha>`.

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

Last reviewed: 2026-05-01
