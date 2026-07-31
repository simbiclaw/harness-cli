# CLAUDE.md

## What this repository is

Three products --`Argus`,`Metis`,`Hermes`-- built end-to-end by Claude Code.  human engineers steer; agents execute. There is no human-written application code in `src/`. The system of record is `docs/`. Now focus on `Argus` first.

## First action on every session

Read the most recent file in `docs/exec-plans/active/` end-to-end. Read its **Surprises & Discoveries** section first. That is the work in flight. If there is more than one active plan, ask the human which to pick up. Do not start work in the middle of a plan you have not read.

## Plan Completion Report

When an ExecPlan completes (all milestones verified and checkbox flipped):

1. **Generate HTML report** using template `.claude/templates/plan-execution-report.html`
2. **Output to** `docs/exec-plans/reports/{plan-id}-report.html`
3. **Include:** milestones timeline, Tier C decisions, surprises, technical debt, lessons learned
4. **Style:** dashboard (not document), with health metrics at top
5. **Add link** in Outcomes & Retrospective section

Use playground skill to render. See `.claude/templates/README.md` for variable mapping.

## Read these before doing any non-trivial work

- `docs/PLANS.md` — the rubric every ExecPlan follows. Read once per session if you are creating or modifying a plan.
- `docs/conventions/ask-threshold.md` — when to proceed silently vs. flag vs. stop and ask.
- `docs/conventions/pev-loop.md` — the Plan→Execute→Verify control loop primitive. Every milestone traverses it. Milestones may carry machine-readable constraint fields (`Allowed Reads`, `Allowed Writes`, `Requires`, `Risk Tier`).
- `docs/conventions/implementation-notes.md` — per-milestone structured log for deviations, discoveries, and human-todos during implementation.
- `docs/conventions/verification-floor.md` — what "done" means for a milestone.
- `docs/conventions/deps-and-secrets.md` — how new dependencies and secrets are handled.
- `docs/conventions/commit-hygiene.md` — commit message format and discipline.
- `docs/conventions/i-dont-know-protocol.md` — how to handle uncertainty in Decision Log entries.
- `docs/conventions/layering.md` — the layered architecture for `src/` and how it is enforced.

## Before writing an ExecPlan

After producing a draft ExecPlan, consult `docs/conventions/ask-threshold.md` and scan every consequential decision in the plan against the Tier C checklist. Any decision that falls under Tier C (new top-level dependency, CLI surface change, config schema change, on-disk format change, stdout format change, >100 line deletion, sensitive-path edit) must go into the **Awaiting Steering** section with the question, the options, and a default-if-not-decided deadline. Do not decide Tier C questions yourself.

## The harnesses, one sentence each

0. **PEV loop** — the control primitive: Plan (failing test + Tier C gate + constraint check), Execute (implement until green, in worktree sandbox, with implementation notes), Verify (adversarial falsification by independent subagent B, gated by structural test). Every milestone traverses all three phases. No flip without CONFIRMED. No implementation without a test. See `pev-loop.md`.
1. **Ask before assuming** — three explicit tiers; default to the most cautious. See `ask-threshold.md`.
2. **Verification floor** — every milestone has a runnable Acceptance Test exercising an externally observable property. See `verification-floor.md`.
3. **Deps and secrets** — new dependencies are vetted by the dep-vetter skill before adoption; secrets never enter the repo. See `deps-and-secrets.md`.
4. **Commit hygiene** — every commit references its ExecPlan and milestone, with a Decision trailer. See `commit-hygiene.md`.
5. **"I don't know" protocol** — Decision Log entries cite evidence, run experiments, or flag uncertainty explicitly. Forbidden phrases enforced by structural test. See `i-dont-know-protocol.md`.
6. **Adversarial verification** — two independent subagents: A implements, B falsifies. Test-first, one test per milestone minimum, E2E with real data after all M's complete. B's prompt is "prove this doesn't work"; A and B never prompt each other. This is the Verify phase of harness #0. See `verification-floor.md`.
7. **Promotion rule** — every rule starts in documentation. When violated twice across different ExecPlans, move it left: documentation → structural test → hook → CI gate → architecture. Do not try harder to remember.
8. All the harnesses in this repository are inspired by and derived from this source material [harness-engineering (read document)](docs/references/harness-engineering-llm.md), when you struggle with a harness-related task, re-read this file for new angles, and try combining previous near-misses.


## The promotion rule

Every rule starts as documentation in `docs/conventions/`. When the same rule is violated twice — by you, in different ExecPlans — the documentation has failed. Open an ExecPlan to promote the rule one step left:

