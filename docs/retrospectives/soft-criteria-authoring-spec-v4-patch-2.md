# Patch 2 — Compiler Pipeline Gaps: Source Validation, Dependencies, Gate-Checkability, and Self-Audit

**Patches:** `soft-criteria-authoring-spec-v4.html`
**Date:** 2026-07-16
**Status:** draft
**Source:** Adversarial review of Item 20/21 compilations (v1 → v2) + companion doc ambiguity discovered during review

---

## Context

Patch 1 (D1–D12) defined the operationalized artifact structure and the per-item compilation procedure. The adversarial review of Items 20 and 21 exposed six surprises that the procedure does not handle — gaps in the compiler pipeline itself, not in individual Item compilations. These gaps affect every Item that depends on companion documents, has cross-Item dependencies, or contains signals that claim gate-checkability while hiding model dependencies.

---

## Surprise 1: Hidden companion document dependency

**What happened:** Compiling Items 20/21 required a companion document (营销话术.md) that is not declared anywhere in the rubric or the compiler procedure. The rubric text alone — "对用户表达中明显的潜在营销机会置之不理" — does not enumerate what those opportunities are. The standard scripts live entirely outside the rubric, in a companion document.

**Compiler gap:** No mechanism exists to (a) declare which companion documents an Item needs, (b) verify those documents are present and version-pinned before compilation begins, or (c) report missing companion documents to the human.

### Recommendation: Per-item companion document manifest

Add a pre-compile step that checks a `companion_docs` declaration per Item. The compiler halts if a required companion document is missing or its SHA doesn't match the pinned version, and reports the gap before starting any compilation work.

```yaml
item_20:
  companion_docs:
    - path: "docs/PRD/eval/营销话术.md"
      sha: "<pinned at compilation epoch>"
      role: "standard_scripts"
```

The companion document manifest is defined once by the human when an Item is first set up for compilation, then version-pinned at each compile run. The compiler validates existence and SHA match before processing the Item.

---

## Surprise 2: Source document contradiction — halt and await human decision

**What happened:** A companion document contained two conflicting keyword definitions (T001-T005 vs. VAS-001-VAS-005) with only 7 shared keywords across 49+ combined. The compiler silently selected the first set, producing a compilation that was internally consistent but objectively incomplete. The adversarial reviewer was the first to flag this.

**Compiler gap:** The compiler has no source validation step. When companion documents contain internal contradictions, the compiler cannot resolve them autonomously — the choice of which keyword set is authoritative is a domain decision, not a technical one.

### Recommendation: Pre-compile source validation with halt-on-conflict

The compiler runs a pre-compile validation pass over all companion documents before any Item compilation begins:

1. **Duplicate detection:** For each trigger/rule ID, check whether multiple definitions exist with different keyword sets or thresholds.
2. **On conflict:** Halt compilation. Populate an `Awaiting Steering` entry listing the conflicting definitions, their source locations, and the options for resolution.
3. **On human decision:** Resume compilation using the selected authoritative definition.

This is the only surprise that requires a human decision. All other surprises can be resolved by automated compiler passes.

---

## Surprise 3: Cross-Item compilation order dependency

**What happened:** Item 21's `applicability_gate` depends on Item 20's signal IDs (S01_trigger_detected, S04_agent_responded). The per-item compilation loop in §3.6b assumes Items are independent — but some Items form pairs (20+21, 22+26) where the dependent Item cannot be compiled until the prerequisite Item's signal IDs are locked.

**Compiler gap:** The compilation procedure has no concept of dependency ordering. If Items 20 and 21 are compiled in parallel, Item 21's gate may reference signal IDs that haven't been finalized yet, or may use stale IDs from a previous compile run.

### Recommendation: Dependency-aware topological compilation order

Before the per-item loop begins, the compiler scans all Items' `applicability_gate` fields for cross-Item signal references (pattern: `item_\d+\.S\d+` or explicit `depends_on` declarations). It builds a directed acyclic graph (DAG) and compiles in topological order:

```
Round 1: Compile all independent Items (no cross-Item references in their gates).
          Lock their signal IDs.

Round 2: Compile dependent Items, referencing locked signal IDs from Round 1.
```

If a cycle is detected (A depends on B which depends on A), the compiler halts and reports the cycle. Dependency detection is a pure syntactic scan — no semantic understanding required.

---

## Surprise 4: "Gate-checkable" signals routinely hide model dependencies

