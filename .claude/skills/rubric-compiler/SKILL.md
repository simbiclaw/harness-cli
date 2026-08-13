---
name: rubric-compiler
description: Compile a human-authored Specific QA Rubric (1/0/NA scored items with qualitative pass/fail standards),
  a Generic Evaluator Skill template, and an align.md item→dimension map into
  enriched _rubric/ nodes through the GAN-style Planner/Generator/Evaluator
  compile loop over the deterministic 9003 core. Use when the human asks to
  compile a soft-criteria rubric, run the 9003 compiler, author FAIL/EXCELLENCE
  signals for an item, plan the compile order for a dependency pair, produce
  the residue manifest, or apply a targeted fix to a signal after evaluation.
  Invoked by the model, never by a hook.
---

# Rubric-Compiler Skill

Compile a human-authored soft-criteria rubric into machine-executable
`_rubric/` nodes by running the patch-2 GAN-style compile loop (Planner →
Generator → Evaluator, max 3 feedback rounds) over the deterministic 9003
core (M1–M5). Invoked by the model, never by a hook. Hooks cannot invoke
skills — the model invokes this skill manually.

## When to use this skill

- The human asks to compile a soft-criteria rubric into `_rubric/` nodes
  ("run the 9003 compiler", "compile this rubric", "author the signals for
  item 20").
- A companion document changed and an item needs recompiling.
- The Evaluator found an issue and a targeted fix is requested
  (`{signal_id, field, issue, suggested_fix}`).
- A residue manifest must be produced for what the compilation left behind.

Do NOT use for: runtime evaluation of calls (that is 9002), calibration
manifest injection (that is M7's channel), or hand-editing evidence/lexicon
files outside a compile run.

## Inputs

Three compiler inputs plus companion documents:

| Input | File | Supplies |
|---|---|---|
| Specific QA Rubric | `specific-rubric.yaml` | `1/0/NA` scored items with values, NA conditions, pass/fail standards |
| Generic Evaluator Skill | `generic-skill.yaml` | 4 dimensions, 1–10 scale, failure signatures (`source: ai_template`) |
| align.md | `align.md` | item → dimension mapping (`—` = no dimension covers) |
| Companion docs | `companions/*.md` | machine-header keyword sets (S1: SHA-256 pinned per item's `companion_docs`) |

A practice fixture set ships with the skill at `fixtures/` — use it for dry
runs before touching real inputs.

## Preconditions

- `[ASSERT]` M1–M5 deterministic core is landed (`src/argus/core/compiler/` —
  validator, signals, classify, agreement, bridge). The runner executes the
  real core chain (M6a `Requires: M5`); if the core is missing, stop and
  report: "M6a Requires: M5 — land M1–M5 first."
- `[ASSERT]` The three inputs exist and parse (run
  `scripts/run_compile.py plan --inputs <dir> --out <dir>` to check).
- `[ASSERT]` No conflicting milestone is currently in flight.
- For real-tree runs: `INTENTS` symlink resolves to the external tree.

## The compile loop

### Planner (runs once)

1. **Companion docs (S1)** — resolve every item's `companion_docs`, pin
   SHA-256 of each document, record `{document, role, sha256}` in the plan.
2. **Source validation (S2)** — run `scripts/run_compile.py plan`; it calls
   `validate_sources` over the companion machine headers. On conflict
   (trigger ID redefined with different keywords): **halt** — do not pick a
   winner. Write the conflict report (the runner emits
   `conflict-report.yaml`), open an `Awaiting Steering` entry naming both
   definitions with source lines, and stop.
3. **Dependency scan + topological order (S3)** — Items 20→21 and 22→26:
   dependent items compile only after prerequisite signal IDs are locked.
   Cycle → halt with a cycle report. Batch structurally simple items
   (no companion, no dependencies, lexical values) into one Generator pass.

### Generator (one pass per item or batch)

Run `scripts/run_compile.py generate --inputs <dir> --out <out> --item <id>`
(generate reads the plan written by `plan` from `--out`; there is no `--plan`
flag). The runner wires the deterministic chain: decompose → B-F audit →
assign facets →
classify corroborators → declare residue → classify gap → assign escape tier
→ seed agreement → set deduction → bind item → compile applicability gate →
check dimension coverage → extract values; per-dimension hard-fail rules are
synthesized (never copied) for the freeze step.

**B-E refinement (model-judged, D12 — the Generator's authoring step).** The
deterministic chain emits template-level signals; for every standard clause
that landed in the "unmatched standard" / "model-judged" fallbacks, the
Generator performs B-E: decompose the clause into observable signals, ONE per
clause, each carrying:
- `id` — item-XX-SNN sequence (F1..Fn / E1..En convention acceptable)
- `description` — an OBSERVABLE pattern (no evaluative adjectives — AUTH-1):
  name what a proposer could find in a transcript and what a gate could
  verify. Example: "处理或解释死板" → "agent 指导全程使用通用模板话术，未回引客户
  描述的具体细节（产品名/版本号/错误码）"
- `severity` — major / minor
- `decomposed_from` — the exact pass/fail_standard clause it traces to
- `gate_checkable_test` — {proposer_can_find_span, gate_can_verify} (Q1/Q2)
- `checkable` / `audit_result` — pass / split / model_only per the B-F audit

Signals that stay conclusion-only are `checkable: False` (quarantined to S2).
Refined signals REPLACE the deterministic fallbacks (never duplicate them);
the deterministic lexical/ordered signals stay. Every intervention is
recorded: `{"step": "b-e-refine", "item": <id>, "rationale": ...}` in
compile-decisions.jsonl. The refined node must pass
`scripts/run_compile.py evaluate` before freezing. The target shape follows
`docs/retrospectives/item-18-example-v2.yaml` (4 FAIL + 3 EXCELLENCE
clause-traced signals with gate_checkable_test).

Model judgment is confined to authoring-time gaps ONLY (B-E refinement
above, signal-split adjudication, exclusion-set polish). Every such
intervention is recorded as a decision-log entry. When the Evaluator returns
fixes, use targeted-fix mode
(`--fix '{"signal_id": "22-S01", "field": "description", "issue": "AUTH-1 …",
"suggested_fix": "transcript contains one of the named phrases: 您别着急"}'`)
— never a full recompile.

### Evaluator (single quality gate)

Run `scripts/run_compile.py evaluate --out <out>` — the M1 validator
(AUTH-1..10 plus S1/S3/S4 checks) and S5 adversarial exclusion-set cases
(warn-level, flagged for human review, non-blocking). Verdicts: CONFIRMED /
AWAITING_STEERING. Blocking findings trigger up to 3 targeted-fix rounds
(`generate --fix`) before the loop escalates to AWAITING_STEERING. Review
simple items batched; isolate complex items (20, 21). One global consistency
pass after all items CONFIRMED: the manifest must cover every lossy item
(AUTH-5 — no compile run without a residue manifest).

## Decision log

Every model-judged step gets one entry. The runner writes machine-assertable
lines to `compile-decisions.jsonl` in the output dir; the model also appends
human-readable markdown entries under
`docs/exec-plans/active/9003-implement-soft-criteria-compiler-notes/compile-decisions/`.

## Output contract (frozen)

The final outputs are frozen — do not deviate:

- Nodes → `_rubric/rules_criteria/{dimension}/item-XX.yaml` (per-dimension,
  patch-1 D1)
- Hard-fail gates → `_rubric/gates/{dimension}.yaml` (D3 — never on a node)
- Residue manifest → `_meta/residue-manifest.yaml` (always, AUTH-5)
- Written through the `INTENTS` symlink into the external tree; recompile =
  in-place overwrite + new epoch commit in the external repo (round-3
  decisions 3/4)
- `edited_by_human: true` files are never overwritten (D8)
- No node carries `hard_fail_rule` or `w_c` (patch-1 D3/D6)

Headless staging (never touches the real tree):
`scripts/run_compile.py loop --inputs <dir> --out <dir> --evaluator mock
--no-epoch-commit`

## What this skill must NOT do

- Resolve source conflicts autonomously — halt and open Awaiting Steering.
- Invent item values (M8 rule — never fabricate rubric content).
- Write to `_rubric/` outside a compile run.
- Overwrite `edited_by_human` files.
- Run during evaluation.
- Call the model during the deterministic compile path.

Last reviewed: 2026-08-12
