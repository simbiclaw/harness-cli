# 9031 — The Argus Derivation Pipeline: Upstream Contract, S2, and the First End-to-End Run

## 1. Purpose

本计划**完全取代并推翻** 9021 family（9021 及其全部子计划 9024–9030，已归档至
`docs/exec-plans/archived/`；各归档文件末尾附有 overturn 记录）。

**推翻原因：**

原 family 的执行方案——把 simbi（B）的提案半 port 进 `src/argus/io/` 再桥接到
spec 派生的 core——被人工裁定推翻（2026-09-16，"no simbi at all"）。裁定依据是测量
而非执行失败：port 产出无 span 的整轮证据，而 spec §3.2 的 finding 需要 span+quote+epoch；
fidelity floor（2,370 行守卫基建）使 port 不可扩展、接缝不可建；B 自身从未对真实模型
运行过；其本地 NLI 仪器被裁定**未经测量即视为空**。完整理由见归档的 9021
Outcomes & Retrospective — OVERTURN RECORD。

**与旧计划的关键区别：**

| 方面 | 原计划 (9021 family) | 本计划 (9031) |
|:-----|:---------------------|:--------------|
| S2 提案阶段的来源 | 从 simbi port 七个模块 | 按 spec 从零构建（span 锚定 finding） |
| types 契约 | port 自 `models/schemas.py` + fidelity floor | Argus 侧自有契约；仅 `VerdictResult`/`RubricItem` 两个符号需要安家 |
| 上游契约 | 隐含（消费既有产物） | 显式：criteria-shaped facets + schema（PRODUCERS.md §9.1） |
| 下游契约 | 无（报告无处可写） | 报告记录写树（§9.3）+ sira-proxy 渲染模版 |
| 验收标准 | fixture / fake-LLM 可接受 | **每关必须真实数据执行；fixture-only 不再验收** |
| 代码基线 | core/（保留）+ io/ port（保留并扩展） | core/ 原样保留；io/ port 删除 |

**产品需求来源：** `docs/product-specs/argus/Argus.md`（四维质量模型、25 评分项、
双证据仪器、五条保证、三个人工队列、部署形态——本计划交付的就是它描述的系统）。
**架构依据：** `docs/PRD/PMCA.txt`（四层：感知→记忆→认知→行动）；
`INTENTS/PRODUCERS.md` §9（消费端契约——**唯一规范文本**）；
`docs/adr/0005`（指针：harness 侧后果与 provenance）。
**规格：** `docs/retrospectives/process-derivation-pipeline-spec-v5.html` + patch-1；
`soft-criteria-authoring-spec-v4` + patches 1–3。规格与产品文档冲突时，规格为准。

## 2. Big Picture

Argus is the pure derivation pipeline — the cognition layer of PMCA: given one call
recording and the INTENTS tree at a pinned epoch, produce one defensible QA report
record written back alongside the call log. Three sections, in dependency order:

1. **Upstream contract (§9.1)** — Argus defines, per expertise class, which facets
   producers must extract and in what schema, shaped by the gradable criteria. The
   compiled `_rubric/` nodes (9003/9010/9026-line) are the established part of this
   contract; what is new is the explicit facet/schema statement and the anchoring
   requirements (resolvable spans, exact quotes, pinned epoch).
2. **The pipeline itself** — S1 Read (Provider at pinned epoch), S2 Propose (built from
   scratch: turn-level span addressing, finding extractor, Chinese QA prompts), then
   wiring the already-landed pure stages: S3 ground → S4a score → S4b adjust → S5 route.
3. **Downstream contract (§9.3)** — the report-data schema Argus writes into
   `<domain>/<case>/reports/` (append-only, epoch-carrying) and the report template
   sira-proxy renders for human review.

**Code inheritance (measured, not assumed):** `src/argus/core/**` (2,007 lines, zero B
lineage) is kept untouched in substance; `types/anchored.py` (the anchor slot) is kept;
`io/call_record.py` (Argus-original consumer reader) is kept and extended to retain the
positional data it currently drops. Everything else in `io/` with simbi lineage —
`qa_agent`, `fact_checker`, `nli`, `question_generator`, `atomizer`, `prompts`,
`llm_client` — and the ported `types/pipeline.py` are **deleted** (M2). The fidelity
floor's artifacts (schema snapshot, mutation sweep, deviation register, the floor half
of `test_schemas.py`) are deleted with them.

