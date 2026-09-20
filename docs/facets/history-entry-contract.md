# History-entry contract — cookbook / errors nodes (proposal)

**Status:** staged in harness-cli (9031 M1 family). The history shelf is curated-owned;
this is the consumer's field contract for what a precedent entry must carry so the
evaluation can consume it. Lands with the §9.1 revision after producer + curated review.

**Who produces:** audio2tree produces the analysis (why a QA-annotated sample is labeled
its item, from the sample library + chain A transcriptions + acoustic readings);
**curated lands the entry** (human-gated, as the shelf's ownership requires).

**Why these fields.** A history entry is both (a) the confirmed referent I6's *correlated*
signal matches a live finding against (W_C = 0.4 — "a model-judged match to a confirmed
referent"), and (b) an auditable record: every claim traceable to a span, an instrument
reading, and a threshold. An entry without anchoring is a story; the evaluator cannot
consume a story.

## Shape

```yaml
# <domain>/<case>/cookbook.<slug>.yaml   (best practice, confirmed pass)
# <domain>/<case>/errors.<slug>.yaml     (negative case, confirmed fail)
entry_id: <stable id, minted once>          # e.g. err-<slug> / cb-<slug>
kind: errors | cookbook
created_at: <iso8601>
updated_at: <iso8601>
authored_by: curated                        # human-gated landing
status: confirmed                           # only confirmed entries reach the shelf

anchor:
  intents_path: <domain>/<case>/<L3>        # the node this precedent binds to
  call_id: <record id>
  call_archive: <relpath under calls/>
  intents_sha: <40-hex>                     # the epoch it was derived against

finding:
  source_item: <dimension>/item-N           # the rubric item it confirms
  confirmed_verdict: pass | fail
  statement: <one line — the violation or the excellence>
  evidence:
    - turn_id: <T-id in the record>
      span: {start: <int>, end: <int>}
      quote: <EXACT substring of the record's turn text>
      supports: <true for pass-evidence, false for fail-evidence>
  instruments:                              # ids from the indicators registry
    - id: <indicator | predicate id>
      measured: <the reading>
      threshold: <registry threshold the reading meets or breaks>

matching:                                   # what the correlated matcher consumes
  description: <discriminative summary — why this sample is labeled so>
  key_features: [<3–6 short phrases>]
  applicable_items: [<item refs this precedent may corroborate>]
  not_applicable_when: <carve-outs, e.g. attribution conditions>

# Never present: a score. Precedents carry evidence and a verdict, not a number;
# adjustment arithmetic is core/score.py + core/adjust.py's job (I3).
```

## Hard requirements

1. **Quote verbatim.** `quote` is an exact substring of the record's `turns[].text` at
   turn granularity (9031 M4's anchoring unit); a quote that does not resolve makes the
   entry unusable, not approximately usable.
2. **Instrument ids come from the registry** (`_rubric/evidence/acoustic/indicators.yaml`,
   now argus-owned): every `instruments[].id` must exist there with a threshold. A reading
   with no registry entry is a new-instrument proposal — coordinate the id before shipping.
3. **Attribution stays in `not_applicable_when`**, never inside a counter (the compile
   line's carve-out rule, extraction_notes).
4. **`description` + `key_features` are the match surface.** The matcher judges "is this
   live finding the kind of thing this precedent confirms" from these, not by semantic
   crawl of the evidence block — keep them discriminative and short.

## Notes

- The shelves are **empty today** (measured: zero `dkb/cookbook/errors.*.yaml` files) —
  these would be the first entries. Format changes before the first landing are cheap;
  after, they are migrations.
- item-7 has no compiled node (recorded by audio2tree 2026-09-20): entries for it land
  when it compiles (the 9011 M5 coverage-map class).
- This contract is the consumer's proposal, not a ruling: curated's landing review may
  amend it, and the §9.1 revision carries the final text.
