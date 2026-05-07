# ARCHITECTURE.md

The single map of domains, layers, and dependency directions for the Argus / Metis / Hermes platform. The structure here is mechanically enforced — every prose rule in this file names the linter or structural test that fails CI when the rule is violated, or carries an `Aspiration:` marker with an explicit `Revisit:` date if the enforcement is not yet implemented. Rules without enforcement are not rules.

This document does not describe how to implement the system. It describes the constraints any implementation must satisfy. Implementation choices live in `docs/adr/` (decisions that outlive a single feature) and `docs/product-specs/` (per-feature elaboration).

## 1. Domain inventory

The platform is partitioned into ten domains. Each domain exists because something is deliberately separated from something else; the separation is named in each line. Domains are numbered for reference in the dependency matrix.

| # | Domain | Why separated | Consumed by |
|---|---|---|---|
| 1 | **Audio Intake** | Raw audio handling, VAD, diarisation, ASR — separated because it has fundamentally different test data, latency profile, and external-dependency surface than anything that operates on text. | Conversation Distillation |
| 2 | **Document Ingestion** | Operation-manual parsing, image extraction, visual-annotation handling, OCR — separated because input is unstructured authored documents with mixed text-and-image and the failure modes (OCR drift, layout misparse) are fundamentally different from those of audio. | Knowledge Calibration |
| 3 | **Conversation Distillation** | Bottom-up pipeline: structural transcription → atomic-claim extraction → hierarchical clustering → intents-tree. Separated because this is the **authoritative source of behavioural truth** in the system; coupling it to anything that consumes it would invert authority. | Knowledge Calibration |
| 4 | **Knowledge Calibration** | Where bottom-up (intents-tree) and top-down (compute-graph) meet and reconcile. Separated because the bottom-up-authoritative invariant lives here and must be enforced at exactly one place. | Argus, Metis, Hermes, Expertise Library |
| 5 | **Expertise Library** | The seven expertise modules — Rules&Criteria, Acoustic Feature, Product Introduction, Dynamic Knowledge Base, Best Practice Cookbook, Error Case Library, Phrase&Keyword Library. Separated because each module has different update cadence, ownership, and consumer set; bundling would force false uniformity. | Argus, Metis, Hermes (selectively) |
| 6 | **Argus** | AI QA application: fact-checking, report-generation, coaching-task emission. Separated because the user role (QA Reviewer / Supervisor / Agent) and the failure tolerances differ from the other two apps. | end users |
| 7 | **Metis** | Business diagnosis: AI triage, ticket emission to Kanban. Separated because the discovery-to-fix loop has a fundamentally different cadence (daily) and audience (PM / BA / Marketing) than the other two apps. | end users |
| 8 | **Hermes** | Autonomous service agent: procedural reasoning + action execution via Playwright MCP / CDP. Separated because the action-tier system (read-only / confirmed / autonomous) is a unique safety surface that does not exist elsewhere. | end users |
| 9 | **Providers** | Cross-cutting concerns: authentication, observability, LLM access, ASR access, browser-automation access, ticket-system access, feature flags. Separated because every domain consumes some subset and direct consumption would create a cross-product matrix of edges; routing through Providers makes every cross-cutting use auditable. | every other domain |
| 10 | **Utils** | Pure functions, no I/O, no Provider access. Separated to keep the Provider boundary honest — anything that needs a Provider is not a util. | every other domain |

## 2. Layered model

Within each domain, code is partitioned into a fixed sequence of layers. Dependencies flow forward only: a later layer may depend on an earlier layer; an earlier layer may not depend on a later layer. Cross-cutting concerns enter via the Providers domain, never directly.

```
Types  →  Config  →  Repo  →  Service  →  Runtime  →  UI
                       ↑
                  Providers
                       ↑
                     Utils
```

**Types**: data shapes — atomic claims, intent nodes, tensors, operators, transcription frames, ticket records, action descriptors. No I/O. No business logic. Parsed at the boundary using a typed schema validator (the model favours Zod in TypeScript surfaces, Pydantic in Python surfaces; specific library is non-prescriptive — *what* is prescriptive is that boundaries parse, never trust unparsed inputs).

**Config**: domain-specific settings, schema versions, feature flags consumed at startup. Reads only from environment and configuration files; never from runtime data.

**Repo**: persistence — corpus storage, graph storage, ticket storage, audit logs. Repo is the only layer that owns external state. All other layers receive data via Repo, not by reaching for storage directly.

