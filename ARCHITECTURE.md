# ARCHITECTURE.md

The single map of domains, layers, and dependency directions for **Argus** — the AI QA application this repository implements. The structure here is mechanically enforced — every prose rule in this file names the linter or structural test that fails CI when the rule is violated, or carries an `Aspiration:` marker with an explicit `Revisit:` date if the enforcement is not yet implemented. Rules without enforcement are not rules.

Argus is one of three consumer-tier applications. For the full three-tier platform map (transformation → semantic → consumer), see `docs/references/platform-architecture.md`. That document is a reference, not enforced; this document is the enforced architecture for code in this repo.

## 1. Domain inventory

The Argus application is partitioned into five domains. Each domain exists because something is deliberately separated from something else; the separation is named in each line. Each domain maps directly onto one layer in `.importlinter` (see Section 2).

| # | Domain | Why separated | Maps to layer | Consumed by |
|---|---|---|---|---|
| 1 | **types** | Data shapes — FactCheckVerdict, INTENTS-read result shapes, report/coaching task shapes. Separated because types have no I/O, no business logic, and are the only layer with zero internal imports. | `types` | every other domain |
| 2 | **config** | Rubric-version pinning, INTENTS-SHA pinning, scoring thresholds, feature flags. Separated because configuration is resolved at startup and must be immutable during a run. | `config` | io, core, cli |
| 3 | **providers + utils** | Cross-cutting: the INTENTS reader (resolves paths at a pinned SHA), external-service boundaries, and pure helper functions. Separated because every external dependency and shared utility routes through here, making the dependency surface auditable. This is where the former "Expertise Library" domain goes — collapsed from nine reader interfaces to one INTENTS Provider with typed returns. | `io` | core, cli |
| 4 | **core** | Domain logic: `raw = score(facts, rubric)`, `adjusted = adjust(raw, history)`, report emission, coaching-task emission. All pure where possible — core receives and returns types, never performs I/O directly. External effects flow through providers. | `core` | cli |
| 5 | **cli** | Typer command surface. Deliberately thin: parse arguments, call into core, format result, set exit code. Separated because the CLI surface may be replaced or augmented (e.g., with an HTTP API) without touching core. | `cli` | end users |

Two v1 domains — Knowledge Calibration and Expertise Library — are no longer code domains in this repo. Their dispositions are recorded in `docs/adr/0003` (Calibration dissolves to write-time file ownership) and `docs/adr/0004` (Expertise Library is the INTENTS runtime artefact, not a code domain). Metis and Hermes are interface references: Argus emits findings via `IArgusFindingFeed` that Metis consumes, and coaching tasks Hermes may act on. Neither is a domain in this repo.

## 2. Layered model

Within Argus, code is partitioned into a fixed sequence of layers matching the `.importlinter` contract. Dependencies flow forward only: a later layer may depend on an earlier layer; an earlier layer may not depend on a later layer.

```
types  →  config  →  io  →  core  →  cli
             ↑                ↑
          providers        providers
             ↑                ↑
           utils            utils
```

Providers and Utils are cross-cutting: any layer may consume them. They are organised under the `io` layer (providers are I/O boundaries; utils are pure functions that serve all layers).

**types**: data shapes — `FactCheckVerdict` with `raw`, `adjusted`, and `applied_precedents` fields; INTENTS tree node shapes; report and coaching-task records. No I/O. No business logic. No imports from any other `argus.*` module. Parsed at the boundary using Pydantic; the prescription is "parse at boundary," not the specific library.

**config**: rubric-version pinning, INTENTS-SHA pinning, scoring thresholds, feature flags. Read at startup only — no reading of config from within core hot paths. All configuration is resolved into typed structures during CLI initialisation and passed in.

**io**: filesystem, network, subprocess, and OS interactions. The INTENTS reader is a Provider in this layer: it resolves paths at a pinned SHA and returns typed tree-node structures. Each I/O concern is its own submodule (`io.fs`, `io.http`, `io.subprocess`). Providers expose typed interfaces declared in `types`. Providers must be replaceable in tests via constructor injection — no global singletons.

**core**: domain logic. The two-stage evaluation contract: `raw = score(facts, rubric)` then `adjusted = adjust(raw, history)`, with per-precedent attribution in `applied_precedents[]`. Also: report emission, coaching-task emission. Pure where possible — core receives and returns types, never performs storage or external calls directly. External effects happen by returning a description of the effect, which `cli` (or a future Runtime) executes via providers. This is what makes core testable without mocks.

**cli**: Typer command definitions. Outermost layer. Parse arguments, call into core, format result, set exit code. Deliberately thin — the CLI surface is a skin over core, not a place for logic.

### Mechanical enforcement

