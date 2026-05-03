# Ask-Before-Assuming Threshold

Three tiers govern when Claude Code proceeds vs. escalates.

## Tier A — Proceed silently

Examples: naming a new internal helper function, choosing between two equivalent style options where one is already used elsewhere, fixing a typo, adding a unit test for an existing function, adding a docstring, importing a module already imported elsewhere in the same package.

Action: log a Decision Log entry only if the call shaped the implementation in a non-obvious way. Otherwise proceed without ceremony. Do not interrupt the human.

## Tier B — Proceed and flag

Examples: adding a new module under `src/argus/`, importing a peer of an already-vetted dependency (e.g. `tomli-w` if `tomli` is already in use — but still requires running `dep-vetter` first; the difference from Tier C is that a peer of an already-trusted maintainer is less surprising), choosing between two viable implementations of a documented feature, refactoring a function used in fewer than five places, adding a new pytest fixture.

Action: Decision Log entry with rationale. Mention in the next milestone commit message body so the human sees it on review. Note that "Tier B + dep" still requires the dep-vetter skill to run.

## Tier C — Stop and ask

Examples:

- Any new top-level dependency from a maintainer not already trusted by the project.
- Any change to the on-disk file formats this CLI reads or writes (these are public contracts even if undocumented; users have files in those formats).
- Any change to the CLI's command surface — adding/removing/renaming a subcommand, changing a flag's name or default, changing exit codes.
- Any change to the config file schema or environment-variable surface.
- Any change to logging output destined for stdout (which scripts may parse).
- Choice of CLI framework (argparse vs click vs typer vs cyclopts) — promote to ADR.
- Choice of config format (TOML vs YAML vs JSON vs INI) — promote to ADR.
- Choice of any third-party SaaS or external API the CLI will call.
- Deletion of more than 100 lines of existing code.
- Any change to `pyproject.toml` outside of `[dependency-groups]` (which is dev-only).

Action: stop. Add an "Awaiting Steering" section to the active ExecPlan describing the decision needed and the options. Do not proceed on related milestones until the human resolves it.

## When unsure of the tier

Default to Tier C. The cost of pausing for human input is minutes; the cost of an unflagged Tier-C decision shipped to users is hours to days. For a CLI specifically, the asymmetry is sharper than for a service: users have shell scripts that depend on output formats and exit codes, and a silent change can break automation that nobody knows exists until they file a bug.

## Sensitive paths (Tier C automatic)

Configurable in `.claude/sensitive-paths.txt`. Default contents for this CLI:

```
src/argus/cli/**          # The command-line surface itself
src/argus/config/**       # Config schema
docs/adr/**                  # Architecture decisions are not silently rewritten
.env*
.github/workflows/**
pyproject.toml
docs/PLANS.md
CLAUDE.md
```

Note: `src/argus/types/`, `src/argus/core/`, and `src/argus/io/` are *not* sensitive by default. Internal refactors there are Tier A or Tier B per the layered architecture rule. The sensitive list is for things users see (CLI surface, config schema) and for things the harness depends on.

Last reviewed: 2026-05-01.
