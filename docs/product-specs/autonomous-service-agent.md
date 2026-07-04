## Feature slug

autonomous-service-agent

## User job

When a citizen navigates a complex government procedure, the customer wants an assistant that reasons over documentation and performs operations so that repeated calls are avoided.

## Acceptance behavior

Given a user intent, the system reconstructs the workflow from scattered documentation and completes the procedure with explicit confirmation at each step, or guides the user through it with visual cues.

## Tiebreaker citations

- Automation vs. human oversight — human oversight wins. Every autonomous action requires explicit user confirmation.
- Shared infrastructure vs. product-specific UX — product-specific UX wins. The procedural reasoning must match the specific service domain, not a generic flow.
- `PRODUCT_SENSE.md` — cross-product principles and failure tolerances.

## Open questions

- What authentication is required for the system to act on behalf of a user?
- Which operations are explicitly forbidden from autonomous execution?
