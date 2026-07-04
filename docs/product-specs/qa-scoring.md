## Feature slug

qa-scoring

## User job

When reviewing agent performance, the QA supervisor wants an automated score against 27 rubrics so that manual sampling is no longer needed.

## Acceptance behavior

A transcript ingested via the CLI produces a `QAReport` with an overall score, per-dimension scores, pass/fail/partial/NA verdicts for each rubric, and improvement suggestions. The report is emitted to stdout (formatted with `rich`) or to a JSON file when `-o` is provided. Grade thresholds are: >=90 优秀, >=80 良好, >=60 合格, else 不合格. Any `is_veto=True` rubric that fails forces `overall_score=0` and grade=不合格.

## Tiebreaker citations

- Scoring accuracy vs. throughput — accuracy wins. The scoring formula (weighted average with NA exclusion) and veto semantics must not be approximated or cached in a way that changes the final grade.
- Automation vs. human oversight — human oversight wins. The pipeline accepts an optional `human_review_callback`; if any verdicts require human review, they are sent to the callback before aggregation.
- `PRODUCT_SENSE.md` — cross-product principles and failure tolerances.

## Open questions

- Awaiting Steering: Is the `human_review_callback` intended for a synchronous CLI prompt, an async webhook, or a batch queue? The PRD shows the parameter exists but no CLI flag wires it up.
- Awaiting Steering: Should the 27 rubrics remain code-defined in `config/rubric_items.py`, or should they be loaded from the empty `data/knowledge_base/QA_RUBRICS/rubrics.md` file?
