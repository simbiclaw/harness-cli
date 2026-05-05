## Feature slug

fact-checking

## User job

When a QA reviewer needs to defend a score, they want claims verified against transcript evidence and domain knowledge so that verdicts are defensible.

## Acceptance behavior

For any claim, the system returns a verdict (pass/fail/partial/NEI/NA/human_review) with confidence score and cited evidence within 10 seconds. The NLI path scores dialogue consistency, the LLM path verifies against KB content, and the ASR-suspect path routes to human review.

## Tiebreaker citations

- Scoring accuracy vs. throughput — accuracy wins. The hypothesis pair design and NLI scoring must not be approximated.
- Automation vs. human oversight — human oversight wins. ASR-suspect and low-confidence claims route to human_review.

## Open questions

- What is the acceptable NEI rate when the KB is empty?
- Should the NLI model run on CPU fallback when GPU is unavailable?
