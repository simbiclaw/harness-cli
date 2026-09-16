# ADR-0005: The Report Write Path and the Two Boundary Contracts

**Status:** accepted (human-dictated 2026-09-16)

**Date:** 2026-09-16

## Context

The system's four-layer architecture (`docs/PRD/PMCA.txt`): **perception** (the producers)
→ **memory** (the INTENTS tree, path-as-ontology) → **cognition** (Argus, the eval
consumer) → **action** (routing + feedback). Four producers — audio2tree, doc2graph,
soft-compiler, and **curated** (human review landing via SIRA + sira-proxy) — fill the
tree. Argus consumes it (three epistemic classes per ADR-0001; eight expertise library
modules, the ninth v6 module being the per-call transcription input artifact, not library
knowledge) and must, per call, produce one QA report record.

Two gaps prompted this ADR (human-directed 2026-09-16):

1. The consumer's output had no sanctioned home in the tree — D15 forbade *all* writes,
   so the report lived nowhere and the downstream renderer had no single source.
2. The knowledge contracts were not yet stated as serving the evaluation function: what
   facets producers extract, and in what schema, must be shaped by the gradable criteria.

The consumer contract is recorded in `INTENTS/PRODUCERS.md` §9 (this repository's copy of
the tree-side authorization is the human's 2026-09-16 directive; the epoch was minted on
that revision).

## Decision

1. **D15 narrows to the referent rule.** Argus never writes *knowledge* — `_rubric/**`,
   `kb.*`/`cookbook.*`/`errors.*`, manifests, `_meta/**`. It gains **exactly one** write
   surface: the **report record**, append-only, written alongside the call log, carrying
   the INTENTS epoch it was evaluated against (replay uses the recorded epoch — I4/I5).
2. **One call recording ↔ one QA report record** (每一通电话录音对应一份质检报告).
3. **Upstream contract — criteria-shaped facets.** Argus defines, per expertise class,
   *which facets* producers must extract and the *schema* of their output, shaped by the
   gradable criteria. The knowledge organization serves the consumer's evaluation function.
4. **Downstream contract — SIRA/sira-proxy.** Argus defines (a) the report-data schema it
   writes into the tree and (b) the report template sira-proxy renders (human-readable,
   likely an H5 page). sira-proxy is a *reader* of the tree, not a producer; human review
   outcomes re-enter as `curated` writes (the §6 feedback loop of PRODUCERS.md, unchanged).

## Consequences

- `tests/test_no_write_path.py` (the S1 fixture) is amended: from "no `src/argus/` writes"
  to "no writes outside the report glob", with red/green samples updated. The referent
  prohibition keeps its teeth.
- `_meta/ownership.yaml` needs a **human-directed re-sync** adding `argus` as writer of the
  report glob, at schema-landing time. Proposed default: reports live in a **sibling
  `reports/` directory** (`*/**/reports/*.json` → `argus`), *not* inside `calls/` —
  audio2tree's existing glob `*/**/calls/*.json` would otherwise multi-own them, and
  `fnmatch` cannot exclude. `conventions.yaml` gains the report type token under the
  `<type>.<slug>.<ext>` grammar.
- D15 prose in CLAUDE.md's operating invariants, spec v5, and the plan-family citations is
  superseded on each document's next executed touch; this ADR governs meanwhile.
- The fresh derivation-pipeline plan owns three sections: the upstream contract, the
  pipeline itself (S2 from scratch; first end-to-end run), the downstream contract.
