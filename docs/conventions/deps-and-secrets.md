# Dependencies and Secrets

Two rules. Both non-negotiable. Both mechanically enforced.

## New dependencies must be vetted

Before any direct dependency is added to `pyproject.toml` (under `[project] dependencies` or `[dependency-groups] dev`), the dep-vetter skill checks:

1. **Package age**: more than 30 days since first publish on PyPI.
2. **Weekly downloads**: more than 1000 (per `pypistats`).
3. **Recent activity**: at least one commit in the source repository within the last 90 days.
4. **License**: compatible with project license. Default allowed list: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, MPL-2.0, PSF-2.0.

Any failure rejects the dependency. Override only via a commit message containing the literal token `[dep-override-approved-by-human]`, which is itself caught and surfaced by the doc-gardener for audit.

## Decision Log entry per dependency

Every direct dependency in `pyproject.toml` has a Decision Log entry in some ExecPlan naming the package and its rationale. The structural test `test_dep_decisions.py` walks the manifest and Decision Logs and fails CI if any dependency lacks a corresponding entry.

This rule applies to dev dependencies (under `[dependency-groups]`) too. Test frameworks, linters, and type-checkers are often left unjustified in real-world projects; here they are not.

## Pinning

- `pyproject.toml`: minor-range floats permitted (`>=1.2.0`, `~=1.2`). No upper-bound pins unless there is a specific Decision Log entry explaining why.
- `uv.lock`: exact versions, committed. Always.
- Never: `latest`, `*`, unbounded `>=`, or version specifiers without a lower bound.

`uv lock` regenerates the lockfile; commits that change the lockfile must include a Decision Log entry naming the upgrade or the new dependency that prompted the change.

## Secrets

- `.env` is gitignored. Always.
- `.env.example` is committed; contains stub values only.
- For a self-hosted CLI, the user supplies secrets via env vars at runtime or via a config file under `~/.config/argus/` (or `$XDG_CONFIG_HOME`). The repo has no live secrets, ever.
- Default config-file paths the CLI reads from must be added to the user-facing documentation, not just to source comments.

## Secret detection

- Pre-commit hook runs `gitleaks` against staged changes. Any match blocks commit.
- CI job runs `gitleaks` over the entire history on every PR (catches anything that slipped past pre-commit on a previous commit).
- The `.gitignore` template covers `.env*`, `*.pem`, `*.key`, `id_rsa*`, `**/credentials.json`, `**/service-account*.json`.

If a secret is detected post-commit, the response is **rotation, then history rewrite**, in that order. A new ExecPlan documents the incident and references the doc-gardener entry that caught it (or, if not caught, identifies why the detection missed and what new pattern to add).

## What "self-hosted CLI" means for this rule

Because users install and run the CLI on their own machines, the secret threat model centers on:

- Secrets the *user* configures, which the CLI must never log to stdout or stderr (the verification floor's stdout-content assertions help catch accidental leaks).
- Secrets the *developer* might paste into a test fixture during debugging (the gitleaks history scan catches these).
- API keys for any third-party service the CLI calls; these are user-supplied and must come from env vars or a config file, never from defaults baked into source.

The CLI must redact secrets in any error message it produces. The Acceptance Test for any feature handling secrets includes a check that the secret value does not appear in stdout, stderr, or any logged artifact.

Last reviewed: 2026-05-01.
