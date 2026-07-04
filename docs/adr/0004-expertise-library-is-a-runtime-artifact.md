# ADR-0004: Expertise Library Is a Runtime Artefact, Not a Code Domain

**Status:** accepted

**Date:** 2026-07-04

## Context

The v1 architecture described the "Expertise Library" as domain #5 in the 10-domain inventory — a code domain with nine typed reader interfaces (`IRulesAndCriteriaReader`, `IAcousticFeatureReader`, `IPhraseKeywordReader`, etc.) plus an `IExpertiseReader` facade, consumed selectively by Argus, Metis, and Hermes. Each module had different update cadences, ownership, and consumer sets.

The v6 design reframed this: the expertise modules are the **content of the INTENTS tree** (see ADR-0002), not code interfaces. The tree is a git-versioned runtime artefact read by a single Provider. The nine reader interfaces were an abstraction over what is fundamentally a filesystem walk with typed returns.

This ADR records the dissolution of the Expertise Library as a code domain. It is the fourth and final foundational ADR, completing the domain reduction from ten to five.

## Decision

### The Expertise Library is the INTENTS tree

The nine expertise modules from v1 map to the INTENTS tree as follows:

| v1 Module | INTENTS location | Epistemic class (ADR-0001) |
|---|---|---|
| Rules & Criteria | `_rubric/rules/` | Versioned rubric |
| Acoustic Feature (framework) | `_rubric/acoustic/` | Versioned rubric |
| Phrase & Keyword (lexicon) | `_rubric/phrase-keyword/` | Versioned rubric |
| Product Introduction | `<domain>/<case>/kb.*.yaml` | Descriptive facts |
| Operation Manual | `<domain>/<case>/kb.*.yaml` | Descriptive facts |
| Dynamic Knowledge Base | `<domain>/<case>/kb.*.yaml` | Descriptive facts |
| Best Practice Cookbook | `<domain>/<case>/cookbook.*.yaml` | Accumulated history |
| Error Case Library | `<domain>/<case>/errors.*.yaml` | Accumulated history |
| Audio Transcription | N/A — per-call input artefact, not in the tree | N/A |

### Nine reader interfaces collapse to one Provider

The v1 design exposed each module through a dedicated typed reader interface. In the v6 design, there is **one Provider** — the INTENTS reader in `argus.io` — with typed return shapes declared in `argus.types`:

```python
# Conceptual — actual types declared in argus/types/
class IntentNode: ...
class RubricModule: ...
class FactRecord: ...
class HistoryRecord: ...

# The INTENTS Provider exposes typed reads, not nine separate interfaces:
def read_rubric(sha: str, module: str, version: str) -> RubricModule: ...
def read_facts(sha: str, domain: str, case: str) -> list[FactRecord]: ...
def read_history(sha: str, domain: str, case: str) -> list[HistoryRecord]: ...
```

The three read methods map to the three epistemic classes (rubric, facts, history) — not the nine modules. The granularity of the v1 interfaces was an artefact of the flat module list; the v6 design groups by epistemic class because that is what `score()` and `adjust()` actually consume.

### The library is git-versioned, not runtime-resolved

In v1, each module had its own update cadence and the Expertise Library was imagined as a service that resolved the "current" version of each module. In v6, the entire tree is pinned at one SHA. There is no "current" version — there is only "the version at SHA `abc123`." Module-level versioning is handled by the rubric version field within the tree, not by a runtime resolution step.

### No runtime writes

The v1 spec's forbidden behaviours (no runtime writes, no silent merging, no stripping of version metadata) are preserved and structurally enforced: the INTENTS Provider is read-only. Tree updates happen through the transformation layer's build pipeline, with human approval gates. The Provider has no write methods.

## Consequences

- Expertise Library is removed from `ARCHITECTURE.md`'s domain inventory. It is not a code domain.
- The nine v1 reader interfaces (`IRulesAndCriteriaReader`, etc.) are not implemented. The `IExpertiseReader` facade is not implemented.
- The three epistemic-class readers (rubric, facts, history) replace the nine-module interface surface. These are methods on the INTENTS Provider, not separate interfaces.
- The `providers+utils` domain in `argus.io` owns the INTENTS Provider. This is the collapsed form of the Expertise Library.
- Updates to expertise content follow the tree's build pipeline and git workflow — not a runtime module-resolution step.
- The INTENTS tree's `_meta/ownership.yaml` tracks which producer (audio2tree, doc2graph, Navigator) owns each file. This is the structural replacement for the v1 spec's "TBD" ownership model.
