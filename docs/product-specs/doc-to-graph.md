## Feature slug

doc-to-graph

## User job

When onboarding a new procedure, the operations lead wants to convert Word/PDF manuals into computational graphs so that AI can reason over prerequisites and steps.

## Acceptance behavior

A manual uploaded as Word/PDF is converted into a directed graph of Tensors (states) and Operators (actions) with UI logic blocks, enabling path planning, fault diagnosis, and dynamic jumping.

## Tiebreaker citations

- Scoring accuracy vs. throughput — accuracy wins. Incorrect graph edges cause downstream reasoning failures; manual verification of critical paths is required.
- Automation vs. human oversight — human oversight wins. New computational graphs for high-risk procedures must be reviewed before activation.
- `PRODUCT_SENSE.md` — cross-product principles and failure tolerances.

## Open questions

- What is the minimum manual length or complexity threshold that justifies graph conversion?
- How are visual annotations (red boxes, arrows) represented in the UI logic block?
