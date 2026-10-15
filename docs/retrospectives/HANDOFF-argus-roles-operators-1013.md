# HANDOFF — Argus three roles + rubric→operator compilation (as of 2026-10-13, updated 2026-10-14)

For the next session. Self-contained; read end-to-end before acting. This is design/spec work
that sits **beside** the active plan `9031-argus-derivation-pipeline` (rev. 5 kernel). It does not
amend 9031.

## 0. Where the artifacts are (read this first)

All artifacts are committed on branch **`claude/argus-roles-operators-1013`**, cut from
`claude/9031-derivation-pipeline` @ `1d17f69` (pushed 2026-10-14). The branch is not merged.
Merge it into 9031, or open a PR, when the open decisions in §5 are settled.

| Path (in `docs/retrospectives/`) | What it is | Status |
|---|---|---|
| `process-derivation-pipeline-spec-v6.html` | Spec rev. 6: folds rev. 5 patch-1; adds Instrument → Grader → Coach (D23–D33, I8–I12, §2.6, §3.7–3.11, §6.5, T0–T7, §8.5 failure modes, §9.5 Awaiting Steering A1–A10) | draft. **D24 and I9 are superseded by §3 below.** |
| `operator-compilation-research-issue-25.html` | Research note for issue #25: shaping chain, 8-kind operator vocabulary, Item-9 / Item-12 critique, judge contract, R1–R10 | draft |
| `operators-item-01-05.yaml` | Items 1–5 compiled to operator programs (shared ops + per-item signals/extract/decide + open questions). **rev 2 (10-14)** recompiled from the full rubric; changes marked `# rev2:` | draft, validated as YAML |
| `HANDOFF-argus-roles-operators-1013.md` | this file | — |
| `../rubric/rubric_com_hotline.md` | **the full human rubric** (issue #25 attachment, provided by the human 10-14), sha256 `73f1f905…`. The authority for `human_version`. | new 10-14 |
| `../rubric/rubric-source-diff.md` | Clause-by-clause diff showing `specific-rubric-27.yaml` is **abridged**: 13 items lose verdict-changing clauses | new 10-14 |

Posted to GitHub (updated 10-14 with a "附：全文核对" section): a review comment on **issue #25**, in Chinese (the rubric's language):
`https://github.com/simbiclaw/harness-cli/issues/25#issuecomment-6143007978`. It references the
research HTML by path, so the path only resolves once that file is pushed.

## 1. Rulings of record — human-locked, do not re-litigate

| # | Ruling | Date |
|---|---|---|
| H1 | The output of attitude evaluation is **mostly a coaching signal**. Mindset moves from "scoring" to "diagnostic". | 10-12 |
| H2 | Metis is out of scope for now; focus on Argus. | 10-12 |
| H3 | Argus has three roles in order: **Measurement Instrument (quantitative) → Grader/Verdict (qualitative) → Coach (apply and close the loop)**. The human-supplied diagram shows a linear path. | 10-13 |
| H4 | Grader verdicts serve **both performance tracking and coaching**. Final; don't spend time on it. | 10-13 |
| H5 | Cause claims go **straight to the agent**. The agent reviews; on disagreement or anything unclear, a **human supervisor** reviews, comments and gives the final verdict. The human disposer satisfies "model proposes, gate disposes" (my earlier "only partly fits" was wrong and was retracted). | 10-13 |
| H6 | Prosodic features are normalised **relative to each agent's own baseline**. | 10-13 |
| H7 | Whether accepted claims enter performance records is an **offline process, unrelated to Argus**. | 10-13 |
| H8 | Review timeout is **configurable with a default value**. | 10-13 |
| H9 | Remaining parameters are settled **during implementation**. They are carried as A1–A10 with defaults in spec v6 §9.5. | 10-13 |
| H10 | **Shaping chain:** audio2tree is shaped to the soft-compiler, which is shaped to Argus. The soft-compiler defines operators per rubric item: regex, algorithmic heuristics, multi-dimensional metrics (prosodic, textual/semantic, interactional/temporal) and LLM prompt templates for quantitative and qualitative compute. audio2tree extracts facets and evidence from the call log, criterion-shaped and operator-shaped. | 10-13 |
| H11 | Issue comments are written in the **rubric's original language (Chinese)**. | 10-13 |
| H12 | The full rubric `rubric_com_hotline.md` is the source to compile from (the human supplied it after the download failed). | 10-14 |

## 2. Design state carried by spec v6, still valid

- **Topology.** The roles form a DAG, not a pure chain. Grader verdicts trigger the Coach (v1 is rule-bound), the Coach also reads Instrument readings directly, and **no edge runs Coach → Grader** (I10, with a mutation fixture).
- **Coach evidence is gated (I11).** Observations must cite confirmed findings on trusted criteria or readings that fired. `cause_hypothesis` is the only ungated field and is disposed by humans.
- **Alternatives are anchored (D29).** The compliance-layer practice script is verbatim from an INTENTS node. Judgment-layer adaptations are flagged `adapted: true`.
- **Agent baseline (D30) is Coach-lane only.** It is robust (median/MAD), scoped per agent × L1 intent, warms up from a population prior, keeps rolling and frozen references, and resets on discontinuities. Reason: history purity (D17), and per-agent values can't be compared across agents for performance tracking.
- **Review ledger (D31/I12).** Append-only and hash-chained. Unanswered past the timeout becomes `expired`, and `expired ≠ accepted`. Argus never writes review events. Who writes the ledger is A9 (Tier C, blocks T4).
- **Contest outcomes (D32)** never feed κ or the escape rate, because they are selection-biased. They go to calibration candidates only.
- **Re-measurement (D33).** Same agent, same L1 intent, same rubric epoch, next N calls. An epoch change sets `epoch_break`. Engagement (a played clip) is never a learning signal.
- **Indeterminate band (D26).** A reading within its error of the threshold yields `defer_reason: measurement_indeterminate`.
- **Conformance folded in:** ADR-0005 (the report record is Argus's one write path), the item count is 25, measurement-profile decisions are namespaced MP-D13…18, and Q2 is open (the registry has 13 acoustic indicators vs "12" in the prose).

## 3. Corrections to spec v6 from the issue #25 work (apply in v6.1)

- **C1 — I9 was too strong.** v6 said "no model in the Instrument". Compiled items mix deterministic and model operators by design (Item-9 ④, Item-12 ①④; the 9011 programmatic/model_based lanes). Replace with I9′: *deterministic readings are pure functions of (call record, operator version); model readings are span-anchored, typed `model`, grounded by S3, and never independent corroboration.*
- **C2 — D24 put extraction in the wrong tier.** v6 had S1m "apply the registry to the call record" inside Argus. Per H10 and §9.1 ("the consumer never re-derives a facet"), extraction runs in audio2tree. Replace with D24′: *S1m verifies that each reading names a known operator id/version at the pinned epoch with a valid anchor, then runs the decide half (`label` with the indeterminate band, then `combine`).* D25 and D26 carry over.
- **C3 — new facet requirements on audio2tree** for the §9.1 revision:
  - inter-pausal units per speaker with syllable count and articulation rate;
  - per-unit intensity (dB) and F0 (semitones);
  - an `overlaps[]` list: onset, offset, first/second speaker, onset class, resolution, confidence;
  - `channel_mode`;
  - judge outputs as span-anchored records;
  - **CTI call metadata**: direction, line_type, holds, transfers, end_reason, end_side (from the items 1–5 compile, G3).

## 4. Operator IR (from the research note §3)

Eight kinds: `segment · window · measure · event · lexicon/regex · judge` run in the **extract** stage (audio2tree), and `label · combine` run in the **decide** stage (Argus S1m).

- **Rule:** measure in the producer, decide in the consumer.
- **Extraction parameters** (window length, pause, seed, onset tolerance): changing one requires re-extraction and a version bump.
- **Decision parameters** ("?次/?秒", bands): changing one means a new rubric epoch only.
- **Judge contract:** one closed yes/no question; a `yes` must return `turn_id + quote`. Run the lexicon first and the judge only as fallback. Provenance stays `model` (never independent, I6). Track κ per judge operator.
- **Window default:** `census`. Sampling only when declared and seeded, and **never** for event operators.

## 5. Open decisions (need the human)

**From the issue #25 research (R1–R10)**

| ID | Decision | Recommendation |
|---|---|---|
| R1 | Split each item into an extract half and a decide half | yes |
| R2 | Closed operator vocabulary instead of free `calculation` Python | yes |
| R3 | Where judge operators run | audio2tree, returning a span |
| R4 | **Are hotline recordings stereo?** Decides whether Item-12 is measurable | establish the fact first |
| R5 | Item-9 "语音平稳" = intensity/F0 jumps, not speech-rate variance | needs a human ruling |
| R6 | Item-9 ③ vs Item-12: partition overlaps by onset class (terminal vs mid-turn) | yes |
| R7 | Census by default | yes |
| R8 | Item-9 F1 requires a customer-discomfort marker ("使客户表现不适") | yes |
| R9 | Fit "?次/?秒" on the 50 κ seed calls | yes |
| R10 | κ per operator | yes |

**From the full-rubric read (10-14, see `docs/rubric/rubric-source-diff.md`):**
- **Source authority:** `specific-rubric-27.yaml` (generated from `simbiclaw/sim config/rubric_items.py`) is abridged. Fix it at the generator, or retire it as a compile input. Any 9003/9011 node whose `human_version` was seeded from it needs re-checking.
- **D-7:** Item 7 has a recording-only pass path ("当录音质检时，只要能确认客服已将提交所需信息全部都确认清楚了，即可视为通过"). Compile it? That moves the scored count 25 → 26 and changes Argus.md's "6–7 deferred". Human ruling needed.
- **D-agent_role:** items 1 (NA), 2 (relaxed standard) and 10 (反问 exemption) depend on 支持客服 vs 热线. Add `agent_role` to the CTI facet (extends G3).
- **D-20-NA:** Item 20's NA column contains a fail-like clause. Probably a source error; confirm.
- **X3:** Item 26 "多次带有情绪的抢话、压话" vs Item 12, and "严重质问、反问" vs Item 10 "轻微反问". Partition by an emotion/severity qualifier (research note §5.7).
- **Item-9 corrections:** R5 is now textually grounded (pass: 音量…不会出现忽高忽低). R6 is confirmed (③ "虽未出现抢话"). ④ is a conjunction (客户语速很慢 ∧ 客服语速快 ∧ 要求慢一点). A new minor signal covers audibility (音量能使客户听清).

**From the items 1–5 compile:**
- **G1:** when the fail clause is empty or narrower than the pass clause, does negating a pass clause count as FAIL? Proposed: numeric or required elements yes; wording elements are minor.
- **G2:** "其他没有明显得1分或0分的情形" means indeterminate → human, not N/A.
- **G3:** where the CTI metadata comes from.
- **G4:** promote the 称谓 lexicon to a shared (Layer 1) lexicon.
- **G5:** never infer gender from voice.
- **X1:** item 4 / item 17 double-penalty on blanks.
- Per-item questions **R1-1 … R5-3** are listed in the YAML.

**From spec v6 (§9.5):** A1–A10 defaults stand unless overridden. **A9** (who writes the review ledger) is Tier C and blocks T4.

## 6. Traps (each cost time once)

- **Issue attachments can't be downloaded** from the cloud container: `github.com/user-attachments` returns 403 to curl, and WebFetch rejects the signed S3 URL as too long. RESOLVED for `rubric_com_hotline.md`: the human uploaded it, and it is now at `docs/rubric/rubric_com_hotline.md`. **Never compile from `specific-rubric-27.yaml` again.** It is abridged.
- **`INTENTS/`** is a symlink to `/Users/prometheus/workspace/INTENTS` and **`docs/PRD`** to `../../papers/PLAN`. Both are absent in the cloud. `PRODUCERS.md` §9 and `indicators.yaml` could not be read directly; their content is known only through `docs/facets/producers-9.1-revision-proposal.md` and `HANDOFF-argus-0922.md`.
- **Branch names.** The human wrote `claude/9301-…`; the real branch is `claude/9031-derivation-pipeline`. `main` is old (2026-08-17) and lacks all 9031-era docs.
- **GitHub access.** The repo was attached with push access mid-session. Before that, `gh api` returned 403. A new session may need `add_repo` again.
- **Commit hooks** require `Plan:` and `Decision:` trailers. This work has no ExecPlan yet, so cite it as a design note or open the T-series plan first.
- **Tables in v5** overflowed on narrow screens; v6 adds a CSS fix. v5 also had an unclosed `<p>`, fixed in v6.

## 7. Next actions (ordered)

1. ~~**Persist.**~~ Done 2026-10-14: branch `claude/argus-roles-operators-1013`. Decide whether to merge into 9031 or open a PR.
2. Get human rulings on **R4 (stereo?)**, **R5**, **G1**, **G3 + agent_role**, **D-7**, and the **source-authority fix**. They unblock the most.
3. Write **spec v6.1**: apply C1/C2/C3, fold the operator IR as a new section, and update fixtures I9/D24 accordingly.
4. Fold C3 and G3 into the **§9.1 facet-contract revision** (`docs/facets/producers-9.1-revision-proposal.md`) for producer review.
5. Continue compiling **items 8–27** from `docs/rubric/rubric_com_hotline.md` in the format of `operators-item-01-05.yaml` rev 2. Items 9 and 12 are analysed in the research note §4–§5 (updated with the full text) and only need transcribing into YAML. Item 7's recording path waits on D-7; item 6 stays deferred.
6. Post the items 1–5 programs to issue #25 in Chinese if the human wants them there.
7. Then author the T-series exec-plan from spec v6 §10's handoff prompt, with dependencies on 9031 M4/M5/M7/M9. Do not amend 9031.
