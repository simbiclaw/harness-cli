# harness-go

**Purpose.** Generate the harness's knowledge spine from a `docs/PRD/` directory.
Produces five artifacts in dependency order:
`PRODUCT_SENSE.md` → `DESIGN.md` → `ARCHITECTURE.md` → `QUALITY_SCORE.md`,
with a transient `docs/MAP.md` routing aid that is deleted before the skill exits.

**Do not skip steps.** Each step's output is a required input to the next.
The chain enforces this through explicit `[ASSERT]` preconditions.

---

## When to invoke this skill

- A `docs/PRD/` directory exists and no knowledge spine exists yet.
- You are regenerating from a steering change — pick up at the changed step
  and re-run all downstream steps.
- You are resuming a mid-flight run after a session reset.

In **all three cases**, run Phase 1 (borrow) first before executing any step.
Phase 1 is always the entry point. Do not skip it.

Do **not** invoke for incremental edits to a single artifact undriven by a PRD
change. Do **not** invoke for routine doc-gardener sweeps.

---

## CLAUDE.md borrow — transactional, not permanent

The spine generation is **session-scoped scaffolding**, not a permanent
navigational layer. Once the four artifacts exist and cross-link to each other,
the agent navigates by following those links. A top-level routing map added
to `CLAUDE.md` becomes permanent background noise that pays a context tax on
every future session for a problem that only existed during bootstrap.

Instead, this skill **borrows the auto-loaded slot transactionally**:

### Phase 1 — borrow (always run this first)

1. Check `CLAUDE.md` for a pre-existing `harness-spine-bootstrap` sentinel
   block. If found, remove it (cleaning up a previous crash or partial run).
2. Append this block to the end of `CLAUDE.md`, preserving all other content
   byte-for-byte:

   ```
   <!-- harness-spine-bootstrap:begin -->
   read docs/MAP.md first
   <!-- harness-spine-bootstrap:end -->
   ```

3. Register `trap cleanup EXIT` so Phase 2 runs even on crash or signal-kill.

`docs/MAP.md` is created by Step 0 via `prompts/00-map.md`. Phase 1 does not
create MAP.md — that is Step 0's job.

### Phase 2 — release (Step 5)

1. Delete `docs/MAP.md`.
2. Remove the sentinel block from `CLAUDE.md`.
3. Commit both deletions in the same commit that ships the spine.

A CI lint asserting the sentinel block is absent on `main` makes Phase 2 a
mechanical check, not a matter of discipline.

---

## Chain overview

| Step | Artifact produced | Reads | Prompt file |
|------|-------------------|-------|-------------|
| 0 | `docs/MAP.md` (transient) | `docs/PRD/*.md` | `prompts/00-map.md` |
| 1 | `docs/PRODUCT_SENSE.md` + `docs/product-specs/` | PRD | `prompts/01-product-sense.md` |
| 2 | `docs/DESIGN.md` + `docs/design-docs/` | MAP.md, PRD, PRODUCT_SENSE, product-specs | `prompts/02-design.md` |
| 3 | `ARCHITECTURE.md` + `tools/lint/` scaffold | MAP.md + all prior | `prompts/03-architecture.md` |
| 4 | `QUALITY_SCORE.md` | all prior + codebase | `prompts/04-quality-score.md` |
| 5 | *(teardown)* delete MAP.md, remove sentinel | — | `prompts/05-teardown.md` |

Run each step as a **subagent with a narrow context window** — pass only the
inputs listed in the "Reads" column. PRODUCT_SENSE generation does not need
the codebase. ARCHITECTURE generation does not need the PRD's marketing prose.

---

## Preconditions (check once before Phase 1)

```
[ASSERT] docs/PRD/ exists and contains at least one .md file
[ASSERT] CLAUDE.md exists and is readable
[ASSERT] No active ExecPlan in docs/exec-plans/active/ blocks these paths
         (check .claude/sensitive-paths.txt)
```

If any assertion fails: stop, report the failure, list the exact remediation,
do not proceed.

