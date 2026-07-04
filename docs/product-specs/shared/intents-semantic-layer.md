---
verification-status: proposed
last-reviewed: 2026-07-04
consumed-by: Argus (Metis and Hermes via interface reference)
---

# INTENTS Semantic Layer (shared)

The INTENTS tree is the **single source of behavioural truth** for the Argus/Metis/Hermes platform. It is a git-versioned, path-as-ontology data artefact — not code, not a database, not a service. Argus reads it at a pinned SHA via the INTENTS Provider (`argus.io`). See ADR-0002 for the full architectural rationale.

## Path-as-ontology

The directory structure *is* the ontology. The path of every file encodes its semantic role. The naming grammar is `<type>.<slug>.<ext>`:

- **`type`** — the node's role: `kb` (knowledge base / descriptive fact), `cookbook` (best practice), `errors` (error case), `case` (L3 case node), `index` (L2 capsule Bone), `ui_step` (L2 capsule Flesh), `rules` (rubric rule), `acoustic` (rubric indicator), `lexicon` (rubric phrase/keyword).
- **`slug`** — a stable, human-readable identifier, demand-minted from customer language (not assigned by an engineer). Slugs are permanent; renaming is a breaking change.
- **`ext`** — `yaml`, `json`, `jsonl`, or `md` depending on content type.

## Tree layout

```
INTENTS/
  AGENTS.md                  # how agents read and write this tree
  EPOCH.yaml                 # current git SHA epoch
  tensors.json               # pre-computed cross-tree embeddings
  _meta/
    conventions.yaml          # naming, formatting, and structural rules
    ownership.yaml            # producer → file glob mapping
  _rubric/
    rules/                    # Rules & Criteria (versioned rubric)
    acoustic/                 # Acoustic indicator framework (versioned rubric)
    phrase-keyword/           # Phrase & Keyword lexicon (versioned rubric)
  <domain-slug>/              # one directory per business domain
    index.md                  # L2 capsule Bone (top-loaded)
    <case-slug>/              # L3 case node
      context.yaml            # case metadata, anchors
      kb.<slug>.yaml          # anchored descriptive fact
      cookbook.<slug>.yaml    # anchored best practice (history)
      errors.<slug>.yaml      # anchored error case (history)
```

## Anchor levels

The anchor level determines where a piece of knowledge is attached in the tree:

- **Rubric** (`_rubric/`) — anchored to the rubric version, not to any domain or case. The rubric is the yardstick; it applies across all domains equally.
- **Facts** (`kb.*.yaml`) — anchored at **scope level** (the `<domain-slug>/` directory). A fact about "annual report submission" belongs to the `annual-report-submission/` domain, not to a specific case within it. Scope-level anchoring means facts are shared across all cases in that domain.
- **History** (`cookbook.*.yaml`, `errors.*.yaml`) — anchored at the **L3 case node** (`<case-slug>/`). A precedent set during one case lives with that case; `adjust()` resolves which precedents apply to a new call by matching case characteristics. L3 anchoring means history is case-scoped, not domain-scoped — a precedent from a different case may not apply.

## The `_rubric/` shelf

The `_rubric/` shelf holds the three versioned-rubric modules:

| Module | Path | Content |
|---|---|---|
| Rules & Criteria | `_rubric/rules/` | Scoring rules: pass/fail/requires-review criteria per rule, evidence requirements |
| Acoustic Framework | `_rubric/acoustic/` | 12 indicators: pitch range thresholds, pause-duration buckets, intensity floors, voice-quality metrics, speech-rate ranges |
| Phrase & Keyword Lexicon | `_rubric/phrase-keyword/` | Sensitive-word lists, negative-phrase patterns, recommended-phrase alternatives, ASR biasing terms; one script per language/domain |

The rubric is **versioned**. Each rubric release has a version number; Argus pins the version in config (`argus.rubric_version`). Changing the rubric version changes future scoring only — past verdicts cite the rubric version they were scored against. See ADR-0001 for the epistemic classification.

## Git-SHA epoch

Consumers read the INTENTS tree at a **pinned git SHA**, declared in config (`argus.intents_sha`). This means:

- Tree upgrades are explicit — no consumer sees a change it didn't ask for.
- Rollback is `git checkout <previous-sha>` — a filesystem operation.
- Reproducibility: a verdict computed at SHA `abc123` can be re-verified at SHA `abc123`.

Running without a pinned SHA is forbidden. The tree has no "latest" — there is only "the version at SHA `abc123`."

## Configurable location

The default location is `INTENTS/` at the repository root. The path is overridable via `argus.config.intents_path` for deployments where the tree lives elsewhere (e.g., a separate data repository, a mounted volume, or a checked-out submodule). The actual config mechanism is deferred to the first Argus exec-plan.

## Boring-tech choice: filesystem over RAG

The INTENTS tree is small enough to be read directly from disk. No vector database, no RAG pipeline, no embedding index at read time. The path-as-ontology structure is the index — walking the tree is the query. This is deterministic, zero-latency, and requires no external service.

`tensors.json` provides pre-computed embeddings for cross-tree search, generated at build time by the transformation layer, not at read time by the consumer.

## Ownership

Every file in the tree is owned by exactly one producer, tracked in `_meta/ownership.yaml`:

- `audio2tree` — produces the intents tree from support-call audio (L2 capsules, L3 cases, `kb.*.yaml` facts)
- `doc2graph` — produces the compute graph from operation manuals (operator definitions, procedural sequences)
- `Navigator` — produces operator sequences from live web-app instrumentation

Zero multi-owner, zero orphaned. The ownership file is the structural replacement for the v1 Expertise Library's "TBD" ownership model.

## Naming grammar

Slugs are **demand-minted from customer language** — the term the customer uses, not the term an engineer invents. Examples:

- `annual-report-submission` — what customers call the domain, not `form-1040-filing`
- `verify-identity` — what customers call the step, not `step-3a`

Slugs are permanent. Renaming a slug is a breaking change — it changes every path that references it. Choose carefully; commit early.

## Tiebreaker references

- ADR-0002 — path-as-ontology and git-SHA epoch.
- ADR-0001 — epistemic classification; rubric vs facts vs history.
- ADR-0004 — Expertise Library dissolution; the tree is the library.
- `docs/product-specs/shared/calibration.md` — bottom-up authority and the coverage/content axes.
- `docs/product-specs/shared/expertise-library.md` — the three category readers.
- `PRODUCT_SENSE.md` — cross-product principles and failure tolerances.
