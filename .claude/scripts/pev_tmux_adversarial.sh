#!/usr/bin/env bash
# pev_tmux_adversarial.sh — PEV adversarial loop via tmux IPC.
#
# A (Implementer) and B (Verifier) run in separate Claude Code sessions,
# different tmux windows, potentially different models. Handoff uses
# tmux send-keys + capture-pane — no git push/fetch, no network.
#
# This is the single PEV implementation as of plan 9006. It replaces:
#   - .claude/scripts/pev_orchestrator.js (Dynamic Workflow pipeline) — DEPRECATED
#   - .claude/scripts/pev_repair.py (Python repair library)        — DEPRECATED
#
# Usage:
#   bash .claude/scripts/pev_tmux_adversarial.sh --plan <plan-id> --milestones <m1,m2,...>
#   bash .claude/scripts/pev_tmux_adversarial.sh --plan <plan-id> --milestones <...> --resume
#   bash .claude/scripts/pev_tmux_adversarial.sh --help

set -euo pipefail

# ── Argument parsing ─────────────────────────────────────────────────────────

PLAN_ID=""
MILESTONES_INPUT=""
RESUME_MODE=false
CLEANUP_ON_SUCCESS=true

usage() {
    cat <<EOF
Usage: $(basename "$0") --plan <plan-id> --milestones <m1,m2,...> [--resume] [--help]

  --plan PLAN_ID         Required. ExecPlan stem (e.g., "9006-pev-tmux-convergence").
  --milestones M1,M2,...  Required. Comma-separated milestone numbers (e.g., "0,1,2,3").
  --resume               Resume from last checkpoint in .pev-signals/state.json.
  --help                 Show this message.

Example:
  bash .claude/scripts/pev_tmux_adversarial.sh --plan 9006-pev-tmux-convergence --milestones 0,1,2
  bash .claude/scripts/pev_tmux_adversarial.sh --plan 9006-pev-tmux-convergence --milestones 0,1,2 --resume
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --plan)
            PLAN_ID="$2"
            shift 2
            ;;
        --milestones)
            MILESTONES_INPUT="$2"
            shift 2
            ;;
        --resume)
            RESUME_MODE=true
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [ -z "$PLAN_ID" ]; then
    echo "ERROR: --plan is required." >&2
    usage >&2
    exit 1
fi

if [ -z "$MILESTONES_INPUT" ]; then
    echo "ERROR: --milestones is required." >&2
    usage >&2
    exit 1
fi

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ACTIVE_DIR="$REPO_ROOT/docs/exec-plans/active"
SIGNAL_DIR="$REPO_ROOT/.pev-signals"
STATE_FILE="$SIGNAL_DIR/state.json"
SESSION="pev-adversarial"

# ── Validate plan file ────────────────────────────────────────────────────────

PLAN_FILE="$ACTIVE_DIR/$PLAN_ID.md"
if [ ! -f "$PLAN_FILE" ]; then
    echo "ERROR: Plan file not found: $PLAN_FILE" >&2
    exit 1
fi

# ── Resume mode: load state ───────────────────────────────────────────────────

if $RESUME_MODE; then
    if [ ! -f "$STATE_FILE" ]; then
        echo "WARNING: --resume specified but no state file found at $STATE_FILE. Starting fresh." >&2
    else
        echo "=== Resume mode: reading checkpoint from $STATE_FILE ==="
        # Extract plan_id for verification
        STATE_PLAN_ID=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['plan_id'])" 2>/dev/null || echo "")
        if [ -n "$STATE_PLAN_ID" ] && [ "$STATE_PLAN_ID" != "$PLAN_ID" ]; then
            echo "WARNING: state.json plan_id ($STATE_PLAN_ID) does not match --plan ($PLAN_ID)." >&2
            echo "Using --plan value ($PLAN_ID)." >&2
        fi
        # Report current state
        STATE_PHASE=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['phase'])" 2>/dev/null || echo "unknown")
        STATE_MILESTONE=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['current_milestone'])" 2>/dev/null || echo "0")
        echo "Resume state: phase=$STATE_PHASE, current_milestone=$STATE_MILESTONE"
        echo "Confirmed milestones will be skipped; in-progress milestone will be resumed."
    fi
fi

# ── Parse milestones ──────────────────────────────────────────────────────────

