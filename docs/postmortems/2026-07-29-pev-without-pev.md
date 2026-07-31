# 2026-07-29 — 9006 PEV loop built without PEV

## What happened

The 9006 ExecPlan (PEV Tmux Convergence) had 8 milestones. All 8 were implemented by a single Claude Code session in ~3 hours — writing code, running tests, committing, and flipping checkboxes. No independent adversarial verification occurred. No implementation notes were written. The plan's own PEV mechanism (three independent subagents per milestone: P/E/V) was never exercised on the plan's own milestones.

After completion, an additional ~4 hours were spent attempting to retrofit adversarial verification via tmux-based autolaunch and subagent dispatch. The tmux approach failed due to fundamental TTY-sharing issues. Subagent-based verification succeeded but produced 100% CONFIRMED verdicts (8/8), raising validity concerns.

## Impact

- **9006 milestones**: All 8 implemented without adversarial falsification. Untrusted.
- **Time**: ~3 hours of unverified implementation + ~4 hours of failed tmux debugging + ~1 hour of subagent retrofitting ≈ 8 hours total.
- **Artifacts**: `pev_tmux_adversarial.sh` script corrupted by repeated regex edits (recovered from git). `pev_loop.sh` (bash-only variant) created as fallback. State files, violation tracker, and promotion arbiter built but never used in a real PEV loop.
- **Learning**: The session produced a postmortem and updated conventions, but no verified deliverables.

## Root cause

The 9006 handoff document (`docs/exec-plans/active/9006-handoff.md`) prescribed linear execution: "Implement M0, then continue to M1." It treated PEV as a delivery checklist rather than a verification mechanism. There was no structural enforcement — no hook or test that prevented flipping a checkbox without a subagent B verdict.

Underlying factors:
1. **No bootstrap threshold.** The plan never identified a milestone after which the PEV infrastructure should govern its own completion. M3 (arbiter autonomy) was the natural bootstrap point but wasn't designated as such.
2. **No structural gate on checkbox flips without notes.** `test_repair_feedback_gate.py` checks for notes entries only when REJECTED verdicts exist in the Decision Log — not when no verdict exists at all.
3. **Agent incentives.** The session agent's default behavior is to complete tasks linearly. Breaking that pattern requires explicit structural constraints, not documentation alone.

## Detection

The user asked: "9005计划中，要求在执行计划过程中，记录structured feedback that determines the next action，为什么没有" — the 9005 plan required implementation notes, and none existed for 9006. This triggered the root-cause analysis that revealed the entire PEV bypass.

## Resolution

1. Identified that tmux-based autolaunch is fundamentally unreliable (TTY sharing between bash and dcode)
2. Switched to subagent-based PEV: three independent agent dispatches per milestone (P→E→V)
3. Key subagent design rules discovered through iteration:
   - P/E use sonnet, V must use opus
   - V's prompt must state "DEFAULT STANCE: REJECTED. Prove it works to confirm."
   - V must use general-purpose type (Write access needed for edge cases)
4. Retroactively verified M0-M3 with properly adversarial B subagents; all confirmed
5. Codebase reset to pre-9006 baseline for clean restart

## Lessons

1. **Promote from documentation to structural test**: Add a test that verifies every checkbox flip has a corresponding notes entry in `-notes/M<N>.md`. A flipped checkbox without a `[plan-confirmed]` or `[deviation]` entry is a harness violation.

2. **Promote from documentation to hook**: Add a PreToolUse hook that blocks checkbox flips (Edit on plan files matching `- [ ] M<N>:` → `- [x] M<N>:`) unless `.pev-signals/state.json` shows the milestone as `verified`.

3. **Bootstrap threshold must be explicit in every plan**. Plans that build PEV infrastructure must designate a milestone after which the infrastructure governs remaining milestones. This is a Tier C decision (architectural) and belongs in the Plan's Decision Log.

4. **No artificial verification mechanisms**. Do not use tmux send-keys + paste-buffer to simulate keyboard input to Claude Code sessions. The Agent tool is the correct dispatch mechanism for subagent isolation.

5. **V subagent model is opus**. The cost of a false CONFIRMED verdict (undetected defect propagates to production) exceeds the cost of opus inference. V must use the strongest available adversarial reasoning model.
