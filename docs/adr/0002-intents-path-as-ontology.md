# ADR-0002: INTENTS Path-as-Ontology Semantic Layer

**Status:** accepted

**Date:** 2026-07-04

## Context

The v1 architecture named a "Conversation Distillation" domain that produced an intents tree and a "Knowledge Calibration" domain that reconciled it with a compute graph, but neither was given a concrete on-disk representation. The tree existed as a concept, not as a data structure consumers could read at a pinned version.

This ADR establishes the INTENTS semantic layer as a concrete, git-versioned, path-as-ontology data artefact — not code, not a database, not a service. It is the single source of behavioural truth for all consumer-tier applications.

## Decision

### Path-as-ontology

The INTENTS tree is represented on disk as a directory tree. The path *is* the ontology — the structure of the filesystem encodes the intent hierarchy, and every node has a predictable location derived from its semantic role.

The naming grammar is `<type>.<slug>.<ext>`:

- **`type`** — the node's role in the ontology: `kb` (knowledge base / descriptive fact), `cookbook` (best practice), `errors` (error case), `case` (L3 case node), `index` (L2 capsule Bone), `ui_step` (L2 capsule Flesh), `rules` (rubric rule), `acoustic` (rubric indicator), `lexicon` (rubric phrase/keyword).
- **`slug`** — a stable, human-readable identifier, demand-minted from customer language (not assigned by an engineer). Slugs are permanent; renaming is a breaking change.
- **`ext`** — `yaml`, `json`, `jsonl`, or `md` depending on content type.

### Tree structure

```
INTENTS/
  AGENTS.md                  # how agents read and write this tree
  EPOCH.yaml                 # current git SHA epoch
  tensors.json               # cross-tree embeddings index
  _meta/
    conventions.yaml          # naming, formatting, and structural rules
    ownership.yaml            # producer → file glob mapping
  _rubric/
    rules/                    # Rules & Criteria (versioned rubric)
      ...
    acoustic/                 # Acoustic indicator framework (versioned rubric)
      ...
    phrase-keyword/           # Phrase & Keyword lexicon (versioned rubric)
      ...
  <domain-slug>/              # one directory per business domain
    index.md                  # L2 capsule Bone (top-loaded)
    <case-slug>/              # L3 case node
      context.yaml            # case metadata, anchors
      kb.<slug>.yaml          # anchored descriptive fact
      cookbook.<slug>.yaml    # anchored best practice (history)
      errors.<slug>.yaml      # anchored error case (history)
```

### Git-SHA epoch

Consumers (Argus, Metis, Hermes) read the INTENTS tree at a **pinned git SHA**, declared in their config. This means:

- Tree upgrades are explicit — no consumer sees a change it didn't ask for.
- Rollback is `git checkout <previous-sha>` (a filesystem operation, not a database migration).
- Reproducibility: a verdict computed at SHA `abc123` can be re-verified at SHA `abc123` by any consumer.
- The tree is **the single source of truth** — no secondary store, no cache that can diverge.

### Configurable location

The default location is `INTENTS/` at the repository root. The path is overridable via `argus.config.intents_path` for deployments where the tree lives elsewhere (e.g., a separate data repository, a mounted volume, or a checked-out submodule). The actual config mechanism is deferred to the first Argus exec-plan.

### Bottom-up authority

The intents tree is the **authoritative source of behavioural truth**. When the tree and the compute graph (from doc2graph) disagree, the tree wins. This is the bottom-up authority invariant established in `docs/product-specs/shared/calibration.md` and encoded in the asymmetric `calibrate(intentTree, computeGraph)` signature.

Support calls are the behaviour corpus from human agents performing real work. Operation manuals are documentation, which is always partial and frequently stale. The tree captures what agents actually do; the graph captures what the manual says to do.

### Boring-tech choice: filesystem over RAG

The INTENTS tree is small enough (a few hundred files for the worked domain) to be read directly from disk. No vector database, no RAG pipeline, no embedding index at read time. The path-as-ontology structure is the index — walking the tree is the query. This is deterministic, zero-latency, and requires no external service. The `tensors.json` file provides pre-computed embeddings for cross-tree search, generated at build time by the transformation layer, not at read time by the consumer.

## Consequences

- `INTENTS/` is a first-class top-level tree in the repository, sibling to `src/` and `docs/`.
- The Expertise Library domain (v1) dissolves — its nine reader interfaces collapse to one INTENTS Provider that walks the tree and returns typed nodes. See ADR-0004.
- Knowledge Calibration (v1) dissolves — the tree is already single-source; no runtime reconciliation is needed. See ADR-0003.
- Every consumer must declare its pinned SHA in config. Running against an unpinned (floating) tree is forbidden.
- The tree is exempt from `.importlinter` — it is data, not code.
- Every file in the tree must be owned by exactly one producer, tracked in `_meta/ownership.yaml`. Zero multi-owner, zero orphaned.
- The `references/node_contract.md` (the capsule Bone/Flesh shape contract) is a prerequisite for tree-interior schemas; it is owned by the human and is not delivered by this ADR.
