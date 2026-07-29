#!/usr/bin/env bash
# pev_subagent_adversarial.sh — Generate adversarial B verification prompts for PEV milestones.
#
# Generates subagent B (adversarial verifier) prompts using the plan spec and
# milestone structure. Supports --resume to load checkpoint from state.json.
#
# This replaces the hardcoded verify logic in:
#   - .claude/scripts/pev_orchestrator.js (Dynamic Workflow pipeline) — DEPRECATED
#   - .claude/scripts/pev_repair.py (Python repair library)           — DEPRECATED
#
# Usage:
#   bash .claude/scripts/pev_subagent_adversarial.sh --plan <plan-id> --milestones <m1,m2,...>
#   bash .claude/scripts/pev_subagent_adversarial.sh --plan <plan-id> --milestones <...> --resume
#   bash .claude/scripts/pev_subagent_adversarial.sh --help

set -euo pipefail

# ── Argument parsing ─────────────────────────────────────────────────────────

PLAN_ID=""
MILESTONES_INPUT=""
RESUME_MODE=false

usage() {
    cat <<EOF
Usage: $(basename "$0") --plan <plan-id> --milestones <m1,m2,...> [--resume] [--help]

  --plan PLAN_ID         Required. ExecPlan stem (e.g., "9006-pev-tmux-convergence").
  --milestones M1,M2,...  Required. Comma-separated milestone numbers (e.g., "0,1,2").
  --resume               Load checkpoint from .pev-signals/state.json.
  --help                 Show this message.

Generates an adversarial subagent B prompt that falsifies implementations
for the given plan milestones. Use --resume to produce a prompt that
skips already-confirmed milestones.
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

# ── Resume mode: load state ───────────────────────────────────────────────────

RESUMED_FROM=""
if $RESUME_MODE; then
    if [ ! -f "$STATE_FILE" ]; then
        echo "WARNING: --resume specified but no state file found at $STATE_FILE." >&2
        echo "Starting fresh. Generating prompt for all milestones." >&2
    else
        RESUMED_FROM="$STATE_FILE"
        echo "=== Resume mode: reading checkpoint from $STATE_FILE ==="
        STATE_PLAN_ID=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['plan_id'])" 2>/dev/null || echo "")
        STATE_PHASE=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['phase'])" 2>/dev/null || echo "unknown")
        STATE_MILESTONE=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['current_milestone'])" 2>/dev/null || echo "0")
        echo "Resume state: plan=$STATE_PLAN_ID, phase=$STATE_PHASE, current_milestone=$STATE_MILESTONE"
        if [ -n "$STATE_PLAN_ID" ] && [ "$STATE_PLAN_ID" != "$PLAN_ID" ]; then
            echo "WARNING: state.json plan_id ($STATE_PLAN_ID) does not match --plan ($PLAN_ID)." >&2
        fi
        echo ""
    fi
fi

# ── Parse milestones ──────────────────────────────────────────────────────────

IFS=',' read -ra MS <<< "$MILESTONES_INPUT"
M_COUNT=${#MS[@]}
MS_TRIMMED=()
for m in "${MS[@]}"; do
    # Strip leading/trailing whitespace from each milestone number
    m="${m#"${m%%[![:space:]]*}"}"
    m="${m%"${m##*[![:space:]]}"}"
    MS_TRIMMED+=("$m")
done

# Validate milestone values are numeric
for m in "${MS_TRIMMED[@]}"; do
    if ! [[ "$m" =~ ^[0-9]+$ ]]; then
        echo "ERROR: Invalid milestone value '$m' — must be a number." >&2
        usage >&2
        exit 1
    fi
done

M_LIST=""
for m in "${MS_TRIMMED[@]}"; do
    M_LIST="${M_LIST}M${m}, "
done
M_LIST="${M_LIST%, }"

# ── Extract milestone acceptance tests ────────────────────────────────────────

PLAN_FILE="$ACTIVE_DIR/$PLAN_ID.md"
TESTS=""
for m in "${MS_TRIMMED[@]}"; do
    if [ -f "$PLAN_FILE" ]; then
        test_name=$(awk "/^### M${m}[[:space:]]/,/^### M[0-9]/" "$PLAN_FILE" \
            | grep -i "acceptance test" \
            | sed 's/.*`Acceptance Test:`[[:space:]]*`\{0,1\}\([^`\n]*\)`\{0,1\}.*/\1/' \
            | head -1) || true
        if [ -n "$test_name" ]; then
            TESTS="${TESTS}  - M${m}: ${test_name}"$'\n'
        fi
    fi
done

# ── Generate adversarial B prompt ─────────────────────────────────────────────

cat <<PROMPT
╔══════════════════════════════════════════════════════════════╗
║  Adversarial B Verification Prompt                         ║
║  Plan: ${PLAN_ID}
║  Milestones: ${M_LIST} (${M_COUNT} total)
║  Resume: ${RESUME_MODE}
╚══════════════════════════════════════════════════════════════╝

You are the ADVERSARIAL VERIFIER (subagent B) for ExecPlan ${PLAN_ID}.

Your job is to FALSIFY each milestone implementation. For each milestone:

1. Read the milestone spec in the ExecPlan document.
2. Run the acceptance test — it must pass.
3. Design at least 3 edge cases NOT covered by the test. Run them.
4. Run ALL structural tests: uv run pytest .claude/tests/ -q
5. Run lint: uv run ruff check . && uv run ruff format --check .

If the implementation passes ALL checks, write a CONFIRMED verdict.
Otherwise, write a REJECTED verdict with specific findings:
   - mechanical: test/implementation has a mechanical error (fix and retry)
   - semantic: design quality or subjective judgment issue (needs human)
   - constraint-violation: implementation exceeded declared constraints

Write each verdict directly as an implementation notes entry. The notes
directory is docs/exec-plans/active/${PLAN_ID}-notes/. Each milestone N
has a file at docs/exec-plans/active/${PLAN_ID}-notes/M<N>.md.

Use the following entry types for your verdicts:

  [plan-confirmed]  — CONFIRMED: acceptance test passed, edge cases held,
                      structural tests and lint all green.
  [deviation]       — REJECTED (constraint-violation): implementation exceeded
                      declared constraints. Include all four devgrid fields
                      (plan, discovered, conservative choice, revisit).
  [human-todo]      — REJECTED (semantic): requires human judgment. Describe
                      what needs a decision.
  [discovery]       — REJECTED (mechanical): specific defect, test failure,
                      or assertion error found.

Rules:
- Your default stance is SKEPTICISM. Try hard to find defects.
- Do NOT read A's commit messages, decision logs, or implementation notes.
  Checkout the SHA, do NOT run git log.
- Judge the code by its BEHAVIOR, not its intentions.

Milestones to verify:
${TESTS:-  (no acceptance tests found in plan file)}
PROMPT
