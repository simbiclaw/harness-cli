# Atomic Claim Schema (v1.0)

Every claim is one JSON object on one line in `state/claim_library.jsonl`. The library is append-only. Claims are never edited in place; corrections happen by writing a new claim that supersedes the old one, with the old one's `id` recorded in `supersedes`.

## Shape

```json
{
  "id": "c_<sha256-12>",
  "schema_version": "1.0",
  "created_at": "2026-05-07T13:42:11Z",
  "claim_type": "assertion" | "inquiry" | "commitment" | "complaint" | "preference",
  "speaker_role": "customer" | "agent" | "unknown",
  "proposition": "The U-Key driver order placed by the customer on 2026-04-23 has not arrived as of the call.",
  "source": {
    "audio_id": "call_a1b2c3d4e5f6789a",
    "segment_ids": [3],
    "supporting_segment_ids": [2, 4]
  },
  "decontextualisation": {
    "resolved_references": [
      {"surface": "it", "resolved_to": "the U-Key driver order placed on 2026-04-23"}
    ],
    "resolution_evidence_segment_ids": [2]
  },
  "extraction_method": "inline" | "batch_script",
  "extractor_version": "conversation-distillation@1.0",
  "supersedes": null
}
```

## Field semantics

### `id`
Stable identifier. SHA-256 of the canonical JSON (sorted keys, `id` and `created_at` excluded), truncated to 12 hex chars, prefixed `c_`. Same proposition extracted from different segments gets different IDs because `source` differs — that's correct; we want frequency to be a signal at clustering time.

### `claim_type`
Five values, exhaustive enough to cover support-call discourse without being a labeling rabbit hole:

- **`assertion`** — speaker stated a fact about the world or about themselves. *"The customer's account was charged twice on 2026-04-15."*
- **`inquiry`** — speaker wanted to know something. *"The customer wanted to know whether form 8-K is required for their situation."*
- **`commitment`** — speaker committed to do something. *"The agent committed to email the customer a refund confirmation by end of business today."*
- **`complaint`** — speaker expressed dissatisfaction with a specific event or state. *"The customer complained that the support ticket they opened on 2026-04-20 had not received a response."*
- **`preference`** — speaker stated a preferred option among alternatives. *"The customer preferred to receive the refund via the original payment method rather than store credit."*

A turn often produces claims of multiple types. Extract them separately. If a candidate genuinely doesn't fit any of the five, drop it — don't invent a sixth type.

### `speaker_role`
From the source segment's `speaker` cross-referenced against `speakers[].label` in the structural transcription. When the label is null (mono diarization without enrollment), use `"unknown"` rather than guessing from content.

### `proposition`
The claim's text. One sentence, one logically complete statement. Past tense for events that happened during or before the call. Present tense for ongoing states. Specific entities, not pronouns. No hedging like "the customer seemed to" — either it was said or it wasn't; if it was implied rather than said, drop the claim.

### `source.audio_id`
The structural transcription's `audio.id`. Required.

### `source.segment_ids`
The segment(s) whose `text` is the primary basis for the claim. Usually one segment. If the proposition was split across two segments by ASR ("I ordered the // U-Key driver last Tuesday"), include both.

### `source.supporting_segment_ids`
Optional. Segments that supplied resolved references but whose text didn't directly assert the proposition. Example: segment 3 says "it hasn't arrived"; segment 2 said "I ordered the U-Key driver Tuesday". Segment 3 is `segment_ids`, segment 2 is `supporting_segment_ids`. This makes the citation chain auditable.

### `decontextualisation.resolved_references`
List of every pronoun or underspecified noun phrase you replaced in the proposition. Each entry has the original surface form and what you resolved it to. Empty list is valid (no references needed resolving). If you write a proposition with a pronoun still in it, the verifier will reject it.

### `decontextualisation.resolution_evidence_segment_ids`
Segments that grounded the resolutions. Often a subset of `supporting_segment_ids`.

### `extraction_method`
Where the claim came from. Lets us audit quality differences between inline subagent reasoning and the batch script.

