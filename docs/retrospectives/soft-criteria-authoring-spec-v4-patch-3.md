# Patch 3 — Calibration Manifest as a Living Channel, Exposure Integrity, and Item-Count Correction

**Patches:** `soft-criteria-authoring-spec-v4.html`
**Date:** 2026-08-25
**Status:** draft
**Source:** LLM-as-a-Verifier (arXiv:2607.05391v2) analysis + 9010 requirements interview
**Follows:** Patch 1 (accepted 2026-07-10), Patch 2 (accepted 2026-07-16)
**Companion:** `process-derivation-pipeline-spec-v5-patch-1.md` (D19–D22, I8)

---

## Context

Patch 1 established that Acoustic and Phrase are **evidence sources**, not sibling rule
categories. Patch 2 fixed the compiler pipeline itself — companion-doc manifests, halt-on-
conflict, topological ordering, gate-checkability audit, self-audit. This patch addresses the
remaining input the spec still models incorrectly: the **Calibration Manifest**.

The spec (§0.5) treats it as a passive artifact with one consumer. It has two, on different
sides of the seam, with different lifecycles and opposite depreciation curves — and conflating
them is how a human anchor quietly becomes a model self-report.

---

## 1. The Calibration Manifest has two consumption paths

| | Consumer | Role | Class |
|---|---|---|---|
| **Severity anchoring** | disposer — `severity_map` reference | the shipped score stays human-anchored regardless of what the proposer believes | **lock** — authority-bearing, appreciates, never absorbed by a model |
| **Curated exposure** | proposer — few-shot anchors in the S2 prompt | a better-aligned proposer hunts better: higher recall, less quarantine waste | **crutch** — capability-substituting, depreciates on base-model change |

**Why aligning the proposer with humans is safe:** the proposer never disposes. If alignment
fails, the gate and the pure stages are unmoved and the shipped verdict is unchanged — the only
cost is wasted hunt budget. This is the seam doing exactly the work it exists for.

**Asset-management rule.** The manifest is the durable artifact; any exposure set is *derived*.
Human judgment lives in versioned manifest epochs. No human correction may exist **only** inside
an alignment artifact.

**No SFT/DPO.** Alignment is curated few-shot exposure, permanently. This is not a staging
decision to be revisited: it keeps the crutch model-portable, so a base-model swap costs
re-validation rather than re-training — a materially slower depreciation curve than fine-tuning.

---

## 2. The manifest is drift-triggered, not one-time

Per the generic evaluator skill's own calibration philosophy, distribution is **deliberately
uneven** — countermeasures, not a curriculum — concentrated where the evaluator's bias is known
to misjudge, at roughly a **2:1 danger-zone ratio**, because a false pass on the judgment layer
costs asymmetrically more than a false flag.

1. **Trigger** — a scoring deviation: falling κ, rising escape rate, or **widening
   proposed-vs-derived divergence** (companion D20).
2. **Injection** — targeted human-judged cases drawn from the **Error Case Library** (confirmed
   failures) and **Best Practice Cookbook** (confirmed exemplars), curated, committed as a new
   manifest epoch. **Standalone: no compile run required.**
3. **Recalibration by reference** — because `severity_map` is a *reference into* the manifest
   epoch, injection re-anchors severity and re-evaluates AUTH-9 coverage on existing nodes.
   The compiler re-runs only when **rules** change.

**Boundary.** The channel recalibrates judgment; it does not author rules. If an injection
reveals a *rule* is wrong rather than miscalibrated, that correction goes through the compile
path. A manifest-edits-rules shortcut is the C5 loop wearing a calibration costume.

**Location and epoch.** `INTENTS/_meta/calibration-manifest.<epoch>.yaml`. Epoch in the filename
means the calibration channel versions **independently** of `_rubric/` — which is what makes
standalone injection real. Argus reads it and never writes it; minting is producer-owned,
write-time, outside `src/argus` (the S1 no-write-path fixture extends to this file).

---

## 3. Schema additions to CalibrationManifest rows

The Pydantic `CalibrationManifest` landed in 9003 M0. Rows gain three fields:

```yaml
used_for: exposure | measurement   # EXCLUSIVE, no migration, ever
provenance: deferred | ungrounded | drift | escape-random | escape-prioritized | manual
blind: true | false                # was the human score produced before seeing the disposed verdict?
reason: <free text>                # required when provenance == manual
```

### 3.1 `used_for` — exposure and measurement are disjoint

