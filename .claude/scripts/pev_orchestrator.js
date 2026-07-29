/**
 * DEPRECATED — Replaced by pev_tmux_adversarial.sh (plan 9006).
 *
 * This Dynamic Workflow-based PEV orchestrator is superseded by the tmux
 * arbiter architecture defined in docs/exec-plans/active/9006-pev-tmux-convergence.md.
 * The tmux script replaces all hardcoded repair classification with Claude
 * reasoning and converges three PEV implementations into one.
 *
 * This file is kept as a reference implementation for the Dynamic Workflow
 * pattern and the failure classification taxonomy. It will be moved to
 * .claude/scripts/archived/ at M7.
 *
 * Do not use for new ExecPlans. Use pev_tmux_adversarial.sh instead.
 *
 * --- Original docstring below ---
 *
 * PEV Orchestrator — Dynamic Workflow script.
 *
 * Orchestrates the Plan→Execute→Verify loop for ExecPlan milestones using
 * the pipeline() pattern. Each milestone flows through three stages:
 *   Plan:    create failing test, check constraints, create worktree
 *   Execute: implement in worktree, run tests, commit
 *   Verify:  subagent B runs test + edge cases in clean worktree → CONFIRMED/REJECTED
 *
 * On REJECTED, the repair loop reads implementation notes and decides
 * the next action autonomously.
 */

export const meta = {
  name: 'pev-orchestrator',
  description: 'Orchestrate PEV loop for ExecPlan milestones',
  phases: [
    { title: 'Plan', detail: 'Create failing test, check constraints, create worktree' },
    { title: 'Execute', detail: 'Implement in worktree, run tests, commit' },
    { title: 'Verify', detail: 'B runs test + edge cases in clean worktree' },
  ],
}

// Schemas for structured agent results
const PLAN_SCHEMA = {
  type: 'object',
  properties: {
    milestone: { type: 'number', description: 'Milestone number' },
    test_file: { type: 'string', description: 'Path to acceptance test file' },
    test_written: { type: 'boolean', description: 'Whether failing test was created' },
    constraints_ok: { type: 'boolean', description: 'Whether constraints check passed' },
    worktree_path: { type: 'string', description: 'Path to created worktree' },
    blocked: { type: 'string', description: 'Reason if blocked (Tier C, constraint violation)' },
  },
  required: ['milestone', 'test_written', 'constraints_ok'],
}

const EXECUTE_SCHEMA = {
  type: 'object',
  properties: {
    milestone: { type: 'number' },
    tests_pass: { type: 'boolean', description: 'Whether acceptance test passes' },
    structural_pass: { type: 'boolean', description: 'Whether structural tests pass' },
    committed: { type: 'boolean', description: 'Whether changes were committed' },
    commit_sha: { type: 'string', description: 'SHA of implementation commit' },
    notes: { type: 'string', description: 'Implementation notes summary' },
  },
  required: ['milestone', 'tests_pass', 'committed'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    milestone: { type: 'number' },
    verdict: { type: 'string', enum: ['CONFIRMED', 'REJECTED'], description: 'Adversarial verdict' },
    acceptance_test_passed: { type: 'boolean' },
    edge_cases_passed: { type: 'boolean' },
    failure_class: { type: 'string', enum: ['mechanical', 'semantic', 'constraint-violation'], description: 'Failure classification if REJECTED' },
    findings: { type: 'string', description: 'Structured findings for repair loop' },
  },
  required: ['milestone', 'verdict'],
}

