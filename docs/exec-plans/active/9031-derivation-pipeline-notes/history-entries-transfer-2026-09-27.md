# Transfer note — the 24 history entries (audio2tree → curated), 2026-09-27

**What is being transferred.** audio2tree's 24 history entries — **18 `errors` + 6
`cookbook`** — plus one gap record (`item-7-coverage-gap.md`), delivered 2026-09-20 and
living in its worktree:

```
9008-audio2tree-rebuild/docs/exec-plans/active/9008-notes/history-entries-draft/
  ├─ 24 × <item>-<slug>.yaml      (the entries)
  ├─ item-7-coverage-gap.md       (the gap record; not an entry)
  ├─ library-index.json           (the index)
  ├─ DELIVERY.md                  (its own manifest, with per-entry support figures)
  ├─ verify_entries.py            (mechanical re-check — re-run below)
  ├─ fix_spans.py                 (span repair/validation)
  └─ na-material/                 (moved out by the 2026-09-20 ruling)
```

Contract: `docs/facets/history-entry-contract.md` @ `e4d98ab` + `04fa259` (span =
character offsets). Instrument registry: `INTENTS/_rubric/evidence/acoustic/indicators.yaml`.

## Verification — re-run 2026-09-27, not inherited

```
uv run python .../history-entries-draft/verify_entries.py
→ drafts: 24 | registry ids: 31
→ item-*: OK   (24/24; no PROBLEM, and no note raised)
```

Measured today, with counts, rather than carried over from the delivery session:

| check | result |
|---|---|
| entries parse as YAML | 24/24 |
| `finding.instruments[].id` ∈ the registry's 31 ids | **80 refs, 0 outside** |
| every quote an exact substring of the call archive's `turns[].text` (and of the named turn where `turn_id` is `T<n>`) | **88 evidence items, 0 failures** |
| no score-like field anywhere (`score`/`points`/`deduction`/`raw_score`/`adjusted`) | clean |
| `turn_id` convention stated in each header | clean |
| archive named by `anchor.call_archive` resolves on disk | clean (no notes raised) |

**Binding as delivered:** 8 entries bind to business **L3** nodes (the item-20/21
marketing family); 16 bind to the **business-domain level** (`法人数字证书业务`), because
their failure surface is agent behaviour rather than a scenario. `intents_sha` =
`b2287d10…`, the epoch that carries this calibration input.

**NA material is not part of this transfer** — moved to `na-material/` by the 2026-09-20
human ruling; NA samples are not precedents, and `kinds` stay `errors | cookbook`.

## The three rulings this transfer needs, each with a closure condition

1. **Confirm the anchors.** Accept the binding as delivered (8 L3 + 16 domain), or name
   specific changes.
   *Closure:* one sentence from the human.
   *Default if unruled:* the delivery is accepted as bound, and the tree lands it as-is.
2. **The 16 domain-level anchors' upgrade path.** Either (a) they stay domain-level
   permanently — a behaviour-level failure surface has no scenario to bind to; or (b) a
   later pass re-binds individual entries to an L3 when one exists, through a tree-side
   revision (one epoch commit), never through Argus.
   *Closure:* pick (a) or (b); (b) additionally needs the pass to be named with an owner.
   *Default if unruled:* (a). Re-binding stays available later either way; (a) is the
   honest description of what the evidence supports today.
3. **item-6's `0-分` typo** in the deferred appendix. Items 6 and 7 are deferred pending
   ticketing-system access (R6), so nothing reads the typo today.
   *Closure:* fix it when items 6/7 compile, or fix it now.
   *Default if unruled:* leave it recorded and unfixed until 6/7 compile — editing a
   deferred item's text now changes a rubric that no criterion reads.

## What landing this does and does not do

- **Does:** makes the history shelves non-empty, which is what the I6 correlated class
  needs — the nine attitude items (8/9/10/11/12/13/14/22/26) are the ones the entries
  support, and `adjust()` reads the shelves at the pinned epoch once M6/M7 wire them.
- **Does not:** grant any criterion an auto-final. The shelves are precedents, not
  calibration fragments; `auto_final_allowed` moves only when a calibration fragment
  covers a criterion (`apply_manifest_epoch`).
- The delivery's own per-entry support figures (字/秒, 静音比, f0 bands, phrase hits) are
  in `DELIVERY.md` and are the producer's measurements, not re-derived here.

## Disposition

With the three rulings taken (or their defaults accepted), this transfer closes: curated
lands the shelves, and the only thing that stays open is item 6/7's deferral, which is
already recorded as R6 and is blocked on an external integration rather than on anyone
here.