**Service**: business logic. Pipelines, calibration, triage rules, scoring. Pure with respect to I/O — Service receives and returns Types, never performs storage or external calls directly. External effects flow through Providers.

**Runtime**: orchestration. Job scheduling, retries, concurrency limits, observability emission. Runtime composes Services into pipelines and supervises them. The map-with-concurrency helper, retry policy, circuit breakers — all Runtime.

**UI**: surfaces consumed by humans. The Argus QA review interface, the Metis Kanban, the Hermes citizen-facing chat-and-act surface. UI depends on Runtime to drive operations and on Repo (read-only) for display data; UI never depends on Service directly. (Why: Service is a stable contract; Runtime adds the orchestration semantics — observability, partial-failure handling, cancellation — that UI needs to behave well under load.)

**Providers** (cross-cutting): the explicit boundary for every external dependency. Auth, observability, LLM access, ASR access, browser automation, ticket-system integration, feature flags. Every external call in the system goes through Providers; if a Service or Runtime layer reaches an external API directly, the structural test fails CI.

**Utils** (cross-cutting): pure functions consumed by any layer. No I/O. No Provider access. Limited to genuinely pure helpers.

### Mechanical enforcement

| Rule | Enforcement | Status |
|---|---|---|
| No layer may import from a later layer within the same domain. | Custom lint `no-backward-layer-import` analysing the import graph; fails CI on violation. | `Aspiration:` — to be implemented in `0001-bootstrap-the-spine.md` M3. `Revisit:` 2026-06-15. |
| External-dependency imports allowed only in Providers. | Lint `external-imports-only-in-providers`. | `Aspiration:` — M3. `Revisit:` 2026-06-15. |
| Boundary types must parse via the project's typed schema validator. | Lint `parse-at-boundary`. | `Aspiration:` — M4. `Revisit:` 2026-06-22. |
| Util modules must contain no I/O and no Provider access. | Lint `utils-purity`. | `Aspiration:` — M4. `Revisit:` 2026-06-22. |

## 3. Dependency matrix

Every cross-domain edge is named. Cells marked `none` are forbidden — a structural test fails CI if such an edge appears in the import graph. Cells marked `via providers` mean the edge passes through the Providers domain. Cells naming an interface mean the edge is a direct call to that named interface (and the interface is the only permissible entry point).

Rows depend on columns; read across.

| ↓ depends on → | 1.AudioIntake | 2.DocIngest | 3.ConvDistill | 4.Calibration | 5.Expertise | 6.Argus | 7.Metis | 8.Hermes | 9.Providers | 10.Utils |
|---|---|---|---|---|---|---|---|---|---|---|
| **1. Audio Intake** | — | none | none | none | none | none | none | none | via providers | yes |
| **2. Doc Ingestion** | none | — | none | none | none | none | none | none | via providers | yes |
| **3. Conv Distillation** | `ITranscriptionStream` | none | — | none | none | none | none | none | via providers | yes |
| **4. Calibration** | none | `IComputeGraphSource` | `IIntentTreeSource` | — | none | none | none | none | via providers | yes |
| **5. Expertise Lib** | none | none | none | `ICalibratedGraphReader` | — | none | none | none | via providers | yes |
| **6. Argus** | none | none | `IIntentTreeReader` | `ICalibratedGraphReader` | `IExpertiseReader` | — | none | none | via providers | yes |
| **7. Metis** | none | none | `IIntentTreeReader` | `ICalibratedGraphReader` | `IExpertiseReader` (selective; see § 5) | `IArgusFindingFeed` (read-only) | — | none | via providers | yes |
| **8. Hermes** | none | none | none | `ICalibratedGraphReader` | `IExpertiseReader` | none | none | — | via providers | yes |
| **9. Providers** | none | none | none | none | none | none | none | none | — | yes |
| **10. Utils** | none | none | none | none | none | none | none | none | none | — |

### Three invariants this matrix encodes

**Bottom-up authority**: Calibration depends on `IIntentTreeSource` and `IComputeGraphSource` separately; the calibration logic's signature requires the intents-tree input as the dominant operand. Argus and Metis read both `IIntentTreeReader` (for the behavioural truth) and `ICalibratedGraphReader` (for the official path). Hermes reads only the calibrated graph because Hermes acts on procedural sequence; the intents-tree informs calibration, calibration informs Hermes. The compute-graph cannot write to the intents-tree directly — there is no `IIntentTreeWriter` exposed to anything other than Conversation Distillation itself.

