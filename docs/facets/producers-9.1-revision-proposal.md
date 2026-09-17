# PRODUCERS.md §9.1 Revision Proposal — The Criteria-Shaped Facet Contract

**Status:** staged in harness-cli (9031 M1). Lands tree-side after producer review
(ruling R7, 2026-09-16). Until it lands, `INTENTS/PRODUCERS.md` §9 (epoch `631d16e`)
governs; this document is its proposed §9.1 text, plus the measured gaps the proposal
rests on. One contract, one copy — this file carries no normative text that §9.1 will not.

**Authorities:** `INTENTS/PRODUCERS.md` §9 · `docs/adr/0001` (epistemic classes) ·
`docs/adr/0005` (pointer) · `docs/PRD/PMCA.txt` §1–2 · `docs/product-specs/argus/Argus.md`
(25 items, two evidence instruments) · `docs/PRD/eval/*` (rubric source) ·
9031 M1 contract. Measurements dated 2026-09-17 against the live tree.

---

## 1. The contract in one paragraph

Every producer output that the evaluation consumes must be **criteria-shaped**: for each
facet, the producing class names *what is extracted*, *in what schema*, *at what
granularity*, and *how it anchors* (a transcript span + exact quote + pinned epoch, or a
node reference, or explicitly neither, with the reason). A facet that cannot be anchored
is deliverable but is consumed only as **corroboration or context** — never as the sole
support of a scored finding. The consumer (Argus) never re-derives a facet; a missing
facet degrades to routing the affected criterion to a human, declared, not guessed.

## 2. The eight expertise classes × facets

Classes per ADR-0001. "Current state" is measured against the live tree (2026-09-17).

### 2.1 Versioned rubric (the yardstick — `_rubric/`, human-gated changes)

