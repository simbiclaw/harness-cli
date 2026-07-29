# 9006 — PEV Tmux Convergence: Unified Arbiter Architecture

## 1. Purpose

9005 evolved the PEV loop from documentation to structural enforcement. But it left three PEV implementations coexisting (`pev_orchestrator.js`, `pev_repair.py`, `pev_tmux_adversarial.sh`) with overlapping repair logic and no convergence plan. The promotion mechanism (doc → test → hook → CI → architecture) remains manual. This plan resolves both: formalize the tmux arbiter architecture as the single PEV implementation, deprecate the JS and Python variants, and extend the arbiter model to govern rule promotion.

`Source: docs/experiments/interview-harness-gaps.html (2026-07-29) · docs/PRD/PMCA.txt · docs/exec-plans/completed/9005-pev-loop-evolution.md`

## 2. Big Picture

Two architectural shifts, eight milestones:

**Shift 1 — Converge to tmux.** `pev_orchestrator.js` (Dynamic Workflow pipeline) and `pev_repair.py` (Python repair library) are replaced by `pev_tmux_adversarial.sh` (tmux IPC with three Claude sessions). The arbiter session replaces all hardcoded repair classification — failure diagnosis, action routing, and notes writing are now Claude reasoning, not if/else switches. B writes verdicts directly into implementation notes (single source of truth). The arbiter has full autonomy: flip checkboxes, commit verdicts, send repair instructions to A, re-trigger verification. Semantic failures pause for human; everything else runs autonomously. Checkpoint recovery via `.pev-signals/state.json` survives tmux session crashes.

**Shift 2 — Arbiter-managed promotion.** The manual promotion rule ("violated twice → open ExecPlan") is replaced by a violation tracker + promotion arbiter. The tracker detects same-rule violations across ExecPlans. The promotion arbiter (fourth tmux window in the same session, or a standalone session) reads violation records, decides whether to promote and to which level, and either auto-executes (mechanical promotions) or drafts an ExecPlan for human approval (architectural promotions).

**PMCA nesting.** PEV and PMCA are the same cybernetic pattern at different scales: a milestone's Plan→Execute→Verify is a micro PMCA cycle; the full Argus build process (sensors write INTENTS → cognition evaluates → action routes) is the macro PMCA, driven by the PEV orchestrator. This plan doesn't change that relationship — it formalizes the orchestration layer that had been split across three files.

**Deliberately out of scope:**
- Changes to PMCA layers themselves (Argus evaluator, INTENTS tree, sensors)
- Container/VM sandboxing (git worktree only, per 9005 decision)
- Multi-Plan continuous execution (single Plan per tmux session; daemon mode is future work)

## 3. Milestones

### M0 — Signal directory and state schema

Formalize `.pev-signals/` as the coordination directory. Define the state file schema for checkpoint recovery. Create the directory structure and a structural test that validates state file format.

```
.pev-signals/
├── state.json          # {plan_id, phase, current_milestone, pending_verdicts, last_checkpoint_at}
├── violations/         # {rule_id}.json — violation records for promotion tracker
└── .gitkeep
```

`state.json` schema:
```json
{
  "plan_id": "9006-pev-tmux-convergence",
  "phase": "verify",
  "current_milestone": 3,
  "milestones": {
    "M1": "confirmed",
    "M2": "confirmed",
    "M3": "pending_verdict"
  },
  "last_checkpoint_at": "2026-07-29T16:00:00Z",
  "arbiter_pid": null,
  "tmux_session": "pev-adversarial"
}
```

`Acceptance Test:` `.claude/tests/test_pev_signals.py::test_state_schema_validates` — round-trip parse of state.json against schema. `.claude/tests/test_pev_signals.py::test_signal_dir_exists` — .pev-signals/ present with .gitkeep.

