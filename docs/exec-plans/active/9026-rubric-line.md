# 9026 — The Rubric Line: From 27 Rows to Epoch-Pinned Nodes

## 1. Purpose

What the evaluation is scored against must be compiled, versioned and reviewable — not a flat table
a runtime reads and a model interprets. This plan takes the human rubric sheet through the compiler
line: fix the polarity-blind signal that would corrupt every compiled item, land the 27 rows as
compiler input, and compile them into epoch-pinned `_rubric/` nodes with the dimension mapping and
the residue recorded.

## 2. Big Picture

Three steps, in this order, because each corrupts the next if skipped: **M14** fixes
`core/compiler/signals.py`'s FAIL signal, which at present does not distinguish polarity — item 18
shipped that signal as its *only* gate-checkable output, and it deducted for consulting the business
manual the rubric explicitly rewards. Compiling 27 items through an undetected polarity defect
manufactures 27 wrong rubrics faster than a human can review them. **M15** lands the rows as
`docs/rubric/specific-rubric-27.yaml` and switches `question_generator`'s input from the flat table
to the compiled nodes — the second derivation path from rubric to machine-checkable question is the
defect, and closing it is this milestone's work. **M16** compiles through 9003 and stops at a
staging path: committing nodes into `INTENTS/` is an upstream write-time epoch act, never this
repository reaching into its own referent (D15).

**Depends on:** 9024 (the imported `question_generator`), 9025 (the Provider the compiled nodes are
read through). **Depended on by:** 9027's `score()`.

