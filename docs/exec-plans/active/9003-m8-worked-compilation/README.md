# 9003 M8 — worked compilation over the real 27-item rubric (2026-08-31)

The M8 gating inputs arrived from the human (attached in-session) and the full
worked compilation ran end-to-end. Executes the §3.6b contract recorded in
`docs/exec-plans/completed/9003-implement-soft-criteria-compiler.md` (M8,
27 = 25 operational + 2 deferred).

## Inputs

- `sources/rubric_com_hotline.md` — the real Specific QA Rubric, verbatim as
  received (27 `1/0/NA` items).
- `sources/align-full.md` — the real human align doc, verbatim as received.
- `companions/营销话术.md` — 18 standard marketing scripts (item 21's truth
  source), verbatim as received.
- `specific-rubric.yaml` — compiler-format conversion: standards copied
  verbatim; `named_phrases`/`numeric_thresholds` extracted only where the
  rubric text carries the exact value (B-D); item 18 byte-identical to the
  pilot entry; dependencies 20→21, 22→26 per patch-2 S3.
- `align.md` — runner-format projection of align-full.md (cross-axis items on
  their primary axis: 9→Procedural Accuracy, 15→Problem Resolution,
  26→Empathy & Tone; items 6/7 → no dimension).
- `generic-skill.yaml` — the real 4-dimension template (same as pilot).

## Run

`run_compile.py loop` (plan → generate ×27 → evaluate → freeze), then the
refined pilot item-18 node restored, `evaluate` re-run (CONFIRMED), then
`freeze --dest INTENTS`. Records in `run-records/`.

Result, delivered to the external INTENTS tree:

- **25 nodes** under `_rubric/rules_criteria/{dimension}/item-N.yaml`
  (Procedural Accuracy 7, Empathy & Tone 8, Problem Resolution 8,
  Proactive Value 2), every one pinned at epoch `148e363` and validator-clean.
- **4 synthesized hard-fail gates** under `_rubric/gates/{dimension}.yaml`.
- **Residue manifest**: 2 `dimension_coverage_gap` rows (items 6/7,
  `defer_until_source_connected`, with `data_dependency`) + 9
  `within_dimension` rows (items 9, 11, 15, 16, 18, 20, 23, 24, 25) + the
  legacy C21 row preserved.
- `auto_final_allowed: false` on every node — correct until the first
  calibration manifest injection (AUTH-9/M7).
- item-18 unchanged in the tree (the refreeze reproduced the refined pilot
  node byte-identically).

## Decisions

1. **B-E refinement deferred for the 24 new items.** The local B-E endpoint
   (`deepseek-v4-flash-local`, LAN-only) is unreachable from this
   environment and SKILL.md forbids a session-model fallback. The 24 new
   nodes therefore carry the deterministic core's signals, with unmatched
   standard clauses quarantined as `model_based` fallbacks
   (`checkable: false`) — valid per the validator, lossy rows declared in the
   manifest. When the endpoint is reachable, run `befine.py` per item and
   re-freeze; item 18 shows the target shape.
2. **Values extraction is conservative.** Only phrases/numbers literally
   present in the rubric text were extracted (e.g. 30s/15s silence caps for
   item 17, >2 filler-word cap for item 8, 88234732 for item 27). Items whose
   standards carry no concrete value (3, 9, 11, 13, 15, 16, 21, 23, 24, 25,
   26) got empty values and rely on fallback/model signals until B-E runs.
3. **营销触发.md (item 20's trigger library, named in align-full.md) was NOT
   provided** — item 20 compiled from its rubric text values only; the P31
   trigger-keyword set remains residue.
4. **`tests/test_worked_compilation.py` (M8's named acceptance test) does not
   exist in the repo** — the M8 checkbox is NOT flipped. The plan is archived
   as completed with M8 open; this run is the follow-on work its
   retrospective anticipated. Landing that test remains open work.

## Still absent

- 营销触发.md (item 20 trigger set).
- Local B-E endpoint (for refining the 24 new items).
- First calibration manifest (M7 channel — grants auto-final where covered).
- `tests/test_worked_compilation.py`.
