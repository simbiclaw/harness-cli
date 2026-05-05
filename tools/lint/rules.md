# tools/lint/rules.md

For every rule in ARCHITECTURE.md, add a row:

| Rule | Location in ARCHITECTURE.md | Enforcement | Status |
|---|---|---|---|
| Layer directionality (imports flow left-to-right: types -> config -> io -> core -> cli) | Section 2: Layered model | import-linter | enforced: .importlinter |
| Types validation (Pydantic models validate on construction; no raw dicts beyond types layer) | Section 5: types / Parsing | structural-test | Aspiration: .claude/tests/test_type_contracts.py does not exist yet — Revisit: 2026-05-19 |
| No raw dicts beyond types layer | Section 5: types / Parsing | lint | enforced: ruff ANN annotations + mypy strict in pyproject.toml |
| No logging in types layer | Section 5: types / Logging | lint | enforced: ruff ANN + manual review |
| Config parsing boundary (no os.environ outside config layer) | Section 5: config / Parsing | structural-test | Aspiration: .claude/tests/test_config_boundary.py does not exist yet — Revisit: 2026-05-19 |
| Config logging contract | Section 5: config / Logging | lint | Aspiration: no automated enforcement yet — Revisit: 2026-05-19 |
| I/O parsing boundary (external data parsed into Pydantic models before crossing into core) | Section 5: io / Parsing | structural-test | Aspiration: .claude/tests/test_io_boundary.py does not exist yet — Revisit: 2026-05-19 |
| I/O logging contract | Section 5: io / Logging | lint | Aspiration: no automated enforcement yet — Revisit: 2026-05-19 |
| Core logging contract (no debug dumping of full model contents) | Section 5: core / Logging | lint | Aspiration: no automated enforcement yet — Revisit: 2026-05-19 |
| CLI parsing boundary (no business logic parsing in CLI modules) | Section 5: cli / Parsing | structural-test | Aspiration: .claude/tests/test_cli_thinness.py does not exist yet — Revisit: 2026-05-19 |
| CLI logging contract (use typer.echo / typer.secho, no logging module) | Section 5: cli / Logging | lint | Aspiration: no automated enforcement yet — Revisit: 2026-05-19 |
| Cross-domain communication within same layer must pass through explicit interfaces | Section 2: Layered model | structural-test | Aspiration: no automated enforcement yet — Revisit: 2026-05-19 |
| QA Engine domain boundary justified by non-goal | Section 1: Domain inventory | documentation | enforced: cites PRODUCT_SENSE.md non-goal |
| Knowledge Base domain boundary justified by non-goal | Section 1: Domain inventory | documentation | enforced: cites PRODUCT_SENSE.md non-goal |
| Report Generation domain boundary justified by non-goal | Section 1: Domain inventory | documentation | enforced: cites PRODUCT_SENSE.md non-goal |
| Dependency matrix completeness (all domain x domain pairs listed) | Section 3: Dependency matrix | documentation | enforced: matrix covers 4x4 |
