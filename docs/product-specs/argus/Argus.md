# Argus — AI QA

## Problem

Service quality is hard to guarantee. Traditional QA relies on manual sampling, typically covering less than 5% of all calls. Inefficient, costly, and subjective, this approach leaves compliance risks and service gaps undetected, relegating QA departments to cost centers rather than value creators.

Automating QA with a bare LLM does not solve it — it relocates the problem. A model that grades a call directly produces scores nobody can audit, disagrees with human inspectors in ways nobody can measure, and drifts silently as calls shift. A wrong score is worse than a missing one: it erodes agent trust and manufactures false compliance records.

## Product Goal

Transform QA from passive sampling into a **100% full-coverage proactive intelligence center**, significantly improving service quality and compliance while empowering agent growth.

100% coverage does not mean 100% automation. Argus evaluates every call, auto-finalizes the calls it can fully ground, and routes everything else to a human — by design, not as a limitation to be optimized away. The share it auto-finalizes grows only as fast as its agreement with human inspectors proves it should.

## Target Users

- **QA Reviewer**: Reviews AI QA results, ensures scoring accuracy, and provides initial feedback to agents.
- **QA Supervisor**: Monitors overall team service quality, identifies systemic issues, and delivers targeted coaching to agents.
- **Call Center Agent**: Receives QA feedback, tracks personal performance, and improves skills through coaching tasks.

## The Quality Model

Argus scores every call against the four dimensions the human QA rubric already defines, weighted as the QA team weights them:

| Dimension | What it measures | Weight | Hard rule |
|---|---|---|---|
| **Empathy & Tone** | acknowledgment, warmth, politeness, handling of customer emotion | 3× | — |
| **Problem Resolution** | need understood, solution given, next step confirmed | 3× | dimension score < 7 → escalate to human QA regardless of total |
| **Procedural Accuracy** | script compliance, identity/privacy norms, required disclosures | 2× | — |
| **Proactive Value** | marketing opportunity recognized, extra value offered | 1× | — |

Weighted total ÷ 9; **PASS requires ≥ 7.5**. The hard-fail rule on Problem Resolution is not any single item — it is synthesized from the items that collectively indicate dimension collapse, and it escalates to a human rather than silently capping the score.

The rubric itself is compiled from the QA team's own checklist: **25 scored items** (of the human rubric's 27 — items 6 and 7 require ticketing-system and escalation-record access, and become compilable the moment that access exists; both are product requirements on external integrations, not rubric gaps). Each item keeps its original human wording as the authority; the machine version underneath it is the operational restatement, and where an item's judgment cannot be reduced to checkable evidence, that is **declared and routed to a human — never silently dropped**.

Two evidence instruments back the items where text alone cannot see the answer:

- **Acoustic indicators** (12: pitch, intensity, speaking rate, pauses, voice quality, …) — the most direct signal for emotion and tone, serving 9 of the 25 items, concentrated in Empathy & Tone.
- **Phrase & keyword lexicons** (~190 terms across customer-emotion, agent-attitude, agent-competence, interaction patterns, plus 18 standard marketing scripts) — serving 13 of the 25 items.

These are measurement instruments for the items, not independent rules: a lexicon hit or a prosody number is evidence a finding cites, never a verdict by itself.

## What a Score Must Be Before It Ships

Every Argus score carries five guarantees, and each exists because its absence is a known failure mode of LLM grading:

1. **Evidence before conclusions.** Every finding cites the exact transcript quote it rests on and the rubric item it violates. A finding that cannot anchor to real evidence is not scored down-weighted — it leaves the scored set entirely and goes to a human.
2. **The AI proposes; rules decide.** The model's job is to locate candidate findings, including ones past text — prosody, keyword patterns, known error cases. Whether a finding counts is decided against the confirmed rubric and knowledge base, deterministically. The model's own confidence number never enters any score; where it diverges from the derived score, that divergence is tracked as a diagnostic, not a result.
3. **Aligned with humans, never with itself.** Every soft criterion carries a continuously measured agreement rate with human inspectors. A criterion below the agreement threshold cannot auto-finalize — its findings route to a human no matter how confident the model is. Multiple model samples voting on one call are prohibited as a labeling mechanism: manufactured consensus is not agreement.
4. **It audits its own passes.** The agreement instrument samples calls a human also reviewed; auto-passed calls are by construction the ones humans never see. So Argus additionally samples its auto-passes for human audit — half at random, so the audit stays unbiased — and tracks the rate at which audits catch a missed failure. A criterion whose escape rate rises is demoted to human review even if its agreement looks healthy: auto-passes are exactly the calls agreement sampling is blind to.
5. **It cannot edit its own rulebook.** Correction is a loop, and the loop is closed on the human's side only: human-confirmed corrections re-enter the rubric and knowledge base through producer-owned, versioned commits. No Argus output ever edits a rule. The same discipline applies to calibration: reviewers score **before** seeing the machine's verdict, so human labels cannot quietly inherit machine bias.

## Calibration: Human Judgment as a Standing Asset

Argus's severity anchoring comes from human-judged calibration cases, drawn from the QA team's confirmed error cases and best-practice exemplars. Three properties make this an asset rather than a one-time setup:

- **Danger-zone weighted.** Cases concentrate roughly 2:1 where the evaluator is known to misjudge (a false pass costs more than a false flag), not spread evenly like a curriculum.
- **Drift-triggered.** Injection fires when agreement falls, escapes rise, or the model's self-assessment diverges from derived scores — targeted at the specific bias observed, not on a calendar.
- **Model-portable.** Alignment is curated exposure, never fine-tuning. Swapping the base model costs re-validation, not re-training — the human judgment outlives any model.

## What Stays Human, by Design

Three queues route to people permanently. They are the product correctly reporting the boundary of what it can ground — not scaffolding to be removed:

- **Findings with no anchorable evidence.** Often a real issue no rubric item covers yet — the seed of the next calibration case.
- **Findings in the contested regime.** Where confirmed experts themselves disagree — e.g. "substantive rather than scripted", "genuine not performative" — guessing is the failure mode, not the fallback.
- **Drift demotions.** A criterion whose agreement with humans is falling routes to humans until it is re-grounded.

The honest limits are stated, not hidden. The audit rate is a **floor**: it counts the misses a reviewer catches, so it reports "no residue we can currently find", never "no residue". And judgment-layer evidence never promotes to compliance-grade certainty: corroboration narrows what the text alone misses (a flat acknowledgment caught by prosody), but warmth-minus-sincerity — sarcasm that keeps the correct sequence and warm prosody — stays human forever.

## Where Argus Sits

Argus is a consumer. Its inputs — intent structure, procedure docs, the compiled rubric, curated error cases and best practices, speaker roles and call structure — are produced and confirmed upstream by the producer chain (audio2tree, doc2graph, the criteria compiler, curation). Argus reads that knowledge base at a pinned version and never re-derives what a producer has established: if a call's speaker roles were never established, Argus routes to a human rather than re-guessing them from the transcript.

Two consequences the business can rely on:

- **Quality is a chain property.** Argus's accuracy is bounded by the confirmed knowledge it reads; investments in the knowledge base are investments in QA accuracy.
- **Nothing is unexplained.** Every evaluation is replayable bit-for-bit from its stored record — the same evidence, rubric version and case history produce the identical score forever. A score can always be re-shown, audited, and defended.

## Deployment Shape

- **On-premise, local model.** The proposing model runs inside the deployment; call audio and transcripts never leave it.
- **Full-coverage throughput.** Sized for the full call stream (target ≈3,000 calls/day on a single accelerator node), not a sampling fraction.
- **Every evaluation is a record.** Findings, evidence, applied precedents, routing reason and the derivation trail are stored with each result — the audit trail is the product, not a log.

## Sources

This document is the product-level statement of a specified system; every claim in it traces to one of the following. Where this document and a spec disagree, the spec governs.

**Runtime pipeline (what runs per call, and why it is trustworthy)**

- `docs/retrospectives/process-derivation-pipeline-spec-v5.html` — the deterministic QA pipeline: propose → gate → re-derive; the two-layer criteria split; grounding; routing; what stays human (§9).
- `docs/retrospectives/process-derivation-pipeline-spec-v5-patch-1.md` — the model's own score as a never-shipping diagnostic (D19/D20/I8); local on-premise proposer and the ≈3,000 calls/day capacity target (D21); the unbiased random audit floor (D22).

**Rubric authoring (where the quality model comes from)**

- `docs/retrospectives/soft-criteria-authoring-spec-v4.html` — the four-input contract that compiles the human rubric into machine-gradable form; what compiles, what is declared residue; the calibration channel.
- `docs/retrospectives/soft-criteria-authoring-spec-v4-patch-1.md` — acoustic and phrase as evidence instruments serving the 25 items (per-item audit, §2); the 12 indicators and lexicon groups; dimension hard-fail gates as synthesized escalation rules (§5).
- `docs/retrospectives/soft-criteria-authoring-spec-v4-patch-2.md` — compiler self-audit and adversarial testing of Chinese keyword gates (internal to the compiler; cited for completeness).
- `docs/retrospectives/soft-criteria-authoring-spec-v4-patch-3.md` — calibration as a living channel: danger-zone 2:1 curation, drift-triggered injection, blind-first review, no fine-tuning (§1–3); the 25-item count correction (§6).

**The rubric itself**

- `docs/PRD/eval/align.md` — the 25 items and their dimension binding; items 6–7 excluded pending ticketing/escalation system access; dimension weights and the Problem-Resolution hard threshold.
- `docs/PRD/eval/skills/evaluator/SKILL.md` — the four-dimension quality model and the weighted-total pass line (≥ 7.5).

**Plan of record**

- `docs/exec-plans/active/9031-argus-derivation-pipeline.md` — the derivation pipeline plan (successor to the overturned 9021 family, archived 2026-09-16): the producer/consumer seam (audio2tree, doc2graph, the criteria compiler, curation produce the knowledge base; Argus consumes it and never re-derives what a producer establishes), the consumer contracts of `INTENTS/PRODUCERS.md` §9, and the plan this product spec's guarantees rest on.
