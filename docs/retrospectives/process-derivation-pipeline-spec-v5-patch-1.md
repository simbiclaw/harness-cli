# Patch 1 — Continuous Proposer, Divergence Diagnostic, and Provenance Separation

**Patches:** `process-derivation-pipeline-spec-v5.html`
**Date:** 2026-08-25
**Status:** draft
**Source:** LLM-as-a-Verifier (arXiv:2607.05391v2) analysis + 9020 requirements interview
**Exec-plan:** 9020 (next free; 9002–9009 consumed)

---

## Context

`LLM-as-a-Verifier` proposes three verification-scaling axes: score granularity (expectation
over scoring-token logits instead of argmax), repeated evaluation (K), and criteria
decomposition (C). Read against this pipeline, **all three live on the propose side of the
seam.** The paper has no deterministic gate; its "verification accuracy" is measured against a
hidden oracle that this domain does not have. Its transferable content is therefore *making a
proposer worth grounding* — not a replacement for S3/S4.

This patch adopts the granularity axis into S2, adds the divergence diagnostic it enables,
and fences the result so the finer number cannot leak into the disposer.

**What is NOT adopted, and why:**

- **The continuous score as a shipped number.** D7/D8 stand unchanged. A continuous
  `proposed_score` is still a proposed score; quarantine is indifferent to its resolution.
- **Repeated evaluation (K) as a routing signal.** §4.2 of the paper is explicit: averaging K
  evaluations shrinks variance as O(1/K) while **bias is unchanged**, with diminishing returns
  from correlated biases on hard examples. Low variance can mean confidently wrong. D12 stands:
  resample variance never touches routing. K is available behind a flag, diagnosis-only.
- **Criteria decomposition as a new mechanism.** The compiler (9003) already is this axis, and
  does it better — the paper's decomposition is hand-designed, which its own limitations section
  concedes.

---

## D19: The proposer MAY emit a continuous proposed_score

Where S2 emits a `proposed_score`, it is computed as the expectation over the distribution of
scoring-token logits rather than by taking argmax of the sampled score token.

- **Scale:** single-token letter scale, G=20. Integers multi-tokenize and break extraction.
- **Resolution:** per-dimension (4 per call), matching the derived scores it will be diffed
  against. Per-criterion is a later refinement if divergence localization proves too coarse.
- **Repetition:** K=1 at launch. K>1 behind a config flag, diagnosis-only, never routing.
- **Storage:** a quarantined block in `FindingGraph`. `EvaluationResult` remains
  derivation-only and gains nothing from this patch.

**Contingent on capability.** G=20 requires top-k logprobs at the chosen token position with
k ≥ G. This is unverified on the target stack (see *Carried-open* below). Declared fallback: set
G to whatever k the stack exposes and **record G per evaluation**, so the number stays
interpretable across a capability change.

**Rationale for adopting at all, given it never ships.** Three uses, in descending value:
(1) it makes the divergence diagnostic (D20) a real scalar rather than a tie-saturated
near-binary; (2) it lets S2 order its hunt budget toward likely violation mass; (3) it
prioritizes escape sampling within the constraint of D22.

---

## D20: Divergence diagnostic (|proposed − derived|)

Per dimension per call, compute `|proposed_score − derived_score|`, aggregated over the same
windows as κ — one drift clock, two instruments.

- Feeds the **existing §6 drift detector as an additional input**, not a separate channel. One
  demotion pathway.
- A widening divergence flags for **calibration injection** — i.e. it schedules human-side work
  (manifest minting), it does not change any machine decision.
- Divergence is the observable meaning of "the proposer became more aligned with human" as
  curated anchors land: shrinking divergence across manifest epochs, confirmed by rising κ.

**Prohibition (see I8):** divergence never touches routing, auto-final rights, coverage, or any
`score()`/`adjust()` input.

---

## I8 — Provenance separation (new invariant)

> Logit-derived continuity is proposer-internal and MUST NOT reach any disposer input.
> Specifically: no logit-derived quantity may feed `severity_map`, `deduction`, coverage,
> criterion health, or routing.

Two continuities now exist in the system and they must never be confused:

