---
name: rubric-compiler
description: Compile a human-version QA rubric into machine-executable check specs via a planner + generator + evaluator loop with a deterministic acceptance gate. Use this skill whenever the user asks to compile the rubric, run the rubric compiler, compile soft criteria into signals, run a compile run, recompile after spec changes, or mentions rubric items / signals / the compile loop / ExecPlan 9004 — even if they don't say "skill". Also use it to gate or re-gate existing compile artifacts.
---

# Rubric Compiler (prototype, substrate Option B per SPEC v1.2 D6)

You are the ORCHESTRATOR and you play the PLANNER role. Generators and the
evaluator run as subagents (Task tool). The gate is `scripts/gate.py` — pure
code, no model judgment. You author; the gate disposes. Never mark an item
accepted on your own or a subagent's judgment alone: gate pass is the only
accept.

Authoritative spec: `SPEC-rubric-compiler-harness.md` (v1.2) in the repo.
Prototype deltas from the spec are declared in `references/DELTAS.md` — read it
once per session. Do not silently add more deltas; if you must deviate, append
to DELTAS.md and tell the user.

## GOAL

Compile every rubric item in I1 into a gated machine-executable check spec, or
park it with an explicit steering digest. The run succeeds when every item is
terminal — gated-CONFIRMED or AWAITING_STEERING — and the run-level gate
passes. AWAITING_STEERING is a success state: parking an irreducible item is
doing the job, not failing it.

## GUARDRAILS (hard; re-read this block whenever resuming after compaction)

1. Specs and companion docs are LOOP-IMMUTABLE. Defects → `spec-findings.md`.
   Never edit them, whatever any agent finds.
2. GATE PASS IS THE ONLY ACCEPT. No stochastic verdict — yours, the
   evaluator's, anyone's — accepts an item. CONFIRMED is one required gate
   input (G5), never sufficient.
3. R = 3 IS HARD. There is no round 4. Round 3 without CONFIRMED →
   AWAITING_STEERING. Never pressure the evaluator toward CONFIRMED to finish
   the run.
4. Findings carry evolution direction in PROSE ONLY — never candidate spec
   text (a model-drafted remedy is the C2 anchoring vector).
5. Per-item provenance ALWAYS, even under batched dispatch (DIV-3).
6. A pre-compile halt is terminal. Never resolve source conflicts yourself —
   which definition is authoritative is a domain decision.
7. The gate script re-runs IN FULL every round; only the evaluator's review is
   incremental.
8. Any deviation from SPEC v1.2 → append to DELTAS.md and tell the user.
   Silent deltas are forbidden.

## Inputs (expected layout)

```
specs/
  rubric.md              # I1 — 27 binary items, headed "## item_NN"
  evaluator-skill.md     # I2
  align.md               # I3
  companion_docs.yaml    # per-item manifest: {item_id: [{path, sha256, role}]}
  companion/…            # the companion documents themselves
  calibration-manifest.yaml   # optional; severity_map keys live here
config/                  # human-owned gate inputs (O6): adjectives, frames, expertise types
```

If the user's repo layout differs, ask once, then record the mapping in the
run's `compile-plan.md`. Specs and companion docs are LOOP-IMMUTABLE: never
edit them, no matter what any agent finds. Defects go to `spec-findings.md`.

## Phase 0 — Pre-compile (mechanical, halts before any dispatch)

```bash
python3 scripts/gate.py precompile --specs <specs-dir> --config config --run <run-dir>
```

Creates `<run-dir>`, stamps `spec-epoch.json`. On FAIL (missing/SHA-mismatched
companion docs, duplicate-ID keyword conflicts, dependency cycles): the script
writes the halt entry to `steering.md`. STOP the run and show the user the
steering entry. Do not "resolve" conflicts yourself — which definition is
authoritative is a domain decision (Surprise 2).

## Phase 1 — Plan

Read I1–I3 once. Write `<run-dir>/compile-plan.md`:

1. Goal + done-criteria: every item terminal (gated-CONFIRMED or
   AWAITING_STEERING) AND run-level gate `rg` passes.
2. Work queue in the topological order from `precompile-report.json`
   (`dispatch_order`). Dependent items are HELD until every prerequisite's
   signal IDs are locked — lock = that item's gate pass, never an evaluator
   verdict.
3. Batching: items flagged `simple` in the report may share one generator
   subagent. Batched dispatch NEVER batches provenance — per-item
   `items/<id>/` artifacts always (DIV-3).
