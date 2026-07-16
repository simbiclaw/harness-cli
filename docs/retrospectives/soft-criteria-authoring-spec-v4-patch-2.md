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

**What happened:** Compiling Items 20/21 required two companion documents (营销触发.md, 营销话术.md) that are not declared anywhere in the rubric or the compiler procedure. The rubric text alone — "对用户表达中明显的潜在营销机会置之不理" — does not enumerate what those opportunities are. The trigger keywords live entirely outside the rubric, in companion documents.

**Compiler gap:** No mechanism exists to (a) declare which companion documents an Item needs, (b) verify those documents are present and version-pinned before compilation begins, or (c) report missing companion documents to the human.

### Recommendation: Per-item companion document manifest

Add a pre-compile step that checks a `companion_docs` declaration per Item. The compiler halts if a required companion document is missing or its SHA doesn't match the pinned version, and reports the gap before starting any compilation work.

```yaml
item_20:
  companion_docs:
    - path: "docs/PRD/eval/营销触发.md"
      sha: "<pinned at compilation epoch>"
      role: "trigger_keywords"
    - path: "docs/PRD/eval/营销话术.md"
      sha: "<pinned at compilation epoch>"
      role: "standard_scripts"
```

The companion document manifest is defined once by the human when an Item is first set up for compilation, then version-pinned at each compile run. The compiler validates existence and SHA match before processing the Item.

---

## Surprise 2: Source document contradiction — halt and await human decision

**What happened:** 营销触发.md contained two conflicting keyword definitions (T001-T005 vs. VAS-001-VAS-005) with only 7 shared keywords across 49+ combined. The compiler silently selected the first set, producing a compilation that was internally consistent but objectively incomplete. The adversarial reviewer was the first to flag this.

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

## Changelog

| Date | Change | Source |
|------|--------|--------|
| 2026-07-16 | Patch 2 created. Six surprises and recommendations documented: companion document manifest (S1), pre-compile source validation with halt-on-conflict (S2), dependency-aware topological compilation (S3), B-F Gate-Checkability Audit (S4), pragmatic adversarial test generation for exclusion sets (S5), compiler self-audit pass (S6). Updated compiler pipeline diagram and AuthoredNode schema. | Adversarial review of Item 20/21 v1 compilations; Items 20/21 v2 re-compilation and re-review |
