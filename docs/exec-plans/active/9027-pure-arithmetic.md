# 9027 — The Pure Arithmetic: Score, Corroborate, Adjust, Replay

## 1. Purpose

Everything downstream of the model is arithmetic that must re-derive identically forever. This plan
builds the four pure stages: the score that turns grounded facts and the rubric into a number, the
corroboration aggregator that decides how much several independent instruments are worth, the
adjust stage that applies anchored precedent without touching the raw number, and the replay record
that makes the whole thing reproducible. None of them moves from B — B's aggregator is a report
builder with no rubric parameter, and neither codebase has any notion of precedent.

## 2. Big Picture

**Raw is history-free.** `score(facts, rubric)` never receives history (I3): the shipped number is a
pure re-derivation from grounded findings and a versioned rubric, and a runtime purity assert
catches a precedent-citing verdict that somehow reaches it. **Adjustment is separate** — the
precedent lane changes `adjusted`, never `raw`. **Replay is the contract that makes it auditable**:
the hash is a function of grounded inputs *and anchored precedents*, and never of a proposed score
(I5).

**Corroboration is weighted by independence, not by count** (I6): independent instruments at 1.0,
a model-judged match to a confirmed referent at a provisional 0.4, and a redundant model judgement
on the same span at **0.0** — no number of correlated re-reads manufactures confidence. The
correlated class has to be *invented* here; B has independent and redundant signals but no concept
of a model-judged referent match.

**The dimension weights land here** (M10): `(Empathy×3 + Resolution×3 + Procedure×2 + Proactive×1)
÷ 9`, read from the compiled rubric — the only weighting that exists, since per-item `deduction` is
uniformly 1.0. The shipped `core/score.py` sums flat across dimensions, as does B's aggregator, so
every score either has produced has weighted all dimensions equally. The compiled home is 9026's
recompile; M10's weighted assertion is blocked on it (Q24).

**Depends on:** 9024 (the port), 9025 (grounding — the gate produces what these stages consume),
9026 (the compiled rubric and the weight).

**File Scope:**
- `docs/exec-plans/active/9027-pure-arithmetic.md` (this plan)
- `src/argus/core/score.py`
- `src/argus/core/corroboration.py`
- `src/argus/core/adjust.py`
- `src/argus/core/replay.py` (new + modify)
- `tests/test_score.py`
- `tests/test_corroboration.py`
- `tests/test_adjust.py`
- `tests/test_replay.py` (new)

## 3. Milestones

### M10 — Extract `score(facts, rubric)`

Not a move. B's `aggregate()` is an 8-argument report builder taking model-authored prose, with no
rubric argument — weight is stamped onto verdicts by `fact_checker.py:193-196` and `is_veto` by
`question_generator.py:110`, both inside modules now in `io/`. Lift both out so the rubric enters
the arithmetic from `core/`.

`Acceptance Test:` `tests/test_score.py::test_i3_determinism_canary` — identical inputs give
byte-identical `raw`. `::test_score_receives_no_history`. `::test_weight_comes_from_rubric_not_verdict`.
`::test_core_no_model_client`.


**Amended 2026-09-14 — the dimension weights are missing, and they were specified all along.**
The formula is `(Empathy×3 + Resolution×3 + Procedure×2 + Proactive×1) ÷ 9`, stated verbatim in
`docs/PRD/eval/skills/evaluator/SKILL.md:221` and `:310`, and it was carried into this line's
design: the legacy v1 node format held the field (`_rubric/rules_criteria/c21-active-flexible-marketing.yaml:50`
still carries `dimension_weight: 1.0`), and patch-1's `AuthoredNode` schema **dropped it** with no
re-adding. **Neither codebase implements it** — simbi's `core/aggregator.py:66-69` and this
repository's shipped `core/score.py:241-242` both sum flat across dimensions, so every score
either has produced weights all dimensions equally. Per-item `deduction` is uniformly 1.0 (the
source rubric is 1/0/NA scored, with no per-item weight column), so the dimension multiplier is
the only weighting that exists.

