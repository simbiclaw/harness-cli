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
│   ├── conventions/               ← The five harnesses, documented
│   ├── plans/
│   │   ├── active/                ← In-flight ExecPlans
│   │   ├── completed/             ← Shipped ExecPlans
│   │   └── archived/              ← Cancelled / absorbed
│   ├── adr/                       ← Architecture Decision Records
│   ├── experiments/               ← "I don't know" protocol artifacts
│   └── retrospectives/            ← Cross-plan retrospectives
├── .claude/                       ← Mechanical enforcement
│   ├── hooks/                     ← PreToolUse / PostToolUse / commit-msg
│   ├── tests/                     ← Structural tests over the repo itself
│   ├── skills/                    ← Custodial subagents
│   ├── decisions/                 ← dep-vetter outputs
│   └── sensitive-paths.txt
├── .github/
│   └── workflows/harness.yml
├── src/                           ← Application code (created by ExecPlans)
└── tests/                         ← Application tests
```
