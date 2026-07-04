# Platform Architecture — Three-Tier Reference

The three-product platform (Argus, Metis, Hermes) is organised into three tiers. This document describes the full picture. It is a **reference** — not enforced by any lint, structural test, or CI gate, because the tiers span multiple repositories, services, and data artefacts. The enforced architecture lives in `ARCHITECTURE.md` (this repo only).

## The three tiers

```
Transformation layer          Semantic layer           Consumer layer
(not this repo)               (data, not code)        (this repo = Argus only)

audio2tree ─────────┐                                 Argus ─── findings ──→ Metis
  (Audio Intake +    │                                 (fact-checking,
   Conv Distillation)│                                 scoring, coaching)
                     ├──→ INTENTS/ ──→ read at ──→
doc2graph ──────────┘    (git-versioned,              Metis
  (Document Ingestion)    path-as-ontology)             (business diagnosis,
                                                        triage, Kanban)
Navigator ──────────┘
  (live web-app                                        Hermes
   instrumentation)                                     (autonomous service
                                                        agent, Playwright/CDP)
```

## Transformation layer

Produces `INTENTS/`. Each pipeline is a separate concern with its own input modality:

- **audio2tree** — Raw audio → structural transcription → atomic claims → hierarchical clustering → intents tree. Implemented as `.claude/skills/structural-transcription/`, `.claude/agents/conversation-distillation.md`, and the `harness-go` skill. The intents tree is the **authoritative source of behavioural truth**: support calls are the behaviour corpus from human agents performing real work.
- **doc2graph** — Operation manuals, product documentation, and written procedures → tensor-operator compute graph. Implemented as `.claude/skills/doc-to-graph/` (envisioned). Written documentation is always partial and frequently stale; it serves as the *official path*, not the *behavioural truth*.
- **Navigator** — Live web-application instrumentation → operator sequence graph. Captures the actual UI workflow as operators with data dependencies.

## Semantic layer

`INTENTS/` is a **git-versioned runtime artefact**, not code. It lives on disk as a path-as-ontology tree (the `<type>.<slug>.<ext>` grammar, described in `docs/product-specs/shared/intents-semantic-layer.md`). Argus reads it at a pinned SHA via the INTENTS Provider (`argus.io`).

The path is configurable (default: `INTENTS/` at repo root; override via `argus.config.intents_path`). The actual config mechanism is deferred to the first Argus exec-plan.

Key properties:
- **Single source of truth** — the bottom-up intents tree is authoritative; when it conflicts with the compute graph, the tree wins (see `docs/product-specs/shared/calibration.md`).
- **Git-SHA epoch** — consumers pin a specific SHA; upgrades are explicit.
- **Producer-owned** — every file in `INTENTS/` is owned by exactly one producer (audio2tree, doc2graph, or Navigator), tracked in `_meta/ownership.yaml`.
- **Versioned rubric** — the `_rubric/` shelf carries the acoustic framework, phrase-keyword lexicon, and rules & criteria at specific versions.

## Consumer layer

Three applications consume the calibrated output. This repository is **Argus only**. Metis and Hermes are interface references — Argus emits findings they consume, but their code is not here.

### Argus (this repo)

AI QA application: reads INTENTS → `score(facts, rubric)` → `adjust(raw, history)` → emits per-call verdicts with evidence citations, reports, and coaching tasks. The enforced architecture is in `ARCHITECTURE.md`.

### Metis (separate repo, not yet bootstrapped)

Business diagnosis: consumes Argus findings via `IArgusFindingFeed` (read-only, polling), plus the calibrated graph via `ICalibratedGraphReader`. Triage rules produce Kanban tickets. Audience: PM, BA, Marketing. Cadence: daily diagnostic run.

### Hermes (separate repo, not yet bootstrapped)

Autonomous service agent: procedural reasoning over the calibrated operator graph, action execution via Playwright MCP / Chrome DevTools Protocol. The action-tier system (read-only / confirmed / autonomous) is a unique safety surface. Cadence: per-session, real-time.

## What this document is not

- **Not enforced.** No lint, test, or CI gate references this file. It exists so a reader of `ARCHITECTURE.md` can see where Argus fits without the document having to describe Metis and Hermes in detail.
- **Not a deployment diagram.** The physical layout (which services run where, which queues connect them) is a separate concern, undocumented at this stage.
- **Not a substitute for `ARCHITECTURE.md`.** The architectural constraints that code in this repo must satisfy are in `ARCHITECTURE.md`. This document provides context; `ARCHITECTURE.md` provides rules.

`Last reviewed: 2026-07-04.`
