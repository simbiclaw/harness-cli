# CLAUDE.md

Auto-loaded at the start of every Claude Code session in this repo. Intentionally short — long instruction files crowd out task context and rot. This file is a table of contents.

## What this repository is

A CLI tool built end-to-end by Claude Code. A human steers; agents execute. There is no human-written application code in `src/`. The system of record is `docs/`.

## First action on every session

Read the most recent file in `docs/plans/active/` end-to-end. Read its **Surprises & Discoveries** section first. That is the work in flight. If there is more than one active plan, ask the human which to pick up. Do not start work in the middle of a plan you have not read.

## Read these before doing any non-trivial work

- `docs/PLANS.md` — the rubric every ExecPlan follows. Read once per session if you are creating or modifying a plan.
- `docs/conventions/ask-threshold.md` — when to proceed silently vs. flag vs. stop and ask.
- `docs/conventions/verification-floor.md` — what "done" means for a milestone.
- `docs/conventions/deps-and-secrets.md` — how new dependencies and secrets are handled.
- `docs/conventions/commit-hygiene.md` — commit message format and discipline.
- `docs/conventions/i-dont-know-protocol.md` — how to handle uncertainty in Decision Log entries.
- `docs/conventions/architecture-layering.md` — the layered architecture for `src/` and how it is enforced.

## The five harnesses, one sentence each

1. **Ask before assuming** — three explicit tiers; default to the most cautious. See `ask-threshold.md`.
2. **Verification floor** — every milestone has a runnable Acceptance Test exercising an externally observable property. See `verification-floor.md`.
3. **Deps and secrets** — new dependencies are vetted by the dep-vetter skill before adoption; secrets never enter the repo. See `deps-and-secrets.md`.
4. **Commit hygiene** — every commit references its ExecPlan and milestone, with a Decision trailer. See `commit-hygiene.md`.
5. **"I don't know" protocol** — Decision Log entries cite evidence, run experiments, or flag uncertainty explicitly. Forbidden phrases enforced by structural test. See `i-dont-know-protocol.md`.

## The promotion rule

Every rule starts as documentation in `docs/conventions/`. When the same rule is violated twice — by you, in different ExecPlans — the documentation has failed. Open an ExecPlan to promote the rule one step left:

- documentation → structural test (in `.claude/tests/`)
- documentation → hook (in `.claude/hooks/`)
- documentation → CI gate (in `.github/workflows/harness.yml`)
- documentation → architecture (enforced by `import-linter` in `pyproject.toml`)

Do not "try harder to remember." Move the rule into code.

## Skills available

- `.claude/skills/dep-vetter/` — vet a new dependency against the four-check policy.
- `.claude/skills/verifier/` — re-run a milestone's Acceptance Test on a checkbox flip.
- `.claude/skills/garbage-collector/` — recurring scan for cruft (runs nightly).
- `.claude/skills/doc-gardener/` — recurring scan for stale docs and broken cross-refs (runs weekly).

## What the hooks block

- Edits to paths in `.claude/sensitive-paths.txt` without a resolved "Awaiting Steering" entry in the active ExecPlan.
- Package installs without a dep-vet record in `.claude/decisions/dep-vet-<pkg>.md`.
- `git push --force` unless `CLAUDE_FORCE_PUSH_OK=1` is set, which it never is in normal operation.
- Commits whose message lacks the `Plan:` and `Decision:` trailers.

When a hook blocks you, the error message includes the exact remediation. Do what it says.

## What the structural tests fail on

- Imports in `src/argus/` that violate the layered architecture (enforced by `import-linter`).
- ExecPlan Decision Log entries without a recognized rationale shape (Source / Experiment / `Confidence: low`).
- ExecPlan Decision Log entries containing forbidden phrases ("standard approach", "best practice", etc.).
- Recent commits without `Plan:` / `Decision:` trailers, or with vague subjects.
- Direct dependencies in `pyproject.toml` without a corresponding Decision Log entry and dep-vet record.

When a structural test fails, the error message names the file, line, and required fix.

## When in doubt

The `docs/` directory is the system of record; trust it over your memory. The `.claude/` directory is the enforcement layer; if a rule isn't enforced there, treat it as advisory documentation, not law.

Last reviewed: 2026-05-01.
