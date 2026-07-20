# Audio2Tree Design Decisions — Round 2 (2026-07-20)

**Companion to:** `2026-07-19-clio-to-audio2tree-design.md`, `2026-07-19-clio-to-audio2tree-design-decision.md`
**Source:** Structured interview resolving four architecture-changing ambiguities

---

## Decision 1: Phase 2 facet extraction — incremental by default, full reprocess on demand

**Context:** Phase 1 processes all calls with basic facets (Request + programmatic). When Phase 2 runs, criteria-shaped model-based facets could be extracted for all historical calls (expensive: thousands of LLM calls) or only new calls since last run.

**Options considered:**
- A. Full re-extraction every Phase 2 run. Simple, consistent, but cost grows linearly with call corpus
- B. New calls only. Needs tracking of which calls have been processed, but cost is bounded
- C. Incremental by default with manual full-reprocess flag (selected)

**Selected:** C. Phase 2 extracts criteria-shaped facets only for calls that haven't been processed yet (tracked via `pipeline_state/processed_calls.json` — same pattern as the structural-transcription skill's `processed_audio_ids.txt`). A `--reprocess-all` flag allows Curated to manually trigger full re-extraction when Items are significantly updated.

**Architecture impact:** M2 and M7 need a tracking mechanism for processed calls. The `pipeline_state/` directory gains a new file. The `argus audio2tree cluster --phase 2` command gains a `--reprocess-all` flag.

---

## Decision 2: L2 description collision detection with automated freeze

**Context:** L2 `description` fields are semantic anchors for dual-channel routing. If two L2 descriptions are too similar (weak contrastive boundary), cosine matching produces false positives — calls match to both L2s.

**Options considered:**
- A. Curated-only: all descriptions manually reviewed before activation. Highest quality but human bottleneck
- B. Automated detection + human fallback (selected)
- C. Doc2Graph improvement: push the quality responsibility to the producer

**Selected:** B. At embedding time (M1), compute pairwise cosine distance between all L2 descriptions. If any pair has cosine > 0.7 (too similar), mark the newer L2's anchor as `frozen` — excluded from cosine matching. Flag for Curated review. Existing L2 anchors with sufficient distance continue working. The collision threshold (0.7) is configurable.

**Architecture impact:** M1 gains a collision detection sub-step in the embedding module. The routing engine must skip frozen anchors. Pipeline config gains a `collision_threshold` parameter. A `argus audio2tree audit --collisions` command surfaces frozen anchors to Curated.

---

## Decision 3: Deviation L2 centroids participate in matching like any other centroid

**Context:** A deviation L2 has `status: pending_review` and 100+ calls. On the next audio2tree run, new calls arrive. How does the routing engine treat the deviation L2's centroid?

**Options considered:**
- A. Deviation L2s are invisible to the routing engine until Curated confirms them. New calls re-run full matching and may land in different deviation clusters each run. Rejected: unstable — same call pattern produces different clusters on different runs
- B. Deviation L2 centroids participate in matching like any other centroid (selected)
- C. Semi-frozen: centroid participates but no new L3 sub-clusters generated until confirmed

**Selected:** B. Once a deviation L2 exists, its centroid is part of the routing pool. New calls with cosine ≥ 0.65 are assigned to it. request_count grows naturally. The only difference from a matched L2 is the `status: pending_review` flag and the absence of `top_down`. This is consistent with the stability protocol — existing centroids always participate.

**Architecture impact:** No special routing logic for deviation L2s. The routing engine treats all centroids equally. The distinction is in manifest output, not in routing behavior.

---

## Decision 4: Calibration runs as a git hook on INTENTS commits

**Context:** Calibration (0017) compares `top_down` and `bottom_up` presence in each `intent_manifest.json` and sets `calibration_status` (calibrated / needs_manual / needs_calls / conflict). This needs to stay current as the tree changes.

**Options considered:**
- A. Git hook on INTENTS commits (selected)
- B. Independent `argus calibrate` CLI command, manually triggered
- C. Automatically after each `audio2tree cluster` run

**Selected:** A. A post-commit hook in `.claude/hooks/` runs calibration whenever the INTENTS tree advances. This is the most timely option and requires no manual triggering. The hook is scoped to commits that touch `intent_manifest.json` files.

**Architecture impact:** Calibration is not part of the audio2tree pipeline — it's infrastructure triggered by git events. audio2tree writes bottom_up → commits → hook fires → calibration updates calibration_status → amends the commit (or creates a follow-up commit). This creates a potential double-commit pattern that the hook must handle gracefully.

---

## Decision 5: DKB/Cookbook/Errors routing via path convention

**Context:** `knowledge_accuracy` and other model-based facets need to compare agent statements against curated expertise files (DKB, Cookbook, Errors). How does audio2tree Consumer locate the relevant expertise file for a given call?

**Options considered:**
- A. Path convention: look at L2 directory first, fallback to L1, resolve parent/extends/overrides chain (selected)
- B. Manifest references: L2 manifest contains explicit dkb_refs/cookbook_refs/errors_refs fields
- C. Defer: return checkable=false until DKB infrastructure matures

**Selected:** A. For a call assigned to L2 `证书延期` under L1 `法人数字证书业务`:
  1. Check `INTENTS/法人数字证书业务/证书维护/dkb.certificate-maintenance.yaml` (L2 directory)
  2. If not found, check `INTENTS/法人数字证书业务/dkb.service-hours.yaml` etc. (L1 directory)
  3. Resolve parent/extends/overrides chain per expertise-decision-log §6 inheritance rules
  Same pattern for Cookbook and Errors.

**Architecture impact:** M2's knowledge_accuracy facet extractor needs a DKB resolver that walks the path convention. The resolver is a pure function in `core/` (no model calls). If no DKB file is found at any level, the facet returns `checkable: false` for that call.

---

## Changelog

| Date | Change | Source |
|------|--------|--------|
| 2026-07-20 | Round 2 decisions: Phase 2 incremental extraction, L2 collision detection, deviation centroid participation, calibration git hook, DKB path convention | Structured interview session |
