---
owned-by: steering
---

# PRODUCT_SENSE.md

## The user we are building for

The primary user is a **QA manager or operations lead at a Chinese enterprise call center** who needs to scale quality assurance from <5% manual sampling to 100% automated coverage without sacrificing scoring accuracy or explainability.

## Goals (derived from PRD)

- Transform QA from passive sampling into a 100% full-coverage proactive intelligence center.
- Automatically mine customer needs, market trends, and product issues from call transcripts.
- Reason procedurally over operational documentation to complete service procedures autonomously.
- Bridge top-down official documentation with bottom-up real-world customer interactions.
- Eliminate semantic drift between colloquial user language and structured operational knowledge.

## Non-goals

- **Real-time call interception or live-agent whispering.** The PRD describes post-call analysis only; live coaching would require streaming infrastructure and latency guarantees not mentioned. Source: `docs/PRD/Argus.md` (describes review of recordings, not live calls).
- **Multi-language support beyond Chinese.** All PRD documents, rubrics, and sample transcripts are Chinese-centric. Expanding to English or other languages would require retraining the NLI model, rewriting all 27 rubrics, and re-annotating the knowledge base. Confidence: low — a confirmed requirement for bilingual support would change this.
- **General-purpose RAG or open-domain QA.** The system is scoped to RegTech domains (CA certificates, e-seals, corporate registration, annual reporting, credit restoration). Source: `docs/PRD/Audio-to-Tree(Bottom-up).md`.
- **Replacement of existing Jira/CRM systems.** Metis auto-creates tickets but the PRD shows human review and coding agents as downstream steps; we do not own those tools. Source: `docs/PRD/Metis.md` (loop includes Jira and Claude Code, external to this product).
- **Voice synthesis or outbound calling.** Hermes is described as reasoning over documentation and performing operations, but there is no mention of generating speech or initiating phone calls. Source: `docs/PRD/Hermes.md`.
- **On-premise GPU cluster deployment.** The NLI model requires GPU (`device=0` hardcoded), but the PRD does not specify on-premise packaging, air-gapped installs, or edge deployment. Confidence: low — a confirmed deployment constraint to on-premise-only would change this.

## Failure-mode tolerances

| Failure class | Blocks release? | Observable threshold |
|---|---|---|
| **QA scoring false-negative** (agent marked fail on a passing call) | Yes | False-negative rate > 2% on a held-out test set of 100 manually labeled transcripts. |
| **KB coverage gap** (fact-check returns NEI because knowledge base is empty) | Yes | Coverage score < 0.50 on any transcript where entity extraction identifies a known L1 intent. |
| **ASR misparse** (transcript format not recognized, roles swapped) | No | Pipeline must log `ASR_PARSE_ERROR` and exit with non-zero code; must not produce a QA report with fabricated scores. |
| **LLM API transient failure** | No | Pipeline must retry up to 3 times with exponential backoff; if all fail, emit `HUMAN_REVIEW` verdicts rather than crash. |
| **Semantic drift in intent tree** (colloquial claim maps to wrong L3 node) | No | Drift rate > 5% on sampled atomic claims triggers a doc-gardener alert for manual tree review. |

## Decision tiebreakers

1. **Scoring accuracy vs. throughput.** When a faster pipeline stage would reduce LLM call volume at the cost of verdict precision, accuracy wins. The PRD positions this as a QA system whose scores must be defensible to human reviewers. Source: `docs/PRD/Fact-Checking.md` (scoring formula and veto semantics are load-bearing).
2. **Shared infrastructure vs. product-specific UX.** When a component could be generalized across Argus, Metis, and Hermes but product-specific behavior would be compromised, product-specific behavior wins. The PRD explicitly states "All three share the same call analysis and QA infrastructure, but serve distinctly different user roles and use cases." Source: `docs/PRD/Requirment.md`.
3. **Automation vs. human oversight.** When a fully automated path would remove a human checkpoint that the PRD shows in the loop, human oversight wins. The Metis loop includes "Human Review" and "Human review → CI → Deploy → Verify & close". Source: `docs/PRD/Metis.md`.
