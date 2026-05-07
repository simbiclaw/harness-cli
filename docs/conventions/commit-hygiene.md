# Commit Hygiene

The git log is the second narrative thread alongside ExecPlan Progress sections. The two must agree.

## Message format

```
<type>(<scope>): <subject>

Plan: docs/exec-plans/active/NNNN-<slug>.md#milestone-N
Decision: <one-line rationale, or "implementation only">
```

Where:

- `<type>`: one of `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `harness`. The `harness` type is reserved for changes inside `.claude/` or in `docs/conventions/`, `docs/PLANS.md`, or `CLAUDE.md`.
- `<scope>`: short module/area name (e.g. `cli`, `core`, `io`, `ci`, `bootstrap`).
- `<subject>`: imperative-mood verb phrase, 12 to 72 chars, must contain a verb and a noun.

The structural test `test_commit_messages.py` enforces the format and checks that the referenced ExecPlan path exists somewhere under `docs/exec-plans/active/`, `docs/exec-plans/completed/`, or `docs/exec-plans/archived/`.

## One commit per milestone-checkbox flip

Every flip of a Progress checkbox from `[ ]` to `[x]` is its own commit. The commit message names the milestone in the `Plan:` trailer, including the `#milestone-N` fragment.

Implementation work toward a milestone may span multiple commits. Only the final commit (the one that flips the checkbox) needs to claim completion. Intermediate commits use `Decision: implementation only`.

Structural tests pass before any flip. A checkbox flip commit that causes a structural test failure is invalid — the flip is reverted and the failure fixed before re-flipping.

## Never amend pushed commits

`git commit --amend` is permitted only for the most recent local commit that has not been pushed. Once pushed, fixes go in new commits.

## Force-push requires explicit unlock

The pre-push hook blocks `--force` and `--force-with-lease` unless the env var `CLAUDE_FORCE_PUSH_OK=1` is set. This var is never set in normal agent operation. If a force-push is genuinely needed (e.g. to remove an accidentally committed secret), the human sets the env var for one push and writes a Decision Log entry explaining why.

## What "useful commit message" means

The subject must contain a verb and a noun. Subjects like `update files`, `fix issues`, `various changes`, `wip`, `misc`, `stuff`, `tweaks` are rejected by the structural test even if they pass the regex hook. The hook is fast feedback; the structural test is the real enforcement.

## Examples

```
feat(cli): add convert subcommand for CSV input

Plan: docs/exec-plans/active/0003-add-convert-subcommand.md#milestone-1
Decision: chose subprocess-style integration test as the Acceptance Test.
```

```
test(core): add unit tests for CSV format detection

Plan: docs/exec-plans/active/0003-add-convert-subcommand.md#milestone-2
Decision: implementation only
```

```
harness(bootstrap): create convention docs

Plan: docs/exec-plans/active/0001-bootstrap-harness.md#milestone-1
Decision: implementation only
```

Last reviewed: 2026-05-01.