**The one ported capability carried across as a method, not code:** both-polarity
hypothesis testing (`hypothesis_pos`/`hypothesis_neg`), as a candidate *correlated*
signal (I6, W_C = 0.4) — never as a verdict mechanism.

### File Scope

| path | action |
|---|---|
| `docs/exec-plans/archived/9021*.md`, `9024–9030*.md` | archived (this overturn) |
| `docs/adr/0005-…` | exists (pointer); cited, not modified |
| `src/argus/io/{qa_agent,fact_checker,nli,question_generator,atomizer,prompts,llm_client}.py` | delete (M2) |
| `src/argus/types/pipeline.py` | delete; `VerdictResult`/`RubricItem` re-homed (M2) |
| `tests/fixtures/upstream_schema_snapshot.json`, `scripts/build_schema_snapshot.py`, `scripts/mutate_m5_contract.py`, `tests/fixtures/intentional_deviations.yaml` | delete with the floor (M2) |
| `tests/test_schemas.py` | floor half deleted; roundtrip half re-homed to Argus types (M2) |
| `tests/test_no_write_path.py` | amended: report-glob carve-out (M7) |
| `src/argus/io/call_record.py` | keep; stop dropping `start_sec`/`end_sec`/`segment_ids` (M4) |
| `src/argus/io/local_proposer.py`, `logprob_scoring.py` | keep (spec boundary); extractor lands against it (M5) |
| `src/argus/io/` new: `reader.py`, `spans.py`, `extractor.py`, `propose_prompts.py`, `report_record.py` | new (M3–M7) |
| `docs/facets/…` or PRODUCERS.md revision proposal | new (M1) |
| `pyproject.toml` | drop transformers/torch references if present (M2; NLI retired — no dep-vet needed for a removal) |

## 3. Milestones

Each milestone carries its Behavioral/Structural test declarations per
`docs/conventions/pev-loop.md`. **Every acceptance test runs on real corpus data**
(`/Users/prometheus/workspace/INTENTS/**/calls/*.json`, 718 records; real compiled
`_rubric/` nodes). Fixture-only validation is not acceptance — that is the overturn's
first lesson.

### M1 — The upstream facet/schema contract (criteria-shaped)

**Contract.** For each of the eight expertise classes, state: which facets must be
extracted, the output schema, and how each facet maps to the gradable criteria it
serves — including the anchoring requirements (span resolvable at turn granularity or
finer, exact quote, pinned `intents_sha`). Reconcile with the established parts:
`_rubric/rules_criteria/` four-layer structure, `_rubric/profiles/` (D13–D15), the
`calls/` record schema (producer's real shape, `schema_version: "1.0"`).

- *Deliverable:* the facet/schema specification as a PRODUCERS.md §9.1 revision
  proposal (staged, not committed to the tree), reviewed with the producer sessions
  — **this includes the two-tier report-storage refinement of §9.3** (ruling #1).
- *Known evidence (advisory):* ~~the acoustic shelf's producer is unowned~~ **resolved
  by ruling #2 (2026-09-16): the 12 acoustic indicators are produced by audio2tree
  (its M11 per-turn measurement, in flight); Argus consumes them as facts.** The
  facet spec names audio2tree as the acoustic producer.
- `Behavioral Test:` `tests/test_facet_contract.py::test_every_facet_maps_to_a_gradable_criterion`
  and `::test_every_facet_names_its_producer` — the spec, parsed as data, must satisfy
  both over all eight classes; validation runs against one real compiled `_rubric/`
  node per dimension (real data, not fixtures).
- `Structural Test:` `::test_contract_cites_sole_normative_text` — the spec cites
  PRODUCERS.md §9 as governing and duplicates no normative content (the ADR-0005
  discipline: one contract, one copy).
- **Depends on:** nothing (doc milestone; the only one that can run in parallel with M2).

### M2 — Retire the port; re-home the two symbols; land the fences

**Contract.** Delete the seven ported `io/` modules, the ported `types/pipeline.py`,
and the fidelity floor's artifacts. Give `core/`'s two needed symbols
(`VerdictResult`, `RubricItem`) Argus-side homes (new `types/verdict.py` — spec-derived
naming, no upstream-comparison constraint). Land 9024 M8's four `forbidden`
import-linter contracts and repoint the I8 checker (9024 M9) at the post-port tree.
Drop the `transformers`/`torch` dependency references (the NLI instrument is retired by
ruling; removal needs no dep-vet).

- *Acceptance property:* the suite is green with no simbi lineage anywhere in
  `src/argus/`; `grep -rniE 'simbi|929d5a7|ported from' src/` returns nothing.
- `Behavioral Test:` the surviving roundtrip tests re-homed to the Argus types
  (`tests/test_verdict_types.py`) — construction, serialization, replay-hash
  exclusion of proposed scores (I3/I5 properties preserved on the re-homed types).
- `Structural Test:` `tests/test_fences.py` (the four contracts, red/green samples),
  `tests/test_i8_provenance_separation.py` repointed at the live tree with its
  allowlist, and `::test_no_ported_provenance_strings` — the grep above as a fixture.

### M3 — S1 Read: the Provider at a pinned epoch

**Contract.** One read surface (`io/reader.py`): the call record, the compiled
`_rubric/` nodes for the applicable dimensions, and the history shelves
(`cookbook.*`/`errors.*`) — all resolved at the epoch recorded in `EPOCH.yaml`, cached
by capsule id per 9025 M13's design. No write path (unchanged until M7's carve-out).

- `Behavioral Test:` `tests/test_reader.py::test_reads_a_real_record_at_the_pinned_epoch`
  — one real `calls/*.json` plus one real `_rubric/` item, fields resolved, `intents_sha`
  == the pinned SHA; `::test_a_manifest_without_a_rubric_item_is_routing_only`
  (the AGENTS.md 9002 read protocol, on real nodes).
- `Structural Test:` `::test_reader_imports_no_core` (layer fence) and
  `::test_sole_read_surface` (no other `src/argus/` module opens INTENTS).

### M4 — Turn-level span addressing

**Contract.** `io/spans.py`: resolve each turn's `text` (via the record's
`segments[]`/`start_sec`/`end_sec`, no longer dropped by `call_record.py`) to a
character span in the pinned transcript, exact-substring verified. **Turn granularity
is the accepted unit** — the concession from the #20 rebuttal: a turn-level span
asserts exactly what was looked at, errors toward the safe direction, and is I2-legal
by I2's own wording ("exact-quote verified" is a substring check).

