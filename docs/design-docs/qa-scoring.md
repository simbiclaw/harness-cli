---
feature-slug: qa-scoring
verification-status: proposed
last-reviewed: 2026-07-20
---
**Corresponding product-spec:** [docs/product-specs/qa-scoring.md](../product-specs/qa-scoring.md)


# qa-scoring Design Doc

## User job

When reviewing agent performance, the QA supervisor wants an automated score against 27 rubrics so that manual sampling is no longer needed.

## UI surface (CLI stdout states)

- **Idle**: No UI; the command is invoked via `python cli.py -t <transcript>`.
- **Processing**: `ProgressIndicator` shows the current pipeline stage (Stage -1 through 6).
- **Result**: `ScorePanel` displays overall score and grade. `ReportTable` shows per-dimension breakdown. `VerdictList` lists each rubric verdict with rationale.
- **Error**: `ErrorBanner` on stderr for ASR parse failure, API timeout, or missing `--no-color` support.

## Component usage

- `ScorePanel` — overall score and grade (优秀 / 良好 / 合格 / 不合格).
- `ReportTable` — per-dimension weighted scores with NA exclusion noted.
- `VerdictList` — 27 rubric verdicts; veto failures are highlighted.
- `ProgressIndicator` — shown during the 8-stage pipeline.
- `ErrorBanner` — emitted on `ASR_PARSE_ERROR` or unrecoverable LLM failure.

## Core-beliefs citations

- Belief 2 (composable report sections) — The QA report is decomposed into ScorePanel, ReportTable, and VerdictList rather than a single monolithic template.
- Belief 3 (stable `--json` equivalent) — `cli.py -o output.json` emits the same report as stdout; automated tests assert against the JSON schema.
- Belief 5 (explicit numeric thresholds) — Grade thresholds and confidence thresholds are surfaced as numbers in JSON, not just rendered labels.

## Test selectors

- `test_cli_json_output_schema` — Assert that `-o` produces valid JSON with all required fields (`overall_score`, `grade`, `dimension_scores`, `verdicts`).
- `test_veto_forces_zero_score` — Assert that any `is_veto=True` rubric with a fail verdict forces `overall_score=0` and grade=不合格.
- `test_na_exclusion_in_scoring` — Assert that NA rubrics are excluded from both numerator and denominator.
- `test_no_color_flag_disables_rich` — Assert that `--no-color` strips ANSI codes from stdout.
- `test_progress_indicator_shown` — Assert that pipeline stages emit stage names to stderr or a spinner.

## Open design questions

- Awaiting Steering: Is the `human_review_callback` intended for a synchronous CLI prompt, an async webhook, or a batch queue?
- Awaiting Steering: Should the 27 rubrics remain code-defined in `config/rubric_items.py`, or should they be loaded from the empty `data/knowledge_base/QA_RUBRICS/rubrics.md` file?
