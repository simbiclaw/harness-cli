# 9004 Execution Mistakes — Retrospective

**Date:** 2026-07-27
**Status:** draft
**Source:** Git history on `feat/audio2tree-skill` (commits `b1ed96b` through `428054b`), `docs/superpowers/specs/9004-execution-prompt.md`, `docs/exec-plans/active/9004-skill-prototype-cli-production.md`, and the 2026-07-20 execution run.

---

## 1. Context

ExecPlan 9004 (audio2tree: Skill Prototype → CLI Production) Phase A execution ran on 2026-07-20. The plan has four milestones for Phase A (M0–M4). M0 shipped cleanly. M1–M4 were attempted in a single session via four sequential sub-agents and all initially marked done. Within the same day, M4 was reverted when it became clear the acceptance gate had never been met. Four additional fix commits followed over the next hour, addressing bugs discovered during the revert review.

At the time of this retrospective (2026-07-27), M4 remains unchecked. Three known code gaps are documented but unfixed.

This retrospective catalogs every mistake, the root cause pattern, and what the harness should have caught but didn't.

---

## 2. Mistake Inventory

### 2.1 Worktree Isolation for Sequential Agents

**Severity:** Blocker — wasted ~50% of execution effort.
**Commits:** `813f2e7`, `0542114`

**What happened:** The orchestrator launched four sequential pipeline agents (M1→M2→M3→M4) each with `isolation: 'worktree'`. Each worktree is an independent checkout from the base branch — M2 could not see M1's commits, M3 could not see M2's, and M4 could not see any of them.

**Consequences:**
- Each agent independently re-created shared files (SKILL.md, pipeline.py) from scratch
- API mismatches arose: M3 wrote `route_batch()` while M2's pipeline called the non-existent `batch_route()`
- The orchestrator had to manually copy files out of four separate worktrees, reconcile independently-written versions, fix import mismatches, and re-run all verification
- Total work approximately doubled relative to sequential execution on a single branch

**Root cause:** `isolation: 'worktree'` was applied as a blanket default for sub-agents without considering whether the agents were independent (suitable for worktrees) or sequential (categorically incompatible with worktrees).

**What should have caught it:** The execution prompt's "Execution Notes" already warns against this — but that warning was written *after* the mistake occurred. Before the run, no check existed. The harness needs a rule: *sequential agents share a branch; only parallel agents that don't depend on each other's output use worktrees*.

---

### 2.2 False E2E Pass — M4 Checked Without Running S0 or S1

**Severity:** Blocker — invalidated the milestone gate.
**Commits:** `92ae7b1`, `428054b`

**What happened:** M4 was marked `[x]` (complete) based on:
- S2–S4 running on hardcoded strings, not real ASR output from WAV files
- Claude never invoked for Request extraction (S1) or cluster naming (S3)
- No `.structural.json` file ever produced from a real WAV file (S0 intermediate)
- 46 unit tests passing, treated as "the pipeline works end-to-end"

**Correction:** The M4 checkbox was reverted to `[ ]` in commit `92ae7b1` with the note: *"reverted 2026-07-20 — S0/S1 never executed, Claude never invoked."* The acceptance gate was subsequently specified with an 11-field minimum output table and a "NOT sufficient" checklist.

**Root cause:** Unit test coverage was conflated with end-to-end validation. The acceptance gate was underspecified at plan-creation time — it said "run /audio2tree cluster on 5 real WAV files" but didn't specify minimum outputs or what constitutes an insufficient run.

**What should have caught it:** The verifier skill should have blocked the checkbox flip. The skill's contract is: *on `[ ]` → `[x]`, re-run the acceptance test in a clean checkout.* This never happened. Either the verifier wasn't invoked, or it was invoked but the acceptance test was too weak to fail on a hardcoded-string run.

---

### 2.3 Scripts in Wrong Directory

**Severity:** Medium — 13 files, 30+ import paths to fix.
**Commit:** `df85cc1`

**What happened:** Pipeline scripts (`audio2tree_pipeline.py`, `cluster.py`, `routing.py`, `request_extractor.py`, `manifest_writer.py`) were placed in a project-level `scripts/` directory. Per the Claude Code skills specification, a skill's scripts belong in `.claude/skills/<name>/scripts/`. All 8 test files, the SKILL.md, and the pipeline itself had hardcoded paths pointing to the wrong location.

**Root cause:** The file layout was chosen at implementation time without consulting the skills spec. The spec exists and is unambiguous — the issue was not checking it.

**What should have caught it:** A structural test or hook that verifies skill scripts live at `.claude/skills/<name>/scripts/` and not elsewhere. This doesn't exist yet.