**File Scope:**
- `docs/exec-plans/active/9026-rubric-line.md` (this plan)
- `src/argus/core/compiler/signals.py` (modify — M14)
- `docs/rubric/specific-rubric-27.yaml` (new — M15)
- `build/rubric-staging/**` (new — M16's compiled-node output; a build artifact, never committed and never read at runtime)
- `tests/test_signals.py`
- `tests/test_rubric_input.py`
- `tests/test_rubric_compile.py` (new)

## 3. Milestones

### M14 — Fix the polarity-blind FAIL signal before compiling anything

`core/compiler/signals.py:353-361` emits a FAIL signal that does not distinguish polarity. The
compiler's only shipped output carries it. Compiling 27 items through this manufactures 27 wrong
rubrics faster than a human can review them.

`Acceptance Test:` `tests/test_signals.py::test_fail_signal_polarity` — item 18 as the regression
case; an inverted-polarity input no longer produces a passing signal.


**Contract.**
- *Deliverable:* A compiler signal that distinguishes polarity.
- *Binding constraint:* None beyond the floor.
- *Acceptance property:* An inverted-polarity input no longer yields a passing signal.
- *Known evidence (advisory):* Reported in the signals module; item 18 is the natural regression case. Compiling many items through an undetected polarity defect manufactures wrong rubrics faster than review can catch them.


### M15 — Land B's 27 items as `SpecificRubric` input

B's `config/rubric_items.py` becomes `docs/rubric/specific-rubric-27.yaml` — all 27 rows, with
items 6 and 7 carrying a permanent inapplicability gate and a `data_dependency` naming the system
they need. Re-verify all 27 against the upstream source where recoverable; B's transcription is
lossy in at least two places (item 18 drops a counter-example, item 1 has an empty fail standard).

`Acceptance Test:` `tests/test_rubric_input.py::test_27_rows_parse_as_specific_rubric`.
`::test_items_6_and_7_are_permanently_inapplicable` — both carry a `data_dependency` and neither
reaches the denominator. `::test_25_items_scored`. `::test_no_empty_fail_standard`.


**Amended 2026-09-14 — the item count is settled, the `(*)` reading is not, and the diff re-points.**
The live tree settles the count: `_rubric/rules_criteria/` holds **25 item nodes, ids 1–5 and 8–27**;
items 6 and 7 are already excluded, so this plan's operational 25 and patch 3's ontology 25 are the
same 25. (Recorded where the contest lived, at Q14.) B's transcription remains lossy in at least two
places.

**`(*)` is undefined in the source and read two ways.** `docs/PRD/eval/rubric_com_hotline.md`
contains the marker exactly twice — on items 6 and 7 — with no legend anywhere in the document.
B reads it as weight 2.0 (`config/rubric_items.py:80-94`, comment `# (*) 项`); this line's
compiler reads it as data-dependency/deferred, and that reading has the content support: both
marked items are precisely the ones whose criteria need external systems (the service-record store;
the escalation workflow). Under either reading the shipped number is identical — 25 items at weight
1.0, total 25.0 — **because the only two weighted items are the two excluded ones.** The plan's
earlier "total weight 29.0 → 25.0" line was numerically correct and rhetorically misleading: it
presented the weights as load-bearing when they cancel.

**The diff re-points.** M15 was framed as diffing B's hand-assigned **weights** against the
compiler's; weights are uniform across the shipped set, so there is nothing to diff there. The
interesting divergence is **which items are excluded and on what grounds** — data-dependency versus
weight — and that is what this milestone's divergence record covers.

**The `question_generator` input switch lives here** — this is the "input changed" M7 refers to.
`core/question_generator.py:14` imports `RUBRIC_ITEMS, RUBRIC_BY_ID` from `config/rubric_items.py`
and `_rubric_driven` (`:53-96`) iterates `kb_context.applicable_rubrics`, which
`kb_context_builder.py:65` sets from that flat table. That is a second, model-mediated derivation
path from rubric to machine-checkable question, running in parallel with the compiler's
deterministic one — the two cannot even be checked for agreement. This milestone re-points the
read at `_rubric/` through M13's Provider: the questions come from the compiled nodes
(`signals[].description`, the `facets` split into programmatic and model_based), and the flat YAML
becomes compile input only, never a runtime source. The prohibition M7 defers here — *no
rubric→question derivation from the flat table* — is asserted in this milestone's tests.

`Acceptance Test (additions):` `tests/test_rubric_input.py::test_question_generator_reads_compiled_nodes`
— no module under `src/argus/` imports `config/rubric_items.py` or reads the flat table at
runtime; the generated questions resolve to compiled node ids.
`::test_no_second_rubric_path` — the compiled nodes are the only runtime source of
machine-checkable questions.

`Acceptance Test:` `tests/test_rubric_input.py::test_27_rows_parse_as_specific_rubric`.
`::test_items_6_and_7_are_permanently_inapplicable` — both carry a `data_dependency` and neither
reaches the denominator. `::test_25_items_scored` — asserted against the live node ids, and
**without encoding a per-item weight semantics**: the scored set is uniform at 1.0 and the
dimension multiplier lives in M10. `::test_no_empty_fail_standard`.
`::test_star_marker_divergence_recorded` — where B's transcription and the compiler disagree on the
`(*)` items, the disagreement is recorded as a finding rather than resolved by importing B's
reading.

**Contract.**
- *Deliverable:* The human rubric available as compiler input, with the `(*)` ambiguity recorded rather than silently resolved.
- *Binding constraint:* The rubric is a public artifact. Items excluded for data dependency are recorded with their reason, not deleted. **A contested reading in the source is a finding, not a value to import** — and the shipped arithmetic must not depend on which reading wins.
- *Acceptance property:* The scored set matches the operational scope, an excluded item never reaches the denominator, and the `(*)` divergence is visible in the record.
- *Known evidence (advisory):* The count is settled by the live tree (25, ids 1–5 and 8–27). B's transcription is lossy in at least two places. Do not let `test_25_items_scored` acquire weight semantics it does not have.


### M16 — Compile the rubric through 9003

Produce epoch-pinned `_rubric/` AuthoredNodes with the align map decided in Q3: item 22 to
Empathy & Tone, items 23–25 to Problem Resolution, item 26 to Empathy & Tone with its Problem
Resolution axis recorded as `within_dimension` residue, item 27 to Procedural Accuracy at the
compliance layer. Compiler output is diffed against B's hand-assigned weight and veto; divergences
are findings, not overrides.

**Where the output goes (declared 2026-09-14 — it was named nowhere).** §2 asserts that this
milestone *"emits them to a staging path and stops there"*, and neither the Contract nor the File
Scope said what that path is. It is **`build/rubric-staging/`** (repo-relative, gitignored, not
under `INTENTS/`): the compiled nodes are emitted there, and committing them into
`INTENTS/_rubric/rules_criteria/**` is an upstream write-time epoch act performed by the compiler
line or a human — never by this repository reaching into its own referent (D15, ADR-0003). The
path is a build artifact, so it must not be committed and must not be read by anything at runtime;
the plan's File Scope carries it as the one path this milestone writes.

`Acceptance Test:` `tests/test_rubric_compile.py::test_all_27_compile_or_declare_residue`.
`::test_item_27_is_compliance_layer` — the veto item does not depend on the judgment gates.
`::test_hand_assignment_divergences_recorded`.


**Contract.**
- *Deliverable:* Compiled rubric nodes.
- *Binding constraint:* D15 — Argus emits nodes; the epoch commit that lands them is an upstream write-time act. Until compilation, soft criteria correctly return deferred.
- *Acceptance property:* Every item either compiles or declares residue, and the veto criterion does not depend on the judgment gates.
- *Known evidence (advisory):* Q3 fixed the dimension mapping. Assessment mode may be inferred at runtime from key presence rather than stored — verify against the live nodes before assuming either.


## 4. Progress

- [ ] M14: Fix the polarity-blind FAIL signal  (created 2026-09-12)
- [ ] M15: Land B's 27 items as SpecificRubric input — `(*)` divergence recorded  (amended 2026-09-14)
- [ ] M16: Compile the rubric through 9003  (created 2026-09-12)

## 5. Decision Log

### Decision: 25 scored items — 6 and 7 excluded for data dependency, not deleted (2026-09-12, settled 2026-09-14)

**Rationale:** `Source:` the live tree — `_rubric/rules_criteria/` holds exactly 25 item nodes,
ids 1–5 and 8–27; items 6 and 7 are already excluded. Both need systems Argus cannot read (a
service-record store; an escalation workflow). They are marked permanently inapplicable rather than
removed, so the reason is auditable and restoring them later is a gate change. The archived plan's
Q14 records how the contested 25-vs-25 question was settled, and the citation error made in closing
it.

**Confidence:** high.

### Decision: The `(*)` marker is contested in the source; neither reading ships as data (2026-09-14)

**Rationale:** `Source:` `docs/PRD/eval/rubric_com_hotline.md` — the marker appears exactly twice
(items 6 and 7) and is defined nowhere. B reads it as weight 2.0; this line's compiler reads it as
data-dependency, which the items' content supports. Under either reading the shipped arithmetic is
identical (25 items at 1.0, total 25.0), because the only two weighted items are the two excluded
ones. The plan records the divergence rather than adopting either.

**Confidence:** high on the arithmetic; `Confidence: low` on which reading the source intended.

### Decision: Dimension weights are compiled into the gate file (Q24, human ruling 2026-09-14)

**Rationale:** `Source:` `docs/PRD/eval/skills/evaluator/SKILL.md:221,310` states
`(Empathy×3 + Resolution×3 + Procedure×2 + Proactive×1) ÷ 9`; the legacy v1 node format carried
`dimension_weight`; the live tree carries it nowhere, and neither codebase applies it. The weight is
compiled into `_rubric/gates/{dimension}.yaml` alongside `hard_fail_rule` — a compiled-output
change, so it requires a recompile and a new epoch, which this plan's line executes. **M10 (9027)
cannot pass its weighted-scoring assertion until the recompile lands.** The history of the field is
internally inconsistent in the companion spec and is recorded as unresolved rather than resolved by
preference.

**Confidence:** high on the specification and the gap; `Confidence: medium` that the gate file is
the better home.

## 6. Surprises & Discoveries

**The compiler could not see polarity (2026-09-13, inherited).** `decompose_signals` emitted one
FAIL signal from the flat `named_phrases` list without consulting which standard named each phrase —
so any phrase drawn from the *pass* standard deducted for the behaviour the rubric rewards. Measured
directly: item 18 and item 18 with its two standards swapped produced byte-identical output.

**The flattening starts upstream of the compiler (2026-09-13, inherited).** The pilot's
`named_phrases` mixes pass-standard and fail-standard vocabulary in one list with no field recording
which is which. M14's fix recovers polarity by substring-matching, which is **inference, not data**.
If the rubric input grows an explicit polarity field, the helper should read it.

## 7. Awaiting Steering

**Q24: Recompile for the dimension weights — accept the compiled-output change?** Resolved
2026-09-14 (human ruling): compiled into `_rubric/gates/{dimension}.yaml`. Recorded here because the
recompile is an act by the compiler line at a moment this plan does not control, and M10 (9027) is
blocked on it. The alternative considered and rejected: re-adding `dimension_weight` to the
`AuthoredNode` schema (denormalises a dimension-level fact across 25 nodes).

## 8. Outcomes & Retrospective

*Written at completion or cancellation.*