| Rule | Enforcement | Status |
|---|---|---|
| No layer may import from a later layer. | `.importlinter` contract (`types→config→io→core→cli`) enforced in CI via `uv run lint-imports`; redundant AST check in `.claude/tests/test_layering.py`. | **Enforced.** |
| External-dependency imports allowed only in Providers. | Lint `external-imports-only-in-providers` (`tools/lint/`). | **Enforced.** |
| Boundary types must parse via Pydantic. | Lint `parse-at-boundary` (`tools/lint/`). | **Enforced.** |
| Util modules must contain no I/O and no Provider access. | Not yet implemented. | `Aspiration:` — the purity lint does not yet exist. `Revisit:` 2026-08-01. |

## 3. Dependency matrix

Every cross-domain edge is named. Cells marked `none` are forbidden. Cells marked `via providers` mean the edge passes through the providers+utils domain. Cells naming an interface mean the edge is a direct call to that named interface (and the interface is the only permissible entry point).

Rows depend on columns; read across.

| ↓ depends on → | 1.types | 2.config | 3.providers+utils | 4.core | 5.cli |
|---|---|---|---|---|---|
| **1. types** | — | none | none | none | none |
| **2. config** | yes | — | none | none | none |
| **3. providers+utils** | yes | yes | — | none | none |
| **4. core** | yes | yes | via providers | — | none |
| **5. cli** | yes | yes | via providers | yes | — |

### Invariants this matrix encodes

**Bottom-up authority**: core's `score()` function receives `facts` and `rubric` as separate arguments. The `rubric` is read from the INTENTS tree's `_rubric/` shelf at a pinned SHA; `facts` come from the call record (structural transcription). The tree is authoritative — when an intent-tree claim and a compute-graph operator disagree, the tree wins (see `docs/product-specs/shared/calibration.md`). The compute-graph cannot write to the intents tree; there is no writer interface exposed to anything other than the transformation layer (not in this repo).

**Argus → Metis is one-way**: `IArgusFindingFeed` is read-only from Metis's side. Argus does not consume Metis. The escalation policy (Argus systemic findings forwarded to Metis) is implemented as Metis polling the feed, not Argus pushing to Metis. Metis is not a domain in this repo; the feed interface is declared in `types` for reference.

**Hermes does not write to the graph**: there is no writer interface exposed to Hermes. When Hermes encounters a procedural gap, it logs to a separate gap-log provider; the gap log feeds Metis as a documentation-gap issue. Hermes is not a domain in this repo; coaching tasks emitted by core are consumed by Hermes through a separate interface.

### Mechanical enforcement

| Rule | Enforcement | Status |
|---|---|---|
| No cross-domain edge may exist that is `none` in the matrix. | Lint `forbidden-cross-domain-edges` (`tools/lint/`). | `Aspiration:` — the existing lint checks against the v1 10-domain matrix; it must be updated for the 5-domain Argus matrix. `Revisit:` 2026-08-01. |
| Every named interface in the matrix must have exactly one declaration site, in the depended-upon domain's `types` layer. | Lint `interface-single-declaration`. | `Aspiration:` — not yet implemented. `Revisit:` 2026-08-01. |

## 4. Boring-tech ledger

Dependencies chosen for **agent legibility** — i.e., the agent can reason about them in-context without needing external documentation that may not be in training data. Each entry names the alternative considered and the reason for rejection.

| Choice | Domain | Alternative considered | Reason for choice |
|---|---|---|---|
| Typed schema validator at boundaries (Pydantic) | All domains, types layer | Hand-rolled validators, runtime type assertions | Schema-first parsing fails closed at the boundary; agents reason about typed shapes much more reliably than about runtime assertion strings. |
| Filesystem + bash for INTENTS reading | io (providers) | RAG, vector database, graph database | The INTENTS tree is small enough to read directly from disk at a pinned git SHA. Filesystem reads are deterministic, zero-latency, and require no external service. A vector database would add a dependency for a problem the tree's path-as-ontology structure already solves. |
| Hierarchical clustering for intent-tree construction | Transformation layer (not this repo) | Flat clustering, manual taxonomy | Hierarchical matches the 2-to-3-level intent architecture the bottom-up spec specifies; flat would lose the L1/L2/L3 structure the calibration step relies on. |
| Compute-graph as Tensor-Operator DAG | Transformation layer (not this repo) | Plain flowchart, BPMN | The bottom-up spec's success criteria require backward chaining (fault diagnosis), dynamic routing (jump-to-current-state), and data dependency inspection — only a Tensor-Operator DAG supports all three. |
| Kanban + ticket-system integration for Metis output | Metis (not this repo) | Email digests, dashboard-only, custom ticketing | Kanban surfaces are agent-legible, match analyst workflows, and avoid runtime-coupling. |
| Playwright + Chrome DevTools Protocol for browser automation | Hermes (not this repo) | Selenium, custom CDP wrapper | Playwright has stable API representation in training corpora; its action model maps cleanly to Hermes's tier system. |

