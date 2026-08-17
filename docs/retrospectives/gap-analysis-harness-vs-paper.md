# Gap Analysis — harness-cli's Harness vs. the Paper's Model (arXiv:2605.18747)

Status: SPEC-PHASE DOCUMENT — precedes ExecPlan generation per two-phase discipline.
Evidence base: working clone @ main HEAD + feat/audio2tree-skill FETCH_HEAD;
docs/retrospectives/9004-execution-mistakes.md; blindspot pass B1–B8.
Grading vocabulary:
  PRESENT       — instantiated and enforced
  PARTIAL       — instantiated, with named defects
  CONTRACT-ONLY — declared in docs/ADR, not in code
  BROKEN        — instantiated, falsified in practice
  ABSENT        — neither declared nor instantiated
Repo wins over this document wherever they disagree.

═══════════════════════════════════════════════════════════════════════════
PART 1 — GRADE TABLE
═══════════════════════════════════════════════════════════════════════════

## L1 · Harness Interface (§2)

| Element | Paper's requirement | Current state | Grade | Evidence |
|---|---|---|---|---|
| Code for reasoning (§2.1) | Model proposes, runtime executes; pure verifiable core | Typed layer chain + pure-core contract in ADRs; src/argus/core is a 4-line __init__ | CONTRACT-ONLY | src tree; ADR-0001 |
| Code for acting (§2.2) | Executable boundary filters invalid actions pre-execution | Hook guard layer exists (5 guards) but machine-pinned (B1), tool-shaped (B2), root unguarded (B3) | BROKEN | settings.json; pre_tool_use.py; sensitive-paths.txt |
| Code for environment (§2.3) | Materialized, executable world; verifiable env construction (§2.3.4) | No fixture INTENTS trees, no golden traces, INTENTS/ empty | ABSENT | tests/; INTENTS/ |
| Referent provenance | Env pinned to a versioned referent | Production INTENTS home undeclared; fixture↔production binding nonexistent | ABSENT (B8) | ADR-0004 vs empty INTENTS/ |

## L2 · In-Loop Mechanisms (§3.1–3.3)

| Element | Paper's requirement | Current state | Grade | Evidence |
|---|---|---|---|---|
| Planning: decomposition + rubric (§3.1) | Structured plans with contracts | ExecPlans + PLANS.md rubric, live | PRESENT | docs/PLANS.md; exec-plans/ |
| Planning: orchestration typing (§3.1.4) | Agent topology declared (sequential vs parallel, isolation) | Untyped; worktree blanket default caused 9004 §2.1 | ABSENT | 9004 retro §2.1 |
| Planning: plan scope declaration | Plans declare touched surface (collision precondition) | No file-scope section in rubric | ABSENT | PLANS.md |
| Memory: system of record (§3.2) | Persistent docs-as-experience | docs/ discipline live; Decision trailers | PRESENT | repo-wide |
| Memory: experiential capture | Surprises recorded during execution | Section exists; left empty through 4 mistakes in 9004 | BROKEN | 9004 retro §4 row 2 |
| Memory: compaction contract (§3.2.6) | Compression that preserves raw-trace value (Meta-Harness ablation) | doc-gardener/garbage-collector exist; no retention floor — lossy compression unbounded | PARTIAL | .claude/skills/ |
| Tool use: verification-driven class (§3.3.3) | Checking tools separated as authority-bearing | Verifier, 8 lints, 14 structural tests exist; class not enumerated or registered | PARTIAL | tools/lint/; .claude/tests/ |

## L3 · Control / PEV (§3.4)

| Element | Paper's requirement | Current state | Grade | Evidence |
|---|---|---|---|---|
| Planning-as-contract (§3.4.2) | Falsifiable acceptance gates at plan creation | Gates exist; falsifiability unenforced — "run on 5 WAVs" passed rubric | BROKEN | 9004 retro §2.2, §4 row 4 |
| Permissioned transition (§3.4.3) | Deterministic tiered permissions | Tier A/B/C live; perimeter defects B1–B3 make enforcement tool-shaped | PARTIAL | ask-threshold.md; hooks |
| Deterministic-sensor verification (§3.4.4) | Verifier blocks unverified transitions | Verifier is advisory: hooks cannot invoke skills (B4); [ ]→[x] flipped with no run, no record | BROKEN | 9004 retro §4 row 1; hook contract |
| Verification audit trail | Invocation evidence distinguishable post hoc | None — bypass vs weak-test indeterminate | ABSENT | 9004 retro §4 |
| Hermeticity classification | Acceptance tests declare runnability class | No test declares hermetic vs service-dependent | ABSENT (B5) | all acceptance specs |

