# CLAUDE.md

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

## Behavioral guidelines to reduce common LLM coding mistakes.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

Last reviewed: 2026-05-04.