---

## How to execute a single step

1. Verify all `[ASSERT]` preconditions for that step (listed in the prompt file).
2. Open the corresponding `prompts/NN-<name>.md` file.
3. Collect only the listed input artifacts.
4. Spawn a subagent (or proceed inline) with that context.
5. Run the mechanical checks in `checks/lint-rules.md` for that step.
6. If any check fails, fix the output before advancing.
7. Update MAP.md chain status table: set this step's status to `complete`.
8. Commit with required trailers:
   ```
   Plan: harness-go/<step-name>
   Decision: <rationale per i-dont-know-protocol>
   ```

---

## Resuming after a session reset

On session start, always check `CLAUDE.md` for the sentinel before doing anything else.

**Sentinel present** (a run was in flight):
1. Run Phase 1: remove stale sentinel, re-append fresh sentinel. Do not
   create MAP.md yet — that is Step 0's job.
2. Check whether `docs/MAP.md` exists.
   - If MAP.md exists, read its chain status table to identify the last
     completed step.
   - If MAP.md does not exist, Step 0 did not complete — start from Step 0.
3. For each step marked `complete` in MAP.md, verify its output artifact
   exists and passes the mechanical checks in `checks/lint-rules.md`.
   - If an artifact exists and passes: the step is genuinely complete. Keep
     its status as `complete`.
   - If an artifact is missing or fails checks: reset its status to `pending`
     and treat it as the resume point.
4. Update MAP.md chain status to reflect the verified state, then continue
   from the first `pending` step.

**Sentinel absent, MAP.md absent** (clean start or prior run completed):
1. Run Phase 1 (borrow).
2. Run from Step 0.

**Sentinel absent, MAP.md present** (should not occur; MAP.md must not outlive
the sentinel):
1. Delete MAP.md (stale artifact from a broken teardown).
2. Run Phase 1 (borrow).
3. Run from Step 0.

---

## PostToolUse hook

On every write to any artifact or satellite directory, re-run:

```
CHECK: every product-spec cites ≥ 1 tiebreaker from PRODUCT_SENSE.md
CHECK: every design-doc has a verification-status field
CHECK: every ARCHITECTURE.md rule has a lint entry OR an unexpired Aspiration
CHECK: every QUALITY_SCORE D/F cell has an active ExecPlan or TODO placeholder
```

Failure: revert the write; append failure to the active plan's
**Surprises & Discoveries** section.

Wire at: `.claude/hooks/post-tool-use/cross-link-integrity`

---

## Scheduled doc-gardener extension

The nightly doc-gardener subagent must additionally:

- Fail loudly if `harness-spine-bootstrap` sentinel block is found in
  `CLAUDE.md` on `main`.
- Fail loudly if `docs/MAP.md` exists on `main`.
- Re-grade QUALITY_SCORE and flip drifted design-doc statuses.
- Flag PRODUCT_SENSE tiebreakers uncited by any plan in 30 days as
  archival candidates.

---

## Forbidden phrases (structural test enforced)

Must not appear in any artifact this skill produces:

- "best practice" / "best practices"
- "standard approach" / "standard pattern"
- "clean architecture"
- "industry standard"
- "it is recommended"
- "comprehensive" (as a standalone quality claim)

Replace with a cited source, a named experiment, or `Confidence: low`.

---

## Artifact ownership after generation

- **PRODUCT_SENSE.md** — owned by steering. Agents read; do not edit without
  an `Awaiting Steering:` resolution.
- **DESIGN.md / design-docs/** — owned by doc-gardener for staleness sweeps.
- **ARCHITECTURE.md** — co-owned with `tools/lint/`. Prose rule without a
  corresponding lint entry is `Aspiration:` with a `Revisit:` date.
- **QUALITY_SCORE.md** — regenerated by grader subagent on ≤14-day cadence.
- **MAP.md** — exists only during bootstrap. Must not survive Step 5.

---

Last reviewed: 2026-05-04.