**Argus → Metis is one-way**: `IArgusFindingFeed` is read-only from Metis's side. Argus does not consume Metis. The escalation policy (Argus systemic findings forwarded to Metis) is implemented as Metis polling the feed, not Argus pushing to Metis.

**Hermes does not write to the graph**: there is no `ICalibratedGraphWriter` exposed to Hermes. When Hermes encounters a procedural gap, it logs to a separate `IGapLog` provider; the gap log feeds Metis as a documentation-gap issue and feeds the offline calibration pipeline.

### Mechanical enforcement

| Rule | Enforcement | Status |
|---|---|---|
| No cross-domain edge may exist that is `none` in the matrix. | Lint `forbidden-cross-domain-edges` parsing the import graph against this matrix. | `Aspiration:` — M3 of `0001-bootstrap-the-spine.md`. `Revisit:` 2026-06-15. |
| Every named interface in the matrix must have exactly one declaration site, in the depended-upon domain's Types layer. | Lint `interface-single-declaration`. | `Aspiration:` — M4. `Revisit:` 2026-06-22. |

## 4. Boring-tech ledger

Dependencies chosen for **agent legibility** — i.e., the agent can reason about them in-context without needing external documentation that may not be in training data. Each entry names the alternative considered and the reason for rejection.

| Choice | Domain | Alternative considered | Reason for choice |
|---|---|---|---|
| Playwright + Chrome DevTools Protocol for browser automation | Hermes Providers | Selenium, custom CDP wrapper | Playwright has stable API representation in training corpora; its action model maps cleanly to Hermes's tier system (page-level actions are mostly Tier-A read or Tier-B confirmed click); CDP gives DOM snapshots and screenshots Hermes needs for evidence-citation. |
| Typed schema validator at boundaries (Zod / Pydantic) | All domains, Types layer | Hand-rolled validators, runtime type assertions | Schema-first parsing fails closed at the boundary; agents reason about typed shapes much more reliably than about runtime assertion strings; the model seems to like Zod, but we didn't specify that specific library — the prescription is "parse at boundary," not the specific library. |
| Hierarchical clustering for intent-tree construction | Conversation Distillation Service | Flat clustering, manual taxonomy | Hierarchical matches the 2-to-3-level intent architecture the bottom-up spec specifies; flat would lose the level-1/level-2/level-3 structure the calibration step relies on. |
| Compute-graph as Tensor-Operator DAG | Document Ingestion Service | Plain flowchart, BPMN | The bottom-up spec's success criteria require backward chaining (fault diagnosis), dynamic routing (jump-to-current-state), and data dependency inspection — only a Tensor-Operator DAG supports all three; flowcharts lack data dependencies, BPMN over-specifies for this domain. |
| Kanban + ticket-system integration for Metis output | Metis UI / Providers | Email digests, dashboard-only, custom ticketing | Kanban surfaces are agent-legible (Jira and similar have stable APIs in training corpora), match analyst workflows, and avoid the runtime-coupling-to-coding-agent the PRD initially described and `PRODUCT_SENSE.md § Metis` rules out. |

Aspiration: **the entire boring-tech ledger above is currently `Confidence: low`** because no implementation has run yet. `Revisit:` 2026-08-01 — by which point at least M5 of the bootstrap exec-plan should have surfaced any choice that turned out to be wrong, and an ADR can replace each row that holds up under load.

## 5. Per-layer contracts

### Types

Every type that crosses a domain boundary is declared in the depended-upon domain's Types layer. There is no "shared types" package — that would invert the dependency graph (a shared package consumed by many would force every consumer to depend on every other consumer's types). Cross-domain shared shapes that genuinely have no owner go in Utils (limited to truly primitive shapes — IDs, timestamps, geo coords).

### Config

Config is read at startup only. No reading of config from within Service or Runtime hot paths — all configuration is resolved into typed structures during Runtime initialisation and passed in. This avoids the failure mode where a config change mid-flight produces inconsistent behaviour across concurrent jobs.

### Repo

Every Repo method must have a corresponding test that fails before the method is implemented and passes after. (See `docs/conventions/verification-floor.md` for the test discipline; if that file does not exist, M2 of `0001-bootstrap-the-spine.md` creates it.) Repo never throws on "not found" — returns a typed `null`-or-not result. Throwing for control flow is forbidden; control flow happens via return shape.