**What happened:** In the v1 compilations, 8 of 11 signals across Items 20 and 21 failed the gate-checkable test despite being declared as checkable. The failures fell into two patterns: (a) the signal's precondition required model judgment to identify (SIG-A: "customer context" requires NLU), or (b) the gate check was lexical but the signal claimed to verify a semantic property (SIG-C: claimed "context-specificity" but only checked keyword presence).

**Compiler gap:** The B-E Signal Decomposition step produces signals, but there is no subsequent step that audits whether each signal genuinely passes the Q1/Q2 gate-checkable test. Signals that need splitting (part lexical, part model) are emitted as-is, producing compilations where claimed determinism does not match actual capability.

### Recommendation: B-F Gate-Checkability Audit step

Insert a step after B-E (Signal Decomposition) and before facet assignment:

```
B-E: decompose_signals()      → generates FAIL/EXCELLENCE signals
    ↓
B-F: audit_gate_checkable()   → tests each signal against Q1/Q2
    ├── Q1: Can a proposer find a transcript span?
    ├── Q2: Can a gate deterministically verify that span?
    └── Output per signal: {pass, split_needed, model_only}
    ↓
B-G: assign_facets()          → assigns facets to audited signals
```

When B-F returns `split_needed` for a signal:
- The compiler automatically generates a lexical sibling (checkable=true) and a model_based sibling (checkable=false, quarantined to S2).
- Example: SIG-A "context_triggered_recommendation" splits into SIG-A1 (temporal proximity, gate-checkable) and SIG-A2 (context adaptation quality, model_based).

When B-F returns `model_only`:
- The signal is explicitly marked `checkable: false` and routed to the S2 quarantine.
- No claim of gate-checkability is made.

---

## Surprise 5: Chinese pragmatics fragility in lexical exclusion sets

**What happened:** SIG-B used an AND-NOT exclusion set to distinguish "specific recommendation" from "letting the customer choose." The pattern correctly excluded "您可以选择" — but a combined expression like "我建议您可以选择办理移动证书" (which IS a specific recommendation in Chinese customer service pragmatics) contains both the inclusion pattern (建议) and the exclusion pattern (可以选择) and would be incorrectly excluded. This pattern — recommendation language combined with polite choice-offering — is common in Chinese service interactions.

**Compiler gap:** Lexical gates with AND-NOT exclusion sets have no automated verification that the exclusion doesn't over-fire on legitimate cases. The exclusion set is authored but never adversarially tested.

### Recommendation: Pragmatic adversarial test generation for exclusion sets

The compiler's validator runs an automated adversarial test for every signal that uses an AND-NOT exclusion pattern:

```
For each exclusion pattern P in signal.exclusion_set:
    Generate adversarial case: embed P inside a known-positive pattern
    Example: "我建议" + "您可以选择" + "办理移动证书" → should PASS
    Compare: gate verdict vs. expected verdict
    If mismatch → flag signal for human review

For each exclusion pattern P alone:
    Generate pure-exclusion case: P without any positive pattern
    Example: "您可以选择解锁或办移动证书，随您方便" → should FAIL
    Compare: gate verdict vs. expected verdict
    If mismatch → flag signal for human review
```

This is a compiler validator capability, not a per-Item step. It runs once per compile run, across all signals that use exclusion sets. Flagged signals are reported but do not block compilation — they are routed to human review alongside the compiled output.

---

## Surprise 6: The adversarial reviewer found problems the compiler should have caught

**What happened:** The adversarial reviewer (a separate subagent) found all six surprises. The compiler itself caught none of them — not the source document ambiguity, not the gate-checkability failures, not the adjective violations that the compiler's own comments acknowledged but didn't fix. This pattern maps directly to the "adversarial verification" discipline in CLAUDE.md: "A implements, B falsifies."

**Compiler gap:** The compiler trusts its own output. It has no self-audit pass that verifies the quality of what it produced before marking compilation complete. The adversarial reviewer is necessary precisely because the compiler doesn't check itself.

### Recommendation: Compiler self-audit pass

After writing YAML output and before marking the Item as compiled, the compiler runs an automated self-audit. This does not replace the adversarial reviewer (which does deeper, more creative falsification) — it handles the repeatable, automatable checks that should never require a separate subagent to catch:

