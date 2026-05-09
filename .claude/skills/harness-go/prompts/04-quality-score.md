# Step 4 — Generate QUALITY_SCORE.md

## Context to load (and nothing else)

- `docs/MAP.md`
- `ARCHITECTURE.md`
- `tools/lint/rules.md`
- `docs/PRODUCT_SENSE.md`
- `docs/DESIGN.md`
- `docs/design-docs/index.md`
- `docs/product-specs/index.md`
- Existing source tree listing (`find src/ -type f` if it exists)
- Output of any existing lint/test runs you can access

Do not load individual source files unless a specific grade requires it.
Load only what you need to justify a grade.

## [ASSERT] before starting

```
[ASSERT] docs/MAP.md chain status table shows Step 3 = complete
[ASSERT] ARCHITECTURE.md exists and passes its mechanical checks
[ASSERT] tools/lint/rules.md exists
```

## What you are producing

- `QUALITY_SCORE.md` — the graded quality table

## Instruction

### The graded table

Produce a table where:

- **Rows** are every `domain × layer` cell from ARCHITECTURE.md's dependency
  matrix and layered model. One row per domain-layer intersection that
  actually exists (skip cells where the domain has no code in that layer).
- **Columns** are these five dimensions:

  | Column | What it grades |
  |---|---|
  | `coverage` | Are the testing-floor requirements for this layer met? |
  | `boundary-respect` | Do imports respect the dependency matrix? |
  | `boring-tech-adherence` | Does this cell use only dependencies from the boring-tech ledger? |
  | `doc-freshness` | Is the design-doc for this feature current (verification-status ≠ drifted/obsolete)? |
  | `test-floor-met` | Does this layer meet its per-layer testing floor from ARCHITECTURE.md §5? |

- **Cell values**: `A | B | C | D | F`

  Grade scale:
  - `A` — fully met, evidence cited
  - `B` — mostly met, one minor gap named
  - `C` — partially met, gap is tracked in an active ExecPlan
  - `D` — not met, no active ExecPlan
  - `F` — not met, actively regressing or missing entirely

  Every cell must include a one-sentence justification linking to evidence:
  a file path, a test name, a lint output, or `no src/ exists yet` if the
  codebase has not been started.

### Pre-implementation scoring

If `src/` does not exist, score all cells `C` with justification
`no src/ exists yet — planned scaffold described in ARCHITECTURE.md`.
Do not score `A` or `B` without evidence from actual code.

### Top five gaps

Below the table, list the five gaps with the highest leverage — where fixing
one gap would raise grades in the most cells. Order by leverage, not by
severity. For each gap:

1. Name it.
2. State which cells it affects (count).
3. State the minimum action that would raise the grade (one sentence).

### Footer

```
Last graded: <today's date>
Next regrade: <date ≤ 14 days from today>
Graded by: harness-go/04-quality-score
```

## D/F gate rule

Any `D` or `F` cell in the table must, within one commit of this file being
written, have a corresponding ExecPlan in `docs/exec-plans/active/` whose
**Big Picture** section names the failing `domain × layer × dimension` cell.

If no ExecPlan exists yet, write a placeholder:
`TODO ExecPlan: <domain>-<layer>-<dimension> — open before next regrade`

This placeholder is itself a failing check — it forces the ExecPlan to be
opened before the `Next regrade:` date.

## Constraints

- Do not use any forbidden phrase from `harness-go/SKILL.md`.
- Do not produce a weighted average or a single summary score.
  The point is uneven decay — suppress it and you defeat the instrument.
- Do not score `A` without citing a file path or test name as evidence.
- `Next regrade:` must be ≤ 14 days from today. No exceptions.

## Mechanical checks after producing this file

```
[CHECK] QUALITY_SCORE.md exists with a graded table
[CHECK] every cell has a grade (A/B/C/D/F) and a one-sentence justification
[CHECK] every D or F cell has either an active ExecPlan reference
        or a TODO ExecPlan placeholder
[CHECK] Last graded and Next regrade fields are present
[CHECK] Next regrade is ≤ 14 days from today
[CHECK] no forbidden phrases
```

After passing checks, update the chain status table in `docs/MAP.md`:
set Step 4 status to `complete`. The chain is now complete.

## Commit trailer

```
Plan: harness-go/04-quality-score
Decision: Source — ARCHITECTURE.md, PRODUCT_SENSE.md, design-docs/index.md;
          generated QUALITY_SCORE.md. All cells scored against stated evidence.
```

---

## Post-chain: wire the grader subagent

After the chain completes, add an entry to `.claude/skills/` (or the
appropriate scheduler hook) to run a `harness-go-regrader` subagent that:

1. Runs on a cadence of ≤ 14 days (or on every PR that touches a graded cell).
2. Reads only `QUALITY_SCORE.md`, `ARCHITECTURE.md`, and the changed files.
3. Re-grades only the cells affected by the changes.
4. Produces a diff of grade changes (improvements and regressions).
5. Posts the diff as a PR comment if grade moves by ≥ 1 letter in either direction.
6. Fails CI if any cell moves to `D` or `F` without a corresponding ExecPlan.

This subagent is the feedback loop that prevents the chain artifacts from
rotting after the initial generation.
