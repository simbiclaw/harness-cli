# Core Beliefs

## Belief 1

Expose all output formats as explicit CLI flags rather than auto-detecting terminal capabilities.

Rationale: Source — docs/PRD/Argus.md shows JSON output via `-o` flag; the PRD never mentions TTY detection or adaptive formatting.

## Belief 2

Prefer composable report sections over monolithic output templates.

Rationale: Source — docs/PRD/Fact-Checking.md shows per-dimension scoring with veto semantics that must surface independently; a single template would force conditional branching that is harder to test.

## Belief 3

Every interactive CLI element must have a stable `--json` equivalent for automated testing.

Rationale: Experiment — mocking stdout rich formatting is fragile; JSON schema assertions are reliable. The existing `cli.py` already supports `-o output.json`, confirming this path works.

## Belief 4

Preserve human-in-the-loop checkpoints even when an automated path exists.

Rationale: Source — docs/PRD/Metis.md shows "Human Review" and "Human review → CI → Deploy → Verify & close" in the loop; removing these checkpoints would violate the PRD-defined workflow.

## Belief 5

Surface severity and confidence as explicit numeric thresholds, not relative labels.

Rationale: Source — docs/PRD/Fact-Checking.md defines confidence thresholds (HIGH=0.85, LOW=0.60) and grade thresholds (>=90, >=80, >=60); numeric thresholds are unambiguous across locales and reviewers.