- documentation → structural test (in `.claude/tests/`)
- documentation → hook (in `.claude/hooks/`)
- documentation → CI gate (in `.github/workflows/harness.yml`)
- documentation → architecture (enforced by `import-linter` in `pyproject.toml`)

Do not "try harder to remember." Move the rule into code.

## Skills available

- `.claude/skills/structural-transcription/` — convert support-call audio into structural transcription JSON.
- `.claude/skills/dep-vetter/` — vet a new dependency against the four-check policy.
- `.claude/skills/verifier/` — re-run a milestone's Acceptance Test on a checkbox flip.
- `.claude/skills/garbage-collector/` — recurring scan for cruft (runs nightly).
- `.claude/skills/doc-gardener/` — recurring scan for stale docs and broken cross-refs (runs weekly).
- `.claude/skills/harness-go/` — bootstrap the knowledge spine from PRDs.
- `.claude/skills/harness-go-sync/` — incremental spine regeneration after PRD changes.

## Subagents available

- `.claude/agents/conversation-distillation.md` — distill structural transcription corpora into atomic claims and intent trees.

## What the hooks block

- Edits to paths in `.claude/sensitive-paths.txt` without a resolved "Awaiting Steering" entry in the active ExecPlan.
- Package installs without a dep-vet record in `.claude/decisions/dep-vet-<pkg>.md`.
- `git push --force` unless `CLAUDE_FORCE_PUSH_OK=1` is set, which it never is in normal operation.
- Commits whose message lacks the `Plan:` and `Decision:` trailers.

When a hook blocks you, the error message includes the exact remediation. Do what it says.

## What the structural tests fail on

- Imports in `src/argus/` that violate the layered architecture (enforced by `import-linter`).
- ExecPlan Decision Log entries without a recognized rationale shape (Source / Experiment / `Confidence: low`).
- ExecPlan Decision Log entries containing forbidden phrases ("standard approach", "best practice", etc.).
- Recent commits without `Plan:` / `Decision:` trailers, or with vague subjects.
- Direct dependencies in `pyproject.toml` without a corresponding Decision Log entry and dep-vet record.

When a structural test fails, the error message names the file, line, and required fix.

## Argus eval pipeline — operating invariants

These are the non-negotiable rules derived from the process-derivation pipeline spec (`docs/PRD/process-derivation-pipeline-spec-v5.html`). Every edit to `src/argus/` must preserve them. The spec is the contract; the bullet list below is the operating summary — when in doubt, the spec governs.

### Seven invariants (§1)

| Tag | Name | Rule |
|---|---|---|
| **I1** | Quarantine | Model nondeterminism exists only in S2 (the proposer, `io/`). S3 (ground), S4a (score), S4b (adjust), and S5 (route) are pure functions of their inputs. A module in `core/` that imports the model client is an architecture violation. |
| **I2** | Anchor-or-quarantine | Every finding references a real transcript span (exact-quote verified) and a real INTENTS node at the pinned git-SHA epoch, or it is moved to the `ungrounded` bucket and routed to a human. Findings are never silently dropped. |
| **I3** | Shipped score = pure re-derivation | `raw = score(facts, rubric)`, then `adjusted = adjust(raw, history)`. Both are pure functions. `score` never receives history. The model MAY propose a score (quarantined, D7) — a proposed score enters neither stage and is never the shipped number. Same grounded findings + same rubric version + same anchored precedents ⇒ identical `raw` and `adjusted`. |
| **I4** | Pinned referents | Each evaluation pins the `INTENTS/` tree at a single git-SHA epoch (`EPOCH.yaml`). Re-running against the same epoch reproduces the same grounding outcomes. |
| **I5** | Replayability | The stored FindingGraph + `intents_sha` + rubric version re-derive the identical EvaluationResult forever. The `replay_hash` is a function of grounded inputs + anchored precedents only — never of `proposed_score`. |
| **I6** | Independence-weighted corroboration | Multi-anchor confidence is a pure, independence-weighted function of the signals. Redundant signals (same model-judged text) contribute zero — no number of correlated re-reads manufactures confidence. Corroboration is orthogonal to the §6 agreement gate: it may clear a per-finding `finding_thin` deferral but never a criterion's `criterion_below_tau` deferral (D4). |
| **I7** | Ground evidence, not numbers | S3 grounds the violation, span, and criterion a finding rests on — never a bare score (a digit has no span). A model-proposed score is grounded only by grounding its evidence; the pure stages re-derive the number. No code path passes a model-proposed score through S3 into the verdict (D8). Proposed-vs-derived divergence is logged as a drift probe, never as a result. |

### Layer fences

These are load-bearing — they keep the model quarantined and the pure stages pure.