## L4 · AHE (§3.5)

| Element | Paper's requirement | Current state | Grade | Evidence |
|---|---|---|---|---|
| Telemetry (§3.5.1) | Violations observable as harness state | "Violated twice" lives in human memory; prose-rule violations have no detection event | ABSENT | CLAUDE.md promotion rule |
| Evolution agent (§3.5.2) | Trigger→draft loop | Human+Claude open promotion plans manually; retrospectives are terminal docs, not feeders | PARTIAL | 9004 retro §6.3 |
| Governed mutation (§3.5.3) | Mutation ladder under authority | Promotion ladder + Tier C, live and honored | PRESENT | CLAUDE.md; sensitive-paths |

## L5 · Shared Substrate (§4)

| Element | Paper's requirement | Current state | Grade | Evidence |
|---|---|---|---|---|
| Shared artifacts | Repo/tests/traces as common state | Trivially present | PRESENT | repo |
| Collision detection | Overlapping plan scopes surfaced mechanically | COLLISION-REPORT.md is a frozen v6-upgrade review doc (B7) | ABSENT | its own header |
| Lease / transactional state | Fail-closed leases per ontology | Ontology-level only | CONTRACT-ONLY | HARNESS-ONTOLOGY-v3 |

## L6 · Governance plane (§2.2.2/3.4.3/3.5.3/5.2.5)