This milestone therefore carries: `Rubric` gains a dimension-weight map, and `tally()` groups by
dimension before summing. The weights are read from the compiled rubric, never hardcoded (M22's
binding constraint). Their home is `_rubric/gates/{dimension}.yaml`, which gains `dimension_weight`
alongside `hard_fail_rule` — the co-location the authoring spec states at
`soft-criteria-authoring-spec-v4.html:603` (*"a synthesized many-to-one gate, stored alongside the
dimension's weight in the rubric table"*; **citation corrected 2026-09-14** — earlier revisions cited
"§3.4", which does not exist, and then "§3.5", which is ResidueManifest). **That is a
compiled-output change: it requires a recompile and republish at a new epoch, and is a Tier C
decision recorded in Awaiting Steering.**

`Acceptance Test:` `tests/test_score.py::test_i3_determinism_canary` — identical inputs give
byte-identical `raw`. `::test_score_receives_no_history`. `::test_weight_comes_from_rubric_not_verdict`.
`::test_core_no_model_client`. `::test_dimension_weights_are_applied` — a call failing item(s) in a
3× dimension scores strictly lower than the same failures in the 1× dimension; the ÷9 normalisation
is asserted against the formula, and the weights are read from the compiled rubric, not a literal.
`::test_purity_assert_fires` — **the runtime purity assert, restored 2026-09-14.** Spec §2.5.3 says
the invariant is *"enforced twice, on purpose … the signature stops it going in; the gate catches it
if it somehow appears"*, and §8 M4's acceptance names the firing case explicitly. The shipped
`core/score.py:11-13` argues the runtime half away — *"a signature that cannot express one is the
cheaper version of the same check"* — which is a reasonable engineering preference and **not the
spec**. This milestone lands the assert: a confirmed finding carrying `cites_precedent=True` reaching
`score()` raises rather than scoring, and the test proves it fires by planting one. If the plan's
authority concludes the signature alone is sufficient, that is a spec deviation to record in the
Decision Log — not a change to make by leaving the test out.

**Contract.**
- *Deliverable:* A pure scoring function taking grounded facts and the rubric, with the dimension weighting the spec specifies actually applied.
- *Binding constraint:* I3 — `raw = score(facts, rubric)`, and `score` never receives history. I1 — `core/` imports no model client. M22 — no verdict-altering value lives as a hardcoded constant.
- *Acceptance property:* Identical grounded findings and rubric version produce an identical raw score; the rubric's weight reaches the arithmetic from `core/` rather than from inside the quarantine; and a failure in a 3× dimension counts three times a failure in the 1× dimension, as the formula says.
- *Known evidence (advisory):* B's aggregator is a report builder with no rubric parameter, and weight and veto are stamped inside modules bound for `io/`. This is a redesign, not a move. **The weighting gap is not B's alone — the shipped M10 has it too**, which is why this milestone's acceptance test names the dimension multiplier explicitly rather than leaving it to the redesign.


### M11 — Re-litigate NEI scoring

B scores NEI at 0.5 and keeps it in the denominator, so an unverifiable item contributes half a
point. This repository's rules route an ungrounded finding to a human and block auto-final. Adopt
the latter; it changes every score B has produced.

`Acceptance Test:` `tests/test_score.py::test_nei_excluded_from_denominator` —
an NEI item neither scores nor counts. `::test_nei_blocks_auto_final`.


**Contract.**
- *Deliverable:* A scoring policy for unverifiable items consistent with the deferral rules.
- *Binding constraint:* I2 and D10 — an ungrounded finding routes to a human and blocks auto-final.
- *Acceptance property:* An unverifiable item cannot silently contribute to a shipped score.
- *Known evidence (advisory):* B scores the unverifiable case at half a point and keeps it in the denominator; adopting the deferral rule changes every score B has produced. The spec defines no denominator.


### M17 — Build `core/corroboration.py` (I6)