| Fence | Rule |
|---|---|
| `core ✗ model_client` | No module in `src/argus/core/` imports `anthropic` or any LLM client. This is what keeps v6's "core is pure" claim true. The model touches only S2, which lives in `io/`. |
| `grounding ✗ proposer` | The grounding gate (S3, `core/grounding.py`) never imports the proposer. |
| `grounding ✗ matching_model` | The exemplar/case match that produces a correlated signal happens in the proposer (S2), never in the gate (S3). The gate only verifies that the proposer's signals resolve and co-locate (D3). |
| `aggregate ✗ model_client` | The corroboration aggregator (`core/corroboration.py`) is pure — no model, no clock, no RNG. |

### Corroboration weights and debt

- Independent signals (acoustic measurement, lexical/lookup/ordered-match): weight **1.0**
- Correlated signals (Error Case, Best Practice — model-judged match to confirmed referent): weight **W_C = 0.4 PROVISIONAL** — log the debt; the correct value is `1 − corr(matcher_error, proposer_error)` measured on a human-labeled sample
- Redundant signals (another model-judged text criterion on the same span): weight **0.0** — soft⊕soft = 0 (D5)
- Corroboration changes **routing** (clears `finding_thin`), never the **deduction** (a violation's deduction is the rubric's weight for its anchor, regardless of how many instruments saw it)

### Deferred-verdict rules

- `defer_reason: "finding_thin"` — the finding's single-channel evidence is insufficient; an independent corroborating anchor can clear this
- `defer_reason: "criterion_below_tau"` — the criterion itself is untrusted (κ < τ); **no amount of corroboration clears this** (D4 — the two axes are orthogonal)
- `defer_reason: "ungrounded"` — the finding anchors to nothing real (I2); always routes to human
- Auto-final requires **both** axes clear: coverage gate (no ungrounded, no deferred) AND criterion health gate (every cited criterion `trusted`). Neither substitutes for the other (D10)

### Hard prohibitions

- **No write path into INTENTS/.** Argus is a consumer — zero code in `src/argus/` opens an INTENTS file for writing (D15, S1 fixture). Corrections re-enter via upstream write-time epoch commits (S6, ADR-0003).
- **No Argus-vs-Argus voting.** Agreement is Argus-vs-human, never N model samples voting (§6.4). Soft⊕soft corroboration (D5) is the same prohibition in a different costume.
- **No per-call residue gate.** Per-call residue is not buildable — the checks cannot report what they missed (D10). Coverage is computable per call; escape rate is estimable over a stream. Do not confuse them.
- **Resample variance never touches routing.** Model self-disagreement measures difficulty, not residue (D12/C4). Log it for triage priority; never wire it to auto-final.
- **No precedent in the raw lane.** `score()` never receives history. The runtime purity assert (§5) rejects any raw-lane verdict citing a precedent — belt and suspenders with the signature.

### v6 conformance

- The `IntentsNode` schema accommodates BOTH current v1-format rubric entries AND enriched authoring-schema entries the companion 9003 will compile. Judgment-layer fields (`corroborators`, `agreement`, `applicability_gate`, `severity_map`, `gap_type`, `escape_tier`, `data_dependency`) are Optional with `default=None`.
- Q1 default: nine v6 modules → three category readers (rubric, facts, history). Flag count refs with `# Q1` until `expertise-library.md` reconciles 8-vs-9.
- The companion 9003 (`soft-criteria-authoring-spec-v4.html`) must land enriched `_rubric/` nodes before the judgment-layer gates (M5) activate. Until then, every soft criterion correctly returns `deferred`.

`Source: docs/PRD/process-derivation-pipeline-spec-v5.html` · `docs/adr/0001`…`0004` · `docs/exec-plans/active/9002-implement-argus-eval-pipeline.md`

## Bash: Write Scripts to Files, Not Inline

Several Bash patterns trigger circuit-breaker permission prompts that cannot be pre-approved:

- `command_substitution` — `$()` nested in commands
- `simple_expansion` — `$var` inside quoted arguments
- `source` — `source file` or `. file`
- `#` comments inside quoted `python3 -c` strings

**Rule: when a Bash command does more than a simple one-liner, write it to a temp `.sh` file first, then execute that file.** Example:

```bash
cat > /tmp/script.sh << 'EOF'
# your logic here, with $() and $vars freely
EOF
bash /tmp/script.sh
```

A single `bash /tmp/script.sh` avoids all the inline circuit-breakers. Same for Python: write to a `.py` file, then `python3 /tmp/script.py`.

In CI workflows, prefer `--pretty=tformat:` over `--pretty=format:` in `git log` — `format:` omits newline terminators between commits, which concatenates hashes when piped through `tac` or `grep`.

## Behavioral guidelines to reduce common LLM coding mistakes.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

Last reviewed: 2026-07-08.
