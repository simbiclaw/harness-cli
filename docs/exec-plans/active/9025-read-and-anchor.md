# 9025 — The Anchor: Reading the Tree and Grounding the Finding

## 1. Purpose

A verdict is worth nothing unless it rests on something real. This plan builds the two halves of
that: the read surface that resolves the INTENTS tree at a pinned epoch through one Provider, and
the grounding gate that verifies every finding's span and quote against the transcript and resolves
its anchor node — or routes it to a human. Together they are I2 and I4 made executable.

## 2. Big Picture

**One reader, one epoch.** M13 builds `io/intents_provider.py` as the *sole* path by which anything
under `src/argus/` reads the tree, implementing the read protocol `INTENTS/AGENTS.md` already
specifies (deterministic, by-id, five steps) and the capsule parsing contract doc2graph supplied
(`index.md` Bone/Flesh, `ui_binding_ref = <routine_id>#<step_order>`; **`ui_steps.yaml` does not
exist**). Discovery is not its job: which node a call belongs to is audio2tree's routing decision,
and `bottom_up` is written by exactly one mechanism.

**The gate disposes; the model does not.** M12's `core/grounding.py` is pure — `verify_span`,
`verify_quote` (exact substring), `resolve_anchor`, `check_applicability` per the §4 gradient table,
and `meta_verify`. A finding that anchors to nothing real moves to `ungrounded` and routes to a
human; it is never silently dropped. The two grounding fences (`grounding ✗ proposer`,
`grounding ✗ matching_model`) are proved by planted violations in 9024's M8.

**The three epistemic classes** are what this Provider's three readers expose — Versioned Rubric,
Descriptive Facts, Accumulated History (ADR-0001) — and they are not B's two-bucket "knowledge
base". B's own KB integration was two empty stubs, which is why nothing of it is imported.

**Depends on:** 9024 (the fences, and the imported proposal this gate judges).

**File Scope:**
- `docs/exec-plans/active/9025-read-and-anchor.md` (this plan)
- `src/argus/io/intents_provider.py` (new)
- `src/argus/core/grounding.py` (new)
- `tests/test_intents_provider.py`
- `tests/test_grounding.py` (new)
- `tests/test_no_write_path.py` (modify — the D15 no-write-path AST fixture, landed under 9021 M13 (commit `1536b7d`) and declared by no plan on either side of the split until 2026-09-14. It is a standing structural check, not a new artifact; the same class of gap as the dependency paths the split dropped from 9024)

## 3. Milestones

### M12 — Build `core/grounding.py` (I2)

Exact-quote verification against the transcript, INTENTS node resolution at a pinned epoch, and
the `ungrounded` bucket. Path B evidence is declared unanchorable and routes to `ungrounded`: its
text is model-authored prose, not a quote from the cited document.

`Acceptance Test:` `tests/test_grounding.py::test_i2_anchor_or_quarantine_red` — a finding citing
a non-existent node moves to `ungrounded`. `::test_quote_fidelity_red`. `::test_path_b_always_ungrounded`.
`::test_grounding_no_model_import`. **`::test_garbled_transcript_routes_ungrounded`** — a transcript
whose quotes cannot be matched produces no auto-final verdict and no fabricated quality number
anywhere in the record. **Added 2026-09-14:** this test is 9023's M3 acceptance test, named there
and homed nowhere; the gate it exercises is this milestone's, so it is asserted here. 9023's §2
records the same hand-off from its side.


**Contract.**
- *Deliverable:* S3, the grounding gate.
- *Binding constraint:* I2, plus the two grounding fences — the gate imports neither the proposer nor a matching model.
- *Acceptance property:* A finding that anchors to nothing real is routed, never dropped, and quote fidelity is verified against the transcript rather than asserted.
- *Known evidence (advisory):* Evidence on B's document-verification path is model-authored prose rather than a quotation, so it is not anchorable in its current form.


### M13 — Build `io/intents_provider.py` and the epoch reader (I4) — the sole read surface

**Amended 2026-09-14.** Read-only access to `INTENTS/` at a pinned git SHA from `EPOCH.yaml`, with
three category readers — and it is the **only** path by which anything under `src/argus/` reads the
tree. The three readers are not an implementation detail: they are the consumer's end of the
architecture's three epistemic classes (ADR-0001) — Versioned Rubric, Descriptive Facts,
Accumulated History — which is what B's two-bucket "double knowledge base" was a coarser
approximation of.

The Provider implements the read protocol `INTENTS/AGENTS.md` already specifies, which is
deterministic and by-id: confirm the call's L1/L2/L3 attribution from the manifests, read that
node's `intent_manifest.json` (`top_down`/`bottom_up`), read the `_rubric/` items for the cited
dimension, return `deferred` for signals on a node whose `source == "audio2tree"`, and treat an L2
with no Item as a routing label rather than a scored one. **Discovery is not this milestone's job:**
deciding which node a call belongs to is audio2tree's routing protocol (vectorised request, cosine
over L2 descriptions, 0.60 threshold) and it writes `bottom_up` alone. A second decider is how one
call acquires two intents.

**The evaluation record carries the attributed node (restored 2026-09-14).** The first revision of
this milestone deleted the original's *"record the model-selected KB path in the run manifest so
referent selection becomes replayable rather than re-guessed"* and replaced it with read-by-id —
correct about *how* the node is chosen, silent about *whether the choice is recorded*. Nothing now
records which L1/L2/L3 node a call was attributed to, and **532 of 718 calls sit in `_unassigned`**,
so that is not a corner case. The run manifest records the attributed node id (or its explicit
absence) for every evaluation: I4 pins *which revision* of the tree was read, and this records
*which node* was read from it — without both, two runs against the same epoch with different
attributions replay identically, which is the failure I5's hash exists to make detectable.

