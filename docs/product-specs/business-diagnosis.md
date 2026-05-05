## Feature slug

business-diagnosis

## User job

When product defects are buried in calls, the business analyst wants auto-triaged tickets with severity scores so that data-driven fixes happen faster.

## Acceptance behavior

The system surfaces auto-created Jira tickets for issues mentioned in >= 3 distinct calls within 7 days, with severity score, sample transcript excerpts, and suggested investigation.

## Tiebreaker citations

- Automation vs. human oversight — human oversight wins. Tickets require human validation before routing to engineering.
- Shared infrastructure vs. product-specific UX — product-specific UX wins. The triage UI and severity scoring must match the business analyst's workflow, not the QA reviewer's.

## Open questions

- What Jira project and issue types should tickets map to?
- What is the threshold for "severity" — call volume, sentiment, or business impact?