| module | producer | facets required | anchoring |
|---|---|---|---|
| Rules & criteria (25 items) | soft-compiler (9003/9011) | the four-layer node: `human_version` (authority) / `machine_criterion` / `signals` / `facets`; programmatic lane = deterministic checks, model_based lane = model-judged extraction | n/a (yardstick) — items reference indicators/lexicon by **pinned_sha**, never inline copies (9011's dedup) |
| Acoustic indicator framework (12) | audio2tree (ruling R2) | per indicator: id, unit, measurement window, threshold semantics, **schema aligned to what S0 actually emits** (§3.1) | n/a (yardstick); per-call readings are facts (§2.3) |
| Phrase & keyword lexicons | audio2tree (extensible part: curated) | per group: id, language, term list, match semantics | n/a (yardstick) |

### 2.2 Descriptive facts (authored, versioned; context, not yardstick)

| module | producer | facets required | anchoring |
|---|---|---|---|
| Product introduction | doc2graph | `product-intro.md` per L1 — claims a finding may cite (e.g. 费用/资料/地址) as **declared exposure** in the proposer prompt | node reference (`intents_path` + pinned_sha); never a grounding referent |
| Operation manual (L2 capsule) | doc2graph | `index.md` (Bone) + `ui_steps.yaml` (Flesh): ordered steps with ids, so a finding can cite "step missing" | node reference |
| Dynamic knowledge base | curated | `dkb.*.yaml` — scope-anchored facts (highest authority in its scope) | node reference |
| **Industry proper-noun table** | doc2graph | `PROPER_NOUNS.yaml` (2026-09-17): canonical form / aliases / colloquial / ASR mishears / context — serves transcription biasing and correction | n/a (instrument input) |

### 2.3 Facts (per-call, produced at ingest)

| module | producer | facets required | anchoring |
|---|---|---|---|
| Call record (`calls/*.json`) | audio2tree | top: `schema_version`/`audio`/`config`/`speakers`/`segments`/`turns`/`between_turn_pauses`/`stats`. **Per segment**: `acoustic{f0,intensity,speaking_rate,voice_quality}` (§3.1). **Per turn**: speaker/start_sec/end_sec/segment_ids/text | **the anchor source**: turn-level spans resolve here; exact quotes verified against `turns[].text` in the pinned transcript |

### 2.4 Accumulated history (grows at runtime, anchored to L3 nodes)

| module | producer | facets required | anchoring |
|---|---|---|---|
| Best-practice cookbook | curated | `cookbook.*.yaml` — precedent with the confirmed-pass evidence | L3 node + call-id + span |
| Error-case library | curated | `errors.*.yaml` — confirmed-fail exemplar (the I6 correlated-class substrate) | L3 node + call-id + span |
| **Current state: both shelves are empty** (measured 2026-09-17 — no `dkb/cookbook/errors.*.yaml` files exist yet). Chain A's 44-item proposal manifest is the first landing material. |

## 3. Measured gaps this contract must close (for producer review)

**3.1 Indicator thresholds vs produced units — a live mismatch.** `speech-rate`
indicator declares `unit: wpm, min: 80, max: 200`; the record's
`segments[].acoustic.speaking_rate` emits `words_per_sec` (~0.6) and
`syllables_per_sec_est` (~3.0). As written, **every segment flags**. The thresholds are
placeholders (pitch 75–300 Hz is the human-voice range, not calibrated). Owner of the
fix: soft-compiler 9011 (threshold semantics + units), calibrated against Chain A's
annotated fragments; audio2tree aligns the emitted schema. Until then the acoustic lane
is producer-named but not consumable.

**3.2 Lexicon language.** `lexicon.yaml` declares `language: "en"` with English phrases,
against a Chinese corpus. Same class of defect as the retired English NLI model — the
instrument must be Chinese before any criterion can lean on it.

**3.3 Indicator file header paths** say `_rubric/acoustic/` and `_rubric/phrase-keyword/`
(old layout); actual paths are `_rubric/evidence/acoustic/` and
`_rubric/evidence/phrase-keyword/`. Cosmetic but read as fact by newcomers — fix on the
next compile-side touch.

**3.4 Overlap semantics.** `between_turn_pauses` carries **negative** durations
(measured: −0.33s) that mean inter-speaker overlap; the schema does not say so. The
turn-taking-overlap indicator (and item-12's 抢话/压话) consumes exactly this — define
the sign convention in the schema, not in a reader's head.

**3.5 Two rate measures exist**: per-segment `speaking_rate.words_per_sec` and
per-speaker `wpm_mean`. The contract must name which is canonical for the speech-rate
criterion (and how the other is derived) — two measures that can disagree are two
answers to one question.

**3.6 `audio.path` is a dead pointer** (`/tmp/t9-short/…`, the emptied directory) —
orthogonal to this contract but the same finding that blocks the κ blind-eval audio
(open human decision, 2026-09-17).

## 4. §9.3 refinement — the two-tier report storage (ruling R1)

Argus's write path stays one: the report record, append-only, beside the call log.
Physical shape:
- **tree (hot)**: daily summary JSONL — one line per call: scores (raw/adjusted),
  verdict counts, routing reason, the evaluation epoch, replay hash, and a
  content-addressed pointer + sha256 to the full record;
- **cold (content-addressed)**: the full record (per-item verdicts with evidence,
  dimension rollups, applied precedents, derivation trail) — replay forever (I4/I5);
- **annual compaction** exports Parquet — the Metis-class analytics instrument.

Rationale on record: at 1,500–2,000 calls/day the one-file-per-report tree is
infeasible (~25–45 GB/year, 0.5–0.7 M files); the bounded hot tier keeps the tree
clonable while the annual archive serves cross-case analysis.

## 5. Anchoring requirements (all classes; the consumer's side of §9.1)

- A scored finding anchors to **a real transcript span** (turn-level or finer, resolved
  by exact-substring against the pinned transcript) **and a real node** (compiled
  `_rubric/` item + INTENTS node at the pinned epoch).
- Turn-level spans are the accepted unit (9031 M4); a short turn whose text collides
  elsewhere in the transcript **fails loudly into `ungrounded`** — never a guessed
  offset.
- Spans, quotes and epochs ride the record; replay uses the recorded epoch, never the
  current tree (I4/I5).

## 6. Open items for producer review

1. soft-compiler: fold §3.1/§3.2/§3.5 resolutions and the 9011 quantification results
   into the §9.1 text before it lands.
2. audio2tree: confirm the acoustic facet schema (which fields are contractual vs
   diagnostic) and the overlap sign convention (§3.4).
3. doc2graph: confirm `PROPER_NOUNS.yaml`'s facet row (§2.2) reads correctly as contract.
4. Human: the κ audio-source decision (§3.6) is independent of this proposal but
   blocks the calibration that would calibrate §3.1's thresholds.