Independence-weighted aggregation over verified signals, across **all three** weight classes:
independent (acoustic measurement, lexical/lookup/ordered-match) at **1.0**; **correlated** (Error
Case, Best Practice — a model-judged match to a confirmed referent) at **W_C = 0.4 PROVISIONAL**,
with the debt logged and the correct value being `1 − corr(matcher_error, proposer_error)` measured
on a human-labelled sample; redundant (another model-judged text criterion on the same span) at
**0.0**. B's local NLI path is an independent instrument. Clears `finding_thin`, never
`criterion_below_tau`.

`Notes:` The correlated class is the hard one and it is **not a port**. B has independent signals
and redundant ones but no concept of a model-judged match to a confirmed referent, because its
aggregator only ever sees model-authored prose. Inventing that class — plus a deterministic test
for "same span, same judgment source" — is what makes soft⊕soft = 0 enforceable rather than
aspirational. An earlier revision of this milestone named only 1.0 and 0.0, which would have left
an implementer to treat a correlated match as either independent (over-confidence) or redundant
(discarding evidence). Both violate I6.

`Acceptance Test:` `tests/test_corroboration.py::test_redundant_signals_aggregate_zero`.
`::test_correlated_signal_weighs_w_c` — a model-judged referent match contributes 0.4, neither 1.0
nor 0.0. `::test_independent_signal_clears_finding_thin`.
`::test_corroboration_never_clears_criterion_below_tau`. `::test_aggregate_no_model_client`.


**Contract.**
- *Deliverable:* The independence-weighted corroboration aggregator.
- *Binding constraint:* I6 — all three weight classes, with W_C provisional and its debt logged. D4 — corroboration clears `finding_thin`, never `criterion_below_tau`.
- *Acceptance property:* Redundant signals manufacture no confidence; a correlated signal weighs as neither independent nor redundant; the two deferral axes stay orthogonal.
- *Known evidence (advisory):* The correlated class has no counterpart in B and must be invented — B's aggregator sees only model-authored prose, so there is nowhere a correlation judgement currently lives. This is the hardest of the three inventions.


### M18 — Build `core/adjust.py` (S4b)

`adjust(raw, history)`. Genuinely new — neither codebase has any notion of precedent. Unanchored
precedents are dropped, never applied; empty precedents give `adjusted == raw`.

`Acceptance Test:` `tests/test_adjust.py::test_empty_precedents_adjusted_equals_raw`.
`::test_unanchored_precedent_dropped`. `::test_applied_precedents_recorded`.


**Contract.**
- *Deliverable:* The precedent-application stage.
- *Binding constraint:* I3 — `adjust(raw, history)` is pure, and unanchored precedents are dropped rather than applied. I5 — anchored precedents enter the replay hash.
- *Acceptance property:* Empty precedents leave the score unchanged; the applied set is recorded and replayable.
- *Known evidence (advisory):* Neither codebase has any notion of precedent. What a precedent is on disk is unconstrained by the spec — it is a design, not a port.


### M21 — Persist the replay record (I5)

Store the FindingGraph, `intents_sha` and rubric version. `replay_hash` is a function of
**grounded inputs *and* anchored precedents** — and never of the proposed score (I5). An earlier
revision of this milestone said "grounded inputs only", which drops the precedent set from the hash
and leaves it unable to detect the change it exists to detect: two runs citing different precedents
would hash identically. B discards every intermediate today, so no report is re-derivable.

`Notes:` The manifest path needs a new exact-filename glob in `INTENTS/_meta/ownership.yaml`
assigned to exactly one producer **before** the file may exist. That ledger requires every file to
match exactly one glob with zero orphans, CI-enforced, and `_meta/` uses exact-filename globs with
no `*.yaml` wildcard. The existing compiler-produced sidecar `_meta/residue-manifest.yaml` —
`schema_version: "1.0.0"`, top-level `compiler_epoch`/`sources`/`rows` — is the precedent to
follow. Reported in issue #16; verify against the live tree before writing.

`Acceptance Test:` `tests/test_replay.py::test_stored_graph_rederives_identical_result`.
`::test_replay_hash_includes_anchored_precedents` — two graphs identical but for their precedent
set must hash differently. `::test_replay_hash_excludes_proposed_score`.


