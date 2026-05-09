# Extraction Rules

The four gates from `claim_schema.md` restated as operational rules with worked examples. When inline reasoning produces a claim, run it through these gates before writing to `claim_library.jsonl`. The batch script in `scripts/extract_claims.py` does the same in its prompt template.

## Gate 1: Single proposition

A claim is one logically complete statement. If you can split it into two claims and each one stands alone, do.

**Pass.** "The customer's account was charged twice on 2026-04-15." (One event, one assertion.)

**Fail.** "The customer's account was charged twice on 2026-04-15 and they want a refund." (Two propositions: the double charge happened; the customer requested a refund. Split.)

**Fail.** "The customer is frustrated because the order is late." (One sentence, but two propositions: the order is late; the customer is frustrated. Split — and consider whether "frustrated" is supported by the segment text or just inferred. If only inferred, drop it.)

**Edge case.** "The customer placed two orders on 2026-04-23." (One proposition with a count, not two. Pass.)

**Edge case.** Compound predicates. "The agent committed to send a refund and a follow-up email by end of day." (Two commitments, two claims. Split.)

## Gate 2: De-contextualised

Pronouns and underspecified noun phrases are replaced by specific business entities. The claim must remain factually accurate when read in isolation from its source conversation.

The stoplist of unresolved surface forms the verifier hard-flags by default: `it`, `they`, `them`, `their`, `he`, `she`, `him`, `her`, `his`, `these`, `those`, `here`, `there`, `now`, `then`, `the form`, `the order`, `the issue`, `the problem`, `the account`, `the page`, `the link`, `recently`, `the other day`, `the document`, `last week`, `next month`. Some of these (e.g., "their") are legitimate when the antecedent is a proper noun in the same sentence — the verifier tries to detect quoted spans and skip those. The verifier *soft-warns* for `this` and `that` because both are complementizers and determiners more often than bare demonstratives ("complained that the order was late", "this filing"), so hard-failing them produces too many false positives. When `this` or `that` is genuinely a bare demonstrative, the LLM-side reasoning catches it during extraction. When in doubt, write more specifically.

**Pass.** "The U-Key driver order placed by the customer on 2026-04-23 has not arrived as of the call." (Specific entity: U-Key driver; specific date.)

**Fail.** "It hasn't arrived." (Unresolved.)