A case shown to the proposer as a few-shot anchor cannot also serve as a κ-measurement item or
escape seed. That is measuring on shown data, and κ would overstate alignment exactly when it
most needs to be honest.

Note this holds **despite there being no fine-tuning**. Prompt exposure is still exposure; the
rule is about what the proposer has *seen*, not about gradients.

### 3.2 `provenance` — because review sampling is itself biased

Manifest cases are minted from human review of *disposed* results. But humans only see what the
pipeline surfaced: deferred, ungrounded, drift-demoted, escape-sampled. Auto-finalized calls
nobody reviews cannot generate calibration cases — so the proposer's blind spots partly
determine what it gets aligned on. The loop teaches it about the contested region and nothing
about its silent misses.

The one decorrelated window is the **random tranche** of the escape sampler (companion D22).
`escape-random` cases are therefore the scarce, load-bearing provenance and should be weighted
accordingly during curation.

### 3.3 `blind` — anti-anchoring

If the reviewer sees the machine's verdict before scoring, the "human" label is anchored on the
machine's suggestion — human-confirmed laundering machine bias, the C2 failure exactly. For any
case being minted into the manifest, the discipline is **blind-first**: score before seeing the
disposed result.

Enforce in tooling if a review surface exists. Procedure-only is acceptable as a **declared
debt**, but the `blind` flag is mandatory either way so contaminated cases are at least labeled
rather than silently mixed.

---

## 4. New prohibitions

- **AUTH-11 — manifest row missing `provenance` or `used_for` → reject.** An unlabeled row
  cannot be checked for tranche balance or exposure disjointness, so it poisons both.
- **AUTH-12 — row with `blind: false` used in curation without an explicit override → reject.**
  Anchored labels may exist in the manifest for audit; they may not silently become anchors.
- **AUTH-13 — exposure set intersecting the measurement set → reject.** Enforced at curation
  time, not discovered at κ time.

### Tranche-balance check (F4)

Advisory below a threshold, **hard above it**:

- **Threshold: 40 cases** in the exposure set.
- **Criterion: ≥ 20% of exposure cases carry `escape-random` provenance.**

Below 40 the curated set is small enough that skew is visible by eye and a blocking gate is
friction for no gain; above it, provenance skew becomes invisible and the check earns its cost.

> **Both numbers are authored here, not derived from measurement.** They are the patch author's
> choice and should be tuned once real provenance distributions exist. Flagged rather than
> presented as settled.

---

## 5. Prompt-budget selection (replaces the fine-tuning capacity question)

With no fine-tuning, the binding constraint is **context budget**, not GPU-hours. As the manifest
grows past what fits, selection matters:

- **Launch:** fixed curated capped set — the 2:1 danger-zone curation, whole set until it
  doesn't fit.
- **Future option (declared, not adopted):** per-call retrieval of nearest cases. More
  effective, but it makes *which anchors the proposer saw* vary per call. Harmless past the
  seam, but it must be recorded in `FindingGraph` for drift attribution, so it is not a
  drop-in.

---

## 6. Item-count correction: 25, not 27

The spec body, §3.6b compile pattern, and §7 handoff all say **27 items**. Patch 1 establishes
**25 rules_criteria items**: Procedural Accuracy 7, Empathy & Tone 8, Problem Resolution 8,
Proactive Value 2.

The 27 figure appears to have originated in the sampled-gaps analysis, which itself used both
"27 items" and "25 independent binary verdicts" in the same document. Acoustic Feature and Phrase
& Keyword are **not** two additional rule items — Patch 1 establishes them as evidence sources
consumed by the 25.

Apply as a find-and-replace across the spec, and the same correction to the pipeline spec's §10
handoff.

---

## 7. §3.6b compile pattern is superseded

The per-item pattern in §3.6b loops over items **independently**. Patch 2 Surprise 3 establishes
that items form dependency pairs (21 depends on 20's signal IDs; 22+26), requiring topological
ordering. The §3.6b pseudocode as written will produce stale or unresolvable signal references.

Patch 2's dependency-aware ordering is authoritative. §3.6b should be reduced to a pointer at it
rather than carrying a contradicting loop — this patch does not restate the ordering algorithm.

**Cross-reference for 9010:** Patch 2 Surprise 4 ("gate-checkable signals routinely hide model
dependencies") and companion invariant **I8** are the same boundary observed from two directions
— once in compiled Item signals, once in proposer scores. Both hold that a quantity is only
gate-checkable if a deterministic check can confirm its referent. The B-F Gate-Checkability
Audit and the I8 fixture should be treated as one discipline with two enforcement points.