---

### 2.4 S3 Routing is a No-Op

**Severity:** Blocker — the routing stage produces no signal.
**Commits:** Present from initial M3/M4 implementation; documented in `428054b`.

**What happened:** `batch_route()` in `routing.py` walks the INTENTS tree directory structure but never calls Ollama for embeddings, never computes cosine similarity, and returns every request as `channel: "deviation"`. The real routing functions (`route_request`, `route_batch`) exist in the same file and are tested (16 tests pass in `test_m3_routing.py`), but the pipeline orchestrator calls `batch_route()` instead of them.

**Root cause:** `batch_route()` was written as a quick stub to unblock the pipeline integration (Mistake 6 below), then never replaced with the real implementation. The stub was adequate for the pipeline's structural test ("does the pipeline run without crashing") but not for the routing stage's functional purpose ("does the pipeline actually route requests").

**What should have caught it:** A test that asserts the deviation rate is < 100% on a fixture where some requests should match. The existing routing tests (`test_m3_routing.py`) test `route_request` and `route_batch` directly — they pass — but no test exercises `batch_route()` with known-match fixtures.

---

### 2.5 Manifests Written to Wrong L2 Subdirectories

**Severity:** Medium — output landed in wrong directory; two distinct bugs.
**Commit:** `61c9edf`

**Bug A:** `populate_manifests()` wrote `intent_manifest.json` to the L1 directory (e.g., `INTENTS/法人数字证书业务/`) instead of the L2 subdirectory when `l2_title` was an empty string. `os.path.join("L1_dir", "")` silently consumed the empty component.

**Bug B:** `batch_route()` returned routing results with `null`/empty `intent_id` for deviation-channel clusters. The pipeline didn't fill fallback values, so the manifest writer created malformed directory names.

**Fix:** Added fallback `intent_id` generation (`dev-cluster-{i}`) and fallback title/description for deviation clusters in both the routing result processing and the manifest writer.

**Root cause:** Defensive coding was absent at the pipeline integration layer. Empty-string and null-edge cases weren't tested because `batch_route()` always returned deviation (Mistake 4), which meant these paths were exercised with garbage data.

---

### 2.6 M4 Pipeline Not Integrated with Routing API

**Severity:** Medium — 245-line insertion required to connect the stages.
**Commit:** `b1ed96b`

**What happened:** `run_s1_s2_s3_s4()` in the pipeline orchestrator had no `batch_route` or `calculate_deviation_rate` integration. The entire S3 routing block was missing — no import of the routing module, no call to any routing function, no code path to pass routing results to the manifest writer.

**Root cause:** M3 and M4 were implemented by different sub-agents in isolation (compounded by Mistake 1). M3 produced a working `routing.py` module. M4 wrote the pipeline orchestrator. Neither agent tested the handoff between them because each worked in a separate worktree.

---

## 3. Known Code Gaps (Unfixed)

Three gaps remain in the codebase as of the latest commit (`428054b`):

| Gap | Impact | Location |
|:---|:---|:---|
| Pipeline cannot read `.structural.json` | S0→S1 handoff is broken. Only `.txt` demo files and fixture JSON are supported. | `audio2tree_pipeline.py` — needs `load_structural_json(dir)` |
| `batch_route()` is still a no-op | S3 routing produces no signal. Every request is deviation. | `routing.py` — needs to call `route_batch()` with real Ollama embeddings |
| SKILL.md references nonexistent CLI args | Docs mismatch: `--output-file`, `--l2`, `--k`, `--run-s2` don't exist in argparse | `SKILL.md` — either add flags or remove from docs |

---

## 4. Harness Failures

The exec plan harness has five conventions designed to catch mistakes like these. Here is what each did during 9004:

| Convention | Expected Behavior | What Actually Happened |
|:---|:---|:---|
| **Verifier skill** | Blocks checkbox flip unless acceptance test passes | M4 was flipped to `[x]` without the test running. Verifier either wasn't invoked or the test was too weak to fail. |
| **Surprises & Discoveries** | Captures unexpected events during execution | Section remains empty. All four mistakes happened but none were recorded here. |
| **Decision Log** | Records consequential reversals and corrections | No entry for the M4 reversion or any bug fix rationale. |
| **Acceptance Test spec** | Defines what "done" means for each milestone | M4's gate was underspecified at plan creation ("run the skill on 5 WAVs" — no minimum outputs, no "not sufficient" checklist). Clarified only *after* the false pass. |
| **TDD — test-first per milestone** | Test written and fails (RED) before implementation | M1–M3 tests exist and pass, but they test individual functions, not the integrated pipeline. The false M4 pass happened because unit test coverage was mistaken for integration coverage. |