IFS=',' read -ra MS <<< "$MILESTONES_INPUT"
M_COUNT=${#MS[@]}
M_LIST=""
for m in "${MS[@]}"; do M_LIST="${M_LIST}M${m}, "; done
M_LIST="${M_LIST%, }"

# ── Extract milestone specs ──────────────────────────────────────────────────

# macOS-compatible: use sed instead of grep -oP
extract_milestone_spec() {
    local m="$1"
    awk "/^### M${m}[[:space:]]/,/^### M/" "$PLAN_FILE" | head -n -1
}

extract_acceptance_test() {
    local m="$1"
    extract_milestone_spec "$m" | sed -n 's/.*`Acceptance Test:`[[:space:]]*`\{0,1\}\([^`\n]*\)`\{0,1\}.*/\1/p' | head -1
}

# ── Setup ─────────────────────────────────────────────────────────────────────

mkdir -p "$SIGNAL_DIR"
NOTES_DIR="$ACTIVE_DIR/${PLAN_ID}-notes"
mkdir -p "$NOTES_DIR"

# Clean up previous signal files (but not state.json for resume)
if ! $RESUME_MODE; then
    rm -f "$SIGNAL_DIR"/M*-verdict.txt 2>/dev/null || true
fi

tmux kill-session -t "$SESSION" 2>/dev/null || true

echo "=== PEV Adversarial Loop (tmux IPC) ==="
echo "Plan:       $PLAN_ID"
echo "Milestones: $M_LIST ($M_COUNT total)"
echo "Resume:     $RESUME_MODE"
echo "A model:    sonnet"
echo "B model:    opus"

# ── Build goal prompts ───────────────────────────────────────────────────────

# A's prompt: implement milestones sequentially, commit locally, signal via sentinel
A_PROMPT="You are the IMPLEMENTER (subagent A) for ExecPlan $PLAN_ID.

Milestones to implement, in order: ${M_LIST}

For EACH milestone:
1. Read the milestone spec in docs/exec-plans/active/${PLAN_ID}.md
2. Write the acceptance test FIRST — it must FAIL (RED phase)
3. Implement the code. Run the test — it must PASS (GREEN phase).
4. Run ALL structural tests: uv run pytest .claude/tests/ -q
5. Commit locally (no push needed): git add -A && git commit -m \"...\"
   Use Plan: docs/exec-plans/active/${PLAN_ID}.md#milestone-N and Decision: test-first
6. Print the EXACT sentinel line on its own line:
   __DONE_M<N>__
   (example: __DONE_M1__)

Rules:
- Do NOT read .pev-signals/ directory.
- Do NOT read B's verdicts or any file B writes.
- If B rejects your work, a human will tell you — do not poll.
- Use model=sonnet.

/goal Implement ${M_LIST} sequentially. Print __DONE_M<N>__ after each milestone. All tests pass. All local commits have Plan:/Decision: trailers. Stop when all milestones done or after 40 turns."

# B's prompt: receives milestone spec + commit SHA via tmux send-keys, falsifies
# B writes verdicts DIRECTLY into the implementation notes file (single source of truth).
B_PROMPT="You are the ADVERSARIAL VERIFIER (subagent B) for ExecPlan $PLAN_ID.

Your job is to FALSIFY A's implementations. You will receive instructions
via this terminal for each milestone (sent by the arbiter via tmux).

When you receive a verification request, it will contain:
- Milestone number
- Acceptance test to run
- A's commit SHA (to checkout)

For each request:
1. git checkout <sha> (A's implementation commit)
2. Run the acceptance test — it must pass
3. Design at least 3 edge cases NOT covered by the test. Run them.
4. Run structural tests: uv run pytest .claude/tests/ -q
5. Run lint: uv run ruff check . && uv run ruff format --check .
6. Write your verdict DIRECTLY to the implementation notes file:
   docs/exec-plans/active/${PLAN_ID}-notes/M<N>.md

   Use the following entry types:
   - If CONFIRMED: write a [plan-confirmed] entry summarizing what passed
     Example:
     ### [plan-confirmed] <timestamp> — M<N> adversarial verification passed

     Acceptance test passed. Edge cases held. Structural tests all green.

   - If REJECTED (constraint-violation): write a [deviation] entry with all 4 devgrid fields
     Example:
     ### [deviation] <timestamp> — M<N> exceeded declared constraints

     - **What the plan said:** <quoted constraint from plan>
     - **What the code revealed:** <actual scope discovered>
     - **Conservative choice:** <decision made>
     - **Revisit:** <when to reconsider>

   - If REJECTED (semantic): write a [human-todo] entry
     Example:
     ### [human-todo] <timestamp> — M<N> requires human judgment

     <B's findings requiring human decision>

   - If REJECTED (mechanical): write a [discovery] entry noting the defect
     Example:
     ### [discovery] <timestamp> — M<N> mechanical failure found

     <specific defect, test failure, or assertion error>

7. Print the EXACT sentinel line on its own line:
   __VERDICT_M<N>__
   (example: __VERDICT_M1__)

Rules:
- Your default stance is SKEPTICISM. Try hard to find defects.
- Do NOT read A's commit messages, decision logs, or implementation notes.
  (git checkout the SHA, do NOT run git log)
- Judge the code by its BEHAVIOR, not its intentions.
- Your verdict IS the notes entry. Write it directly. No separate file.
- Use model=opus for stronger adversarial reasoning.

/goal Wait for verification requests. Each request arrives via this terminal. Run tests + edge cases. Write verdicts as notes entries to docs/exec-plans/active/${PLAN_ID}-notes/M<N>.md using the entry types above. Use model=opus. Stop after ${M_COUNT} verdicts or 40 turns."

# Arber prompt: orchestrates the loop via tmux IPC
# Arbiter reads B's verdicts from implementation notes (single source of truth).
# Autonomy scope:
#   - ALLOWED autonomously: flip checkboxes, commit verdicts, send repair
#     instructions to A, re-trigger verification, edit .pev-signals/,
#     edit milestone notes files.
#   - BLOCKED: semantic (human-todo) failures pause for human judgment.
#     Do not proceed past a semantic failure without human input.
ARBITER_PROMPT="You are the ARBITER for the PEV adversarial loop.

Plan: $PLAN_ID
Milestones: ${M_LIST}

Your job is to watch A's output and dispatch verification requests to B.

For each milestone (${M_COUNT} total):

1. Watch A's tmux pane (window A-implementer) for the sentinel: __DONE_M<N>__
   When you see it, A has finished implementing that milestone.

2. Get A's latest commit SHA:
   git log -1 --format='%H'

3. Read the milestone spec and extract the acceptance test.

4. Send a verification request to B (window B-verifier) via tmux send-keys:
   Send this exact text to B's terminal:

   === Verify M<N> ===
   Acceptance test: <test name from spec>
   A's commit: $(git log -1 --format='%H')
   Run: git checkout <sha> && uv run pytest <test> -v
   Write verdict as notes entry to docs/exec-plans/active/${PLAN_ID}-notes/M<N>.md.
   Print __VERDICT_M<N>__ when done.

5. Wait for B's sentinel: __VERDICT_M<N>__
   (monitor B's tmux pane)

6. Read the verdict from the implementation notes file:
   cat docs/exec-plans/active/${PLAN_ID}-notes/M<N>.md

   Determine routing from the entry type:
   - [plan-confirmed] → CONFIRMED. Flip the milestone checkbox to [x].
   - [deviation] → REJECTED (constraint-violation). Display B's findings.
   - [human-todo] → REJECTED (semantic). Pause for human judgment.
   - [discovery] (mechanical) → REJECTED. Auto-retry.

7. Report the result clearly and act accordingly.

8. After each verdict, write a checkpoint to .pev-signals/state.json:
   Update the milestone status, current_milestone, phase, and
   last_checkpoint_at timestamp. This ensures recovery can resume
   from the last processed milestone if the tmux session crashes.

Commands you can use:
- tmux capture-pane -t pev-adversarial:A-implementer -p -S -200
  (captures last 200 lines of A's output)
- tmux send-keys -t pev-adversarial:B-verifier '<text>' Enter
  (sends text to B's terminal)
- cat docs/exec-plans/active/${PLAN_ID}-notes/M<N>.md
  (reads B's verdict from implementation notes)

/goal Orchestrate the adversarial loop for ${M_LIST}. Watch A, dispatch to B, read verdicts from notes, flip checkboxes. Stop when all milestones verified or after 30 turns."

# ── Create tmux session ──────────────────────────────────────────────────────

tmux new-session -d -s "$SESSION" -n "arbiter" -c "$REPO_ROOT"

# Window 0, pane 0: signal file watcher
tmux send-keys -t "$SESSION:arbiter" "
echo '╔══════════════════════════════════════════════════════╗'
echo '║  PEV Adversarial Loop — Arbiter                   ║'
echo '╠══════════════════════════════════════════════════════╣'
echo '║  Plan:       $PLAN_ID                              '
printf '║  Milestones: %-38s ║\n' '$M_LIST'
echo '╠══════════════════════════════════════════════════════╣'
echo '║  A (Window 1): Implementer — sonnet                ║'
echo '║  B (Window 2): Verifier    — opus                  ║'
echo '╠══════════════════════════════════════════════════════╣'
echo '║  IPC: tmux capture-pane / send-keys                ║'
echo '║  No git push/fetch between A and B.                ║'
echo '╚══════════════════════════════════════════════════════╝'
echo ''
echo 'Signal files (.pev-signals/):'
echo 'Notes directory: docs/exec-plans/active/${PLAN_ID}-notes/'
while true; do
  clear
  echo '=== Verdict Log (from implementation notes) ==='
  echo ''
  for m in ${MS[@]}; do
    nf=\"\$NOTES_DIR/M\${m}.md\"
    if [ -f \"\$nf\" ]; then
      first_badge=\$(head -20 \"\$nf\" | grep -o '\[plan-confirmed\]\|\[deviation\]\|\[human-todo\]\|\[discovery\]' | head -1)
      if [ \"\$first_badge\" = '[plan-confirmed]' ]; then
        echo \"  M\${m}  ✓ CONFIRMED (plan-confirmed)\"
      elif [ \"\$first_badge\" = '[deviation]' ]; then
        echo \"  M\${m}  ✗ REJECTED — constraint-violation (deviation)\"
      elif [ \"\$first_badge\" = '[human-todo]' ]; then
        echo \"  M\${m}  ✗ REJECTED — semantic (human-todo)\"
      elif [ \"\$first_badge\" = '[discovery]' ]; then
        echo \"  M\${m}  ✗ REJECTED — mechanical (discovery)\"
      else
        echo \"  M\${m}  ? verdict in notes — see \$nf\"
      fi
    else
      echo \"  M\${m}  — waiting\"
    fi
  done
  echo ''
  echo 'Press Ctrl-C to stop watching.'
  sleep 3
done
" Enter

# Arbiter pane 1: show signals directory
tmux split-window -h -t "$SESSION:arbiter" -c "$REPO_ROOT"
tmux send-keys -t "$SESSION:arbiter.1" "watch -n 2 'ls -la .pev-signals/ 2>/dev/null; echo; for f in .pev-signals/*.txt 2>/dev/null; do echo \"--- \$f ---\"; cat \"\$f\" 2>/dev/null; done'" Enter

# ── Window 1: A (Implementer, sonnet) ────────────────────────────────────────

tmux new-window -t "$SESSION" -n "A-implementer" -c "$REPO_ROOT"
tmux send-keys -t "$SESSION:A-implementer" "
echo '╔══════════════════════════════════════════╗'
echo '║  A: IMPLEMENTER (model: sonnet)          ║'
echo '╠══════════════════════════════════════════╣'
echo '║  Plan: $PLAN_ID'
printf '║  Milestones: %-28s ║\n' '$M_LIST'
echo '╠══════════════════════════════════════════╣'
echo '║  Print __DONE_M<N>__ after each commit. ║'
echo '╚══════════════════════════════════════════╝'
echo ''
echo 'Goal prompt:'
echo '────────────────────────────────────────'
echo '$A_PROMPT'
echo '────────────────────────────────────────'
echo ''
echo 'Run: claude'
echo ''
" Enter

# ── Window 2: B (Verifier, opus) ─────────────────────────────────────────────

tmux new-window -t "$SESSION" -n "B-verifier" -c "$REPO_ROOT"
tmux send-keys -t "$SESSION:B-verifier" "
echo '╔══════════════════════════════════════════╗'
echo '║  B: VERIFIER (model: opus)              ║'
echo '╠══════════════════════════════════════════╣'
echo '║  Plan: $PLAN_ID'
printf '║  Milestones: %-28s ║\n' '$M_LIST'
echo '╠══════════════════════════════════════════╣'
echo '║  Wait for verification requests.        ║'
echo '║  Write verdicts to .pev-signals/.       ║'
echo '╚══════════════════════════════════════════╝'
echo ''
echo 'Goal prompt:'
echo '────────────────────────────────────────'
echo '$B_PROMPT'
echo '────────────────────────────────────────'
echo ''
echo 'Run: claude'
echo ''
" Enter

# ── Window 3: Orchestrator (runs the arbiter Claude session) ─────────────────

tmux new-window -t "$SESSION" -n "orchestrator" -c "$REPO_ROOT"
tmux send-keys -t "$SESSION:orchestrator" "
echo '╔══════════════════════════════════════════╗'
echo '║  ORCHESTRATOR — tmux IPC controller     ║'
echo '╠══════════════════════════════════════════╣'
echo '║  Watches A for __DONE_M<N>__           ║'
echo '║  Sends verification requests to B      ║'
echo '║  Reads verdicts, flips checkboxes      ║'
echo '╚══════════════════════════════════════════╝'
echo ''
echo 'Goal prompt:'
echo '────────────────────────────────────────'
echo '$ARBITER_PROMPT'
echo '────────────────────────────────────────'
echo ''
echo 'After A and B are running, run: claude'
echo ''
" Enter

# ── Select and attach ────────────────────────────────────────────────────────

# ── Window 4: Promotion Arbiter (rule promotion decisions) ───────────────────

# Promotion arbiter prompt: reads violation tracker output, decides promotions.
# Autonomy scope:
#   - AUTO-EXECUTE: mechanical promotions (documentation → structural test)
#   - DRAFT for human approval: architectural promotions (→ CI gate, → architecture)
PROMOTION_ARBITER_PROMPT="You are the PROMOTION ARBITER for ExecPlan $PLAN_ID.

Your job is to read violation tracker output and decide rule promotions.

Source: .pev-signals/violations/*.json

For each violation record:
1. Read the record: cat .pev-signals/violations/<rule-slug>.json
2. Check the violation_count — must be ≥2 to consider promotion.
3. Determine the promotion target based on the rule's current level:
   - documentation → structural test (AUTO-EXECUTE: create a test file)
   - structural test → hook (AUTO-EXECUTE: add hook logic)
   - hook → CI gate (DRAFT: create a pre-filled ExecPlan for human approval)
   - CI gate → architecture (DRAFT: create a pre-filled ExecPlan for human approval)

For AUTO-EXECUTE promotions:
- Create the structural test or hook code directly
- Commit with Plan: and Decision: trailers
- Update the violation record with 'promoted_to' and timestamp
- Report: 'PROMOTED: <rule> from <current> to <target>'

For DRAFT promotions (needs human):
- Create a pre-filled ExecPlan in docs/exec-plans/active/
  with sections: Purpose, Big Picture, Milestones, Decision Log
- The Decision Log entry must cite the violation records
- Report: 'DRAFTED: <rule> promotion plan at docs/exec-plans/active/<plan-id>.md'
- Wait for human approval before executing

Rules:
- Do NOT promote a rule flagged only once (violation_count must be ≥2).
- Do NOT skip promotion levels (always promote one step at a time).
- Mechanical promotions are low-risk — execute them autonomously.
- Architectural promotions affect the build system — draft for human review.

/goal Read .pev-signals/violations/ for repeat violations. Auto-execute mechanical promotions. Draft ExecPlans for architectural promotions. Report decisions clearly. Stop when all violation records are processed or after 20 turns."

tmux new-window -t "$SESSION" -n "promotion-arbiter" -c "$REPO_ROOT"
tmux send-keys -t "$SESSION:promotion-arbiter" "
echo '╔══════════════════════════════════════════╗'
echo '║  PROMOTION ARBITER                      ║'
echo '╠══════════════════════════════════════════╣'
echo '║  Reads: .pev-signals/violations/        ║'
echo '║  Auto-executes: doc → test, test → hook ║'
echo '║  Drafts: → CI gate, → architecture     ║'
echo '╚══════════════════════════════════════════╝'
echo ''
echo 'Goal prompt:'
echo '────────────────────────────────────────'
echo '$PROMOTION_ARBITER_PROMPT'
echo '────────────────────────────────────────'
echo ''
echo 'Run after violation tracker completes: claude'
echo ''
" Enter

# ── Select and attach ────────────────────────────────────────────────────────

tmux select-window -t "$SESSION:arbiter"
tmux select-pane -t "$SESSION:arbiter.0"

echo ""
echo "=== Session ready: $SESSION ==="
echo "  tmux attach -t $SESSION"
echo "  tmux kill-session -t $SESSION"
echo ""
echo "Startup order (manual):"
echo "  1. Window 1 (A): type 'claude' → paste goal prompt → Enter"
echo "  2. Window 2 (B): type 'claude' → paste goal prompt → Enter"
echo "  3. Window 3 (orchestrator): type 'claude' → paste goal prompt → Enter"
echo "  4. Window 4 (promotion-arbiter): type 'claude' → paste goal prompt → Enter"
echo "  5. Window 0 (arbiter): watch signal files"
echo ""
echo "Flow: A prints __DONE_M1__ → orchestrator detects via capture-pane"
echo "      → orchestrator sends verification request to B via send-keys"
echo "      → B writes verdict → orchestrator reads it → flips checkbox"
echo "      → loop to next milestone"
echo "      → promotion arbiter reads violations/ → auto-promotes or drafts"
echo ""

if [ -t 0 ]; then
    tmux attach -t "$SESSION"
fi
