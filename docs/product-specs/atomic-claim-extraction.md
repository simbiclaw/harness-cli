## Feature slug

atomic-claim-extraction

## User job

When analyzing a call, the system wants to deconstruct dialogue into self-contained facts so that downstream reasoning is grounded.

## Acceptance behavior

The Atomizer stage (Stage 2) produces `client_atoms` and `agent_atoms` as lists of decontextualized claims, plus a `coverage_matrix` showing which client atoms were responded, partially responded, or ignored by agent atoms. Each claim is a single proposition with no pronouns, including all context necessary to be understood in isolation.

## Tiebreaker citations

- Scoring accuracy vs. throughput — accuracy wins. Parallel LLM calls are used, but the output must be complete and decontextualized; partial or vague atoms break downstream fact-checking.
- `PRODUCT_SENSE.md` — cross-product principles and failure tolerances.

## Open questions

- Awaiting Steering: Should the system enforce a maximum number of atoms per turn to control LLM token usage and latency?