| | Source | Correlation with model bias |
|---|---|---|
| **Proposer granularity** (D19) | scoring-token logits | maximal — it *is* a model self-report |
| **Verdict granularity** (`severity_map`) | Calibration Manifest, human-annotated | decorrelated by construction |

The anticipated failure is a well-meaning simplification: "we already have a continuous signal,
use it for severity." That converts the human anchor into a model self-report and silently
re-couples the two. I8 exists to make that a fixture failure rather than a design discussion.

This is stated as an **I-series invariant, not a D-series decision** — it is architectural, not
a choice log entry. It is the same prohibition the CLAUDE.md operating section already carries
against trusting `model_confidence`, extended to cover a signal that looks more legitimate.

---

## D21: Proposer deployment contract

The proposer is a **local open-weight model** served on Apple Silicon (M3 Ultra 256 GB) via
mx-vlm. Single canonical model with a declared swap path; a heterogeneous roster is deferred to
a C2-motivated decorrelation experiment.

- **Config:** in-repo, `config/` layer, endpoint + model hash pinned. Proposer identity is part
  of the evaluation record.
- **Determinism:** hunt pass at task temperature; score pass greedy + seeded. All sampling
  params recorded in `FindingGraph`.
- **Interface shape (M0 requirement):** the Provider accepts a **set** of calls and returns a
  set of finding-sets, even when the set has size one. This keeps batched-vs-single-stream a
  swap behind the io boundary (see B2.d, carried-open).
- **KV-cache reuse (M0 acceptance criterion, hard):** scoring passes MUST reuse the transcript
  KV cache. Without it, per-dimension scoring re-prefills thousands of tokens four times and
  D19's per-dimension resolution is unaffordable at volume. **This criterion is what makes D19
  viable — if it cannot be met, D19 falls back to one call-level score.**

### mlx-dspark is a throughput layer, not a judgment component

`mlx-dspark` runs EAGLE-family speculative decoding (DeepSeek DSpark, z-lab DFlash) natively on
MLX. The target verifies every drafted token, so **output is identical to plain decoding**,
diverging only at floating-point ties where the logit margin is ≈0.

Consequences for this spec:

1. It **cannot alter judgment**. No epoch treatment, no rubric adjacency, no appearance in the
   layer fences beyond a pinned dependency of the io Provider. Log drafter + mode + cap
   alongside `sampling_params`.
2. It accelerates the **hunt** pass (long generation) and is **irrelevant to the score pass** —
   a single scoring token has nothing to amortize. The two passes are distinct call types with
   distinct configs, not one setting.
3. Its measured gains are single-stream. Speculative decoding and batching pull against each
   other, and at 3000 calls/day batch throughput is the binding constraint — hence B2.d.

### Capacity note (informational, not normative)

3000 calls/day ≈ 28.8 s/call at 24/7 utilization; under 15 s/call on a 12-hour window. An 8-bit
27B on M3 Ultra decodes roughly 20–25 tok/s single-stream (~35–40 with speculative decoding). A
hunt pass emitting evidence across 25 items plausibly runs 1500–2000 output tokens. The
arithmetic does not close single-stream. Batched decode plus KV-cache reuse is the path that
closes it. **These are estimates, not measurements — M0 must measure before the serving shape
is fixed.**

---

## D22: Escape sampler splits into random floor + prioritized tranche

The escape-rate estimator (D11) requires an unbiased sample of auto-passed calls. D19 enables
prioritizing which auto-passed calls humans review (low continuous proposed score, no grounded
finding — the C6 recall problem wearing a flag). Prioritizing the *whole* sample would bias the
very number D11 depends on.

Therefore the sampler splits:

- **Random tranche** — 50% at launch, never below a declared absolute minimum. Feeds the escape
  rate estimator. This is the only decorrelated window into auto-passed calls.
- **Prioritized tranche** — 50%, ordered by proposer signal. Feeds recall recovery and
  calibration minting. **Excluded from the escape-rate computation.**

`compute_escape_rate()` (M5.5) MUST consume only the random tranche.

---

## Schema deltas

