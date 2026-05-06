# harness-go lint rules

The canonical list of mechanical checks the harness-go skill wires.
Each rule names its enforcement point, the artifact it protects, and the
CI/hook/test that enforces it.

Rules marked `Aspiration:` are documented intent, not active enforcement.
Every `Aspiration:` has a `Revisit:` date. Past-due aspirations fail CI.

---

## Global rules (all artifacts)

| Rule | Enforcement | Status |
|---|---|---|
| No forbidden phrase in any harness artifact | structural-test: `.claude/tests/test_forbidden_phrases.py` | Aspiration: Revisit: <14 days from chain completion> |
| Every `Awaiting Steering:` block ends with a question | structural-test: `.claude/tests/test_awaiting_steering.py` | Aspiration: Revisit: <14 days> |
| Every commit touching a harness artifact has `Plan:` and `Decision:` trailers | hook: `.claude/hooks/commit-msg` | Aspiration: Revisit: <14 days> |

---

## Step 0 — CLAUDE.md sentinel + docs/MAP.md

| Rule | Enforcement | Status |
|---|---|---|
| CLAUDE.md contains exactly one harness-spine-bootstrap sentinel block during a run | structural-test: `.claude/tests/test_sentinel_count.py` | Aspiration: Revisit: <14 days> |
| CLAUDE.md content outside the sentinel is byte-for-byte unchanged | structural-test: `.claude/tests/test_claude_md_immutability.py` | Aspiration: Revisit: <14 days> |
| docs/MAP.md ≤ 80 lines | structural-test: `.claude/tests/test_map_md_length.py` | Aspiration: Revisit: <14 days> |
| docs/MAP.md has "Read when" and "Skip when" entries for all four artifacts | structural-test: `.claude/tests/test_map_md_routing.py` | Aspiration: Revisit: <14 days> |
| docs/MAP.md chain status table is present | structural-test: `.claude/tests/test_chain_status_table.py` | Aspiration: Revisit: <14 days> |
| No forbidden phrases in docs/MAP.md | (covered by global forbidden-phrases test) | Aspiration: Revisit: <14 days> |

---

## Step 1 — PRODUCT_SENSE.md and product-specs/

| Rule | Enforcement | Status |
|---|---|---|
| Non-goals section ≥ Goals section (line count) | lint: `harness-lint/non-goals-parity` | Aspiration: Revisit: <14 days> |
| Every product-spec has a non-empty Tiebreaker citations field | structural-test: `.claude/tests/test_spec_tiebreaker_citations.py` | Aspiration: Revisit: <14 days> |
| Every product-spec in index.md has a corresponding file | structural-test: `.claude/tests/test_spec_index_completeness.py` | Aspiration: Revisit: <14 days> |
| PRODUCT_SENSE.md has `owned-by: steering` front-matter | structural-test: `.claude/tests/test_product_sense_ownership.py` | Aspiration: Revisit: <14 days> |
| No tiebreaker cites a forbidden phrase | (covered by global forbidden-phrases test, scoped to this file) | Aspiration: Revisit: <14 days> |

---

## Step 2 — DESIGN.md and design-docs/

| Rule | Enforcement | Status |
|---|---|---|
| Every design-doc has a `verification-status:` front-matter field | lint: `harness-lint/design-doc-status` | Aspiration: Revisit: <14 days> |
| No design-doc has `verification-status: proposed` older than 14 days | ci-gate: `.github/workflows/harness.yml` (scheduled daily) | Aspiration: Revisit: <30 days> |
| Every design-doc claiming `implemented` has test selectors referenced in the codebase | ci-gate: `.github/workflows/harness.yml` | Aspiration: Revisit: <30 days> |
| Every design-doc cites ≥ 1 core belief | structural-test: `.claude/tests/test_design_doc_belief_citation.py` | Aspiration: Revisit: <14 days> |
| Every core belief is cited by ≥ 1 design-doc | structural-test: `.claude/tests/test_belief_orphan_check.py` | Aspiration: Revisit: <14 days> |
| design-docs/index.md has one row per design-doc file | structural-test: `.claude/tests/test_design_index_completeness.py` | Aspiration: Revisit: <14 days> |

---

## Step 3 — ARCHITECTURE.md and tools/lint/rules.md