| Check | Method | Severity |
|:---|:---|:---:|
| Gate-checkability audit | B-F: Q1/Q2 test per signal | **Block** — do not write YAML if any signal fails without split/defer |
| AUTH-1 adjective scan | Search signal descriptions against an adjective list (灵活, 积极, 混乱, 死板, substantive, engaged, adapted, enthusiastic, proactive, flexible) | **Block** — reject signal if adjective present without observable referent |
| Trigger completeness | Compare compiled trigger_keywords against companion document keyword sets; report coverage gaps | **Warn** — report missing coverage, do not block |
| Signal coverage | Check each fail_standard / pass_standard clause has at least one signal mapped to it | **Warn** — report uncovered clauses |
| Gate logic consistency | Verify applicability_gate logic doesn't contradict itself (e.g., "gate prevents punishment but not reward" when gate unconditionally fails) | **Block** — contradictory gates produce unsound evaluations |
| Exclusion set adversarial test | Run pragmatic adversarial cases per Surprise 5 | **Warn** — flag over-firing patterns |

The self-audit pass runs after YAML generation, before the compilation is marked complete. Block-level failures prevent the Item from being written to `_rubric/`. Warn-level findings are appended to the Item's compilation report for human review but do not block.

---

## Combined compiler pipeline (with Patch 2 additions)

```
PRE-COMPILE:
  ├── Source validation: verify companion docs exist, SHA match, no internal conflicts
  │     └── On conflict → halt, populate Awaiting Steering
  ├── Dependency scan: detect cross-Item signal references, build DAG
  └── Topological sort: order Items for compilation

PER-ITEM COMPILE (topological order):
  for each item (Round 1: independent, then Round 2: dependent):
      A1-A7, B-A through B-E    (per §2.6 + D12)
      B-F: audit_gate_checkable()  ← NEW (Surprise 4)
      B-G: assign_facets()          ← (existing, renumbered)
      gap classification
      emit YAML

POST-COMPILE (per item):
  └── Self-audit pass (Surprise 6):
        ├── Gate-checkability (block)
        ├── AUTH-1 adjective scan (block)
        ├── Trigger completeness (warn)
        ├── Signal coverage (warn)
        ├── Gate logic consistency (block)
        └── Exclusion set adversarial test (warn)

POST-COMPILE (global):
  └── Adversarial reviewer (external subagent, unchanged)
```

---

## Updated AuthoredNode schema (Patch 2 additions)

| Field | Status | Rationale |
|-------|--------|-----------|
| `companion_docs` | **NEW** | S1: list of companion documents with pinned SHA and role, validated pre-compile |
| `depends_on` | **NEW** | S3: explicit list of Item IDs whose signal IDs this Item references in its applicability_gate |
| `signal.checkable` | **ENRICHED** | S4: after B-F audit, each signal explicitly declares `checkable: true` (gate-verifiable) or `checkable: false` (model-only, quarantined). No implicit claims |
| `signal.audit_result` | **NEW** | S4/S6: B-F audit output — `pass`, `split` (auto-split occurred), or `model_only` |
| `self_audit_report` | **NEW** | S6: per-item compilation report with block/warn findings from the self-audit pass |

---

## Claude Code Execution Architecture — GAN-Inspired Multi-Agent Loop

### Motivation

Patch-2 defines a compiler pipeline with four phases (pre-compile, per-item compile, post-compile self-audit, adversarial review) and a feedback mechanism (Surprise 6: the adversarial reviewer found problems the compiler should have caught). The natural execution substrate is Claude Code's dynamic workflow with Planner → Generator → Evaluator multi-agent loop — a GAN-inspired architecture where a Generator produces compilations and an Evaluator adversarially drives them toward stronger outputs through a feedback loop.

### Prompt comparison: delegation vs. prescription

Two prompts were evaluated for the same task:

**Prompt 1 — Delegation (Claude designs the workflow):**

```
ultracode: implement the Patch-2 compiler pipeline from docs/retrospectives/soft-criteria-authoring-spec-v4-patch-2.md.
```

**Prompt 2 — Prescription (human designs the architecture):**

```
use a workflow to build Planner + Generator + Evaluator multi-agent loop per patch 2:
1) Planner dispatches Items to independent Generator subagents
2) Evaluator reviews first-done-first
3) Feedback loop drives Generator toward stronger outputs
4) /goal: don't stop until all adversarial review findings addressed
```

| Dimension | Prompt 1 (Delegation) | Prompt 2 (Prescription) |
|:---|:---|:---|
| Orchestration topology | Claude chooses — likely linear `pipeline(items, compile, audit, review)` | Human-specified Planner→Generator→Evaluator triangle with feedback loop |
| Improvement mechanism | None built in. Each Item passes through once; defects are recorded, not fixed | Feedback loop: Evaluator → Generator fix → Evaluator re-review → CONFIRMED |
| Termination condition | Workflow completes when all items pass through all stages | `/goal` — stops only when all adversarial findings are addressed |
| Token efficiency | Lower overhead per run, but defects require human re-prompting | Higher overhead per run, but defects are auto-fixed within the loop |
| Adversarial alignment | Partial — review happens but doesn't drive improvement | Full — directly implements "A implements, B falsifies" from CLAUDE.md |

