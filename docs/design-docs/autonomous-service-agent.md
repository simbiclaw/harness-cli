---
feature-slug: autonomous-service-agent
verification-status: proposed
last-reviewed: 2026-07-04
---

# autonomous-service-agent Design Doc

## User job

When a citizen navigates a complex government procedure, the customer wants an assistant that reasons over documentation and performs operations so that repeated calls are avoided.

## UI surface (CLI stdout states)

- **Idle**: No UI; invoked via a subcommand (e.g., `hermes run --procedure <id>`).
- **Processing**: `ProgressIndicator` shows the current reasoning step and documentation retrieval status.
- **Result**: `VerdictList` displays each procedural step with confirmation prompt status. `ScorePanel` shows overall completion percentage. `ReportTable` lists prerequisites and their fulfillment status.
- **Error**: `ErrorBanner` on stderr if documentation is missing, authentication fails, or a forbidden operation is requested.

## Component usage

- `VerdictList` — step-by-step procedure status with explicit confirmation prompts.
- `ScorePanel` — overall completion percentage and estimated remaining steps.
- `ReportTable` — prerequisites table showing fulfilled vs. pending requirements.
- `ProgressIndicator` — reasoning and documentation retrieval progress.
- `ErrorBanner` — authentication failure, missing documentation, or forbidden operation attempt.

## Core-beliefs citations

- Belief 1 (explicit CLI flags) — Each procedure is selected via an explicit `--procedure` flag rather than inferred from context.
- Belief 3 (stable `--json` equivalent) — `--json` output exposes step states and confirmation requirements for automated integration tests.
- Belief 4 (human-in-the-loop checkpoints) — Every autonomous action requires explicit user confirmation before execution, matching the PRD loop.

## Test selectors

- `test_procedure_json_schema` — Assert that `--json` output contains `steps`, `confirmation_required`, and `completion_percentage` fields.
- `test_confirmation_gate_blocks_execution` — Assert that steps marked `confirmation_required=true` do not proceed without explicit user input.
- `test_forbidden_operation_emits_error` — Assert that operations on the forbidden list produce an `ErrorBanner` and non-zero exit code.
- `test_missing_documentation_emits_error` — Assert that missing procedural docs produce a clear error message.
- `test_no_color_flag_disables_rich` — Assert that `--no-color` strips ANSI codes from stdout.

## Open design questions

- What authentication is required for the system to act on behalf of a user?
- Which operations are explicitly forbidden from autonomous execution?
