# QUALITY_SCORE.md

Graded table of domain x layer intersections that exist in code.

| Domain x Layer | coverage | boundary-respect | boring-tech-adherence | doc-freshness | test-floor-met |
|---|---|---|---|---|---|
| CLI Runtime x cli | C — 2 smoke tests only; no real coverage | B — import-linter configured in `.importlinter` and `pyproject.toml`; only cli layer has code to enforce | A — uses typer from ledger (`src/argus/cli/main.py`) | C — design-docs exist but are all proposed, none implemented | D — smoke tests only; no contract tests for CLI parsing boundary |
| CLI Runtime x types | C — empty `__init__.py`; no models to cover | B — import-linter enforces no imports from rightward layers | A — empty module; no tech debt introduced | C — design-docs propose types but none implemented | D — no instantiation tests because no models exist yet |
| CLI Runtime x config | C — empty `__init__.py`; no config keys to cover | B — import-linter enforces no imports from rightward layers | A — empty module; no tech debt introduced | C — config contract documented in ARCHITECTURE.md but no code | D — no default/override/validation tests because no config exists yet |
| CLI Runtime x io | C — empty `__init__.py`; no I/O functions to cover | B — import-linter enforces no imports from rightward layers | A — empty module; no tech debt introduced | C — I/O contract documented in ARCHITECTURE.md but no code | D — no mocked I/O tests because no I/O functions exist yet |
| CLI Runtime x core | C — empty `__init__.py`; no pipeline stages to cover | B — import-linter enforces no imports from rightward layers | A — empty module; no tech debt introduced | C — core contracts documented in ARCHITECTURE.md but no code | D — no unit or integration tests because no stages exist yet |
| QA Engine x core | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md |
| QA Engine x types | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md |
| Knowledge Base x core | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md |
| Knowledge Base x types | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md |
| Report Generation x core | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md |
| Report Generation x types | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md | C — no src/ exists yet — planned scaffold described in ARCHITECTURE.md |

## D/F remediation

| Cell | Grade | Remediation |
|---|---|---|
| CLI Runtime x cli — test-floor-met | D | TODO: ExecPlan `0002-cli-contract-tests.md` — add integration tests invoking `argus <command>` as subprocess and asserting exit code and stdout. |
| CLI Runtime x types — test-floor-met | D | TODO: ExecPlan `0003-domain-models.md` — implement first Pydantic model in `src/argus/types/` and add instantiation test with valid and invalid data. |
| CLI Runtime x config — test-floor-met | D | TODO: ExecPlan `0004-config-boundary.md` — implement ConfigProvider and add tests for default value, env override, and validation error. |
| CLI Runtime x io — test-floor-met | D | TODO: ExecPlan `0005-io-boundary.md` — implement IOProvider stub and add mocked filesystem or HTTP test. |
| CLI Runtime x core — test-floor-met | D | TODO: ExecPlan `0006-core-pipeline.md` — implement first pipeline stage and add unit test with mocked I/O plus integration test via CLI subprocess. |

## Top five gaps

1. **Empty core/ layer has no implementation** — affects 5 cells (CLI Runtime x core, QA Engine x core, Knowledge Base x core, Report Generation x core, and their downstream test floors) — minimum action: implement core domain models and pipeline stages.
2. **No contract tests for layer boundaries** — affects 4 cells (types, config, io, core test-floor-met) — minimum action: add import-linter CI gate (enforced) and boundary tests for each layer contract.
3. **No real QA Engine code in core/** — affects 2 cells (QA Engine x core, QA Engine x types) — minimum action: implement atomizer and fact-checker modules.
4. **Test floor not met for types layer** — affects 3 cells (CLI Runtime x types, QA Engine x types, Knowledge Base x types, Report Generation x types) — minimum action: add Pydantic model instantiation tests as soon as first model is implemented.
5. **Design-docs are all proposed, none implemented** — affects 3 cells (doc-freshness across all domains) — minimum action: implement at least one feature end-to-end so design-docs transition from proposed to verified.

---

Last graded: 2026-05-05
Next regrade: 2026-05-19
Graded by: harness-go/04-quality-score