**File Scope:**
- `Allowed Reads:` .pev-signals/**, docs/conventions/pev-loop.md
- `Allowed Writes:` .pev-signals/.gitkeep, .pev-signals/state.json (fixture), .claude/tests/test_pev_signals.py
- `Requires:` none
- `Risk Tier:` B

### M1 — Tmux script formalization

Promote `pev_tmux_adversarial.sh` from experimental (untracked) to production. Add `--resume` flag that reads `state.json` and rebuilds the tmux session from the last checkpoint. Add `--plan` and `--milestones` as required arguments. Add signal file cleanup on successful completion. Mark `pev_orchestrator.js` and `pev_repair.py` as deprecated with a comment header pointing to the tmux script.

`Acceptance Test:` `.claude/tests/test_pev_tmux.py::test_script_accepts_required_args` — `--plan` and `--milestones` parse correctly. `.claude/tests/test_pev_tmux.py::test_resume_reads_state` — `--resume` flag loads state.json. `.claude/tests/test_pev_tmux.py::test_deprecated_markers` — JS and Python files contain deprecation notice referencing this plan.

**File Scope:**
- `Allowed Reads:` .claude/scripts/pev_orchestrator.js, .claude/scripts/pev_repair.py, .pev-signals/state.json
- `Allowed Writes:` .claude/scripts/pev_tmux_adversarial.sh, .claude/scripts/pev_orchestrator.js (deprecation comment), .claude/scripts/pev_repair.py (deprecation comment), .claude/tests/test_pev_tmux.py
- `Requires:` M0
- `Risk Tier:` B

### M2 — Verdict/notes unification

Eliminate the dual-write: B's verdict IS the implementation notes entry. Remove `.pev-signals/M<N>-verdict.txt` as a separate artifact. B writes directly to `docs/exec-plans/active/NNNN-notes/M<N>.md` using the existing entry types (`[deviation]` with devgrid fields for REJECTED, `[plan-confirmed]` style entry for CONFIRMED). Arbiter reads notes to determine routing. Update `test_repair_feedback_gate.py` to check notes format directly rather than checking for a separate verdict file.

`Acceptance Test:` `.claude/tests/test_verdict_notes_unified.py::test_b_writes_notes_directly` — B's output produces valid notes entries. `.claude/tests/test_verdict_notes_unified.py::test_no_separate_verdict_file` — structural grep confirms no code path writes to .pev-signals/M<N>-verdict.txt. `.claude/tests/test_repair_feedback_gate.py` — existing tests pass against unified notes format.

**File Scope:**
- `Allowed Reads:` docs/conventions/implementation-notes.md, .claude/tests/test_repair_feedback_gate.py
- `Allowed Writes:` .claude/scripts/pev_tmux_adversarial.sh (B's goal prompt updated), .claude/tests/test_verdict_notes_unified.py, .claude/tests/test_repair_feedback_gate.py (updated assertions), docs/conventions/implementation-notes.md (updated feedback gate rule)
- `Requires:` M1
- `Risk Tier:` B

### M3 — Arbiter autonomy and hook exemptions

Grant the arbiter session the permissions it needs for full autonomy. Update `pre_tool_use.py` to allow arbiter-originated edits to checkbox lines in ExecPlan files and to `.pev-signals/`. Add a structural test verifying the arbiter's `/goal` prompt includes the required autonomy scope. Document the hook exemption rules in `pev-loop.md`.

`Acceptance Test:` `.claude/tests/test_arbiter_autonomy.py::test_hook_allows_arbiter_checkbox_flip` — arbiter edit to `[ ]` → `[x]` in plan file is not blocked. `.claude/tests/test_arbiter_autonomy.py::test_hook_blocks_non_arbiter_checkbox_flip` — non-arbiter edit to checkbox is still blocked. `.claude/tests/test_arbiter_autonomy.py::test_arbiter_goal_includes_autonomy_scope` — goal prompt contains explicit autonomy boundaries.

**File Scope:**
- `Allowed Reads:` .claude/hooks/pre_tool_use.py, .claude/hooks/pre_execution_gate.py, .claude/settings.json, docs/conventions/pev-loop.md
- `Allowed Writes:` .claude/hooks/pre_tool_use.py (arbiter exemption logic), .claude/tests/test_arbiter_autonomy.py, docs/conventions/pev-loop.md (arbiter autonomy section)
- `Requires:` M1
- `Risk Tier:` C — modifies hook behavior; Awaiting Steering not required (decision recorded in this plan's Decision Log)

### M4 — Checkpoint recovery

Implement the `--resume` path in `pev_tmux_adversarial.sh`. On startup with `--resume`: read `state.json`, determine which milestones are already CONFIRMED (skip them), find the current milestone and phase, rebuild the tmux session with A and B at the correct state. Arbiter writes a checkpoint to `state.json` after each verdict is processed. Structural test verifies idempotent recovery: simulate a crash after M2 CONFIRMED, resume, assert M1 and M2 are skipped and M3 is the current milestone.

`Acceptance Test:` `.claude/tests/test_pev_recovery.py::test_checkpoint_written_after_verdict` — state.json updated after each verdict. `.claude/tests/test_pev_recovery.py::test_resume_skips_confirmed` — resumed session correctly identifies completed milestones. `.claude/tests/test_pev_recovery.py::test_resume_rebuilds_tmux_session` — tmux session structure matches fresh start.

**File Scope:**
- `Allowed Reads:` .claude/scripts/pev_tmux_adversarial.sh, .pev-signals/state.json (fixture)
- `Allowed Writes:` .claude/scripts/pev_tmux_adversarial.sh, .claude/tests/test_pev_recovery.py
- `Requires:` M0, M1
- `Risk Tier:` B

### M5 — Violation tracker

Add a structural test that detects when the same documented rule is violated across different ExecPlans. Reads all completed and active plan retrospectives, extracts violation patterns, and flags rules that appear in ≥2 plans. Output format: `.pev-signals/violations/{rule-slug}.json` with plan references, violation dates, and suggested promotion target. Does NOT auto-promote — that's M6.

`Acceptance Test:` `.claude/tests/test_violation_tracker.py::test_detects_same_rule_two_plans` — given two plans with the same violation pattern, tracker flags it. `.claude/tests/test_violation_tracker.py::test_no_false_positive_single_violation` — single violation is not flagged. `.claude/tests/test_violation_tracker.py::test_output_writes_to_signals_dir` — violation record written to .pev-signals/violations/.

**File Scope:**
- `Allowed Reads:` docs/exec-plans/completed/**, docs/exec-plans/active/**, docs/retrospectives/**
- `Allowed Writes:` .claude/tests/test_violation_tracker.py, .pev-signals/violations/.gitkeep
- `Requires:` none
- `Risk Tier:` B

### M6 — Promotion arbiter

Add a fourth window to the tmux session: the promotion arbiter. On startup (or when triggered by the violation tracker detecting a new repeat violation), the promotion arbiter reads `.pev-signals/violations/`, decides for each flagged rule whether to promote, to which level, and either auto-executes (for mechanical promotions like doc → structural test) or drafts a pre-filled ExecPlan for human approval (for architectural promotions like → CI gate). The promotion arbiter is a Claude Code session with its own `/goal`. It shares the same state.json checkpoint system.

`Acceptance Test:` `.claude/tests/test_promotion_arbiter.py::test_mechanical_promotion_auto_executed` — a simple format rule flagged twice is auto-promoted to structural test without human. `.claude/tests/test_promotion_arbiter.py::test_architectural_promotion_drafted` — a complex promotion (→ CI gate) generates a pre-filled ExecPlan draft. `.claude/tests/test_promotion_arbiter.py::test_arbiter_reads_violation_records` — arbiter correctly ingests violation tracker output.

**File Scope:**
- `Allowed Reads:` .claude/scripts/pev_tmux_adversarial.sh, .pev-signals/violations/**, docs/conventions/
- `Allowed Writes:` .claude/scripts/pev_tmux_adversarial.sh (fourth window), .claude/tests/test_promotion_arbiter.py, docs/exec-plans/active/ (pre-filled plan drafts)
- `Requires:` M5
- `Risk Tier:` B

### M7 — Integration, E2E, and cleanup

End-to-end test of the complete tmux PEV pipeline with promotion arbiter. Run the full loop on a test ExecPlan with 3 milestones, including one designed to trigger a REJECTED verdict and one designed to trigger a repeat violation. Archive `pev_orchestrator.js` and `pev_repair.py` to `docs/exec-plans/archived/` (or remove them — Decision Log below). Update cross-references in `pev-loop.md`, `verification-floor.md`, `implementation-notes.md`, `PLANS.md`, and `CLAUDE.md`.

`Acceptance Test:` `tests/integration/test_pev_tmux_e2e.py::test_full_pipeline_three_milestones` — 3 milestones, 1 REJECTED + repair, all CONFIRMED, state.json valid throughout. `tests/integration/test_pev_tmux_e2e.py::test_promotion_triggered` — repeat violation detected and promotion arbiter executes. `.claude/tests/test_cross_refs.py` — no references to deprecated JS/Python implementations remain in active docs.

**File Scope:**
- `Allowed Reads:` All conventions, all active plans, .claude/scripts/pev_*
- `Allowed Writes:` tests/integration/test_pev_tmux_e2e.py, docs/conventions/*.md, docs/PLANS.md, CLAUDE.md, .claude/scripts/ (archival)
- `Requires:` M0–M6
- `Risk Tier:` B

## 4. Progress

- [x] M0: Signal directory and state schema
- [x] M1: Tmux script formalization
- [x] M2: Verdict/notes unification
- [x] M3: Arbiter autonomy and hook exemptions
- [x] M4: Checkpoint recovery
- [x] M5: Violation tracker
- [x] M6: Promotion arbiter
- [ ] M7: Integration, E2E, and cleanup

## 5. Decision Log

### Decision: pev_orchestrator.js and pev_repair.py are deprecated, not deleted

**Rationale:** `Source: structured interview 2026-07-29` — the JS orchestrator and Python repair library are replaced by the tmux arbiter architecture, but they serve as reference implementations for the Dynamic Workflow pattern and the failure classification taxonomy. They are marked with deprecation comments pointing to this plan and `pev_tmux_adversarial.sh`, then moved to `.claude/scripts/archived/` at M7. `Confidence: high`.

### Decision: B writes verdicts directly into implementation notes

**Rationale:** `Source: structured interview 2026-07-29` — the dual-write (verdict file + notes entry) creates two sources of truth for the same REJECTED feedback. The verdict IS the notes entry. B writes `[deviation]` (with devgrid fields) for constraint violations, `[human-todo]` for semantic failures, and `[plan-confirmed]` for CONFIRMED. The arbiter reads notes to determine routing. The feedback gate structural test (`test_repair_feedback_gate.py`) is updated to check notes format directly. `Confidence: high`.

### Decision: Arbiter has full autonomy except for semantic failures

**Rationale:** `Source: structured interview 2026-07-29` — the arbiter is a Claude session with reasoning capability exceeding the hardcoded if/else it replaces. It can autonomously flip checkboxes, commit verdicts, send repair instructions, and re-trigger verification for mechanical and constraint-violation failures. Semantic failures (design judgment, subjective quality, human preference) pause for human input. Hook exemptions for arbiter-originated edits are scoped to ExecPlan checkbox lines and `.pev-signals/` writes only. `Confidence: high`.

### Decision: Promotion follows the same arbiter model as PEV repair

**Rationale:** `Source: structured interview 2026-07-29` — the promotion rule ("violated twice → promote") is currently manual (human notices, human decides, human opens ExecPlan). This is the same pattern that 9005 solved for PEV repair by replacing hardcoded if/else with a Claude arbiter. The same model applies: a promotion arbiter reads violation tracker output, decides promotion target based on violation severity and rule type, and either auto-executes (mechanical promotions) or drafts a pre-filled ExecPlan for human approval (architectural promotions). `Confidence: medium` — the promotion arbiter's decision quality depends on violation tracker signal quality, which will be refined during M5-M6 execution.

### Decision: Checkpoint granularity is per-verdict, not per-phase

**Rationale:** `Source: structured interview 2026-07-29` — writing checkpoints after each verdict (rather than after each plan/execute/verify phase) minimizes lost work on crash. The state.json schema records milestone-level progress (`confirmed`, `pending_verdict`, `in_progress`) plus the current phase. On resume, the arbiter can skip confirmed milestones, re-dispatch the current verdict if it was in-flight, and continue. `Confidence: high`.

## 6. Surprises & Discoveries

*None yet — this section grows during execution.*

## 7. Awaiting Steering

*None at plan creation. All Tier C decisions (hook modification in M3, arbiter autonomy scope) are resolved in the Decision Log above.*

## 8. Outcomes & Retrospective

*Written at completion or cancellation.*
