# PRODUCERS.md §9.1 Revision Proposal — The Criteria-Shaped Facet Contract

**Status:** staged in harness-cli (9031 M1). Lands tree-side after producer review
(ruling R7, 2026-09-16). Until it lands, `INTENTS/PRODUCERS.md` §9 (epoch `631d16e`)
governs; this document is its proposed §9.1 text, plus the measured gaps the proposal
rests on. One contract, one copy — this file carries no normative text that §9.1 will not.

**Authorities:** `INTENTS/PRODUCERS.md` §9 · `docs/adr/0001` (epistemic classes) ·
`docs/adr/0005` (pointer) · `docs/PRD/PMCA.txt` §1–2 · `docs/product-specs/argus/Argus.md`
(25 items, two evidence instruments) · `docs/PRD/eval/*` (rubric source) ·
**`docs/exec-plans/active/9011-evidence-citation-compile.md` @ `33f6efe`** (the
compiler line's implementation plan — lane definitions, admission gates, future
coverage map; cited by location so this proposal and that plan cannot drift apart) ·
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
| Rules & criteria (25 items) | soft-compiler (9003/9011) | the four-layer node: `human_version` (authority) / `machine_criterion` / `signals` / `facets`. **Lane definition — cite verbatim from 9011, never restate:** programmatic = phrase gates (`values_gate_locates`) **+ acoustic indicator refs** (`facets.programmatic[].indicator + calculation`, with indicator id + threshold + window + producer + combination); model_based = model-judged extraction facets; the split is *deterministic computation vs model judgment* — I6's 1.0 vs `W_C`/0.0 (9011 @ `33f6efe`, Decision Log Part 2, "The association carrier is `facets.programmatic[].indicator + calculation`, never `corroborators[]`") | n/a (yardstick) — items reference indicators/lexicon by **pinned_sha**, never inline copies (9011's dedup) |
| Acoustic indicator framework | **argus** (ownership transferred by human ruling 2026-09-20; was audio2tree/curated) | per indicator: id, unit, measurement window, threshold semantics, **schema aligned to what S0 actually emits** (§3.1). Scope broadened by the same ruling: the registry carries **every quantified predicate extracted from the rubric text** (hold-time ≤30s, name-ask >2, filler-repeat >2, …), acoustic and behavioural alike — soft-compiler extracts, Argus curates | n/a (yardstick); per-call readings are facts (§2.3), producer unchanged (audio2tree, R2) |
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
| Per-call attitude labels (`服务态度标签`, a JSON column on the Coco side's `stack-a` table — not carried in `calls/*.json`) | `call-inspector/v1_5_cuda` (Coco side) | per call, five dimensions `机械化` / `敷衍` / `亲切` / `不耐烦` / `中性`, each `{value ∈ {是, 否, 未知}, unknown_reasons[] (closed enum: `z_uncalibrated` / `baseline_missing` / `baseline_insufficient` / `baseline_degenerate` / `insufficient_windows`; two further values reserved, never emitted), baseline_ref, calibration_ref, n, n_excluded_mixed, k}`. A z component is evaluated by a fixed four-step short-circuit cascade (baseline state → `n < 2` → uncalibrated → calibrated `F = k/n ≥ c`) and the dimension is a strong-Kleene OR union of its components; invariant: `z_uncalibrated ∈ unknown_reasons ⇔ calibration_ref is None`. `value = 是` carries an empty reason set. **Empty is not "measured"**: `n_excluded_mixed` is structurally 0 this round (`exclude_mixed=False` — no data source, not "no mixed windows found"), and the 28 pre-existing baseline rows carry `baseline_ref = None` by construction (built before the ref mechanism), never to be back-filled. Alignment of record on the producer side: `call-inspector/v1_5_cuda` `docs/phase3-bfamily-plan.md` §6.3 (2026-09-26) | **no span — a call-level aggregate ⇒ consumed as facts / context only.** Never evidence for a finding, and never a corroborator: corroboration requires the signal's span to co-locate with the finding's (I6), which a call-level aggregate cannot satisfy. Serving these labels as an acoustic corroborator would require per-window / per-turn anchoring — a **new facet requirement**, not an upgrade of this row |

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

**3.7 Duration-threshold collapse — a class, 2 of 6 hits.** The compiler's audit
(9011 `f6a223c`) checked every `extracted` threshold against its compiled node:
items 2 and 8 are clean count predicates with verbatim clause provenance; items 4
and 17 exist in the nodes **only as lexical phrase gates** — "转接、候线时长不超过30秒"
and the attribution split "非客服原因>30s / 客服原因>15s" have no duration predicate
at all (`decomposed_from` empty on the S-lane gates 4-S01/17-S01/12-S01). The
extraction entries in the registry stand as-is — they faithfully reflect the rubric;
the nodes are the unfaithful side. Recovery is 9011 M2's acceptance
(`test_item17_attribution_recovered`, `test_item4_duration_predicates`), with the
principle recorded there: phrase gates stay a lexical channel, duration predicates
are a new programmatic channel, never a silent substitution.

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

## 5. The two admission gates (9011's flip precondition, conjunctive)

A rubric item turns `checkable: true` only when **both** hold — partial green over
fake wiring is the failure mode these gates exist to forbid:

1. **measurable** — the predicate's 口径 exists (an indicator/lexicon entry with
   defined semantics) **and** a producer's schema supplies the reading;
2. **computable** — thresholds + combination logic + NA conditions fully specified,
   with **no step left to model discretion**.

Owned by 9011 (its M2), carried with negative tests there; this contract states the
gates because they are the consumer's requirement, not the compiler's preference.
Two 9011 artifacts land later and complete this proposal's §2.1 picture — cited now,
consumed when they flip: the **coverage map** (25-item three-way ledger: green /
model_only / reason ∈ {no indicator coverage, no producer, inherently
whole-judgment}, 9011 M5) and the **mapping-input format** (9011 M0).

## 6. Anchoring requirements (all classes; the consumer's side of §9.1)

- A scored finding anchors to **a real transcript span** (turn-level or finer, resolved
  by exact-substring against the pinned transcript) **and a real node** (compiled
  `_rubric/` item + INTENTS node at the pinned epoch).
- Turn-level spans are the accepted unit (9031 M4); a short turn whose text collides
  elsewhere in the transcript **fails loudly into `ungrounded`** — never a guessed
  offset.
- Spans, quotes and epochs ride the record; replay uses the recorded epoch, never the
  current tree (I4/I5).

## 7. Open items for producer review

1. soft-compiler: fold §3.1/§3.2/§3.5 resolutions and the 9011 quantification results
   into the §9.1 text before it lands. §3.7 is registered in 9011's Surprises with two
   acceptance tests; §3.6's item-6 typo awaits the human's ruling (recorded verbatim in
   the registry's extraction_notes).
2. audio2tree: confirm the acoustic facet schema (which fields are contractual vs
   diagnostic) and the overlap sign convention (§3.4).
3. doc2graph: confirm `PROPER_NOUNS.yaml`'s facet row (§2.2) reads correctly as contract.
4. Human: the κ audio-source decision (§3.6) is independent of this proposal but
   blocks the calibration that would calibrate §3.1's thresholds.