- *Known evidence (advisory):* 9024:144 recorded a 17/17 round-trip on the sample
  transcript and warned that short turns may collide on longer calls — verify on the
  real corpus, not the sample.
- *Acceptance property:* over a real batch (≥50 records), every turn resolves; any
  ambiguous collision (short turn text appearing multiple times) **fails loudly into
  the ungrounded bucket** — it never silently picks an offset.
- `Behavioral Test:` `tests/test_spans.py::test_every_turn_in_a_real_batch_resolves`,
  `::test_a_colliding_short_turn_routes_ungrounded_not_guessed`,
  `::test_the_span_survives_the_epoch_round_trip`.
- `Structural Test:` `::test_call_record_no_longer_drops_positional_data` (the M7-era
  comment is gone with the code that wrote it).

### M5 — S2 Propose: the finding extractor and its prompts

**Contract.** `io/extractor.py` + `io/propose_prompts.py`: the spec-shaped proposer.
Output is `ProposedFinding` (the §3.2 shape: `finding_id`, `rubric_id`, `intents_node`,
`violation`, `checking_path`, `evidence: tuple[AnchoredEvidence, ...]` — all seven
spec-named fields including `span_ref`, `quoted_text`, `anchor_node`,
`grounding_signals`, `primary_channel`, `model_confidence`, `finding_type`). Prompts
are written fresh for span-anchored findings (Chinese, domain vocabulary sourced from
`docs/PRD/eval/` and the INTENTS corpus — **not** copied from B's mechanism-bound
prompts). Land against `local_proposer.py`'s existing spec boundary (batch interface,
injected model protocol, quarantined output). Both-polarity hypothesis testing is a
permitted *correlated*-signal method (I6, W_C = 0.4), never the verdict mechanism.

- *Acceptance property:* one real call → candidate findings, each either fully anchored
  (real span + exact quote + real node) or explicitly quarantined to `ungrounded`;
  zero fabricated anchors.
- `Behavioral Test:` `tests/test_extractor.py::test_one_real_call_yields_anchored_findings`,
  `::test_a_finding_without_a_resolving_quote_is_quarantined_not_scored` (I2 red),
  `::test_the_proposed_score_never_reaches_a_disposer_input` (I7/I8, on real extractor
  output).
- `Structural Test:` `::test_extractor_lives_behind_the_proposer_boundary` (no `core/`
  import from the extractor; quarantine shape per I1).

### M6 — Wire S3 → S4: gate, score, adjust

