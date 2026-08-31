# Item-18 pilot — tree delivery record (2026-08-31)

The frozen pilot node (`frozen/item-18.yaml`, B-E refined 2026-08-17, evaluate
CONFIRMED) has been delivered into the external INTENTS tree via the runner's
freeze step (`run_compile.py plan → generate → evaluate → freeze --dest INTENTS`):

- Node: `INTENTS/_rubric/rules_criteria/Problem Resolution/item-18.yaml` —
  byte-identical to `frozen/item-18.yaml`.
- Residue manifest: regenerated (one `within_dimension` row for item-18);
  the pre-existing hand-authored C21 rows were preserved as merged rows
  (`legacy_entry` retained verbatim) rather than clobbered.
- No gate emitted: Problem Resolution binds a single item; `synthesize_hard_fail`
  correctly returns no rule for <2 bound items.
- Epoch: content commit `148e3638df40ad5cdf0a9aa1e15ff33772a61c40` in the
  INTENTS repo, stamped into `EPOCH.yaml`. The node's `intents_sha`
  (`011c94b…`, the baseline pinned at compile time) is unchanged.

## Decisions for this run

1. **Frozen B-E output reused, not re-derived.** The B-E refinement endpoint
   (`deepseek-v4-flash-local` at `http://192.168.3.55:4000`, LAN-only per
   `docs/references/ds4-flash-GUIDE.md`) is unreachable from this environment.
   Per SKILL.md, no fallback to the session model — instead the already-CONFIRMED
   frozen node was adopted verbatim. Fresh `plan`/`generate` runs confirmed zero
   drift in every deterministic field (only `signals`/`facets`/`gap_rationale`
   carry the recorded B-E refinements). `evaluate` re-ran against the real M1
   validator: CONFIRMED.
2. **INTENTS symlink retargeted to `../INTENTS` (relative).** The absolute
   `/Users/prometheus/workspace/INTENTS` target resolves only on the owner's
   machine; the relative form resolves both there and on any checkout where the
   two repos are siblings.

## Required but absent (blocks the full M8 25-item compile)

- `docs/PRD` is a symlink to `../../papers/PLAN`, which is not in the repo —
  so ALL PRD referents are absent, including the M8 gating inputs
  `docs/PRD/eval/rubric_com_hotline.md` (the real 27-item Specific QA Rubric)
  and `docs/PRD/eval/align.md` (the real 25-item map), the companion
  `营销话术.md`, and the governing specs
  (`soft-criteria-authoring-spec-v4.html`, `process-derivation-pipeline-spec-v5.html`).
  Only item 18 exists in-repo (this pilot's converted inputs). M8's "never
  invent item values" rule forbids reconstructing the other 24 items.
- The local B-E model endpoint (LAN-only) — required for refining any NEW item.
- `uv.lock` pins `pypi.tuna.tsinghua.edu.cn`, unreachable through the remote
  proxy — the venv was provisioned from pypi.org for already-vetted deps
  (pydantic, pyyaml) only.