**Contract.**
- *Deliverable:* A stored record that re-derives the verdict.
- *Binding constraint:* I5, as written in CLAUDE.md — quoted, not paraphrased: the hash is a function of grounded inputs and anchored precedents only, never of the proposed score.
- *Acceptance property:* The stored record re-derives an identical result; changing only the precedent set changes the hash; the proposed score never does.
- *Known evidence (advisory):* An ownership ledger governs where such a file may live, and an existing compiler-produced sidecar is the precedent. Shape, name and versioning are yours.


## 4. Progress

- [ ] M10: Extract score(facts, rubric) + apply the dimension weights  (amended 2026-09-14)
- [ ] M11: Re-litigate NEI scoring  (created 2026-09-12)
- [ ] M17: Build core/corroboration.py (I6)  (created 2026-09-12)
- [ ] M18: Build core/adjust.py (S4b)  (created 2026-09-12)
- [ ] M21: Persist the replay record (I5)  (created 2026-09-12)

## 5. Decision Log

### Decision: B's aggregator is not `score(facts, rubric)`; M10 is a redesign, not a move (2026-09-12, inherited)

**Rationale:** `Source:` B's `core/aggregator.py:17-27` — an eight-argument report builder taking
model-authored prose, with no rubric parameter; weight and veto are stamped onto verdicts at
`core/fact_checker.py:193-196` and `core/question_generator.py:110`, inside modules now quarantined
in `io/`. Lifting both out is what lets the rubric enter the arithmetic from `core/`.

**Confidence:** high — established by an adversarial pass that set out to falsify the opposite claim.

### Decision: Dimension weights are applied here, read from the compiled gate (Q24, 2026-09-14)

**Rationale:** `Source:` the archived plan's Q24 entry and its Surprises — neither codebase
implements the specified weighting, including the `score.py` this plan modifies. `Rubric` gains the
dimension-weight map; `tally()` groups by dimension before summing; the values come from the
compiled rubric, never a literal (M22's constraint).

**Confidence:** high on the gap; the home is 9026's recompile and this milestone is blocked on it
until then.

### Decision: NEI is excluded from the denominator and blocks auto-final (2026-09-12, inherited)

**Rationale:** `Source:` B scores NEI at 0.5 and keeps it in the denominator, so an unverifiable
item contributes half a point. This repository's rules route an ungrounded finding to a human and
block auto-final (I2, D10). Adopting the deferral rule changes every score B has produced.

**Confidence:** high.

## 6. Surprises & Discoveries

**Dimension weights: specified, unimplemented by both codebases, home unresolved in the record
(2026-09-14).** The formula is verbatim in the evaluator skill; the legacy v1 node carries
`dimension_weight`; the current compiled tree carries it nowhere; and both aggregators sum flat.
**Corrected 2026-09-14:** this entry asserted the field was "dropped in a schema migration" — the
companion `soft-criteria-authoring-spec-v4-patch-1.md:181` says it was **added** by that patch, the
same file contradicts itself later, and the pipeline patch-1 never mentions it. The *gap* is
verified; the *cause* is unresolved (9026's entry records the same). A three-week-old field
drop survived two reviews and a shipped milestone because no test asserts what a score *should* be,
only that it re-derives. The companion spec is internally inconsistent about the field's history —
recorded as unresolved rather than resolved by preference.

**Corroboration's correlated class already existed on the authoring side (2026-09-13, inherited).**
9003's `core/compiler/classify.py` classifies an exemplar/case match as correlated and
`core/compiler/agreement.py` already holds `_W_C = 0.4` with the same provisional note. M17 invented
the runtime aggregator, not the class; the constant now lives deliberately in two places (a compiler
private is not a runtime contract), which is new debt for the surface plan.

## 7. Awaiting Steering

*None open. Q24 is resolved and its consequence — M10's weighted assertion waits for 9026's
recompile — is recorded in the Decision Log rather than re-litigated here.*

## 8. Outcomes & Retrospective

*Written at completion or cancellation.*