**The capsule parsing contract** (doc2graph's, one page, M13's reader implements it directly): a
leaf is `index.md` + `assets/` + optional `intent_manifest.json`; **`ui_steps.yaml` does not exist** (0 of 48 capsules carry one — the Flesh steps are embedded in `index.md`. **Discrepancy recorded 2026-09-14:** `INTENTS/PRODUCERS.md` — human-ratified 2026-08-18, and named by this plan as the producer-footprint authority — still lists `ui_steps.yaml` in doc2graph's footprint twice, in §1 and §2. This plan follows the tree, not the ledger, and records the divergence rather than silently overriding a declared authority)
— PRODUCERS.md's name is legacy, and the Flesh steps are embedded in `index.md` as one fenced JSON
block per routine after the `## Part 1: Bone` / `## Part 2: Flesh` sections; `ui_binding_ref` is
`<routine_id>#<step_order>`, and the Operation Manual's ordered-match sequence is a routine's
`step_instruction` values ascending by `step_order`. Read by id and pin the epoch; do not read
`.pipeline/`. Parent-capsule cascade loading and model-compressed summaries are **not** part of the
contract — capsules are authored per-leaf self-sufficient, and hierarchy is carried by the manifest
chain.

`Acceptance Test:` `tests/test_intents_provider.py::test_reads_at_pinned_epoch`.
`::test_no_write_path` — the provider exposes no mutating method.
**The D15 fixture is already built — do not write a second one (corrected 2026-09-14).** This line
previously read *"This is 9002's M7 fixture, which was specified and never written."* It was
written: `tests/test_no_write_path.py` landed under 9021 M13 (commit `1536b7d`, its module
docstring recording exactly that provenance), and it is now declared by this plan. The name given
above — `test_s1_no_write_path_into_intents` — exists in no file in the repository; M13's
no-write-path assertion is the module that already stands.
`::test_sole_read_surface` — no module outside the Provider reads `INTENTS/` (structural).
`::test_capsule_parse_by_id` — a routine's step sequence resolves from `index.md` by id, with
`step_order` ascending, and no traversal by content.
`::test_audio2tree_source_defers` and `::test_manifest_without_item_is_routing_only` — the
protocol's two routing rules, which the plan previously did not implement.

**Contract.**
- *Deliverable:* Read-only access to INTENTS at a pinned epoch, implementing the documented read protocol, as the sole read surface.
- *Binding constraint:* I4 — pinned referents. D15 — no write path into INTENTS from `src/argus/`. **One reader, one epoch:** an unpinned second reader means part of an evaluation reads whatever the working tree says, which is an I4 hole rather than an untidiness.
- *Acceptance property:* Two runs against the same epoch reproduce the same grounding outcomes; no code path opens an INTENTS file for writing; and no module outside this Provider reads the tree.
- *Known evidence (advisory):* One tree, confirmed by inspection (Q7): `_rubric/` and the L1/L2/L3 business KB are co-located, so this is one provider, not two.


## 4. Progress

- [ ] M12: Build core/grounding.py (I2)  (created 2026-09-12)
- [ ] M13: Build io/intents_provider.py and the epoch reader (I4) — sole read surface  (amended 2026-09-14)

## 5. Decision Log

### Decision: One tree, one provider (Q7, answered by inspection 2026-09-14)

**Rationale:** `Source:` the live tree — `INTENTS` is a symlink to a local checkout holding
`_rubric/` and the L1/L2/L3 business knowledge together. The plan's Q7 asked whether they were one
tree or two and committed to recording a scope increase if two; they are one, so M13 is one
provider.

**Confidence:** high — verified by inspection rather than from a document.

### Decision: Path-B evidence is unanchorable under I2 (2026-09-12, inherited)

**Rationale:** `Source:` B's `core/fact_checker.py:119-125` — path B's `EvidenceItem.text` is
model-authored prose produced from a concatenation over cascade-loaded nodes, filed under a single
`primary_intent_path`, so a faithful quote can be attributed to the wrong document. Path B routes to
`ungrounded` until the verification prompt returns a verbatim span.

**Confidence:** high. **Revisit:** M12's execution — and note the empty-KB finding in the archive
makes this structural rather than incidental: there was never a document to anchor to.

### Decision: The gate partitions rather than filters (2026-09-13, inherited)

**Rationale:** `Source:` the archived plan's Surprises — a finding that fails grounding moves to the
`ungrounded` bucket and is routed; it is not discarded. I2's wording ("or it is moved to the
`ungrounded` bucket and routed to a human. Findings are never silently dropped").

**Confidence:** high.

## 6. Surprises & Discoveries

**The read protocol existed all along (2026-09-14).** `INTENTS/AGENTS.md` contains a five-step
deterministic Argus read protocol — confirm the call's L1/L2/L3 from the manifests, read the node's
manifest, read the `_rubric/` items, defer on `source == "audio2tree"`, treat an item-less L2 as a
routing label only — and B's `kb_context_builder` ignored all of it in favour of model-guided
drill-down. The protocol also carries **two routing rules the plan had never implemented**; both are
now acceptance tests in M13.

**`ui_steps.yaml` does not exist (2026-09-14).** `INTENTS/PRODUCERS.md` — human-ratified, and named
by the archived plan as the producer-footprint authority — lists it twice in doc2graph's footprint.
The Flesh steps are embedded in `index.md`. Recorded as a discrepancy against a declared authority
rather than silently overridden.

## 7. Awaiting Steering

*None. Q7 was the open question and it is answered by inspection (one tree).*

## 8. Outcomes & Retrospective

*Written at completion or cancellation.*