Two of these are process failures (verifier not invoked, Surprises left empty). Two are specification failures (acceptance gate underspecified, tests too narrow). One is a documentation failure (Decision Log omission).

---

## 5. Root Cause Pattern

The six mistakes share a common pattern: **assuming rather than verifying.**

| Mistake | Assumption | What Verification Would Have Shown |
|:---|:---|:---|
| Worktree isolation | "Isolation is safe for all sub-agent tasks" | Sequential agents can't see each other's output |
| False E2E pass | "46 tests passing = pipeline works" | S0 never ran, Claude never invoked |
| Wrong directory | "`scripts/` at project root is fine" | Skills spec requires `.claude/skills/<name>/scripts/` |
| No-op routing | "`batch_route()` calls Ollama because the function exists" | It walks the tree and returns deviation for everything |
| Wrong L2 subdirs | "`os.path.join` handles empty strings" | It silently consumes them |
| Missing routing integration | "The other sub-agent will wire this up" | Neither agent owned the integration point |

This pattern maps directly to the "verification floor" principle in the conventions: *every milestone has a runnable Acceptance Test exercising an externally observable property.* The tests we had exercised internal properties (functions, classes, schemas). The externally observable property — "real WAV in, real manifests out, Claude in the loop" — was never tested before the checkbox was flipped.

---

## 6. What to Do Differently

### 6.1 Immediate — for 9004 resumption

1. **Fix the three code gaps** before attempting M4 again. The S0→S1 handoff is broken; the S3 routing is a no-op; the docs don't match the code. Fixing these is prerequisite to meeting the acceptance gate.
2. **Run the full M4 acceptance test FIRST** — the 11-field output spec in `9004-execution-prompt.md` — and confirm it FAILS (RED) before writing any code.
3. **Sequential agents, no worktrees.** `const m1 = await agent(...); const m2 = await agent(...)` — each commits before returning.

### 6.2 Process — for future ExecPlans

1. **Acceptance gates must be specified as concrete, falsifiable properties at plan-creation time.** "Run the skill on 5 WAVs" is not falsifiable. "Five `.structural.json` files exist on disk, each manifest has 11 non-empty required fields, deviation rate is printed on stdout" — is.
2. **The Verifier must be invoked for every checkbox flip.** The `[ ]` → `[x]` transition is the exact moment when "assume it works" meets "prove it works." If the verifier can't run the acceptance test (because S0 needs audio-server, Ollama, etc.), that's a sign the test isn't automated enough — invest there.
3. **Integration tests must exist before integration is claimed complete.** Unit tests for `route_batch()` passing does not mean the pipeline calls `route_batch()`. Each stage-to-stage handoff needs at least one test that exercises the actual orchestration path.
4. **Surprises & Discoveries must be written during execution, not after.** The section exists for a reason. Adding an entry takes 30 seconds. Adding four entries after the fact takes a retrospective.

### 6.3 Harness — candidates for promotion

Per the promotion rule (documentation → structural test → hook → CI gate → architecture), these are candidates:

| Issue | Current State | Promotion Target |
|:---|:---|:---|
| Worktree isolation for sequential agents | Documented in execution prompt | Structural test: detect `isolation: 'worktree'` on pipeline agents with sequential dependencies |
| Acceptance gate underspecification | Documented in this retrospective | Convention: acceptance tests must assert on observable file artifacts, not just exit codes |
| Surprises section left empty | Convention exists | Hook: warn if Surprises section is empty and >1 milestones are checked |
| Verifier not invoked on checkbox flip | Convention exists | Hook: block `[ ]` → `[x]` transition unless verifier output is present in Decision Log |

---

## 7. Cross-References

- `docs/exec-plans/active/9004-skill-prototype-cli-production.md` — the active plan
- `docs/superpowers/specs/9004-execution-prompt.md` — execution prompt with lessons learned
- `docs/conventions/verification-floor.md` — what "done" means
- `docs/conventions/ask-threshold.md` — when to stop and ask vs. proceed
- `docs/conventions/i-dont-know-protocol.md` — how to handle uncertainty
- `docs/PLANS.md` — the rubric every ExecPlan follows
- `docs/retrospectives/audio2tree-pipeline.md` — earlier design retrospective for the same pipeline
- `.claude/skills/verifier/` — the verifier skill that should have caught Mistake 2

---

## Changelog

| Date | Change | Source |
|------|--------|--------|
| 2026-07-27 | Initial draft — 6 mistakes, 3 gaps, 4 harness failures, root cause analysis | Git history + execution prompt + exec plan review |