### `extractor_version`
Version of this subagent + extraction prompt. Bump when the extraction logic changes meaningfully so claim quality is comparable within a version.

### `supersedes`
ID of a claim this one replaces. Null for the first version. Use this when re-extraction with improved prompts produces a better claim from the same source segment. The library stays append-only — old claims are kept for audit, but downstream consumers should filter by `supersedes is null OR id not in {supersedes values}`.

## Worked examples

### Example: customer complaint with pronoun resolution

Source structural transcription, segments around segment 3:

```
seg 1, S1 (customer): "Yeah hi, I had a question about my recent order."
seg 2, S1 (customer): "I ordered a U-Key driver last Tuesday, the security USB key thing."
seg 3, S1 (customer): "And it hasn't shown up. Tracking says it shipped but nothing's moved."
seg 4, S0 (agent):    "I'm sorry to hear that. Let me look up the order."
```

Three claims from segment 3:

```json
{"id":"c_a8f2c1d49b03","claim_type":"assertion","speaker_role":"customer",
 "proposition":"The U-Key driver order placed by the customer on the prior Tuesday has not arrived.",
 "source":{"audio_id":"call_xxx","segment_ids":[3],"supporting_segment_ids":[2]},
 "decontextualisation":{"resolved_references":[{"surface":"it","resolved_to":"the U-Key driver order placed on the prior Tuesday"}],
                        "resolution_evidence_segment_ids":[2]}, ...}

{"id":"c_b7e1a2f33c4d","claim_type":"assertion","speaker_role":"customer",
 "proposition":"The tracking record for the customer's U-Key driver order indicates the shipment status as 'shipped'.",
 "source":{"audio_id":"call_xxx","segment_ids":[3],"supporting_segment_ids":[2]},
 "decontextualisation":{"resolved_references":[{"surface":"tracking","resolved_to":"the tracking record for the customer's U-Key driver order"}],
                        "resolution_evidence_segment_ids":[2]}, ...}

{"id":"c_c4d8a59b1e02","claim_type":"complaint","speaker_role":"customer",
 "proposition":"The customer complained that no movement has occurred on their U-Key driver shipment despite its 'shipped' status.",
 "source":{"audio_id":"call_xxx","segment_ids":[3],"supporting_segment_ids":[2]},
 "decontextualisation":{"resolved_references":[{"surface":"nothing's moved","resolved_to":"no movement has occurred on the U-Key driver shipment"}],
                        "resolution_evidence_segment_ids":[2]}, ...}
```

### Example: turn that produces nothing

```
seg 12, S1 (customer): "Uh, yeah."
seg 13, S0 (agent): "Mm-hm."
```

Backchannels carry no propositions. Skip both. Don't write empty-text claims; don't write claims about the act of acknowledging.

### Example: a Q&A exchange becoming two claims

```
seg 8, S1 (customer): "Do I need to file an 8-K for an officer resignation?"
seg 9, S0 (agent): "Yes, an officer resignation is a Section 5.02 trigger; you have four business days."
```

Two claims, never one:

```
inquiry, customer:  "The customer wanted to know whether SEC form 8-K must be filed for an officer resignation."
assertion, agent:   "The agent asserted that an officer resignation is an SEC Item 5.02 trigger requiring an 8-K filing within four business days."
```

Do not write a Q&A-style claim like "When asked about 8-K for officer resignation, the agent said yes". That's an exchange, not a proposition.

## Verification

The `scripts/verify_claims.py` script enforces these gates programmatically against any claim file. Run it before publishing if you're uncertain whether a batch of claims passes the contract. The verifier checks:

- Required fields present and well-typed.
- `proposition` is non-empty and contains no unresolved pronouns from a stoplist (`it`, `this`, `that`, `they`, `them`, `their`, etc., except in proper-noun contexts which the script tries to detect heuristically).
- `source.audio_id` and `source.segment_ids` are present and non-empty.
- `decontextualisation.resolved_references` is consistent with the proposition (every surface form claimed-resolved actually appears nowhere as a bare pronoun in the proposition).

Verifier failures don't auto-delete claims; they list which IDs failed and why, and you decide whether to re-extract or supersede.
