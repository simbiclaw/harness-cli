---
feature-slug: business-diagnosis
verification-status: proposed
last-reviewed: 2026-07-20
---
**Corresponding product-spec:** [docs/product-specs/business-diagnosis.md](../product-specs/business-diagnosis.md)


# business-diagnosis Design Doc

## User job

When product defects are buried in calls, the business analyst wants auto-triaged tickets with severity scores so that data-driven fixes happen faster.

## UI surface (CLI stdout states)

- **Idle**: No UI; invoked via a subcommand or flag that triggers triage analysis over a batch of transcripts.
- **Processing**: `ProgressIndicator` shows aggregation progress across the transcript corpus.
- **Result**: `ReportTable` displays clusters of issues found in >= 3 distinct calls within 7 days, with severity score, sample transcript excerpts, and suggested investigation. `ScorePanel` shows aggregate severity distribution.
- **Error**: `ErrorBanner` on stderr if Jira integration fails or the transcript batch is empty.

## Component usage

- `ReportTable` — issue clusters with call volume, severity score, and sample excerpts.
- `ScorePanel` — aggregate severity distribution (e.g., high/medium/low counts).
- `VerdictList` — per-issue triage rationale and recommended assignee.
- `ProgressIndicator` — corpus aggregation and Jira ticket creation progress.
- `ErrorBanner` — Jira API failure or missing configuration.

## Core-beliefs citations

- Belief 1 (explicit CLI flags) — Triage mode is triggered by an explicit flag (e.g., `--triage`) rather than auto-detecting call volume.
- Belief 3 (stable `--json` equivalent) — `--json` output for triage results enables CI assertions on ticket counts and severity scores.
- Belief 4 (human-in-the-loop checkpoints) — Tickets require human validation before routing to engineering, matching the PRD loop.

## Test selectors

- `test_triage_threshold_3_calls` — Assert that issues appearing in < 3 calls are not surfaced.
- `test_severity_score_in_json` — Assert that every triage item in JSON output contains a numeric `severity_score` field.
- `test_human_review_gate_present` — Assert that the output includes a `human_review_required` flag or equivalent checkpoint.
- `test_jira_failure_emits_error_banner` — Assert that Jira API errors produce a non-zero exit code and `ErrorBanner` on stderr.
- `test_no_color_flag_disables_rich` — Assert that `--no-color` strips ANSI codes from triage stdout.

## Open design questions

- What Jira project and issue types should tickets map to?
- What is the threshold for "severity" — call volume, sentiment, or business impact?