// Helper: parse milestones from ExecPlan text
function parseMilestones(planText) {
  const milestones = []
  const re = /### M(\d+)[\s—–-](.*?)(?=### M\d|$)/gs
  let match
  while ((match = re.exec(planText)) !== null) {
    const num = parseInt(match[1])
    const body = match[2]

    const testMatch = body.match(/Acceptance Test:\s*`?([^`\n]+?)`?\s*$/m)
    const writesMatch = body.match(/Allowed Writes:\s*(.+)$/m)
    const requiresMatch = body.match(/Requires:\s*(.+)$/m)
    const tierMatch = body.match(/Risk Tier:\s*([ABC])\s*$/m)

    milestones.push({
      num,
      title: body.split('\n')[0].trim(),
      acceptanceTest: testMatch ? testMatch[1].trim() : null,
      allowedWrites: writesMatch ? writesMatch[1].split(',').map(s => s.trim()) : [],
      requires: requiresMatch ? requiresMatch[1].split(',').map(s => parseInt(s.trim().replace('M', ''))) : [],
      riskTier: tierMatch ? tierMatch[1] : 'B',
    })
  }
  return milestones
}

// Stage 1: Plan
async function pevPlan(milestone, planText) {
  const prompt = `You are the Plan phase agent for milestone M${milestone.num} of an ExecPlan.

MILESTONE: M${milestone.num} — ${milestone.title}
ACCEPTANCE TEST: ${milestone.acceptanceTest || 'not specified'}
ALLOWED WRITES: ${milestone.allowedWrites.join(', ') || 'any'}
REQUIRES: ${milestone.requires.map(r => 'M' + r).join(', ') || 'none'}
RISK TIER: ${milestone.riskTier}

Your job:
1. Check if the acceptance test file exists. If not, create it as a FAILING test (red phase of TDD).
2. Check constraints: does this milestone's scope match the Allowed Writes?
3. If Risk Tier is C, report blocked — this needs human steering.
4. Report the plan phase result.

Return structured output with: milestone number, test_written (true if failing test exists), constraints_ok, worktree_path (if created), blocked (reason if blocked).`

  return agent(prompt, {
    label: `plan:M${milestone.num}`,
    phase: 'Plan',
    schema: PLAN_SCHEMA,
  })
}

// Stage 2: Execute
async function pevExecute(planResult, milestone) {
  if (planResult.blocked) {
    return { milestone: milestone.num, tests_pass: false, committed: false, blocked: planResult.blocked }
  }

  const prompt = `You are the Execute phase agent (subagent A) for milestone M${milestone.num}.

MILESTONE: M${milestone.num} — ${milestone.title}
ACCEPTANCE TEST: ${milestone.acceptanceTest}
WORKTREE: ${planResult.worktree_path || 'main tree'}

Your job:
1. Implement code that makes the acceptance test pass.
2. Run the acceptance test — it must pass.
3. Run structural tests — they must pass.
4. Write a Decision Log entry for any consequential choice.
5. Commit with Plan: and Decision: trailers.
6. Log any deviations from the plan as implementation notes.

Return structured output with: milestone, tests_pass, structural_pass, committed, commit_sha, notes.`

  return agent(prompt, {
    label: `execute:M${milestone.num}`,
    phase: 'Execute',
    schema: EXECUTE_SCHEMA,
  })
}

// Stage 3: Verify
async function pevVerify(executeResult, milestone) {
  if (!executeResult.committed) {
    return {
      milestone: milestone.num,
      verdict: 'REJECTED',
      acceptance_test_passed: false,
      edge_cases_passed: false,
      findings: 'Execute phase did not produce a commit.',
    }
  }

  const prompt = `You are the adversarial verifier (subagent B) for milestone M${milestone.num}.
Your job is to FALSIFY the claim that this milestone is complete.

MILESTONE: M${milestone.num} — ${milestone.title}
ACCEPTANCE TEST: ${milestone.acceptanceTest}
IMPLEMENTATION COMMIT: ${executeResult.commit_sha || 'unknown'}

For each criterion:
1. Run the named acceptance test in a clean worktree. If it fails, report the failure.
2. If the test passes, design at least one edge case the test does NOT cover. Run it.
3. State your VERDICT: CONFIRMED (test passes + edge cases hold) or REJECTED.

If REJECTED, classify the failure:
- mechanical: test/implementation has a mechanical error (fix and retry)
- semantic: design quality or subjective judgment issue (needs human)
- constraint-violation: implementation exceeded declared constraints

Do NOT read subagent A's commit messages, decision logs, or implementation notes.
Judge the code by its behavior, not its intentions.`

  return agent(prompt, {
    label: `verify:M${milestone.num}`,
    phase: 'Verify',
    schema: VERIFY_SCHEMA,
  })
}

// Repair loop: decide next action on REJECTED
async function pevRepair(verifyResult, milestone) {
  if (verifyResult.verdict === 'CONFIRMED') {
    return { action: 'flip', milestone: milestone.num }
  }

  const failureClass = verifyResult.failure_class || 'mechanical'
  const findings = verifyResult.findings || ''

  if (failureClass === 'semantic') {
    return {
      action: 'human-todo',
      milestone: milestone.num,
      failure_class: failureClass,
      reason: findings,
      notes_entry:
        `### [human-todo] — Semantic failure in M${milestone.num}\n\n` +
        `B's findings require human judgment:\n\n${findings}\n`,
    }
  }

  if (failureClass === 'constraint-violation') {
    return {
      action: 'update-constraints',
      milestone: milestone.num,
      failure_class: failureClass,
      reason: findings,
      notes_entry:
        `### [deviation] — Constraint violation in M${milestone.num}\n\n` +
        `- **What the plan said:** Constraints declared in milestone.\n` +
        `- **What the code revealed:** Implementation exceeded scope.\n` +
        `- **Conservative choice:** Update constraints to match actual ` +
        `scope, with Decision Log entry.\n` +
        `- **Revisit:** Verify updated constraints are minimal.\n`,
    }
  }

  // mechanical → auto-repair, no notes_entry
  return {
    action: 'retry',
    milestone: milestone.num,
    failure_class: failureClass,
    findings: findings,
    note: `Auto-repair triggered for ${failureClass} failure.`,
  }
}

