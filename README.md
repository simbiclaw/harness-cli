# argus

A CLI tool, built end-to-end by Claude Code under the harness defined in `docs/`.

## First-run instructions for the human operator

```bash
# 1. Install uv if you haven't.
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Sync the dev environment.
uv sync

# 3. Install the pre-commit hooks.
uv run pre-commit install --install-hooks
uv run pre-commit install --hook-type commit-msg

# 4. Verify the harness runs cleanly on the empty scaffold.
uv run pytest .claude/tests -v
uv run lint-imports

# 5. Start Claude Code in this directory and say:
#       Read CLAUDE.md, then read the active ExecPlan, then begin.
```

## What this repository is

This is a product where Claude Code writes the application code under `src/` and
the human steers via the harness in `docs/` and `.claude/`. There is no
human-written application code by design.

The system of record is `docs/`. Plans, decisions, experiments, and
retrospectives all live there. `.claude/` holds the mechanical enforcement
(hooks, structural tests, skills, CI) that keeps the system of record honest.

For the methodology, read:

- `CLAUDE.md` — the entry-point routing file
- `docs/PLANS.md` — the rubric every ExecPlan follows
- `docs/conventions/` — the five harnesses
- `docs/ARCHITECTURE.md` — the single map of domains, layers, and dependency directions
- `docs/PRODUCT_SENSE.md` — taste, non-goals, failure tolerances, and tiebreakers
- `docs/DESIGN.md` — the design contract for the three apps
- `docs/QUALITY_SCORE.md` — graded matrix of the platform's current state

## Repository layout

```
argus/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── .pre-commit-config.yaml
├── .gitignore
├── docs/                          ← System of record
│   ├── PLANS.md                   ← ExecPlan rubric
│   ├── ARCHITECTURE.md            ← Domain and layer map
│   ├── PRODUCT_SENSE.md           ← Taste, non-goals, tiebreakers
│   ├── DESIGN.md                  ← Design contract for the three apps
│   ├── QUALITY_SCORE.md           ← Current-state grading matrix
│   ├── conventions/               ← The five harnesses, documented
│   ├── product-specs/             ← Per-app feature specifications
│   │   ├── shared/                ← Cross-cutting specs (audio, docs, calibration)
│   │   ├── argus/                 ← AI QA specs
│   │   ├── metis/                 ← Business diagnosis specs
│   │   └── hermes/                ← Autonomous service agent specs
│   ├── design-docs/               ← Per-app design documents
│   │   ├── shared/                ← Shared UI surfaces
│   │   ├── argus/                 ← QA review surface
│   │   ├── metis/                 ← Triage kanban
│   │   └── hermes/                ← Citizen chat, action confirmation
│   ├── exec-plans/
│   │   ├── active/                ← In-flight ExecPlans
│   │   ├── completed/             ← Shipped ExecPlans
│   │   └── archived/              ← Cancelled / absorbed
│   ├── adr/                       ← Architecture Decision Records
│   ├── experiments/               ← "I don't know" protocol artifacts
│   ├── retrospectives/            ← Cross-plan retrospectives
│   └── references/                ← External reference material
├── .claude/                       ← Mechanical enforcement
│   ├── hooks/                     ← PreToolUse / PostToolUse / commit-msg
│   ├── tests/                     ← Structural tests over the repo itself
│   ├── skills/                    ← Custodial subagents
│   ├── decisions/                 ← dep-vetter outputs
│   └── sensitive-paths.txt
├── .github/
│   └── workflows/harness.yml
├── src/                           ← Application code (created by ExecPlans)
│   └── argus/                     ← Python package (domain/layer structure)
├── tools/                         ← Lint and enforcement tools
│   └── lint/                      ← Architectural-edge linters
└── tests/                         ← Application and structural tests
```
