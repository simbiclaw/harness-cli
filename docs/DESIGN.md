# DESIGN.md

## 1. Design-system tokens

Not applicable — product is a CLI tool with stdout/JSON output; no visual design system specified in PRD.

## 2. Component vocabulary

- **ReportTable** — A tabular CLI output rendered via `rich` that displays per-dimension scores, verdicts, and grade thresholds. It is NOT for raw JSON serialization or machine parsing.
- **ScorePanel** — A summary block in CLI stdout that shows the overall score and final grade. It is NOT for presenting individual rubric evidence or transcript excerpts.
- **VerdictList** — A vertically stacked list of pass/fail/partial/NA/human_review verdicts with concise rationale. It is NOT for unstructured prose or full LLM reasoning traces.
- **ProgressIndicator** — A spinner or stage label shown during the 8-stage pipeline to signal liveness. It is NOT for displaying intermediate results or debug logs.
- **ErrorBanner** — A high-contrast stderr message for fatal or recoverable errors (e.g., ASR parse failure, API timeout). It is NOT for informational notices or scoring nuance.

## 3. Navigation primitives

Not applicable — CLI tool; navigation is via command-line arguments and subcommands.

## 4. Accessibility floor

Observable threshold: All JSON output schemas must include human-readable descriptions for every field. CLI stdout output must use high-contrast text formatting and support `--no-color` flag for screen readers.

## 5. Links to design-docs

- [docs/design-docs/core-beliefs.md](design-docs/core-beliefs.md)
- [docs/design-docs/qa-scoring.md](design-docs/qa-scoring.md)
- [docs/design-docs/business-diagnosis.md](design-docs/business-diagnosis.md)
- [docs/design-docs/autonomous-service-agent.md](design-docs/autonomous-service-agent.md)