| Element | Paper's requirement | Current state | Grade | Evidence |
|---|---|---|---|---|
| Locks exist | Enforcement points at each level | 8 lints, 14 tests, 5 hook guards, importlinter, 5 CI jobs | PRESENT | repo-wide |
| Lock enumeration (Axiom 0) | Registry; deleted lock detectable | None; a deleted CI job is invisible to every remaining lock | ABSENT | — |
| Guards-guarding closure | Authority chain terminates in a guarded root | settings.json, skills/**, conventions/** unguarded (B3) | BROKEN | sensitive-paths.txt |
| Append-only enforcement | Ledger history mechanically immutable | Claimed ×3 (spec-findings + planned), enforced ×0; merge strategy undeclared (B6) | ABSENT | — |

Tally: PRESENT 6 · PARTIAL 4 · CONTRACT-ONLY 3 · BROKEN 6 · ABSENT 10.
The BROKEN row is the headline: six elements the harness claims and 9004
falsified. The model gap is not missing machinery — it is machinery whose
authority is advisory.

═══════════════════════════════════════════════════════════════════════════
PART 2 — PLAN-BOUNDARY PREDICATE
═══════════════════════════════════════════════════════════════════════════

Gaps G share one exec-plan iff ALL hold:
  P1  homogeneous verification floor — one evidence type proves "done"
      (repair-restoration vs new-lock-seeded-RED vs artifact-schema are
      distinct types)
  P2  single blast-radius tier — no mixing Tier-C harness paths with
      Tier-A product paths in one plan's default flow
  P3  no internal seam that neither side's acceptance test exercises
      (the 9004 §2.6 criterion)
  P4  no external Tier-C decision lands mid-plan — required decisions are
      inputs at plan creation, or they split the plan

Anti-criteria (explicitly rejected):
  ×  one-plan-per-topology-part (topology is a map, not a WBS; L5 needs
     zero plans, L3 needs two)
  ×  one-plan-per-phase (phases are sequence, not contract units)
  ×  minimize-plan-count (my prior error: merging repair with capability
     violated P1)

═══════════════════════════════════════════════════════════════════════════
PART 3 — DERIVED PARTITION
═══════════════════════════════════════════════════════════════════════════

## P-I · 9005 — Perimeter Integrity Restoration          [repair class]
Gaps: B1 machine-pinned hooks · B2 bash-shaped hole (session leg) ·
B3 unguarded root · B6a append-only test for the EXISTING ledger
(spec-findings.md) · merge-strategy declaration (input decision).
Floor: restoration-seeded-RED — existing guards demonstrably fire where
intended (worktree checkout, bash mutation, settings.json edit).
Why alone (P1): repair semantics, not new capability. Mixing with P-II
gives one plan two "done" meanings — the 9004 §4-row-4 defect at plan scale.
Decisions required at creation: merge strategy (B6).

## P-II · 9006 — Load-Bearing PEV                        [new-lock class]
Gaps: blocking [ ]→[x] (deny-unless-evidence, B4 inversion) · verifier
invocation ledger · CI ancestry/content-hash leg · acceptance-gate
falsifiability floor (M4.4) · hermeticity classes (B5).
Floor: bypass-seeded-RED — forged flip, offline flip, undeclared class
all go red.
Why separate from P-I (P1) and P-III (P4): requires the hermeticity-budget
Tier-C decision as a creation input; P-III requires none.
Depends on: P-I (a blocking hook on a dead perimeter is theater).

## P-III · 9007 — Gate Registry                          [artifact class]
Gaps: Axiom-0 lock enumeration · bidirectional drift-check · hook
REGISTRATION coverage (B3 registry leg) · schema (pydantic, parse-at-
boundary).
Floor: drift-seeded-RED both directions (deleted lock; unregistered lock).
Why separate from P-II (P1+P4): enumeration artifact + schema, not
enforcement behavior; zero external decisions — can be specced while
P-II awaits steering. Sequenced after P-I (both touch .claude/tests and
no collision detector exists yet — sequencing IS the interim collision
control).

## P-IV · 9008 — AHE Telemetry                           [channel class]
Gaps: violations ledger (mechanical + manual paths) · promotion trigger
test · retrospective-as-feeder test · surprises-empty warn ·
9004 §6.3 seeds.
Floor: channel-seeded-RED — synthetic double-violation trips trigger;
undecomposed retrospective fails.
Depends on: P-III (rule-ids), P-II (ledger append-only discipline from
P-I's test pattern; runs under blocking verifier).

## P-V · 9009 — Mechanism Typing                         [methodology class]
Gaps: orchestration isolation typing (9004 §2.1 promotion) · plan
file-scope declaration + intersection test (= the real Phase-6 trigger,
retiring B7) · doc-gardener retention contract · PLANS.md rubric
amendments.
Floor: rubric-structural-RED — untyped orchestration spec fails; scopeless
plan fails; overlapping active scopes fail.
Why alone (P2): blast radius is methodology docs (PLANS.md, conventions/)
— the Tier-C tier P-I newly guards; heterogeneous with all code-floor plans.

## A-1 · Amendment to 9002 (not a new plan)              [supply]
Gaps: fixture INTENTS trees · golden traces · known-match (anti-no-op)
discipline · byte-determinism acceptance.
Why amendment (P3): fixtures and the pipeline consuming them are one
integration seam; a separate plan recreates 9004 §2.6 — two owners,
untested handoff.

## ADR-000x · INTENTS Provenance (not an exec-plan)      [decision record]
Gap: B8 — production INTENTS home, versioning, fixture schema-pin.
Why ADR: it is a decision, not work; the work it implies lands in A-1.
Precedes A-1.

## Phase 6 · Shared-substrate leases — ZERO plans now
The P-V scope-intersection test going red is the trigger; P-IV's promotion
machinery then REQUIRES a plan be opened. The harness opens this plan;
foresight does not.

═══════════════════════════════════════════════════════════════════════════
PART 4 — RESULT
═══════════════════════════════════════════════════════════════════════════

  5 new exec-plans (9005–9009) + 1 amendment (9002) + 1 ADR
  + 1 mechanism-opened future plan (uncounted by design).

Sequencing: P-I → P-II ∥ P-III (P-III specs during P-II steering wait;
executes after) → P-IV → P-V; A-1 alongside 9002 whenever ADR lands.

Sensitivity of the count (what would change it):
- If merge-strategy + hermeticity decisions are both made before any plan
  is authored, P4 no longer separates P-I/P-II → arguable merge to 4 plans.
- If the collision detector is wanted before P-V (to permit P-II ∥ P-III
  true parallelism), the file-scope rubric amendment splits out of P-V
  into a micro-plan → 6 plans.
The count is a function of two decisions you own, bounded [4, 6].
Prior estimates — 2 (mine) and 6-as-topology-parts — both fall outside
the predicate's derivation for the wrong reasons: 2 violated P1;
6-by-topology maps the wrong object.

═══════════════════════════════════════════════════════════════════════════
PART 5 — OPERATING PROTOCOL (how this document drives the evolution)
═══════════════════════════════════════════════════════════════════════════

Role: governing scoreboard. Grades = progress metric; plans = moves;
grade transitions = campaign-level acceptance evidence, additional to each
plan's own verification floor. A plan with all [x] and no grade movement
is a campaign-level false pass.

## 5.1 Gap IDs and target grades

Format: GAP-<layer>-<nn>. TARGET defines "evolved" falsifiably; targets
are deliberately not all-PRESENT.

| ID | Element (short) | Current | Target | Plan |
|---|---|---|---|---|
| GAP-L1-01 | code for reasoning (pure core) | CONTRACT-ONLY | PRESENT | 9002 (existing) |
| GAP-L1-02 | acting boundary (hook guards) | BROKEN | PRESENT | P-I 9005 |
| GAP-L1-03 | executable environment | ABSENT | PRESENT | A-1 (9002 amd) |
| GAP-L1-04 | referent provenance | ABSENT | PRESENT | ADR-000x → A-1 |
| GAP-L2-01 | planning rubric | PRESENT | PRESENT | — (hold) |
| GAP-L2-02 | orchestration typing | ABSENT | PRESENT | P-V 9009 |
| GAP-L2-03 | plan file-scope declaration | ABSENT | PRESENT | P-V 9009 |
| GAP-L2-04 | docs system of record | PRESENT | PRESENT | — (hold) |
| GAP-L2-05 | experiential capture (Surprises) | BROKEN | PARTIAL* | P-IV 9008 (*warn-not-block: PRESENT unreachable by mechanism alone) |
| GAP-L2-06 | compaction retention contract | PARTIAL | PRESENT | P-V 9009 |
| GAP-L2-07 | verification-driven tool class | PARTIAL | PRESENT | P-III 9007 |
| GAP-L3-01 | planning-as-contract falsifiability | BROKEN | PRESENT | P-II 9006 |
| GAP-L3-02 | permissioned transition | PARTIAL | PRESENT | P-I 9005 |
| GAP-L3-03 | deterministic-sensor verification | BROKEN | PRESENT | P-II 9006 |
| GAP-L3-04 | verification audit trail | ABSENT | PRESENT | P-II 9006 |
| GAP-L3-05 | hermeticity classification | ABSENT | PRESENT | P-II 9006 |
| GAP-L4-01 | AHE telemetry | ABSENT | PRESENT | P-IV 9008 |
| GAP-L4-02 | evolution agent (feeder+draft) | PARTIAL | PRESENT | P-IV 9008 |
| GAP-L4-03 | governed mutation | PRESENT | PRESENT | — (hold) |
| GAP-L5-01 | shared artifacts | PRESENT | PRESENT | — (hold) |
| GAP-L5-02 | collision detection | ABSENT | PRESENT | P-V 9009 |
| GAP-L5-03 | leases / transactional state | CONTRACT-ONLY | CONTRACT-ONLY† | none (†mechanism-opened when GAP-L5-02's test goes red) |
| GAP-L6-01 | locks exist | PRESENT | PRESENT | — (hold) |
| GAP-L6-02 | lock enumeration (Axiom 0) | ABSENT | PRESENT | P-III 9007 |
| GAP-L6-03 | guards-guarding closure | BROKEN | PRESENT | P-I 9005 |
| GAP-L6-04 | append-only enforcement | ABSENT | PRESENT | P-I (existing ledger) + P-II/P-IV (new ledgers) |

Bijection check: every non-hold GAP maps to exactly one owning plan
(GAP-L6-04's split is by ledger instance, one owner each). Every plan
cites its GAP set in its header. Manual check at authoring until P-III
lands; structural-test candidate afterward.

## 5.2 Per-plan cycle

1. RE-VERIFY  — re-check in-scope rows against repo HEAD (evidence column
                = checklist). Grades moved → re-scope before authoring.
2. AUTHOR     — plan prompt = pinned SHA + in-scope GAP rows pasted
                (rows, not this whole doc) + decisions as inputs +
                expected-RED per lock. Two-phase: spec review precedes
                ExecPlan finalization.
3. EXECUTE    — under standing disciplines and all predecessor locks.
4. RE-GRADE   — record transitions in 5.3. No movement = investigate
                before the plan may close.

## 5.3 Grade transition ledger (append-only)

| Date | GAP | From | To | Plan | Evidence |
|---|---|---|---|---|---|
| — | — | — | — | — | (populated as plans close) |

## 5.4 Entry conditions

Before P-I authoring: merge-strategy convention committed.
Before P-II authoring: hermeticity budget resolved (Tier C).
Before A-1 authoring: INTENTS provenance ADR committed.
P-III may be specced during P-II's steering wait; executes after P-I.

## 5.5 Retirement clause

After P-III + P-IV land, grades for L3/L4/L6 become mechanically derivable
(registry = which locks exist; ledgers = which fired; drift-checks = which
died). At that epoch: absorb the grade table into a registry-derived view,
move this document to docs/retrospectives/ as a historical record, and
retire it as an authority. A static grade table outliving mechanical
derivability is exactly the artifact class repo-wins exists to kill.
The document's obsolescence is the evolution's completion signal.
