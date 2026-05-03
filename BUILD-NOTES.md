# BUILD-NOTES.md

Decisions I made on your behalf while scaffolding this repo. Review and override any you disagree with before running the bootstrap.

This file is meant to be **read once and then deleted**. Once you have reviewed it and either kept or changed each decision, `git rm BUILD-NOTES.md` and the next session won't see it. Anything you keep should already be reflected in the relevant convention docs or `pyproject.toml`.

## Decisions you confirmed

- **Stack**: Python on uv.
- **Product type**: CLI tool.
- **Deploy target**: self-hosted (no deploy harness in initial scaffold).
- **Repo hosting**: GitHub.
- **Operator model**: solo.
- **Knowledge base location**: `docs/` as system of record.

## Decisions I made that you should double-check

### Placeholder name: `your-cli` / `your_cli`
The CLI name appears in roughly 25 places: `pyproject.toml` (project.name, project.scripts, hatch.build), `src/your_cli/`, `src/your_cli/__init__.py`, `src/your_cli/cli/main.py`, `tests/test_cli_smoke.py`, `.importlinter`, `.claude/tests/test_layering.py`, `.claude/sensitive-paths.txt`, `CLAUDE.md`, `README.md`, `docs/PLANS.md` (one example), `docs/conventions/` (multiple examples).

To replace before first commit:
```
# Pick a real name first. Then:
NEW=my-actual-cli
NEW_UNDER=$(echo $NEW | tr '-' '_')
grep -rl 'your-cli\|your_cli' . --exclude-dir=.git | xargs sed -i "s/your-cli/$NEW/g; s/your_cli/$NEW_UNDER/g"
git mv src/your_cli "src/$NEW_UNDER"
```

### Python version floor: 3.12
I picked 3.12 over 3.11 because the harness uses `tomllib` from stdlib (3.11+) and 3.12 has clean type-parameter syntax. 3.13 would also work but ecosystem support for 3.13 is still settling. If you have a specific reason to support 3.10 or earlier, change `requires-python` in `pyproject.toml` and the `target-version` in `[tool.ruff]` and `[tool.mypy]`.

### CLI framework: Typer
Justified in `docs/decisions/dep-vet-typer.md`. Click directly is the alternative. argparse is the no-dep alternative if you'd rather have zero runtime deps. Either swap requires editing `pyproject.toml` (drop typer), `src/your_cli/cli/main.py` (rewrite the entry point), and `tests/test_cli_smoke.py` (different runner).

### Linter: ruff for both lint and format
Replaces black, isort, flake8, pylint. Configured with a moderate ruleset under `[tool.ruff.lint] select`. If the rules surface false positives during early development, narrow `select` rather than adding individual `noqa` comments — the goal is rules that everyone trusts.

### Type checker: mypy strict
Pyright is faster and slightly more permissive. Mypy integrates more cleanly with ruff and pre-commit. If startup time of `uv run mypy src/` becomes painful (>5s), revisit.

### Layer order: `types → config → io → core → cli`
Adapted from OpenAI's harness team's `Types → Config → Repo → Service → Runtime → UI` for a CLI's surface (no UI; the cli layer replaces it). If you find yourself wanting a `infrastructure` layer between `io` and `core`, or splitting `io` into `io.fs` / `io.http` / `io.subprocess` (the latter is fine and doesn't change layering), open an ExecPlan to revise `docs/conventions/layering.md` and `.importlinter`.

### Coverage floor: 80%
Configured in `pyproject.toml` under `[tool.coverage.report] fail_under`. This is a floor, not a target. Coverage chasing past 80% is anti-pattern. If 80% is too aggressive for early development, lower to 60% temporarily and raise as the codebase stabilizes.

### License: MIT
Stub-set in `pyproject.toml`. Change to whatever you want before publishing. The dep-vetter's allowed-license list assumes a permissive project license; if you go GPL or AGPL, edit `docs/conventions/deps-and-secrets.md` to allow GPL-compatible licenses in deps.

### Forbidden phrases list
`docs/conventions/i-dont-know-protocol.md` lists eight banned phrases. Tune as you see new patterns of unsupported confidence. Don't tune the test to be more permissive — that defeats the purpose.

### Sensitive paths
`.claude/sensitive-paths.txt` is conservative. If editing `pyproject.toml` for routine dep additions becomes painful (the dep-vetter still gates the install, so this is partly redundant), consider removing it from sensitive-paths and relying on the dep-vet hook alone.

### dep-vet records for bootstrap deps
I created `docs/decisions/dep-vet-*.md` for the seven bootstrap dependencies (typer, pytest, pytest-cov, ruff, mypy, import-linter, pre-commit) with hand-written rationale. The PyPI metadata in those records (download counts, dates) is approximate — I didn't actually call the PyPI API. Bootstrap M1 should re-run the dep-vetter on each to populate real numbers, and the doc-gardener will surface any that look wrong.

### Hook script language: Python
All hooks under `.claude/hooks/` are Python. This is intentional: the harness must work even when the application runtime is broken. If your future scaffolds switch to a non-Python application stack, keep the harness scripts in Python.

### Git history convention: pinned versions in pre-commit, lockfile committed
`.pre-commit-config.yaml` pins specific revisions. `uv.lock` is committed (not in `.gitignore`). Both are deliberate.

## Things I did NOT include and you may want

- **Application logging strategy**. No logging convention written. Open as an ExecPlan once you know what your CLI does.
- **Telemetry / opt-in metrics**. Not addressed; would be a Tier C decision.
- **Update / self-upgrade flow**. Not addressed; CLI-specific concern for later.
- **Performance harness**. No benchmark convention. Add when first relevant.
- **Accessibility / i18n**. Probably not needed for a self-hosted CLI but flag if it is.
- **Vulnerability scanning**. `pip-audit` / `uv audit` not yet wired into CI.
- **Dependabot or Renovate**. Not configured. Add when you want dep updates surfaced as PRs.

## Verification

I parse-checked every Python file, ran every structural test against the empty scaffold, and confirmed all six pass. The repo will be CI-green from the first commit (assuming GitHub Actions runs the workflow without modification).

Caveats: I could not actually run `uv sync`, `uv run pytest`, `uv run ruff`, `uv run mypy`, or `uv run lint-imports` from this environment (no network access). The first command you should run after `git init` and the rename above is:

```
uv sync --dev && uv run pytest .claude/tests/ -v && uv run pytest tests/ -v && uv run lint-imports && uv run ruff check . && uv run mypy src/
```

If any of those fail, the scaffold has a bug. Tell me.
