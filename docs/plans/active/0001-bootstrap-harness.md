# 0001-bootstrap-harness

## Purpose

Lay down the harness scaffolding for this CLI: the convention docs, hook scripts, structural tests, skill definitions, CI workflow, and supporting infrastructure that every subsequent ExecPlan depends on. The product itself is not built in this plan — only the harness that lets agents build it.

The scaffolding has already been placed in the repository as the initial commit. This ExecPlan does two things: documents the rationale for every choice made during scaffolding (in Decision Log, satisfying the dep-decision and i-don't-know structural tests), and verifies each piece is functional through its Acceptance Test before being marked done.

## Big Picture

The harness has four layers, each enforced by different mechanisms:

- **Documentation** under `docs/conventions/` — read by agents at runtime. Soft enforcement.
- **Hooks** under `.claude/hooks/` — run by Claude Code on tool-use events. Block at edit-time.
- **Structural tests** under `.claude/tests/` — run by pytest in CI. Block at commit-time.
- **CI gates** at `.github/workflows/harness.yml` — run by GitHub Actions on PR. Block at merge-time.

In scope: verifying the scaffolding works end-to-end (uv sync, pytest, ruff, mypy, import-linter, hook scripts, CI workflow). Documenting every dep's rationale. Confirming hook activation.

Out of scope: choosing what the CLI actually does. That is a separate ExecPlan after the harness is live.

## Milestones

### M1: Verify uv environment installs and structural tests pass

Run `uv sync --dev`, then `uv run pytest .claude/tests/ -v` and `uv run pytest tests/ -v`. All tests pass. The CLI's smoke test (`tests/test_cli_smoke.py`) confirms `argus --help` and `argus version` work.

Acceptance Test: `tests/test_cli_smoke.py::test_help_runs` and `tests/test_cli_smoke.py::test_version_runs`.

### M2: Verify lint, type, and layer enforcement

Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, and `uv run lint-imports`. All four pass on the empty scaffold.

Acceptance Test: a CI run on the initial PR that completes all four checks green.

### M3: Verify hook scripts run

Pipe a synthetic JSON event into each hook (`pre_tool_use.py`, `post_tool_use.py`, `check_commit_msg.py`) and confirm exit code zero with appropriate output. Confirm `.claude/hooks/settings.json` parses as valid JSON.

Acceptance Test: `.claude/tests/test_hooks_runnable.py::test_each_hook_runs` (this test is created as part of M3; the test pipes a minimal mock event into each hook and asserts each exits 0 without traceback).

Notes: hook *activation* (registering them with Claude Code) is a Tier C step. After M3 completes, add an Awaiting Steering entry asking the human to confirm activation. Do not proceed to M4 until resolved.

### M4: Verify pre-commit hooks fire

Install pre-commit hooks (`uv run pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push`), then create a deliberately-bad commit message and confirm the commit-msg hook rejects it. Then create a properly-formatted commit and confirm it succeeds.

Acceptance Test: `.claude/tests/test_pre_commit_hooks.py::test_commit_msg_rejects_bad_format` (created in this milestone).

### M5: Verify CI workflow

Push the bootstrap branch. CI runs `harness.yml` and the four checks (structural tests, lint, types, layering, gitleaks) all pass.

Acceptance Test: green CI run on the bootstrap PR.

### M6: Self-archive

Move this ExecPlan from `docs/plans/active/0001-bootstrap-harness.md` to `docs/plans/completed/0001-bootstrap-harness.md`. Write the final entry in Outcomes & Retrospective below.

Acceptance Test: `.claude/tests/test_bootstrap_complete.py::test_bootstrap_archived` — asserts the bootstrap plan no longer lives under `active/` and does live under `completed/`.

Notes: this milestone modifies the very plan file it is part of. Do this in two commits: first writes the Outcomes & Retrospective section; second moves the file. Both commits use `harness(plans):` type with `Plan: docs/plans/active/0001-bootstrap-harness.md#milestone-6` (the trailer references the path *as it was* when the work was done).

## Progress

- [x] M1: Verify uv environment installs and structural tests pass  (created 2026-05-01, verified 2026-05-04)
- [x] M2: Verify lint, type, and layer enforcement  (created 2026-05-01, verified 2026-05-04)
- [x] M3: Verify hook scripts run  (created 2026-05-01, verified 2026-05-04)
- [x] M4: Verify pre-commit hooks fire  (created 2026-05-01, verified 2026-05-04)
- [ ] M5: Verify CI workflow  (created 2026-05-01)
- [ ] M6: Self-archive bootstrap  (created 2026-05-01)

## Decision Log

### Decision: Use Python on uv as the application stack

Rationale: stack chosen by the human at scaffolding time, before the harness existed. uv provides faster installs and better lockfile semantics than pip-tools or Poetry. Confidence: low.
Revisit: by 2026-08-01 if uv adoption stalls or a dealbreaker bug surfaces.

### Decision: Use Typer as the CLI framework

Rationale: typer integrates with type hints, plays well with mypy strict, and reduces boilerplate compared to argparse. Built on Click so the underlying behavior is well-known and well-tested. See dep-vet record for vetting details.
Source: docs/decisions/dep-vet-typer.md

### Decision: Use pytest as the test framework

Rationale: pytest is the framework that the verification floor convention and all structural tests under .claude/tests/ are written against. Switching frameworks would require rewriting every test.
Source: docs/decisions/dep-vet-pytest.md

### Decision: Use pytest-cov for coverage measurement

Rationale: required by the coverage gate (`fail_under=80`) configured in pyproject.toml [tool.coverage]. The verification floor convention specifies coverage as a floor not a goal, but the floor must be measured to be enforced.
Source: docs/decisions/dep-vet-pytest-cov.md

### Decision: Use ruff for both lint and format

Rationale: ruff replaces black, isort, flake8, and pylint in one tool, drastically reducing config-file surface area and dev-time check latency. Maintained by Astral, who also maintain uv.
Source: docs/decisions/dep-vet-ruff.md

### Decision: Use mypy in strict mode for type checking

Rationale: strict mode forces type annotations on all public APIs, which catches a class of bugs that would otherwise reach the Acceptance Test layer. Mypy was chosen over pyright for closer integration with ruff's per-file-ignores and pre-commit.
Source: docs/decisions/dep-vet-mypy.md

### Decision: Use import-linter to enforce the layering rule

Rationale: import-linter is purpose-built for the "imports may only flow upward in a defined layering" rule documented in docs/conventions/layering.md. Backstopped by an AST-based test in .claude/tests/test_layering.py for redundancy.
Source: docs/decisions/dep-vet-import-linter.md

### Decision: Use pre-commit framework for git-hook orchestration

Rationale: pre-commit normalizes hook configuration across machines and bundles gitleaks, the commit-msg checker, and any future hooks (link-checker, spell-checker, etc.) under one config file. Avoids hand-managed scripts in `.git/hooks/`.
Source: docs/decisions/dep-vet-pre-commit.md

### Decision: Layer order types → config → io → core → cli

Rationale: derived from the OpenAI harness team's reported Types→Config→Repo→Service→Runtime→UI layering, adapted for a CLI tool's surface (no UI; the cli layer replaces it; no Service vs Runtime distinction since CLIs don't host long-lived services in this scope).
Source: docs/conventions/layering.md

### Decision: Self-hosted, no deploy harness in initial scaffold

Rationale: scope decision made at scaffolding time. The deploy harness is its own future ExecPlan when the product is ready to ship.
Source: docs/conventions/verification-floor.md (which explicitly defers preview-environment Acceptance Tests).

### Decision: Forbidden phrases enforced lexically, not semantically

Rationale: a regex test catches the most common patterns of unsupported-confidence claims. A determined or confused agent could paraphrase past it ("the canonical way", "what most teams do"). Confidence: low.
Revisit: by 2026-09-01, expand the forbidden list based on observed failure modes.

## Surprises & Discoveries

### M1: Typer treats no-arg `@app.command()` as callback when no explicit callback exists

`@app.command()` on a function with no parameters (like `def version()`) was treated as the app callback when no `@app.callback()` was defined. The function's docstring replaced the app-level help text, and the subcommand was never registered. Fix: add an explicit `@app.callback()` before defining commands.

Also worth noting: `uv sync --dev` does NOT install optional dependencies in PEP 621 layout — it uses `--extra dev` (or `--group dev` for uv-native groups). The plan's instructions said `--dev` which was stale.

### M2: import-linter container/layer path collision

`.importlinter` defined `containers = argus` and `layers = argus.cli` etc. — import-linter joins container to layer, so it looked for `argus.argus.cli`. Fix: layers must be relative to the container: `cli`, `core`, `io`, `config`, `types`.

Also: `ruff` 0.15 has removed rules ANN101/ANN102 — referencing them in `pyproject.toml` `[tool.ruff.lint] ignore` generates warnings but doesn't fail.

### M3: `tests/` and `.claude/tests/` namespace collision

Both directories have `__init__.py` and are both named `tests`. Pytest collects one first, then fails to import the other's modules under the `tests` namespace. Fix: remove `__init__.py` from `.claude/tests/` since it's not a Python package — it's a harness test suite.

### M4: pre-commit `--hook-stage` flag required for non-default stages

Running `pre-commit run commit-msg-format` failed because the hook is defined with `stages: [commit-msg]` but pre-commit defaults to the `pre-commit` stage. Fix: pass `--hook-stage commit-msg` to target the correct stage.

Also: `.pre-commit-config.yaml` was deleted from the working tree (pre-existing state). Restored from git HEAD. Ruff pin updated from v0.5.7 to v0.15.12 to match the installed version.

## Awaiting Steering

### Hook activation (M3 post-requisite, blocking M4)

The hook scripts under `.claude/hooks/` are verified runnable (M3 Acceptance Test: `test_hooks_runnable.py`). They are also registered in `.claude/hooks/settings.json` and will be activated by Claude Code automatically when that file is present.

**Action required**: Confirm that the hooks have been activated by running something that triggers a guard (e.g., edit a sensitive path, or try a package install without a dep-vet record) and observing the block message. Once confirmed, mark this section "Awaiting Steering: resolved" and proceed to M4.

## Outcomes & Retrospective

*(Written at M6. Empty until then.)*
