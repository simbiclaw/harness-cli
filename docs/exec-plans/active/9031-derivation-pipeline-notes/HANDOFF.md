# HANDOFF — 9031 Argus derivation pipeline (as of 2026-09-22)

For the next session. Read this file end-to-end; it is self-contained. The plan itself is
`docs/exec-plans/active/9031-argus-derivation-pipeline.md` (read its Decision Log — every
ruling below is recorded there or in the linked notes).

## Where we are

The project ruled "no simbi at all" (2026-09-16), archived the 9021 porting family with
full records, and replaced it with **9031**: Argus = the pure derivation pipeline
(S1 read → S2 propose → S3 ground → S4 score/adjust → S5 route; report record written back
to the INTENTS tree). Work runs in the worktree
`/Users/prometheus/workspace/harness-cli/.worktrees/9031-derivation-pipeline`
(branch `claude/9031-derivation-pipeline`). The old `9021-relayer` worktree is **kept**
deliberately (historical site, one abandoned M7 repair in its working tree — do not reuse).

## Milestone status

| M | state | notes |
|---|---|---|
| M1 facet contract | **staged, not flipped** | `docs/facets/producers-9.1-revision-proposal.md` + `history-entry-contract.md`; acceptance test `tests/test_facet_contract.py` green. Awaits producer review + soft-compiler's §9.1 folding. |
| M2 retire the port | **flipped** (63f5a5b, corrected 40492d1) | B round 1 REJECTED → repaired (5b43097) → CONFIRMED → follow-ups (8ada20c) → final confirmation passed. Ledger: `9031-derivation-pipeline-notes/M2.md`. |
| M3 read surface | **committed (e057a8f), awaits ONE B round** | `src/argus/io/reader.py`; 7 acceptance tests on the real corpus. Key discovery: `calls/` is git-ignored by design → knowledge reads via `git show <epoch>:`, facts from the archive. Notes: `...9031-derivation-pipeline-notes/M3.md`. |
| M4 turn-level spans | not started | Bring the mixed-segment caveat (below) into its notes. |
| M5–M10 | not started | M5 S2 extractor + prompts; M7 report record (two-tier storage, gated on the ownership re-sync); M9 first real end-to-end; M10 agreement instrument. |

## The registry (Argus owns it since 2026-09-20)

`INTENTS/_rubric/evidence/acoustic/indicators.yaml` — **v1.4.2**, tree epoch `70926d9`.
Sections: `indicators:` (13 acoustic), `predicates:` (18 rubric-extracted: 6 extracted /
11 provisional / 1 ruled), `calibration_inputs:` (2), `extraction_notes:`. Ownership
ledger updated (PRODUCERS.md §1/§2 + `_meta/ownership.yaml`).
Open calibration items: the **global pitch band is contraindicated** (per-item baseline:
direction flips between items 11 and 12) — re-scope rides 9011 M4; several predicates have
n=1 — they need more annotated samples before thresholds mean anything.

## History shelf — ready for curated, transfer note not yet written

audio2tree produced **24 entries** (18 errors + 6 cookbook) in its worktree
`9008-audio2tree-rebuild/docs/exec-plans/active/9008-notes/history-entries-draft/`
(entry files + `library-index.json` + `DELIVERY.md`). I independently verified: 88 quote
spans resolve exactly, instrument ids all in the registry, anchors bound to real tree nodes
(intents_sha = `b2287d10…`), NA sample moved out to `na-material/`. **Next action: write the
transfer note to the human/curated** — include: my verification method + result; rulings
needed (confirm anchors; define the upgrade path for the 16 domain-level anchors; item-6's
0-分 typo in the deferred appendix).

## Rulings of record — do not re-litigate

No simbi (all of it; the NLI instrument assumed empty without measurement) · D15 narrowed to
the referent rule; report records are Argus's one write path, two-tier storage (daily
summary JSONL + pointer in-tree, full record content-addressed cold, annual Parquet) ·
S2 = LAN 27b behind `local_proposer.py`'s LogitModel protocol · κ seeds = Chain B's 50
calls, labeled blind from transcript + rubric (text-side first; audio only affects
acoustic-item label quality) · rubric stays 25 items (6/7 deferred) · NA samples are not
precedents (kinds stay errors|cookbook) · the matcher is two-stage: deterministic
`applicable_items` pre-filter, then model judgment on description + key_features (W_C=0.4,
clears `finding_thin` only) · evidence rule: `instruments[]` cites only readings that
actually fired · verification economics: **one B round per milestone; repair + re-confirm
only for REJECTION-GRADE findings; MINORs are fix-and-record** (human ruling 2026-09-20).

## Pending on the human

1. **OpenRouter top-up** — blocks B-verification flips only, not building (the session model
   works for subagents; the earlier "402 blocks the queue" conclusion was retracted).
2. **Production audio infrastructure** — where production call audio lives (Linux audio
   server); the κ batch's `audio.path` points at a deleted `/tmp` dir.
3. item-6's rubric typo (deferred; harmless until items 6/7 compile).

## Cross-session ecosystem

- **audio2tree-0921** (producer): transcription/diarization/refinement; delivered the 24
  entries and both calibration baselines; asked to propose the "merged-cluster attribution
  is untrustworthy" rule for left-shift (two independent instances — its M13 pipeline
  should force `unattributed` on merged/mixed segments rather than infer).
- **soft-compiler-76** (compiler line): plan 9011 in progress (M2 repair round carries
  20-S01 polarity, 21-S01 evaluative-phrase, item-4/17 duration-threshold recovery);
  delivers the §9.1 quantification content M1 folds.
- **sira-proxy**: no session; its contract is `PRODUCERS.md` §9.3 + ADR-0005.

## Traps (each cost real time once)

- **The shared venv's editable install points at the MAIN checkout.** Bare
  `python -c "import argus"`, scripts and hooks resolve to the wrong tree; pytest is safe
  (`tests/conftest.py` puts the worktree's `src` first, subprocesses inherit). Any direct
  run must set `PYTHONPATH=src`.
- **`git worktree prune` before running `test_pev_worktree.py`** — a stale registration
  ("missing but already registered") makes the suite fail non-deterministically.
- Never `cd` out of the worktree root in Bash (kills every tool call via the hook path).
- Heredoc/bash: backticks in commit messages execute; `**` at a YAML value start parses as
  an alias; always `PYTHONDONTWRITEBYTECODE=1` for scans.
- The plan's own notes dir accumulates per-milestone records — write M4's there.

## Immediate next actions (ordered)

1. One B round for **M3** (per the cost ruling), then flip.
2. Write the **transfer note** for the 24 history entries.
3. **M4** (turn-level spans; fold in the mixed-segment and venue-vs-quote caveats).
4. M2 follow-ups logged but not done: anti-vacuity floors on the three live-tree scans; the
   commit hook is not firing (harness-level observation).