| Rule | Enforcement | Status |
|---|---|---|
| Every domain cites a PRODUCT_SENSE non-goal OR is marked Aspiration | structural-test: `.claude/tests/test_domain_justification.py` | Aspiration: Revisit: <14 days> |
| Dependency matrix covers all domain × domain pairs | structural-test: `.claude/tests/test_dependency_matrix_completeness.py` | Aspiration: Revisit: <14 days> |
| No cross-domain import not listed in the matrix | import-linter: constraint in `pyproject.toml` | Aspiration: Revisit: <30 days> |
| No layer imports from a layer to its right | import-linter: constraint in `pyproject.toml` | Aspiration: Revisit: <30 days> |
| Every Aspiration: rule has Revisit: ≤ 30 days out | structural-test: `.claude/tests/test_aspiration_revisit_dates.py` | Aspiration: Revisit: <14 days> |
| tools/lint/rules.md has one row per architectural rule | structural-test: `.claude/tests/test_lint_rules_completeness.py` | Aspiration: Revisit: <14 days> |

---

## Step 4 — QUALITY_SCORE.md

| Rule | Enforcement | Status |
|---|---|---|
| Every cell has a grade and a one-sentence justification | structural-test: `.claude/tests/test_quality_score_completeness.py` | Aspiration: Revisit: <14 days> |
| Every D or F cell has an active ExecPlan reference or a TODO placeholder | ci-gate: `.github/workflows/harness.yml` | Aspiration: Revisit: <14 days> |
| D or F TODO placeholders fail CI after Next regrade: date passes | ci-gate: `.github/workflows/harness.yml` | Aspiration: Revisit: <14 days> |
| Next regrade: ≤ 14 days from Last graded: | structural-test: `.claude/tests/test_quality_score_regrade_date.py` | Aspiration: Revisit: <14 days> |
| No weighted average or single summary score present | structural-test: `.claude/tests/test_quality_score_no_summary.py` | Aspiration: Revisit: <14 days> |

---

## Step 5 — teardown (two-phase commit integrity)

| Rule | Enforcement | Status |
|---|---|---|
| `CLAUDE.md` on `main` must not contain `harness-spine-bootstrap` | ci-gate: `.github/workflows/harness.yml` | Aspiration: Revisit: <14 days from spine ship> |
| `docs/MAP.md` must not exist on `main` | ci-gate: `.github/workflows/harness.yml` | Aspiration: Revisit: <14 days from spine ship> |
| CLAUDE.md content post-teardown is identical to pre-run content | structural-test: `.claude/tests/test_claude_md_immutability.py` | Aspiration: Revisit: <14 days> |

CI gate implementation (add to `.github/workflows/harness.yml`):

```yaml
- name: Assert harness-go scaffolding is torn down
  run: |
    if grep -q 'harness-spine-bootstrap' CLAUDE.md; then
      echo "ERROR: harness-spine-bootstrap sentinel found in CLAUDE.md on main."
      exit 1
    fi
    if [ -f docs/MAP.md ]; then
      echo "ERROR: docs/MAP.md exists on main. Run harness-go Step 5."
      exit 1
    fi
```

---

## PostToolUse hook — cross-link integrity

Triggered on every write to any harness artifact or satellite directory.

```
CHECK 1: every product-spec has ≥ 1 tiebreaker citation from PRODUCT_SENSE.md
CHECK 2: every design-doc has a verification-status field
CHECK 3: every ARCHITECTURE.md rule has a lint row OR an unexpired Aspiration
CHECK 4: every QUALITY_SCORE D/F cell has an active ExecPlan or TODO placeholder
```

On failure: revert the write; append failure detail to active plan's
**Surprises & Discoveries** section.

Wire at: `.claude/hooks/post-tool-use/cross-link-integrity`
Status: Aspiration: Revisit: <30 days from chain completion>

---

## Promotion rule (from CLAUDE.md)

When any rule is violated twice across different ExecPlans, escalate:

```
Aspiration → structural-test (.claude/tests/)
           → hook (.claude/hooks/)
           → ci-gate (.github/workflows/harness.yml)
           → architecture (import-linter in pyproject.toml)
```

Do not rely on "trying harder to remember." Move the rule into code.

---

Last reviewed: 2026-05-04.