### Service

Service is pure with respect to I/O. Every Service function takes Types as input and returns Types as output. External effects — DB writes, LLM calls, browser actions — happen by returning a description of the effect, which Runtime executes via Providers. This is what makes Service testable without mocks and what makes Runtime auditable.

**Hermes Service tier system**: every action descriptor produced by Hermes Service must declare its tier. The descriptor type is:

```
type ActionDescriptor =
  | { tier: 'A'; kind: 'read'; ... }      // DOM inspection, screenshot, navigation that does not commit state
  | { tier: 'B'; kind: 'confirmed'; ... } // explicit user confirmation required per-action before Runtime executes
  | { tier: 'C'; kind: 'autonomous'; ... }// no per-action confirmation; reserved for clearly-reversible reads only
```

The Hermes Runtime layer has separate execution paths for each tier, and the Provider that drives the browser exposes different methods per tier; Tier-C actions cannot be invoked through the Tier-B confirmation path or vice versa. This is enforced at the type level: there is no shared interface that all three tiers conform to. Mechanical enforcement: lint `hermes-action-tier-required` fails CI if any action descriptor lacks a tier; structural test ensures the Tier-C method on the browser provider is reachable from no more than the explicitly-listed call sites in `docs/product-specs/hermes/action-execution.md`. **The current canonical policy initialises Tier-C as empty** (see `PRODUCT_SENSE.md § Hermes` Awaiting Steering Question 1).

### Runtime

Runtime emits structured logs at every job boundary. Log shape is enforced by the structured-logging lint (`structured-log-shape`). Free-form log strings are forbidden in Runtime; they are permitted in Service and UI for development but discouraged.

Runtime owns retry policy. Retries are explicit per-call-site, not implicit at the Provider layer; this prevents cascading retry storms and makes retry behaviour visible in the call site rather than hidden in framework configuration.

### UI

UI components must mirror the data shape, not the visual shape. (See `docs/design-docs/core-beliefs.md` for the agent-first design principles; this is the architectural face of the same rule.) Components that take a flat prop list of strings to display are forbidden; components take typed Repo shapes and project from there.

Every interactive UI element has a stable test selector survives restyling. Mechanical enforcement: `stable-test-selectors` lint fails CI on any interactive element without a `data-testid` (or framework equivalent).

### Providers

Every Provider is a single module that owns a single external dependency. No "utils" Provider, no "everything-cloud" Provider — one Provider per external system. Providers expose typed interfaces declared in the consumer's Types layer (this is the `IFooSource` / `IFooReader` pattern in the dependency matrix).

Providers must be replaceable in tests via constructor injection or dependency-injection-equivalent. No global singletons. Lint: `no-global-providers`.

### Utils

Utils is pure. No imports of Providers. No I/O. The "purity" lint enforces this; if a util genuinely needs I/O, it is not a util — promote it to a Provider with a real owner.

## 6. Generated artifacts

Some artifacts are derived from the spine and regenerated automatically; they live in `docs/generated/` and are never edited by hand. The current generated set:

- `docs/generated/db-schema.md` — derived from Repo layer Types; regenerated on Repo schema change.
- `docs/generated/dependency-graph.svg` — derived from the import graph; regenerated nightly by the doc-gardener subagent.
- `docs/generated/interface-inventory.md` — every interface referenced in the dependency matrix § 3, with its declaration site; regenerated on any change to a Types layer.

CI fails if a generated artifact is checked in with hand-edits. Lint: `no-hand-edit-generated`.

## 7. Forbidden phrases

This file may not contain the phrases "best practice", "industry standard", "clean architecture", or "follows convention" without an immediately-following citation, experiment reference, or explicit `Confidence: low` marker. Unjustified appeals to authority are a defect class. Mechanical enforcement: `forbidden-phrases` lint fails CI on this file specifically.

## 8. When this is wrong

If the structure here gets in the way more than it helps, flag it as a Surprise in the relevant active exec-plan and propose a change. Architecture changes are ADRs in `docs/adr/`; ARCHITECTURE.md updates land in the same PR as the ADR they reference. Do not edit this file without an ADR; the linter `architecture-changes-require-adr` checks PR descriptions for an ADR reference when this file changes.

`Last reviewed: bootstrap. Next review: 2026-08-01.`
