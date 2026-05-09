---
name: garbage-collector
description: Recurring custodial agent. Scans the repo for cruft (unused
  files, dead exports, stale TODOs, dormant ExecPlans) and opens an
  ExecPlan per cleanup theme. Does not delete autonomously.
---

# Garbage-Collector Skill

## When to use this skill

Nightly via cron, or on-demand by a human asking "clean up". Never as a
side-effect of feature work.

## Scans

### Unused modules
For each `.py` file under `src/argus/`, check whether anything imports it
(grep across `src/`, `tests/`, `pyproject.toml` entry points). Files with
no inbound references and not in entry-point declarations are candidates.

### Unused exports
Within each module, identify symbols (functions, classes, constants) that
are not referenced anywhere outside the file. Use `vulture` or a custom AST
walker. Candidates for internalization (rename with leading underscore) or
removal.

### Stale TODOs
`grep -rn "TODO\|FIXME\|XXX\|HACK" src/ tests/`. Any match where the
introducing commit (per `git blame`) is >30 days old is a candidate.
Resolution = open ExecPlan to fix, convert to GitHub issue, or remove
the comment.

### Dormant active ExecPlans
Plans in `docs/exec-plans/active/` with no Progress checkbox flips in 14 days
(check with `git log --follow -p <plan>` for `[ ]` → `[x]` diffs).
Candidates for archival or revival.

### Past-deadline Confidence-low entries
Walk every `Confidence: low` Decision Log entry. If the corresponding
`Revisit:` deadline has passed, flag it.

### Empty or skipped tests
Test files where every test has been skipped or commented out, or where
test functions have empty bodies / only `pass`.

## Output

For each cleanup theme with non-empty candidates, open ONE ExecPlan at
`docs/exec-plans/active/NNNN-gc-<theme>-<date>.md` following the PLANS.md
rubric. List the candidates as Milestones. **Do not delete anything.**

## What this skill must NOT do

- Delete files or remove code.
- Modify ExecPlans authored by feature work.
- Modify `CLAUDE.md`, `docs/conventions/`, `docs/PLANS.md`, hooks, or tests.
- Run on a clock that overlaps with active feature work (defer if a
  feature ExecPlan was modified in the last 4 hours).

Last reviewed: 2026-05-01