**Fail.** "The order placed last week hasn't arrived." ("Last week" is relative to the call; that's a hidden temporal pronoun. Resolve to a specific date — even an approximate one based on the call date is better.)

**Pass.** "The order placed approximately one week before the 2026-05-07 support call has not arrived." (Acceptable when the exact date isn't recoverable.)

**Pass.** "The agent stated that SEC form 8-K filing is required within four business days of an officer resignation." (Form 8-K is a specific entity; the deadline is precise.)

**Fail.** "The agent said the form needs to be filed by the deadline." (Two unresolved references: which form, which deadline.)

**When references can't be resolved.** Drop the claim — don't invent a referent. Example: a customer says "Tell them I want a refund" with no prior antecedent for "them" anywhere in the call. There is no honest claim to make from that turn.

## Gate 3: Not a Q&A pair

A claim is a proposition. An exchange between two speakers becomes two propositions, never one Q&A.

**Pass.** Two separate claims:
- `inquiry`, customer: "The customer wanted to know whether SEC form 8-K must be filed for an officer resignation."
- `assertion`, agent: "The agent asserted that an officer resignation is an SEC Item 5.02 trigger requiring an 8-K filing within four business days."

**Fail.** "When asked whether 8-K is required for officer resignation, the agent confirmed it is and stated the deadline is four business days." (Folds two speakers' contributions into one claim. Split.)

**Fail.** "The customer asked whether 8-K is required and was told yes." (Q&A in a single sentence. Split.)

**Why this rule exists.** Atomic claims feed an intents tree. The tree's leaves are about *intents*, not *exchanges*. If a customer asks the same question across many calls and gets different answers, those map to one customer-side intent and several agent-side claims. Folding them into Q&A pairs prevents the clustering from seeing the question pattern.

## Gate 4: Source-cited

Every claim has `source.audio_id` and a non-empty `source.segment_ids`. A claim with no citation is forbidden.

**Pass.** A claim with `source.segment_ids: [3]` and `source.supporting_segment_ids: [2]` because segment 3 contained the proposition and segment 2 supplied the antecedent for a pronoun resolution.

**Fail.** A claim derived from "general impression of the call" with no specific segment cited. There is no such valid claim.

**Edge case.** A proposition split across two adjacent segments by ASR (e.g., "I ordered the // U-Key driver last Tuesday" appearing as segments 4 and 5). Cite both: `segment_ids: [4, 5]`.

## Other rules

### Tense and voice

- Past tense for events that happened during or before the call. "The customer placed an order…", "The agent committed to…".
- Present tense for ongoing states. "The customer is enrolled in the premium plan."
- Active voice. "The agent committed to send a refund" is better than "A refund was committed to by the agent."

### Hedging

If the speaker hedged, preserve the hedge faithfully — don't strengthen or weaken it.

**Pass.** "The agent stated that a system outage *may* qualify the customer for a fee waiver, pending evidence."

**Fail.** "The agent stated that a system outage qualifies the customer for a fee waiver." (Strengthens the agent's claim.)

**Fail.** "The agent thought maybe a system outage might possibly qualify…" (Adds hedges that weren't in the source.)

If the segment doesn't actually contain a proposition (it's hedging, fillers, or pure social acknowledgment), don't extract a claim from it.

### Speaker attribution

The claim's `speaker_role` is determined by the source segment's speaker, not by who the proposition is about. A customer can make a claim about the agent: "The customer asserted that the agent's previous response was incorrect." That's a customer-role claim about the agent's behaviour.

### Multi-turn propositions

A proposition that needs two non-adjacent segments to be complete is rare but possible. If segment 5 says "I want to talk about my last order" and segment 12 (after agent intervention) says "I need a refund for it", the refund-request proposition's `segment_ids` is [12], and `supporting_segment_ids` is [5, ...intermediate segments that confirm the antecedent didn't shift...].

Use this judiciously. Most claims should cite one segment.

### Claims about the call itself

Sometimes the proposition is meta — e.g., the customer asks for the call to be transferred. That's a valid claim:

> `claim_type: assertion`, customer: "The customer requested the call be transferred to a human supervisor."

The intent here ("transfer to supervisor") is a real intent worth tracking even though the proposition is about the call rather than about a product or policy.

### Filler turns

Backchannels, agreements ("uh-huh", "yeah, okay"), greetings without further content, sign-offs. These produce no claims. The whole turn is dropped.

If a backchannel turn unexpectedly contains content ("uh, yeah, also my account is locked"), extract the content claim only — don't include the filler in the proposition.

### Multiple claims from one segment

A segment can produce zero, one, or many claims. The U-Key driver complaint example in `claim_schema.md` produces three claims from one segment. That's normal. Each claim must independently pass all four gates.

## When in doubt, drop

The cost of a missing claim is "we under-extract this turn this time, and the next call with a similar turn might catch the intent". The cost of a low-quality claim is corruption of the intents tree (a polluted leaf, a bogus new cluster).

Asymmetric: dropping is recoverable, low-quality claims are not. When a candidate claim doesn't cleanly pass the four gates, drop it. Log a brief reason so the user can spot patterns of legitimate claims being missed.

## Logging rejections

The subagent maintains `state/extraction_rejections.jsonl` with one line per rejected candidate:

```json
{"timestamp": "...", "audio_id": "call_xxx", "segment_id": 7,
 "candidate_text": "It hasn't arrived",
 "gate_failed": "decontextualised",
 "reason": "Pronoun 'it' could not be resolved; no antecedent in segments 5-7."}
```

This file is for diagnostics, not for downstream consumers. It surfaces patterns: if 40% of rejections are "could not resolve antecedent", maybe upstream segment boundaries from diarization are too aggressive and need tuning.