**Recommendation:** Prompt 2 is the correct architecture for Patch-2 because (a) Patch-2 itself was born from adversarial review (Surprise 6), so the GAN loop is methodologically consistent; (b) the Planner directly solves Surprise 3 (cross-Item dependency ordering); (c) the feedback loop directly solves Surprise 4 (hidden model dependencies the compiler doesn't catch itself).

---

### Refined architecture v2 — token-optimized, feedback loop preserved

Initial Prompt 2 had five sources of redundancy. The v2 refinement eliminates them without weakening the feedback loop:

| Redundancy | Problem | v2 Fix |
|:---|:---|:---|
| Generator self-audit ≈ Evaluator re-check | Same YAML checked twice by two agents (>70% overlap) | Eliminate self-audit. Evaluator is the **single quality gate** — all 8 checks consolidated there |
| Companion doc validation repeated per-Item | Multiple Items depend on the same companion document — validated independently | Planner validates ALL companion docs once at startup, extracts shared data, passes as `args` to Generators |
| Global adversarial reviewer ≈ Evaluator (double-count) | `/goal` requires Evaluator CONFIRMED AND separate global reviewer | Eliminate separate global reviewer. Evaluator runs a final global consistency pass once after all Items CONFIRMED |
| Feedback loop triggers full recompile | One signal's exclusion set broken → entire A1-A7 + B-A..B-G re-run | Evaluator returns **targeted fix lists** (per-signal, per-gate). Generator fixes only the named issues; does not recompile the whole Item |
| Simple Items treated as heavyweight | Item 01 (check for "您好") gets same Generator overhead as Item 20 (11 triggers, cross-doc deps) | Planner batches structurally simple Items (01-07 procedural accuracy) into one Generator; one subagent context serves 7 Items |

**Net token impact:**

| Path | Saving mechanism | Estimate |
|:---|:---|:--:|
| First-pass compile | Eliminated duplicate companion doc reads; simple Item batching | ~15–20% |
| Feedback round (per Item) | Targeted fixes + Evaluator re-reviews only changed signals | ~45–55% per round |
| Global phase | Evaluator consistency pass replaces separate global reviewer | ~10% |

---

### Final execution prompt

```
use a workflow to build Planner + Generator + Evaluator loop per Patch-2.
Keep the feedback loop but eliminate redundancy:

ARCHITECTURE:
1) PLANNER (one agent, runs once):
   - Validate ALL companion documents at startup (shared, not per-Item)
   - Extract shared data: standard scripts from 营销话术.md
   - Scan cross-Item dependencies (Surprise 3), mark which Items depend on which
   - Batch structurally simple Items (01-07 procedural accuracy) into one Generator
   - Dispatch independent Items immediately; hold dependent Items until their
     prerequisite signal IDs are locked by the Evaluator

2) GENERATOR (one subagent per Item or per batch):
   - Receives shared companion doc data from Planner (no re-reading files)
   - Compiles ONLY: A1-A7 + B-A through B-F (gate-checkability) + B-G + gap classification
   - Emits Item YAML + signal IDs
   - Does NOT self-audit — the Evaluator is the single quality gate
   - On fix round: receives a targeted fix list from Evaluator, fixes ONLY those
     specific signals/gates — does NOT recompile the entire Item

3) EVALUATOR (one agent, reviews first-done-first):
   - ALL quality checks consolidated here (no duplication with Generator):
     a. Gate-checkability Q1/Q2 per signal (BLOCK)
     b. AUTH-1 adjective scan (BLOCK)
     c. Hidden model dependencies — declared checkable but Q2 fails (BLOCK)
     d. Exclusion set adversarial test — Surprise 5 (WARN → fix list)
     e. Trigger completeness vs companion doc keywords (WARN)
     f. Signal coverage — every clause has at least one signal (WARN)
     g. Gap classification correctness (BLOCK)
     h. Cross-Item consistency — dependent Item's signal refs match locked IDs (BLOCK)
   - Returns one of: CONFIRMED | FIXES_NEEDED (with targeted fix list) | AWAITING_STEERING
   - After ALL Items CONFIRMED: runs a final global consistency pass (once, not per-Item):
     checks ResidueManifest completeness, dimension-level coherence, no orphan signals

FEEDBACK LOOP:
   Generator → Evaluator → FIXES_NEEDED → Generator fixes only targeted issues
   → Evaluator re-reviews only changed signals → repeat
   Max 3 rounds per Item. After 3 rounds without CONFIRMED → flag as AWAITING_STEERING.

/goal don't stop until all Items have CONFIRMED verdicts from the Evaluator
AND the global consistency pass passes
AND the ResidueManifest covers every lossy compilation.
```

---

### Design decisions

**Decision: Eliminate self-audit; Evaluator is the single quality gate.**

**Rationale:** `Source: Prompt 1 vs Prompt 2 comparison` — the self-audit pass (Surprise 6) and the Evaluator's adversarial review check the same properties: gate-checkability, AUTH-1, model dependencies, exclusion set behavior, gap classification. Running both means the same YAML is inspected twice by different agents with >70% overlap in checklist. Consolidating into the Evaluator removes the duplication without losing coverage — the Evaluator's checks are a strict superset of self-audit. Generator is now purely constructive; Evaluator is purely critical. The separation of concerns is cleaner: Generator doesn't grade its own homework.

**Decision: Planner is the single I/O boundary for companion documents.**

**Rationale:** `Source: Surprise 1 (companion doc dependency)` — multiple Items depend on the same companion documents (Items 20 and 21 both consume `营销话术.md`). Validating and extracting data once at the Planner level prevents N Generators from independently re-reading and re-validating the same files. Shared extraction is an `args` handoff: the workflow passes extracted data to each Generator, so Generators never touch the filesystem for companion documents. Each Generator's context window is smaller because it receives pre-parsed data rather than raw file content.

**Decision: Targeted fixes over full recompile in feedback rounds.**

**Rationale:** `Source: Surprise 4 (gate-checkability failures), Surprise 5 (exclusion set pragmatics)` — when the Evaluator identifies a problem (e.g., signal S03's exclusion set over-fires on "我建议您可以选择"), the fix is localized to that signal's `exclusion_set` field. Re-running A1 (dimension decomposition), A3 (corroborator classification), A5 (agreement seeding), and A6 (deduction weight) produces the same outputs — none of these stages depend on the exclusion set. The Generator in fix mode receives `{signal_id: "S03", field: "exclusion_set", issue: "...", suggested_fix: "..."}` and applies a surgical edit. The Evaluator in re-review mode checks only the changed signals, not the entire Item. This makes feedback rounds O(changed_signals) instead of O(all_signals).

**Decision: Simple Items batched; complex Items isolated.**

**Rationale:** Items 01-07 (procedural accuracy: greeting, address terms, hold procedure, closing) have a shared structure — each is a single lexical check against a small vocabulary with no cross-Item dependencies and no companion document requirements. Batching them into one Generator subagent means one context window serves 7 Items instead of 7 subagent spawns each with full framework context. Complex Items (20, 21) with cross-document dependencies, model-judged signals, and exclusion set pragmatics still get dedicated Generators because their compilation logic doesn't share context with other Items.

**Decision: Max 3 feedback rounds per Item.**

**Rationale:** `Source: verification-floor.md adversarial verification loop` — the feedback loop is a GAN: Generator and Evaluator are adversarial. Without a bound, a non-convergent Item (e.g., an exclusion set with irreducible Chinese pragmatics ambiguity) could loop indefinitely. Three rounds is the cap: round 1 finds issues, round 2 verifies fixes, round 3 is the last chance. After 3 rounds without CONFIRMED, the Item is flagged as AWAITING_STEERING — the ambiguity requires a human decision (Surprise 2 pattern). This bound also caps token spend: worst-case per Item is first-pass compile + 3 fix rounds, not unbounded.

---

## Changelog

| Date | Change | Source |
|------|--------|--------|
| 2026-07-17 | Claude Code execution architecture added. GAN-inspired Planner→Generator→Evaluator multi-agent loop with feedback design. Prompt 1 (delegation) vs Prompt 2 (prescription) comparison. Refined architecture v2 with five token-saving optimizations: consolidated quality gate, shared companion doc extraction, targeted fixes over full recompile, simple Item batching, bounded feedback rounds. Final execution prompt documented. | Prompt comparison experiment; adversarial review of architecture design |
| 2026-07-16 | Patch 2 created. Six surprises and recommendations documented: companion document manifest (S1), pre-compile source validation with halt-on-conflict (S2), dependency-aware topological compilation (S3), B-F Gate-Checkability Audit (S4), pragmatic adversarial test generation for exclusion sets (S5), compiler self-audit pass (S6). Updated compiler pipeline diagram and AuthoredNode schema. | Adversarial review of Item 20/21 v1 compilations; Items 20/21 v2 re-compilation and re-review |
