# ARCHITECTURE.md

## 1. Domain inventory

### QA Engine
Handles post-call analysis, scoring against 27 rubrics, and verdict generation.
Justification: Real-time call interception or live-agent whispering is a non-goal.
Source: `docs/PRODUCT_SENSE.md` Non-goals — "Real-time call interception or live-agent whispering."

### Knowledge Base
Scoped to RegTech operational knowledge (CA certificates, e-seals, corporate registration, annual reporting, credit restoration). Provides entity extraction, intent-tree navigation, and fact-checking context.
Justification: General-purpose RAG or open-domain QA is a non-goal.
Source: `docs/PRODUCT_SENSE.md` Non-goals — "General-purpose RAG or open-domain QA."

### Report Generation
Produces QA reports (stdout/Rich tables, JSON files) and business-diagnosis triage summaries. Does not manage tickets or own CRM state.
Justification: Replacement of existing Jira/CRM systems is a non-goal.
Source: `docs/PRODUCT_SENSE.md` Non-goals — "Replacement of existing Jira/CRM systems."

### CLI Runtime
The delivery mechanism. Parses arguments, orchestrates pipeline stages, formats output, and sets exit codes.

---

## 2. Layered model

Layers (innermost -> outermost):
```
types -> config -> io -> core -> cli
```

Rule: a layer may import from layers to its left. It must not import from layers to its right. Cross-domain communication within the same layer must pass through explicit interfaces.

Providers:
- **ConfigProvider** (lives in `config` layer) — owns settings, environment variables, thresholds, and rubric definitions.
- **IOProvider** (lives in `io` layer) — owns filesystem access, network calls, external API clients, and subprocess invocation.

---

## 3. Dependency matrix

| | QA Engine | Knowledge Base | Report Generation | CLI Runtime |
|---|---|---|---|---|
| QA Engine | — | via Providers | `QAReport` | none |
| Knowledge Base | via Providers | — | `KBCoverage` | none |
| Report Generation | `ReportInput` | `KBCoverage` | — | none |
| CLI Runtime | `QAAgentInterface` | `KBQueryInterface` | `ReportOutputInterface` | — |

Notes:
- QA Engine and Knowledge Base do not import each other directly; they coordinate through ConfigProvider (thresholds, rubrics) and IOProvider (LLM client, KB filesystem).
- Report Generation receives structured data from QA Engine (`ReportInput`) and Knowledge Base (`KBCoverage`) and renders it; it does not call back into either domain.
- CLI Runtime is the only domain that imports from all others; it is the outermost layer.

---

## 4. Boring-tech ledger

| Dependency | Chosen for | Alternative rejected | Rejection reason |
|---|---|---|---|
| typer | Agent legibility: declarative CLI definitions with automatic `--help` generation | click, argparse | Source: pyproject.toml already lists typer; migrating would add churn without benefit. Confidence: low — if typer limits subcommand nesting depth, revisit. |
| pytest | Reliability: test runner with plugin ecosystem | unittest, nose2 | Source: pyproject.toml dev dependencies; pytest's fixture system is used by existing tests. |
| ruff | Agent legibility: single tool replaces black, isort, flake8, pylint | separate tools | Source: pyproject.toml dev dependencies; reduces CI time and config surface. |
| import-linter | Reliability: mechanical enforcement of layer boundaries | manual code review | Source: .importlinter exists; prevents layer violations at commit time. |
| mypy | Reliability: strict mode forces type annotations on all public APIs | pyright | Source: pyproject.toml dev dependencies; closer integration with ruff's per-file-ignores and pre-commit. |
| pre-commit | Reliability: normalizes hook configuration across machines | hand-managed scripts in `.git/hooks/` | Source: docs/plans/completed/0001-bootstrap-harness.md Decision Log; bundles gitleaks, commit-msg checker, and future hooks under one config file. |
| pydantic | Reliability: runtime validation and serialization for domain models | dataclasses + manual validation | Source: docs/PRD/Fact-Checking.md describes Pydantic v2 models as the data layer; used by existing schemas. |
| rich | Agent legibility: formatted tables and panels in CLI stdout | plain text, colorama | Source: docs/DESIGN.md defines `ReportTable`, `ScorePanel`, `ProgressIndicator` as Rich-based components. |

---

## 5. Per-layer contracts

### types
- **Parsing:** All Pydantic models validate on construction; no raw dicts pass beyond this layer.
- **Logging:** No logging in types layer.
- **Testing:** Every model has at least one instantiation test with valid and invalid data.

### config
- **Parsing:** Config files (TOML, env vars) are parsed and normalized into Pydantic models from `types/` before being returned to callers. No `os.environ` lookups outside this layer.
- **Logging:** Log only at load time (info: which file was read; warning: fallback default used).
- **Testing:** Every config key has a test for default value, override via env var, and validation error on bad input.

### io
- **Parsing:** All external data (HTTP responses, file reads) is parsed into Pydantic models from `types/` at the boundary before crossing into `core/`. No raw bytes or untyped dicts leak past this layer.
- **Logging:** Log at debug level for each I/O operation (URL, file path, status code). Log at warning level for retries.
- **Testing:** Every I/O function has a test using mocked filesystem or recorded HTTP cassette (via `vcrpy` or `respx`). Live-network tests do not count toward the verification floor.

### core
- **Parsing:** Inputs are already Pydantic models; no additional parsing except for LLM response JSON, which is validated into models immediately after decoding.
- **Logging:** Log at info level for stage start/end and at warning level for recoverable failures (e.g., ASR-suspect routing to human_review). No debug-level dumping of full model contents.
- **Testing:** Every pipeline stage has a unit test with mocked I/O and at least one integration test invoking the CLI subprocess with a sample transcript.

### cli
- **Parsing:** Arguments are parsed by Typer and immediately passed into `core/` or `config/` functions. No business logic parsing in CLI modules.
- **Logging:** No logging in CLI modules; use `typer.echo` for stdout and `typer.secho(..., err=True)` for stderr.
- **Testing:** Every command has an integration test invoking `argus <command>` as a subprocess and asserting on exit code and stdout/stderr.
