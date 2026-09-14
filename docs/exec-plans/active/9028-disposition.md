# 9028 — Disposition: Routing, the Two Axes, and the Agreement Instrument

## 1. Purpose

A score is not a verdict. Something must decide whether the evaluation is trusted, deferred to a
human, or flagged — and that decision has to rest on evidence about the evaluation itself, not on
how confident the model felt. This plan builds the disposition layer: the routing rules, the
two-axis auto-final gate, the agreement instrument that tracks whether the criteria can be trusted
at all, and the escape sampler that estimates what the gate lets through.

## 2. Big Picture

**Two axes, orthogonal, both required** (D10): coverage (no ungrounded, no deferred) **and**
criterion health (every cited criterion trusted). Neither substitutes for the other — corroboration
can clear a thin finding and can never clear a criterion whose κ is below τ (D4). **The agreement
instrument measures Argus against the *human*** (§6.4): a second model sample is not a second
opinion, and no amount of corroboration among model judgements produces one.

**M19.5 was missing entirely from the archived plan** and two of its acceptance tests asserted over
an axis with no producer. The archived plan's `core/divergence.py` deferred the "real §6 detector and
CriterionHealth" to 9002's M5.5 — which had been overturned — so the deferral chain terminated in
nothing. The mismatch is the reason this milestone exists as its own work rather than a paragraph.

**The escape sampler's split is a hard rule** (patch 1 D22): a random tranche feeds the escape-rate
estimator and a prioritized tranche feeds human recall recovery, and the estimator consumes the
random tranche **only** — otherwise the estimate is biased by the very signal it is meant to check.
The floor is declared (`ESCAPE_RATE_FLOOR = 60`, derived by the rule of three against the 0.05
ceiling), not chosen.

**Depends on:** 9027 (the raw and adjusted numbers the gate dispositions).

**File Scope:**
- `docs/exec-plans/active/9028-disposition.md` (this plan)
- `src/argus/core/route.py`
- `src/argus/core/escape_rate.py`
- `src/argus/core/agreement.py` (new)
- `src/argus/io/criterion_health.py` (new — persistence only; all computation stays in `core/`)
- `tests/test_route.py`
- `tests/test_escape_sampler.py` (modify — the sampler's own tests, present on the tree and declared by no plan until 2026-09-14. This line previously read `tests/test_escape_rate.py`, which does not exist and which no milestone creates; the escape-rate estimator's tests already live in `tests/test_route.py` above)
- `tests/test_agreement_instrument.py` (new)

## 3. Milestones

### M19 — Build `core/route.py` and reconcile the escape estimator (S5)

The three `defer_reason` values, the two-axis auto-final gate, and `core/escape_rate.py` — which
ends 9020's split between sampler and estimator. B's five-condition escalation rule maps onto
`finding_thin` and human routing; `ungrounded` and `criterion_below_tau` are new.

`Acceptance Test:` `tests/test_route.py::test_auto_final_requires_both_axes`.
`::test_ungrounded_always_routes_to_human`. `::test_escape_rate_consumes_random_tranche_only`.


**Contract.**
- *Deliverable:* S5 routing, and the escape estimator reconciled with the sampler.
- *Binding constraint:* D10 — auto-final requires both axes clear. **patch-1 D22** — the escape sampler splits into a random floor and a prioritized tranche, and the estimator consumes the **random tranche only** (the prioritized tranche is excluded from the escape-rate computation); that tranche respects its declared floor. **patch-1 I8** bounds what may reach routing at all.
- *Acceptance property:* A call carrying ungrounded findings never auto-finalises; a biased sample cannot reach the estimator; the floor holds whatever the prioritisation asks for.
- *Known evidence (advisory):* 9020 shipped the sampler with a floor test that must survive this reconciliation. **Corrected 2026-09-14:** the archived text said the floor had no declared value anywhere; it has one — `ESCAPE_RATE_FLOOR = 60` at `src/argus/core/escape_rate.py:45`, landed 2026-09-13 with its derivation recorded in the Decision Log below. This reconciliation must keep it, not declare it.


### M19.5 — The §6 agreement instrument and `CriterionHealth` (added 2026-09-14)

