# Step 1 — Generate PRODUCT_SENSE.md and docs/product-specs/

## Context to load (and nothing else)

- `docs/PRD/*.md` (all PRD files)
- `CLAUDE.md` (the updated index from Step 0)

Do **not** load the codebase. Do not load ARCHITECTURE.md (it does not exist
yet and its absence is correct).

## [ASSERT] before starting

```
[ASSERT] docs/MAP.md exists with chain status table showing Step 0 = complete
[ASSERT] docs/PRD/ contains at least one .md file
```

## What you are producing

- `docs/PRODUCT_SENSE.md` — product judgment that the PRD does not encode
- `docs/product-specs/index.md` — inventory of all user-visible features
- `docs/product-specs/<feature>.md` — one file per distinct user-visible feature in the PRD

## Instruction

Read every file under `docs/PRD/`. Produce the artifacts below.
Do not produce DESIGN.md, ARCHITECTURE.md, or any other downstream artifact.

### docs/PRODUCT_SENSE.md

Must contain exactly these sections, in this order:

#### The user we are building for

A single sentence that names the primary user and resolves at least one
conflict — i.e., who is *not* the primary user when the two conflict, and
what that means for a product decision. If the PRD is silent on this
conflict, write `Awaiting Steering: <question>` and do not invent an answer.

#### Non-goals

A bulleted list of things this product will intentionally *not* do.
This section must be at least as long as the Goals section derived from
the PRD. If you cannot produce a non-goals list at least as long as the
goals, write `Awaiting Steering: non-goals list is shorter than goals —
needs human input` and stop that section there.

Each non-goal must state *why* it is excluded. Acceptable rationale shapes:
- `Source: <doc or person>` — cites a decision already made
- `Experiment: <what was tried and what it showed>`
- `Confidence: low — <what would change this>`

Unacceptable: "out of scope", "not needed", "not a priority" without a reason.

#### Failure-mode tolerances

For at least three distinct failure classes that could occur in this product,
state whether the failure **blocks release** or **does not block release**
and the observable threshold that determines the classification.

Example shape (adapt to this product — do not copy the example):
```
- Data loss of any user record: blocks release. Observable: any test that
  writes then reads a record and finds it missing.
- UI flash on navigation: does not block release. Observable: screenshot
  diff > 5% of pixels changed in under 100ms.
```

#### Decision tiebreakers

For the three most likely recurring tradeoffs you can infer from the PRD,
state the tiebreaker rule. Each tiebreaker must name two competing values
and say which wins and when.

Example shape:
```
Tiebreaker: latency vs. consistency
Rule: consistency wins when the operation is a write; latency wins when
the operation is a read with acceptable staleness defined as <N seconds>.
Source: PRD §<section>.
```

Mark any tiebreaker you cannot derive from the PRD as
`Awaiting Steering: <question>`.

### docs/product-specs/index.md

An inventory table:

| Feature slug | User job | Spec file | Open questions |
|---|---|---|---|

One row per user-visible feature. "Open questions" is a count, not a list
(the list lives in the feature spec).

### docs/product-specs/<feature>.md

One file per feature. Each file contains:

1. **Feature slug** — kebab-case, matches the index row
2. **User job** — one sentence in the form "When <situation>, the user wants
   to <goal> so that <outcome>."
3. **Acceptance behavior** — what an end user can observe to confirm the
   feature works. Must be externally observable (not "the function returns X").
4. **Tiebreaker citations** — explicit references to the tiebreaker rules in
   `PRODUCT_SENSE.md` that apply to this feature. If none apply, write `none`
   — do not leave this field blank.
5. **Open questions** — bulleted list of things that need steering before
   implementation. If none, write `none`.

## Constraints

- Do not use any forbidden phrase from `harness-go/SKILL.md`.
- Anywhere you would write a forbidden phrase, stop and apply the rationale
  shape rules above.
- Do not invent product decisions the PRD does not support. Surface them
  as `Awaiting Steering:` blocks.
- PRODUCT_SENSE.md is owned by steering after this step. Mark it with a
  front-matter field: `owned-by: steering`.

## Mechanical checks before advancing to Step 2

```
[CHECK] docs/PRODUCT_SENSE.md exists and has all four required sections
[CHECK] non-goals section line count >= goals section line count
        (count lines under each heading)
[CHECK] docs/product-specs/index.md exists
[CHECK] one .md file exists per row in the index table
[CHECK] every product-spec has a non-empty "Tiebreaker citations" field
[CHECK] no forbidden phrases in any produced file
[CHECK] no "Awaiting Steering:" block is left without a question
        (i.e., "Awaiting Steering:" must be followed by a ":" and a question)
```

If any check fails: fix the file, re-run, do not advance.

After passing checks, update the chain status table in `docs/MAP.md`:
set Step 1 status to `complete`.

## Commit trailer

```
Plan: harness-go/01-product-sense
Decision: Source — docs/PRD/; generated PRODUCT_SENSE.md and product-specs/.
```
