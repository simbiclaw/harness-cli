# 9006 — PEV Subagent Convergence

## 1. Purpose

Replace the tmux-based PEV architecture with subagent-based PEV. Each milestone traverses three independent subagents: P (Plan), E (Execute), V (Verify). The human session is the arbiter.

## 2. Big Picture

Each milestone M<N>:
1. **P (Plan)**: Writes failing acceptance test, creates fixtures. Prints `__PLAN_M<N>__: READY`
2. **E (Execute)**: Implements until tests pass, commits. Prints `__DONE_M<N>__ <sha>`
3. **V (Verify)**: Adversarial falsification (opus). Writes verdict to notes. Prints `__VERDICT_M<N>__: CONFIRMED|REJECTED`
4. **Arbiter**: Reads verdict, flips checkbox or dispatches repair

Dependencies enforced by sequential execution: M0→M1→M2→M3→M4→M5→M6→M7.

## 3. Milestones

### M0 — Signal directory and state schema

Formalize `.pev-signals/` as the coordination directory. Define state.json schema.

`Acceptance Test:` `.claude/tests/test_pev_signals.py`

`Behavioral Test: none` — harness infrastructure milestone; state.json schema validation is tested structurally via `test_pev_signals.py`. No functional behavior to exercise beyond schema conformance and directory existence.

**File Scope:**
- `Allowed Reads:` none
- `Allowed Writes:` .pev-signals/.gitkeep, .pev-signals/state.json, .claude/tests/test_pev_signals.py
- `Requires:` none
- `Risk Tier:` B

### M1 — Subagent adversarial script

Create `pev_subagent_adversarial.sh` — a reusable script that generates adversarial B prompts. Mark `pev_orchestrator.js` and `pev_repair.py` as DEPRECATED.

`Acceptance Test:` `.claude/tests/test_pev_tmux.py`

**File Scope:**
- `Allowed Reads:` .claude/scripts/pev_orchestrator.js, .claude/scripts/pev_repair.py
- `Allowed Writes:` .claude/scripts/pev_subagent_adversarial.sh, .claude/tests/test_pev_tmux.py, .claude/scripts/pev_orchestrator.js, .claude/scripts/pev_repair.py
- `Requires:` M0
- `Risk Tier:` B

### M2 — Verdict/notes unification

B writes verdicts directly as implementation notes entries. No separate verdict file.

`Acceptance Test:` `.claude/tests/test_verdict_notes_unified.py`

**File Scope:**
- `Allowed Reads:` docs/conventions/implementation-notes.md, .claude/tests/test_repair_feedback_gate.py, .claude/scripts/pev_subagent_adversarial.sh
- `Allowed Writes:` .claude/scripts/pev_subagent_adversarial.sh, .claude/tests/test_verdict_notes_unified.py, docs/conventions/implementation-notes.md
- `Requires:` M1
- `Risk Tier:` B

### M3 — Arbiter autonomy and hook exemptions

Add PEV_ARBITER detection to pre_tool_use.py. Document in pev-loop.md.

`Acceptance Test:` `.claude/tests/test_arbiter_autonomy.py`

**File Scope:**
- `Allowed Reads:` .claude/hooks/pre_tool_use.py, docs/conventions/pev-loop.md
- `Allowed Writes:` .claude/hooks/pre_tool_use.py, .claude/tests/test_arbiter_autonomy.py, docs/conventions/pev-loop.md
- `Requires:` M1
- `Risk Tier:` C (hook modification — approved in Decision Log)

### M4 — Checkpoint recovery

Implement --resume path. state.json checkpoint after each verdict.

`Acceptance Test:` `.claude/tests/test_pev_recovery.py`

**File Scope:**
- `Allowed Reads:` .claude/scripts/pev_subagent_adversarial.sh, .pev-signals/state.json
- `Allowed Writes:` .claude/scripts/pev_subagent_adversarial.sh, .claude/tests/test_pev_recovery.py
- `Requires:` M0, M1
- `Risk Tier:` B

### M5 — Violation tracker

Detect same rule violated across >=2 different ExecPlans. Output to .pev-signals/violations/.

`Acceptance Test:` `.claude/tests/test_violation_tracker.py`

**File Scope:**
- `Allowed Reads:` docs/exec-plans/completed/**, docs/exec-plans/active/**, docs/retrospectives/**
- `Allowed Writes:` .claude/tests/test_violation_tracker.py, .pev-signals/violations/.gitkeep
- `Requires:` none
- `Risk Tier:` B

### M6 — Promotion arbiter

Reads violation tracker output. Auto-executes mechanical promotions, drafts ExecPlans for architectural.

`Acceptance Test:` `.claude/tests/test_promotion_arbiter.py`

**File Scope:**
- `Allowed Reads:` .claude/scripts/pev_subagent_adversarial.sh, .pev-signals/violations/**, docs/conventions/
- `Allowed Writes:` .claude/scripts/pev_subagent_adversarial.sh, .claude/tests/test_promotion_arbiter.py
- `Requires:` M5
- `Risk Tier:` B

### M7 — Integration, E2E, and cleanup

End-to-end structural test. Cross-reference cleanup.

`Acceptance Test:` `.claude/tests/test_pev_tmux_e2e.py` `.claude/tests/test_cross_refs.py`

**File Scope:**
- `Allowed Reads:` All conventions, all active plans, .claude/scripts/
- `Allowed Writes:` .claude/tests/test_pev_tmux_e2e.py, .claude/tests/test_cross_refs.py, docs/conventions/*.md, CLAUDE.md
- `Requires:` M0–M6
- `Risk Tier:` B

## 4. Progress

- [x] M0: Signal directory and state schema
- [x] M1: Subagent adversarial script
- [x] M2: Verdict/notes unification
- [x] M3: Arbiter autonomy and hook exemptions
- [x] M4: Checkpoint recovery
- [x] M5: Violation tracker
- [ ] M6: Promotion arbiter
- [ ] M7: Integration, E2E, and cleanup

## 5. Decision Log

### Decision: PEV uses subagents, not tmux
The tmux IPC architecture was replaced by independent subagent dispatch (Agent tool). Each milestone's P/E/V phases run as separate subagents with model selection: P/E use sonnet, V uses opus for adversarial reasoning. `Source: execution experience 2026-07-29`. `Confidence: high`.

### Decision: Arbiter is the main session
The human session coordinates the loop: dispatches P→E→V for each milestone, reads V's verdict from notes, flips checkbox or dispatches repair. No separate arbiter process needed. `Confidence: high`.

## 6. Surprises & Discoveries
*None yet.*

## 7. Awaiting Steering

**Awaiting Steering: resolved — Q1 (M3 hook modification).** M3 edits `.claude/hooks/pre_tool_use.py` which matches `.claude/hooks/**` in sensitive-paths.txt. This is a Tier C decision. The changes are: adding `_is_arbiter()` detection (already present from prior implementation), Guard 2.5 (PEV agent gate — blocks implementation edits when P/E/V not spawned), and Guard 6 (commit authority — blocks git commit from non-Arbiter sessions). These guards are essential for PEV loop closure — without them, P/E/V can commit independently and bypass the Arbiter. The Arbiter exemption (`PEV_ARBITER=true`) is the mechanism that allows the Arbiter to flip checkboxes and edit plan files. All three guards check `_is_arbiter()` before blocking. The existing test_arbiter_autonomy.py validates arbiter exemption behavior. Default: proceed with M3. Deadline: 2026-07-31.

## 8. Outcomes & Retrospective
*Written at completion.*
