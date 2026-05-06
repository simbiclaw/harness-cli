# Step 3 — Generate ARCHITECTURE.md and tools/lint/ scaffold

## Context to load (and nothing else)

- `docs/MAP.md`
- `docs/PRD/*.md`
- `docs/PRODUCT_SENSE.md`
- `docs/product-specs/*.md`
- `docs/DESIGN.md`
- `docs/design-docs/core-beliefs.md`
- Existing source tree listing (run `find src/ -type f | head -200` if `src/` exists;
  if not, note its absence — do not invent a codebase)

Do **not** load individual source files unless a specific import graph question
requires it. Keep the context window narrow.

## [ASSERT] before starting

```
[ASSERT] docs/MAP.md chain status table shows Step 2 = complete
[ASSERT] docs/PRODUCT_SENSE.md passes its mechanical checks
[ASSERT] docs/DESIGN.md exists
[ASSERT] docs/design-docs/core-beliefs.md exists
```

## What you are producing

- `ARCHITECTURE.md` — the canonical architecture document
- `tools/lint/rules.md` — the lint scaffold: one entry per architectural rule,
  stating whether it is enforced by a test/lint/hook or marked `Aspiration:`

## Instruction

Read all context. Produce `ARCHITECTURE.md` with these sections in order.

### 1. Domain inventory

List every business domain this product contains.

For each domain:
- Name it (noun, not a verb).
- One sentence justifying its existence by reference to a
  **PRODUCT_SENSE.md non-goal** — the domain exists because something is
  *intentionally separated* from something else. Name what.
- If you cannot find a non-goal that justifies a domain boundary, mark it
  `Aspiration: boundary not yet justified — Revisit: <date 14 days from today>`.

Do not create domains for generic layers ("utils", "helpers", "common").
Each domain must map to a user-visible product concern or an explicit
infrastructure boundary.

### 2. Layered model

State the permitted layer set and the directional dependency rule.

Format:
```
Layers (innermost → outermost):
  Types → Config → Repo → Service → Runtime → UI

Rule: a layer may import from layers to its left. It must not import from
layers to its right. Cross-domain communication must pass through Providers.

Providers: <name the explicit cross-cutting boundary and what it owns>
```

Adapt the layer names to this product. If the PRD implies a different
layering, use that and state why.

### 3. Dependency matrix

A table where rows and columns are domain names. Each cell contains one of:

- `none` — no dependency
- `via Providers` — dependency flows through the explicit boundary
- `<InterfaceName>` — the specific named interface used (this is a
  commitment: the interface must be created or the cell must be `Aspiration:`)

No implicit edges. If you are unsure of a dependency, write
`Confidence: low — <reason>` in the cell rather than omitting it.

### 4. Boring-tech ledger

For each dependency this product will use (inferred from PRD or existing
`pyproject.toml` / `package.json`), record:

| Dependency | Chosen for | Alternative rejected | Rejection reason |
|---|---|---|---|

"Chosen for" must be stated in terms of **agent legibility** (how a future
agent will parse or use this dependency) or **reliability** — not aesthetics.
"Rejection reason" must be a source, experiment, or explicit `Confidence: low`.

### 5. Per-layer contracts

For each layer in the layered model, state:

- **Parsing-at-boundary rule**: what transformation happens when data crosses
  into this layer (e.g., "all external data is validated against a schema
  before entering the Repo layer").
- **Logging contract**: what this layer logs and at what level.
- **Testing floor**: the minimum test coverage shape for this layer
  (e.g., "every Repo function has a contract test against a test double").

### tools/lint/rules.md

After producing ARCHITECTURE.md, produce `tools/lint/rules.md`.

For **every rule stated in prose in ARCHITECTURE.md**, add a row:

| Rule | Location in ARCHITECTURE.md | Enforcement | Status |
|---|---|---|---|

`Enforcement` values:
- `structural-test: <path>` — a test in `.claude/tests/` that fails if violated
- `lint: <rule-name>` — a custom lint rule
- `ci-gate: <workflow>` — a CI workflow gate
- `import-linter: <constraint>` — enforced by import-linter in pyproject.toml
- `Aspiration: Revisit: <date>` — not yet enforced; date must be ≤ 30 days out

A rule with `Aspiration` status is **not** a rule. It is a documented intent.
Do not rely on it in any ExecPlan until it is promoted.

## Constraints

- Do not use any forbidden phrase from `harness-go/SKILL.md`.
- Every domain boundary must be justified by a PRODUCT_SENSE.md non-goal or
  marked `Aspiration:`.
- Every `Aspiration:` entry must have a `Revisit:` date. No open-ended aspirations.
- The dependency matrix must have an entry for every domain × domain pair.
  A missing cell is a non-compliant matrix.
- Do not invent a codebase. If `src/` does not exist, say so and produce
  architecture for the planned scaffold as described in the PRD.

## Mechanical checks before advancing to Step 4

```
[CHECK] ARCHITECTURE.md has all five required sections
[CHECK] every domain in the inventory cites a PRODUCT_SENSE non-goal OR is
        marked Aspiration:
[CHECK] dependency matrix covers all domain × domain pairs
[CHECK] tools/lint/rules.md exists with one row per architectural rule
[CHECK] no rule row has an Aspiration: Revisit: date more than 30 days out
[CHECK] no forbidden phrases in any produced file
```

If any check fails: fix the file, re-run, do not advance.

After passing checks, update the chain status table in `docs/MAP.md`:
set Step 3 status to `complete`.

## Commit trailer

```
Plan: harness-go/03-architecture
Decision: Source — PRD, PRODUCT_SENSE.md, DESIGN.md; generated ARCHITECTURE.md and tools/lint/rules.md.
```