// Main pipeline
phase('Plan')
log('PEV Orchestrator starting')

// args should contain: { planPath: string } or { planText: string }
const planText = args?.planText || ''
const milestones = args?.milestones || parseMilestones(planText)

if (milestones.length === 0) {
  log('No milestones found. Provide args.milestones or args.planText.')
  return { error: 'no milestones' }
}

log(`Found ${milestones.length} milestones`)

// Topological sort by requires
const sorted = [...milestones].sort((a, b) => {
  if (a.requires.includes(b.num)) return 1
  if (b.requires.includes(a.num)) return -1
  return a.num - b.num
})

// Run PEV pipeline
const results = await pipeline(
  sorted,
  // Stage 1: Plan
  (m) => pevPlan(m, planText).then(r => ({ plan: r, milestone: m })),
  // Stage 2: Execute
  ({ plan, milestone }) => {
    if (!plan) return null
    return pevExecute(plan, milestone).then(r => ({ plan, execute: r, milestone }))
  },
  // Stage 3: Verify + Repair
  ({ execute, milestone }) => {
    if (!execute) return null
    return pevVerify(execute, milestone).then(v => ({
      execute,
      verify: v,
      repair: v ? pevRepair(v, milestone) : null,
      milestone,
    }))
  },
)

// Summarize
const confirmed = results.filter(Boolean).filter(r => r.verify?.verdict === 'CONFIRMED')
const rejected = results.filter(Boolean).filter(r => r.verify?.verdict === 'REJECTED')
const blocked = results.filter(Boolean).filter(r => r.plan?.blocked)

log(`Results: ${confirmed.length} confirmed, ${rejected.length} rejected, ${blocked.length} blocked`)

return {
  total: milestones.length,
  confirmed: confirmed.map(r => r.milestone.num),
  rejected: rejected.map(r => ({ milestone: r.milestone.num, findings: r.verify?.findings })),
  blocked: blocked.map(r => ({ milestone: r.milestone.num, reason: r.plan?.blocked })),
  results,
}
