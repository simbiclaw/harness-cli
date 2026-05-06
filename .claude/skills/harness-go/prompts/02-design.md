# Step 2 — Generate DESIGN.md and docs/design-docs/

## Context to load (and nothing else)

- `docs/MAP.md`
- `docs/PRD/*.md`
- `docs/PRODUCT_SENSE.md`
- `docs/product-specs/*.md` (all feature specs)

Do **not** load the codebase or ARCHITECTURE.md.

## [ASSERT] before starting

```
[ASSERT] docs/MAP.md chain status table shows Step 1 = complete
[ASSERT] docs/PRODUCT_SENSE.md exists and passes its mechanical checks
[ASSERT] docs/product-specs/index.md exists
```

## What you are producing

- `docs/DESIGN.md` — design-system index
- `docs/design-docs/index.md` — inventory of all design-doc files
- `docs/design-docs/core-beliefs.md` — agent-first operating principles for design
- `docs/design-docs/<feature>.md` — one file per product-spec that has UI surface area

## Instruction

Read all context listed above. Produce the artifacts below.
Do not produce ARCHITECTURE.md or QUALITY_SCORE.md.

### docs/DESIGN.md

An index document. Contains:

1. **Design-system tokens** — the canonical list of spacing, color, and
   typography primitives this product uses. If the PRD does not specify them,
   write `Awaiting Steering: design tokens not specified in PRD` and leave
   placeholders. Do not invent a design system.

2. **Component vocabulary** — the named set of UI primitives (e.g., "Card",
   "ActionBar", "EmptyState"). One sentence per component stating what it
   represents and what it is *not* for. If the PRD has no UI surface, write
   `Not applicable — product has no user-facing UI surface` and do not produce
   `design-docs/<feature>.md` files.

3. **Navigation primitives** — the navigation model (tabs, stack, drawer, etc.)
   with the rationale for the choice cited from PRODUCT_SENSE.md tiebreakers
   or marked `Awaiting Steering:`.

4. **Accessibility floor** — the minimum accessibility standard this product
   must meet. State it as an observable threshold (e.g., "all interactive
   elements must be reachable by keyboard and have a visible focus ring").
   Not as a goal ("we aim for accessibility") — as a release gate.

5. **Links to design-docs** — one line per `design-docs/<feature>.md` file,
   format: `- [<feature-slug>](design-docs/<feature>.md) — <user-job one-liner>`.

### docs/design-docs/index.md

An inventory table:

| Feature slug | verification-status | UI surface? | Design doc |
|---|---|---|---|

`verification-status` values: `proposed | implemented | drifted | obsolete`
All new files start as `proposed`.

### docs/design-docs/core-beliefs.md

The agent-first operating principles for design. Each belief:

1. States the principle as a single imperative sentence.
2. Carries a `Rationale:` field with one of these shapes:
   - `Source: <citation>` — links to PRD section, PRODUCT_SENSE tiebreaker, or external doc
   - `Experiment: <what was tried and what it showed>`
   - `Confidence: low — <what would change this>`
3. Is cited by at least one `design-docs/<feature>.md` file. If a belief
   has no citation after all feature docs are written, demote it to
   `docs/design-docs/archive/` and note why.

Minimum three beliefs. Required belief topics (adapt wording to this product):
- How components should expose their interface to the agent (prop shapes vs. visual shapes).
- When to prefer one composable primitive over multiple specialized ones.
- How interactive elements must be identifiable across restyling (stable test selectors).

### docs/design-docs/<feature>.md

One file per product-spec with UI surface area. Each file:

```yaml
---
feature-slug: <slug>
verification-status: proposed
last-verified: ~
---
```

Body contains:

1. **User job** — copied from `product-specs/<feature>.md` (single sentence).
2. **UI surface** — what the user sees and interacts with, described as
   observable states (idle, loading, error, success, empty). Not as
   implementation details.
3. **Component usage** — which components from the DESIGN.md vocabulary this
   feature uses. If a needed component is not in the vocabulary, add it to
   DESIGN.md and link back here.
4. **Core-beliefs citations** — explicit references to beliefs in
   `core-beliefs.md` that constrain this feature's design.
5. **Test selectors** — the stable selector identifiers that automated tests
   must use for every interactive element in this feature. These must survive
   restyling.
6. **Open design questions** — items that need steering. If none, write `none`.

## Constraints

- Do not use any forbidden phrase from `harness-go/SKILL.md`.
- Do not invent a design system if the PRD does not specify one. Use
  `Awaiting Steering:` for every token category the PRD leaves unspecified.
- `verification-status: proposed` is correct for all new files. Do not
  claim `implemented` for anything that has not been built.
- Every feature doc must cite at least one belief from `core-beliefs.md`.
  A feature doc with zero belief citations is non-compliant.

## Mechanical checks before advancing to Step 3

```
[CHECK] docs/DESIGN.md exists and has all five required sections
[CHECK] docs/design-docs/core-beliefs.md exists with ≥ 3 beliefs
[CHECK] every belief in core-beliefs.md has a Rationale field
[CHECK] every design-docs/<feature>.md has a verification-status front-matter field
[CHECK] every design-docs/<feature>.md cites ≥ 1 belief from core-beliefs.md
[CHECK] every design-docs/<feature>.md has a test-selectors section
[CHECK] docs/design-docs/index.md has one row per design-doc file
[CHECK] no forbidden phrases in any produced file
```

If any check fails: fix the file, re-run, do not advance.

After passing checks, update the chain status table in `docs/MAP.md`:
set Step 2 status to `complete`.

## Commit trailer

```
Plan: harness-go/02-design
Decision: Source — docs/PRD/, PRODUCT_SENSE.md; generated DESIGN.md and design-docs/.
```