**This milestone was missing entirely, and two shipped acceptance tests depended on it.** M19's
`test_auto_final_requires_both_axes` and M17's `test_corroboration_never_clears_criterion_below_tau`
both assert over a two-axis gate whose **criterion axis had no producer**. `core/divergence.py`'s
docstring defers the real detector to "9002 M5.5" — overturned — so the chain terminated in
nothing; the plan inherited the deferral without noticing that its addressee no longer existed.
The spec requires it in §8 M5 (*"Argus-vs-human κ store; τ gate; drift detector; per-call coverage
computation and the two-axis auto-final gate"*) and §8 M5.5 (*"Escape-rate sampler +
CriterionHealth"*), and §3.6 defines the type.

Land, in `core/` (pure computation) and `io/` (persistence):
- **`compute_kappa(argus_verdicts, human_verdicts)`** — Cohen's κ per criterion. Argus-vs-human,
  **never** Argus-vs-Argus (§6.4): the instrument measures agreement with the human label, and a
  second model sample is not a second opinion.
- **The τ gate** — a criterion at κ < τ is `untrusted`, and a finding resting on it defers with
  `criterion_below_tau`. τ defaults to 0.8.
- **`check_drift(criterion_id, windowed_kappas)`** — the falling-κ detector. This is the consumer
  `assess_drift` was written for; the two must be reconciled rather than allowed to coexist as two
  notions of drift.
- **`CriterionHealth`** — computation in `core/`, persistence in `io/`. `types/compiler_schemas.py`
  already declares the field as *"filled by rolling sample at runtime"*; this is what fills it.
- **Per-call coverage** — the fraction of the verdict resting on grounded findings (D10's first
  axis), computable per call, never a per-call *residue* gate (the hard prohibition).

`Acceptance Test:` `tests/test_agreement_instrument.py::test_kappa_is_argus_vs_human` — the
instrument takes a human-labelled sample and refuses a model-only one.
`::test_criterion_below_tau_defers` — κ < τ defers the finding and no corroboration clears it (D4).
`::test_falling_kappa_demotes` — drift moves the criterion's health, and only the κ pathway writes
health.
`::test_criterion_health_is_populated` — the CriterionHealth the two-axis gate reads has a
producer, asserted end to end rather than by construction.
`::test_coverage_is_per_call` — coverage is computable for a single call; nothing attempts a
per-call residue figure.

**Contract.**
- *Deliverable:* The agreement instrument, the τ gate, the drift detector and the criterion-health store — the producer of the two-axis gate's second axis.
- *Binding constraint:* §6.4 — agreement is Argus-vs-human, never model self-agreement. D10 — the two axes are orthogonal: corroboration clears `finding_thin` and never `criterion_below_tau`. D12 — resample variance measures difficulty, and never touches routing.
- *Acceptance property:* A criterion cited by a verdict has a health state produced from a human-labelled sample; an untrusted criterion defers regardless of how well corroborated the finding is; and drift demotes through κ alone.
- *Known evidence (advisory):* `core/divergence.py` already exists with a provisional detector and no consumer — reconcile rather than reimplement. 9020's escape sampler carries the floor; 9020's agreement seed is in `tests/test_agreement_seed.py` and `core/compiler/agreement.py` (9003's authoring-side κ, a **different** instrument at a different layer — do not conflate them).


## 4. Progress

- [ ] M19: Build core/route.py and reconcile the escape estimator (S5)  (created 2026-09-12)
- [ ] M19.5: The §6 agreement instrument and CriterionHealth  (added 2026-09-14 — was missing entirely; two tests depended on it)

## 5. Decision Log

### Decision: The two axes stay two, and the floor gets a value (2026-09-12, inherited)

**Rationale:** `Source:` D10 and D4 — coverage and criterion health are orthogonal; corroboration
clears `finding_thin` and never `criterion_below_tau`. Separately, the archived plan recorded that
`split_tranches(..., absolute_floor: int = 0)` enforced the floor in four test bodies and in no call
site — a default of zero means a caller who forgets gets no floor and no warning. Declared at 60,
derived from the rule of three against the repo's 0.05 escape ceiling (3/0.05), with the relation
asserted so changing either number alone fails.

**Confidence:** high on the orthogonality; high on the derivation, `Confidence: medium` on whether
60 is the right ceiling basis — the relation is asserted so a future change is a deliberate act.

### Decision: `compute_escape_rate` distinguishes "no reviews" from "no escapes" (2026-09-13, inherited)

**Rationale:** `Source:` the archived plan's Surprises — the function returned 0.0 for an empty
sample, the most reassuring number available, for having reviewed nobody. An estimate and the
absence of one now have different shapes.

**Confidence:** high.

### Decision: Drift demotes through κ alone; the divergence probe is alert-only (2026-09-14, inherited)

**Rationale:** `Source:` `docs/retrospectives/process-derivation-pipeline-spec-v5-patch-1.md:61-73`
(D20: the divergence diagnostic *"schedules human-side work (manifest minting), it does not change any
machine decision"*) and `:80-82` (I8: no logit-derived quantity reaches `severity_map`, deduction,
coverage, criterion health or routing). The two are in tension with any reading where divergence
moves the drift detector's health verdict, and this plan resolves toward the stricter one — the
flag-only entry point. **Corrected 2026-09-14:** an earlier revision of this entry cited "the
archived plan's entry of the same name", which does not exist; the provenance was invented during
the split and the substance has been re-grounded on the patch text it actually rests on.

**Confidence:** medium in the archive's own words; `Revisit:` if the drift module's aggregation turns
out to admit an indirect route.

## 6. Surprises & Discoveries

**A whole milestone was missing, and its absence was invisible (2026-09-14).** Two shipped
acceptance tests asserted over a two-axis gate whose criterion axis had no producer, and the code
that would have built it deferred to a plan that had been overturned. Nothing failed, because a
deferral to a deleted plan looks exactly like a deferral to a live one.

**The agreement instrument is not the compiler's κ (2026-09-14).** 9003's `core/compiler/agreement.py`
holds a κ for *authoring* — whether a compiled criterion is trustworthy — at a different layer, over
a different population. M19.5's instrument measures Argus against the human on real evaluations.
Conflating them would make a criterion's health depend on the compiler's review, which is not a
measurement of agreement at all.

## 7. Awaiting Steering

*None open.*

## 8. Outcomes & Retrospective

*Written at completion or cancellation.*
