# Layered Architecture

`src/argus/` is partitioned into five layers. Imports may flow only upward in this list:

```
types  →  config  →  io  →  core  →  cli
```

A module in layer N may import from layers ≤ N. Imports flowing the other direction fail two structural tests, both running in CI:

- `import-linter` (configured in `.importlinter` at the repo root)
- `.claude/tests/test_layering.py` (an AST-based check, redundant on purpose)

Why redundant: import-linter is the production tool and runs fast in CI. The AST test is short, self-contained, and exists as a backstop in case import-linter is broken or unavailable. They check the same property; both must pass.

## What each layer is for

### `argus.types`

The lowest layer. Pure data definitions: dataclasses, TypedDicts, Enums, Pydantic models if used, Protocol classes for interface declarations. No I/O. No business logic. No imports from any other `argus.*` module. Imports from the standard library and from typing helpers (`typing_extensions`, `pydantic`) are fine.

If a file in `types/` would benefit from a "default value" or "factory" — a function that constructs an instance from external state — that function does not belong here. It belongs in `config/` or `core/`. `types/` contains the *shape*, not the *creation* logic.

### `argus.config`

Configuration loading and validation. Reads from environment variables, config files, default-value sources. Knows about XDG paths, TOML parsing, the schema version. May import from `types/`. May *not* import from `io/`, `core/`, or `cli/`.

Note: `config/` can do file reads as part of its job, but only of *config-shaped* files. General file I/O lives in `io/`.

### `argus.io`

Filesystem, network, subprocess, and OS interactions. Reading data files, writing output, calling external programs, fetching URLs, talking to the OS keyring. Each I/O concern is its own submodule (`io.fs`, `io.http`, `io.subprocess`). May import from `types/` and `config/`.

The split between `config/` and `io/` is a recurring source of confusion: configuration is "things the user sets that govern how the CLI behaves." I/O is "things the CLI does to the world or reads from the world that are not configuration." When in doubt: if the file format is hand-edited by users, it's config; if it's data the CLI processes, it's I/O.

### `argus.core`

Domain logic. The actual transformations and computations the CLI performs. Pure where possible. May import from `types/`, `config/`, and `io/`.

Core functions take inputs (often from `io/` reads parameterized by `config/` settings), produce outputs (often passed back to `io/` writes), and ideally do not themselves perform I/O. Easier to test, easier to refactor, easier to reason about.

### `argus.cli`

Typer command definitions. The outermost layer. Glue between user invocations and core logic. May import from any layer.

CLI modules are deliberately thin: parse arguments, call into core, format the result for stdout/stderr, set the exit code. Anything more complex is core logic that should move down a layer.

## What this rule prevents

- A `core/` function calling into a Typer command (would create a circular runtime dependency on argv).
- An `io/` function reading from `core/` results before they exist (inverts the data flow).
- A `config/` module shelling out to a subprocess to determine a config value (turns config loading into an I/O operation, breaks reproducibility).
- A `types/` module knowing about file paths or XDG (couples the data shape to its source).

## When the layers feel wrong

If you find yourself wanting to import "downward" — say, `core/normalize.py` needs to read a config file mid-computation — the right move is *almost never* to break the rule. Instead:

- Pass the config value in as a parameter (most common fix).
- Move the function to `cli/` if it's really a glue concern.
- Restructure the data flow so the I/O happens before `core/` runs.

If after honest attempt none of those work, that's a signal the layering is wrong for this codebase. Open an ExecPlan to revise the layering rule. Do not silently bypass it.

Last reviewed: 2026-07-20