**Contract.** Extractor output → `core/grounding.py` (exists) → `ScorableFact`
production (the first real producer of one — currently zero exist) → `core/score.py` →
`core/adjust.py` with real history from the tree. Deterministic replay: same inputs,
identical raw and adjusted.

- `Behavioral Test:` `tests/test_wire_s3_s4.py::test_a_real_call_derives_a_deterministic_score`
  (run twice, byte-identical), `::test_the_replay_hash_covers_grounded_inputs_and_precedents_only`.
- `Structural Test:` `::test_score_receives_no_history` (the existing canary, now fed
  by real output instead of test literals).

### M7 — S5 Route and the report record (the write path, two-tier storage)

**Contract.** `core/route.py` (exists) → `io/report_record.py`: the report-data schema
per PRODUCERS.md §9.3 — one call ↔ one record, carrying the evaluation epoch, the
findings with evidence, applied precedents, routing reason, derivation trail
(**logical granularity, human ruling 2026-09-16 #4: one full record per call**).
**Physical storage is two-tier (human ruling 2026-09-16 #1):** the tree receives a
**daily summary JSONL** (append-only, one line per call: score, verdict counts,
routing reason, epoch, replay hash, and a content-addressed pointer + sha256 to the
full record); full records go to the **content-addressed cold tier** (replay forever,
I4/I5); an **annual compaction job exports Parquet** for Metis-style cross-case
analytics. At production scale (≈1,500–2,000 calls/day ≈ 25–45 GB/year of full
records, 0.5–0.7 M files) one-file-per-report in the git tree is infeasible — this
shape keeps HEAD small and makes the annual archive the analytics instrument. The
§9.3 physical-shape refinement rides the M1 contract revision proposal (producer
review before landing tree-side). **Gated on the human-authorized
`_meta/ownership.yaml` re-sync registering the `argus` glob** (Awaiting Steering A1 —
the re-sync must land before any report does; doc2graph's zero-orphan CI depends on
the ordering). Amend `tests/test_no_write_path.py`: no writes outside the report
glob; the referent prohibition keeps its teeth.

- *Acceptance property:* one real call → one summary line in the day's JSONL + one
  full record in the cold tier, byte-replayable from its stored epoch; knowledge
  nodes untouched.
- `Behavioral Test:` `tests/test_report_record.py::test_one_real_call_writes_one_summary_and_one_full_record`,
  `::test_the_full_record_round_trips_and_replays_at_its_recorded_epoch`,
  `::test_knowledge_globs_are_untouched_by_a_report_write`,
  `::test_the_annual_export_covers_exactly_one_year_of_summaries` (fixture-scale day
  files; the exporter runs on real summary lines).
- `Structural Test:` `test_no_write_path.py` red/green updated — a write to `_rubric/`
  still fails; a write to the report glob passes; any other path fails.

### M8 — The report template and the sira-proxy contract

**Contract.** The human-readable report template (likely H5) and the rendering
contract: what fields sira-proxy reads from the record, what the reviewer sees, how the
three human queues surface. Downstream contract per §9.3; sira-proxy is a *reader*, not
a producer.

- `Behavioral Test:` `tests/test_report_template.py::test_the_template_renders_a_real_record`
  — a fixture renderer (the contract's reference implementation) renders one real
  report record and every field the template names exists in the schema.
- `Structural Test:` `::test_template_reads_only_schema_fields` (no free-form
  scraping of the record).

### M9 — The first end-to-end run

**Contract.** One real call, producer output → S1 → S2 → S3 → S4 → S5 → report record
in the tree → rendered template. The first time anything in this repository has run
end-to-end on real data. Nothing about this milestone is allowed to be a fixture.

- *Acceptance property:* the run completes without a human patching inputs; the record
  replays bit-for-bit; a human can read the rendered report and trace every finding to
  its quote and node.
- `Behavioral Test:` `tests/test_end_to_end.py::test_one_real_call_end_to_end`,
  `::test_the_record_replays_bit_for_bit`,
  `::test_every_finding_in_the_record_traces_to_evidence`.
- `Structural Test:` the full fence suite over the live run path.

### M10 — Agreement instrument and the audit floor

**Contract.** 9028 M19.5 absorbed: the §6 agreement store (Argus-vs-human κ per
criterion, τ gate), CriterionHealth, and the random-tranche audit sampling (patch-1
D22 — random floor only in the escape-rate estimate). This is what makes auto-final
honest per Argus.md's guarantees 3 and 4. **Seed path (human ruling 2026-09-16 #5):**
the κ seeds are **Chain B's 20–50 complete calls** (sourced from the 2026-06-26
archive per ruling; dispatched to audio2tree) — QA labels them per-item 1/0/NA from
transcript + rubric standards **before any machine verdict exists** (physically
blind); pairing against M5–M9's verdicts seeds the store. Independent of SIRA. Thin
per-criterion κ on rare items degrades honestly through the τ gate (routes to human),
with no compensatory relaxation. Landing the machinery and its data contract is in
scope; producing the labels is the calibration channel's (curated's) — declared, not
silently dropped.

- `Behavioral Test:` `tests/test_agreement.py::test_a_criterion_below_tau_cannot_auto_finalize`
  (on a real criterion with injected labels),
  `::test_the_escape_estimator_consumes_the_random_tranche_only`.
- `Structural Test:` `::test_agreement_never_clears_criterion_below_tau` (D4, the
  orthogonality canary).

## 4. Progress

- [ ] M1: The upstream facet/schema contract
- [ ] M2: Retire the port; re-home the two symbols; land the fences
- [ ] M3: S1 Read — the Provider at a pinned epoch
- [ ] M4: Turn-level span addressing
- [ ] M5: S2 Propose — the finding extractor and its prompts
- [ ] M6: Wire S3 → S4
- [ ] M7: S5 Route and the report record
- [ ] M8: The report template and the sira-proxy contract
- [ ] M9: The first end-to-end run
- [ ] M10: Agreement instrument and the audit floor

## 5. Decision Log

### Decision: Overturn the 9021 family and rebuild S2 from the spec

**Rationale:**
- Source: Human ruling 2026-09-16 ("no simbi at all"), on measurements recorded in
  issue #20 and two adversarial rebuttals; full record in
  `docs/exec-plans/archived/9021-relayer-argus-eval-pipeline.md` (OVERTURN RECORD).
- Evidence: the port's output shape cannot anchor (whole-turn text, no offsets); the
  fidelity floor forbade the bridge; B never executed against a real model; the floor's
  six adversarial rounds bought equality with an unexecuted prototype.

**Confidence:** high (the ruling is the human's; the measurements are reproducible from
the paths in the archived record).

**Consequences:**
- The 9021 family is archived; this plan is the sole successor for the domain.
- `core/**` is inherited as-is; the port and its floor are deleted (M2), not amended.
- The forcing language of the archived plans ("structurally cannot", "the decision is
  forced") is superseded: turn-level anchoring **is** buildable — this plan builds it
  (M4) as the honest form of the seam the rebuttals conceded.
- Every milestone gates on real-data execution; fixture-only validation is no longer
  accepted.

### Decision: simbi's NLI instrument is assumed empty without measurement

**Rationale:**
- Source: Human ruling 2026-09-16 (不用测了，就假定是空的).
- Context: three repo records (synthesis.md T4 default, 9027 M17) premised keeping a
  local NLI as I6's only weight-1.0 independent instrument; the instrument never loaded
  a model, and its configured model is an English cross-encoder over a Chinese corpus.

**Confidence:** high (it is a ruling, not a measurement — and is recorded as such).

**Consequences:**
- `io/nli.py` retires with the port; no transformers/torch dependency.
- Reviving the instrument requires a deliberate act producing a measurement (the Q6c
  pattern): dep-vet, install, run Chinese pairs — then re-litigate.
- The I6 independent-instrument ledger is: acoustic (unowned — M1 must name its
  producer), lexical/lookup (not built), NLI (ruled empty).

### Decision: D15 narrowed to the referent rule; PRODUCERS.md §9 is the sole normative text

**Rationale:**
- Source: Human directive 2026-09-16; `INTENTS/PRODUCERS.md` §9 (epoch `631d16e`);
  `docs/adr/0005` (pointer).

**Confidence:** high.

**Consequences:**
- Argus's only write surface is the report record (append-only, epoch-carrying,
  alongside the call log); knowledge nodes stay zero-write.
- `tests/test_no_write_path.py` is amended in M7, gated on the ownership re-sync (A1).
- This plan restates no contract content; it cites §9.

### Decision: turn-level anchoring is the accepted granularity

**Rationale:**
- Source: Rebuttal round 1 on issue #20 (conceded by the local session): a turn-level
  span derived by exact-substring localization is I2-legal by I2's own wording; the
  record's `segments[]` yields honest spans without re-plumbing anything.
- Counterweight recorded: short-turn collisions (9024:144's warning) must fail loudly
  into `ungrounded`, never guess (M4's acceptance property).

**Confidence:** medium-high (17/17 on one sample transcript; the real-batch test in M4
is what converts this to measured).

**Consequences:**
- S2 is buildable without fabricating anchors — the seam exists and is honest.
- Character-level precision is not required for the acoustic channel (turn-level is the
  natural unit there anyway); if a future criterion needs sub-turn precision, that is a
  new facet requirement through M1's contract, not a silent upgrade.

### Decision: the 2026-09-16 steering-interview rulings (recorded verbatim)

The human ruled on seven open questions in one sitting (steering-interview playground,
2026-09-16). Recorded as one entry with the per-ruling consequences; the source for
each is the human's own words, captured in the interview transcript and quoted in the
plan sections they amend.

**R1 — Report co-location + two-tier storage.** Reports co-locate **only** beside
audio2tree's `calls/` (strict sibling; doc2graph-derived leaves carry no reports) —
for Metis-class consumer agents. Physically: **tree = daily summary JSONL** (append-
only, one line per call, with pointer + sha256) → **cold tier = content-addressed
full records** (replay forever) → **annual Parquet compaction** (the Metis analytics
instrument). Human nuance, translated: at 1,500–2,000 calls/day the one-file-per-
report tree is infeasible; the annual archive is feasible only over a bounded hot
tier. Amends M7 (done); the §9.3 physical-shape refinement rides M1's revision
proposal. *Confidence: high (ruling, with the volume arithmetic on record).*

**R2 — Acoustic producer.** The 12 acoustic indicators are produced by **audio2tree**
(its per-turn measurement chain; M11's repetition work is one named instance, not the
mandate's scope — the producer *identity* is the ruling, the vehicle is audio2tree's
scoping call). Argus consumes as facts, never measures. Resolves Awaiting-Steering
A2. *Confidence: high (ruling).*

**R3 — S2 model and interface.** S2 runs the **LAN 27b behind `local_proposer.py`'s
`LogitModel` protocol** — D7's `proposed_score` comes from scoring-token logits,
matching Argus.md's on-premise deployment shape without exception. *Confidence: high
(ruling).*

**R4 — Report record granularity.** One full record per call: per-item verdicts with
evidence, per-dimension rollups, raw and adjusted scores, applied precedents, routing
reason. (Logical granularity; R1 governs physical storage.) *Confidence: high
(ruling).*

**R5 — κ bootstrap.** Seeds = **Chain B's 20–50 complete calls** (sourced from the
2026-06-26 archive per the same sitting's corpus ruling; dispatched to audio2tree).
QA labels per-item 1/0/NA from transcript + rubric standards **before any machine
verdict exists** — physically blind. Independent of SIRA. Thin per-criterion κ on
rare items degrades through the τ gate with no compensatory relaxation. The
exemplar-clip library (Chain A, also dispatched) is a *different* instrument —
confirmed referents for I6's correlated class and calibration injection, not a κ
source. *Confidence: high (ruling).*

**R6 — Rubric scope stays 25.** Items 6–7 deferred pending ticketing-system access;
they activate when it exists. Approximating from transcript alone is explicitly
rejected (fabrication). *Confidence: high (ruling).*

**R7 — Contract text location.** The facet/schema contract lives as a
**PRODUCERS.md §9.1 revision** (staged in harness-cli, landed tree-side after
producer review). Resolves Awaiting-Steering A3. *Confidence: high (ruling).*

## 6. Surprises & Discoveries

_(empty — filled during execution)_

## 7. Awaiting Steering

**A1 — `_meta/ownership.yaml` re-sync authorizing the `argus` report glob.**
~~Proposed default~~ **Shape now fully settled by R1/R4** (strict-sibling report
location; two-tier storage; daily summary JSONL as the tree-side artifact). What
remains is the **Tier-C act itself**: the human-authorized ledger edit registering
`argus` for the report glob (the 2026-09-13 precedent requires the human's explicit
hand; agents cannot self-authorize). Sequencing unchanged: **before any report
lands** (doc2graph's zero-orphan CI). The exact glob expression is part of the M1
contract revision (daily JSONL changes the natural glob from
`*/**/reports/*.json` toward `*/**/reports/*.jsonl`).
**Deadline:** before M7 can execute. **Default if undecided:** M7 blocks; nothing writes.

**A2 — RESOLVED (R2, 2026-09-16):** acoustic producer = audio2tree; Argus consumes.
**A3 — RESOLVED (R7, 2026-09-16):** contract text = PRODUCERS.md §9.1 revision.

## 8. Outcomes & Retrospective

_(to be filled at completion)_
