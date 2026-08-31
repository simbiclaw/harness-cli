# 9003 M8 — worked compilation over the real 27-item rubric (2026-08-31)

The M8 gating inputs arrived from the human (attached in-session) and the full
worked compilation ran end-to-end, including B-E refinement. Executes the
§3.6b contract recorded in
`docs/exec-plans/completed/9003-implement-soft-criteria-compiler.md` (M8,
27 = 25 operational + 2 deferred).

## Inputs

- `sources/rubric_com_hotline.md` — the real Specific QA Rubric, verbatim as
  received (27 `1/0/NA` items).
- `sources/align-full.md` — the real human align doc, verbatim as received.
- `companions/营销话术.md` — 18 standard marketing scripts (item 21's truth
  source), verbatim as received.
- `companions/营销触发.md` — item 20's trigger-keyword library (T001–T014),
  **derived in-session (human-directed)** from 营销话术.md + item 20's rubric
  text only; every trigger traces to a script or the rubric. S1-pinned via
  item 20's `companion_docs`.
- `specific-rubric.yaml` — compiler-format conversion: standards copied
  verbatim; `named_phrases`/`numeric_thresholds` extracted only where the
  rubric text carries the exact value (B-D); item 18 byte-identical to the
  pilot entry; dependencies 20→21, 22→26 per patch-2 S3.
- `align.md` — runner-format projection of align-full.md (cross-axis items on
  their primary axis: 9→Procedural Accuracy, 15→Problem Resolution,
  26→Empathy & Tone; items 6/7 → no dimension).
- `generic-skill.yaml` — the real 4-dimension template (same as pilot).

## Run

`run_compile.py plan → generate ×27 → evaluate` (CONFIRMED), then **B-E
refinement** (`apply_be.py` + `b-e-signals.yaml`), `evaluate` again
(CONFIRMED), refined pilot item-18 restored, `freeze --dest INTENTS`.
Records in `run-records/` (24 `b-e-refine` decision entries).

Result, delivered to the external INTENTS tree:

- **25 nodes** under `_rubric/rules_criteria/{dimension}/item-N.yaml`
  (Procedural Accuracy 7, Empathy & Tone 8, Problem Resolution 8,
  Proactive Value 2), all validator-clean — **73 FAIL + 27 EXCELLENCE
  signals, 74 gate-checkable**; every clause of every pass/fail standard is
  either a checkable signal or an explicitly quarantined `model_only` signal
  with the reason in its `gate_can_verify`.
- **4 synthesized hard-fail gates** under `_rubric/gates/{dimension}.yaml`.
- **Residue manifest**: 2 `dimension_coverage_gap` rows (items 6/7,
  `defer_until_source_connected`) + 16 `within_dimension` rows (one per item
  with genuine model-quarantined residue) + the legacy C21 row preserved.
- `data_dependency: {connected: false, defer_until_source_connected}`
  declared on items 3, 19, 25 (客服系统/知识库/资费表 not connected — AUTH-8).
- `auto_final_allowed: false` on every node — correct until the first
  calibration manifest injection (AUTH-9/M7).

## Decisions

1. **B-E executed by the SESSION model (human steering, 2026-08-31:
   "instead of LAN model, employ session model").** This overrides SKILL.md's
   no-session-model rule by explicit human direction. The authored signals
   live in `b-e-signals.yaml` (the record), applied by `apply_be.py`: ONE
   observable signal per standard clause, clause-traced (`decomposed_from`),
   AUTH-1-clean descriptions, Q1/Q2 `gate_checkable_test` per signal;
   deterministic lexical signals (N-S01) kept; fallbacks replaced; facets and
   residue regenerated via the real M2/M3 core (`assign_facets`,
   `declare_residue`) — unlike the pilot, no stale facets.
2. **营销触发.md derived, not received** (human steering: "you can spot item
   20's trigger-keyword library from 营销话术.md"). T001–T014 each cite their
   source script or the item-20 rubric clause. Implicit triggers (scenario
   implies need, no keyword) remain declared residue (P33).
3. **Signal-split adjudication**: item 2's deterministic ordered signal
   (2-S03) was a mid-word mis-split of the heuristic and was replaced by the
   authored 2-E1 (recorded in `b-e-signals.yaml` `extra_remove` and the
   decision log).
4. **Values extraction stays conservative** — only phrases/numbers literally
   present in the rubric text (enforced by
   `tests/test_worked_compilation.py::test_no_invented_values`).
5. **`tests/test_worked_compilation.py` landed** (M8's named acceptance
   tests, 4/4 pass): all-items-compiled (25+2 contract), no-invented-values,
   hard-fail-gates-synthesized, manifest-covers-lossy. The M8 checkbox in the
   archived 9003 plan is left to the human/verifier flow to flip.

## Still absent (not DIY-able)

- **First calibration manifest** (M7 channel). Deliberately NOT fabricated:
  its fragments are human-annotated scores from the Error Case Library /
  Best Practice Cookbook (both still empty); inventing them would mint
  auto-final rights from fabricated ground truth (AUTH-9's exact failure
  mode). Until it arrives, every node correctly withholds auto-final.
- **External system connections** for items 6/7 (ticketing/escalation
  lookups) and the declared `data_dependency` sources of items 3/19/25
  (客服系统 query records, product KB, 资费表).

## Environment note

`tests/test_compiler_pipeline.py::TestBFixRound::test_b2_garbage_inputs_clean_exit`
fails only in root-run containers (a 0o555 out-dir is still writable as
root, so the runner succeeds where the test expects exit 2) — pre-existing
environment sensitivity, not a compiler change.