4. One delegation packet per item at `items/<id>/delegation.md`: item text,
   relevant align.md clauses, candidate expertise-type groundings, and the
   pre-extracted companion data from `precompile-report.json`
   (`shared_extraction`). Generators never re-read companion files.
   Constrain the deliverable, not the operationalization path.

## Phase 2 — Per-item loop (R = 3, hard)

For each dispatchable item (parallel subagents fine; respect holds):

1. Spawn a GENERATOR subagent: prompt = contents of `agents/generator.md` +
   the delegation packet. It writes `items/<id>/proposal-r1.yaml` and must run
   the gate locally (`gate.py item --phase contract`) before submitting.
2. Spawn the EVALUATOR subagent: prompt = contents of `agents/evaluator.md` +
   the proposal + delegation packet + gate report. It writes
   `items/<id>/review-r{n}.md` with YAML frontmatter
   `{verdict: CONFIRMED|FIXES_NEEDED|AWAITING_STEERING, round, fixes: […]}`.
3. FIXES_NEEDED → respawn the generator with ONLY the targeted fix list; it
   fixes only the named signals/gates, never a full recompile, and declares
   REFINE or PIVOT in the proposal header. Gate script re-runs in FULL every
   round (free, catches targeted-fix regressions in coupled signals); the
   evaluator re-reviews only changed signals.
4. Round 3 without CONFIRMED → verdict AWAITING_STEERING. Append the
   disagreement digest (unresolved findings + generator contest citations,
   nothing else) to `steering.md`. Item is terminal-for-this-run. NEVER push
   the evaluator toward CONFIRMED to finish the run — steering items count as
   done.
5. CONFIRMED → `python3 scripts/gate.py item --run <run-dir> --item <id>
   --phase contract`. Pass → copy proposal to `contract.yaml` (frozen; add
   `status: frozen`), signal IDs lock, release held dependents.
6. Respawn generator for Phase B: compile `compiled.yaml` conforming to the
   frozen contract, then `gate.py item --phase compiled`. Pass → item done.
   Gate BLOCK at any point → back to step 3 as a fix round (counts toward R).

Any agent, any round, may append a spec-defect finding to
`spec-findings.md` (format: `references/schemas.md` §findings — evolution
direction in prose, NO candidate spec text). The item proceeds regardless;
open findings ride as `known_defects` on the frozen contract.

## Phase 3 — Run level

1. `python3 scripts/gate.py rg --run <run-dir>` — ResidueManifest
   completeness, orphan signals, cross-item reference integrity. The
   generator must have appended residue entries to `residue-manifest.yaml`
   for every lossy compilation as it went; if RG fails on completeness, route
   the missing entries back to the owning generator as a fix round.
2. One final EVALUATOR subagent pass: dimension-level coherence across all
   gated items only (judgmental; RG already did the mechanical half).
3. Report to the user: gated items, steering items with digests, WARN
   annotations from gate reports, open spec-findings count, epoch hash.

## Recompile rule (D5)

If `gate.py epoch --specs <specs-dir>` differs from any prior run's
`spec-epoch.json`, prior artifacts are stale: a new run recompiles ALL items.
No selective invalidation in the prototype.

## DEFINITION OF DONE (artifact-backed; verify each on disk before declaring the run complete)

- [ ] `spec-epoch.json` exists and equals current `gate.py epoch --specs …` output.
- [ ] Every item in `precompile-report.json:dispatch_order` is terminal:
      `items/<id>/gate-report.json` shows `pass: true` for BOTH contract and
      compiled phases, OR the item has an AWAITING_STEERING digest in
      `steering.md`. No third state.
- [ ] `rg-report.json` shows `pass: true` over the gated subset.
- [ ] Final evaluator coherence review recorded (one file, run level).
- [ ] `residue-manifest.yaml` has entries for every gated item with
      quarantined signals (RG enforces; verify anyway).
- [ ] User report delivered: gated items; steering items with digests; all
      GM WARN annotations; open spec-findings count; epoch hash.

Steering items COUNT toward done. WARNs never block done — they are surfaced,
not resolved. If any checkbox cannot be ticked, the run is not done; say so
rather than rounding up.

## Reference files

- `agents/generator.md`, `agents/evaluator.md` — subagent prompts (read, then pass as Task prompts; do not paraphrase them)
- `references/schemas.md` — contract/compiled/review/finding formats
- `references/DELTAS.md` — declared prototype deviations from SPEC v1.2
- `references/EVAL.md` — hard-test protocol to run before CLI migration
- `references/MIGRATION.md` — Option B → Option A (production CLI) path