Aspiration: **rows that touch this repo's domains (the first two) are `Confidence: medium`** — Pydantic is in use and the boundary-parse lint enforces it; the filesystem INTENTS reader is specified but not yet implemented. The remaining rows are platform-level choices recorded here for context; they are not enforced in this repo. `Revisit:` 2026-08-01.

## 5. Per-layer contracts

### types

Every type that crosses a domain boundary is declared in the depended-upon domain's `types` layer. There is no "shared types" package — that would invert the dependency graph. Cross-domain shared shapes that genuinely have no owner go in Utils (limited to truly primitive shapes — IDs, timestamps).

### config

Config is read at startup only. No reading of config from within core hot paths — all configuration is resolved into typed structures during CLI initialisation and passed in. This avoids the failure mode where a config change mid-flight produces inconsistent behaviour across concurrent jobs.

Config keys that exist:
- `argus.rubric_version` — the version of the `_rubric/` shelf to use
- `argus.intents_sha` — the git SHA at which to read the INTENTS tree
- `argus.intents_path` — path to the INTENTS tree (default: `INTENTS/` at repo root; overridable for deployments where the tree lives elsewhere)
- `argus.score_thresholds` — pass/fail/requires-review boundary values

### io

The INTENTS reader is the primary Provider in this layer. It resolves paths at the pinned SHA, walks the path-as-ontology tree, and returns typed node structures (`IntentNode`, `RubricModule`, `FactRecord`, `HistoryRecord`) declared in `types`. The reader is the collapsed form of the v1 Expertise Library's nine reader interfaces — one Provider with typed returns, rather than nine separate readers.

Every Provider is a single module that owns a single external dependency. No "utils" Provider, no "everything-cloud" Provider — one Provider per external system. Providers expose typed interfaces declared in `types` (the `IFooSource` / `IFooReader` pattern).

Providers must be replaceable in tests via constructor injection. No global singletons. Lint: `no-global-providers` (`Aspiration:` — not yet implemented; `Revisit:` 2026-08-01).

### core

Core is pure with respect to I/O. Every core function takes types as input and returns types as output. External effects — filesystem reads, LLM calls — happen by returning a description of the effect, which `cli` executes via providers. This is what makes core testable without mocks.

The two-stage evaluation contract (detailed in `docs/product-specs/argus/fact-checking.md` and `docs/adr/0001`):

```
raw = score(facts, rubric)
adjusted = adjust(raw, history)
```

- `score` receives facts (from the call record) and rubric (from the INTENTS `_rubric/` shelf) and produces a raw verdict per rule — pass, fail, or requires-review, each with evidence citations.
- `adjust` receives the raw verdict and anchored history records (from the INTENTS tree's L3 case nodes) and applies precedents, producing the final verdict with `applied_precedents[]` attribution.

Both stages are pure: they receive data and return a result. No I/O, no config reads, no external calls.

Ambiguity → `requires-review`, never pass/fail by guess. Evidence-citation is non-negotiable — every verdict must cite the specific transcript turn, tree node, or rubric entry that supports it.

### cli

Typer command definitions. The outermost layer. Commands:
- Parse arguments into typed request shapes
- Call into core functions with those shapes
- Format the result for stdout (or emit to a file)
- Set the exit code

cli never contains business logic. If you find yourself writing an `if` statement in a cli module that isn't about argument validation or output formatting, move it to core.

## 6. Generated artifacts

Some artifacts are derived from the spine and regenerated automatically; they live in `docs/generated/` and are never edited by hand. The current generated set:

- `docs/generated/db-schema.md` — derived from types layer shapes; regenerated on schema change.
- `docs/generated/dependency-graph.svg` — derived from the import graph; regenerated nightly by the doc-gardener subagent.
- `docs/generated/interface-inventory.md` — every interface referenced in the dependency matrix § 3, with its declaration site; regenerated on any change to a types layer.

CI fails if a generated artifact is checked in with hand-edits. Lint: `no-hand-edit-generated` (`Aspiration:` — not yet implemented; `Revisit:` 2026-08-01).

## 7. Forbidden phrases

This file may not contain the phrases "best practice", "industry standard", "clean architecture", or "follows convention" without an immediately-following citation, experiment reference, or explicit `Confidence: low` marker. Unjustified appeals to authority are a defect class. Mechanical enforcement: `forbidden-phrases` lint (`tools/lint/forbidden_phrases.py`) fails CI on this file specifically.

## 8. When this is wrong

If the structure here gets in the way more than it helps, flag it as a Surprise in the relevant active exec-plan and propose a change. Architecture changes are ADRs in `docs/adr/`; ARCHITECTURE.md updates land in the same PR as the ADR they reference. Do not edit this file without an ADR; the linter `architecture-changes-require-adr` checks PR descriptions for an ADR reference when this file changes (`Aspiration:` — not yet implemented; `Revisit:` 2026-08-01).

`Last reviewed: 2026-07-04.`