`FindingGraph` gains:

```
proposer_id          # model identity + hash; drift attribution
alignment_epoch      # derived from the calibration manifest epoch it was built at
sampling_params      # temperature, seed, drafter/mode/cap, G, K
proposed_scores{}    # QUARANTINED; per-dimension continuous scores + G actually used
```

**Replay (I5) is unaffected.** The stored findings remain the replay-bearing record; logprob
distributions and `proposed_scores` are **non-replay-bearing diagnostics**. Proposer
nondeterminism must not infect the replay contract — `EvaluationResult` re-derives from
surviving anchored findings regardless of which proposer produced them.

`alignment_epoch` is derived (`align@<manifest-epoch>`), not an independent counter, so
rebuildability and drift attribution are mechanical: when κ moves, the record distinguishes a
rubric-epoch change from a manifest-epoch change from a proposer change.

---

## Milestones for 9020

9020 is a standalone plan declaring a dependency on 9002, not an amendment to it. 9002 is
authored with M0–M7 all unstarted; injecting scope into an open plan is the pattern
`9004-execution-mistakes.md` identifies as a root cause.

| ID | Milestone | Depends on |
|----|-----------|-----------|
| N0 | Logprob capability spike + capacity measurement (gates D19) | — |
| N1 | Batch-shaped Provider interface + KV-cache reuse | 9002 M6 |
| N2 | Continuous `proposed_score` per dimension, quarantined | N0, N1 |
| N3 | Divergence diagnostic into the §6 drift detector | 9002 M5.5, N2 |
| N4 | Escape sampler tranche split | 9002 M5.5 |
| N5 | I8 fixture + `proposed_scores` non-replay-bearing fixture | N2 |

**Fixtures (red+green, standing):**

- `test_i8_red` — a logit-derived quantity wired into `severity_map` → structural rejection.
- `test_i8_green` — `severity_map` resolves only through the calibration manifest.
- `test_d19_quarantine` — a continuous `proposed_score` never reaches shipped raw/adjusted or
  the replay hash (extends the existing `test_i7_end_to_end`).
- `test_d22_red` — `compute_escape_rate()` fed a prioritized-tranche sample → rejection.
- `test_d22_green` — random tranche only; estimator unbiased.
- `test_replay_ignores_proposer` — two `FindingGraph`s with identical findings but different
  `proposer_id`/`proposed_scores` re-derive an identical `EvaluationResult`.

---

## Carried-open

- **B2.a — logprob exposure.** Whether the MLX stack surfaces top-k ≥ 20 logprobs at a chosen
  token position is unverified. Resolved by N0. Fallback declared in D19 (set G to available k,
  record it). If no top-k is exposed at all, D19 reduces to argmax scores and only D20 survives.
- **B2.d — serving shape.** Batched production path (mlx-dspark idle, reserved for
  interactive/dev) vs single-stream + speculative with a longer window or a second box.
  Deferred by owner. Safe to defer **only** because D21 mandates the batch-shaped interface.

---

## Housekeeping surfaced while patching

1. **D-series collision.** `measurement-profiles-design.md` defines D13–D18 (measurement
   profiles, profile organization, profile schema, embed-vs-reference, `_rubric/profiles/`).
   The pipeline spec already uses D13–D18 for the v6 conformance decisions (scope, referent,
   confirmation, acoustic/phrase, two-stage, pins+layers). These are two unrelated series
   sharing numbers. This patch continues the **pipeline** series at D19 and recommends the
   measurement-profiles series be namespaced (e.g. `MP-D1…`) before either is cited elsewhere.
2. **Stale spec path.** `9002-implement-argus-eval-pipeline.md` §1 references
   `docs/PRD/process-derivation-pipeline-spec-v5.html`. The spec lives at
   `docs/retrospectives/process-derivation-pipeline-spec-v5.html`.
3. **Item count.** The spec body and §10 handoff say "27 items". Patch 1 to the companion spec
   establishes **25 rules_criteria items** (PA 7, E&T 8, PR 8, PV 2). Corrected in the companion
   patch 3; the pipeline spec's handoff text needs the same find-and-replace.
