# core-beliefs.md

The agent-first design operating principles. These shape every choice in `docs/design-docs/`. They are not aesthetic preferences — they are properties that make the UI legible to the same coding agents that build and maintain it.

See also: [product-specs index](../product-specs/index.md) for the feature-level specs these beliefs inform. UI that is illegible to the agent will drift; UI that is legible to the agent stays consistent because the agent that next modifies it can reason about it.

Each belief carries a Rationale shaped according to the convention in `PLANS.md` (or its harness equivalent): cited source, named experiment, or explicit `Confidence: low` with a `Revisit:` date.

## Belief 1. Components mirror the data shape, not the visual shape

A component for displaying a fact-check verdict takes a `FactCheckVerdict` typed prop, not a flat list of strings. A component for showing a Hermes action takes an `ActionDescriptor`, not separate "title", "subtitle", "tier-color" props. Visual shape is derived from data shape; never the inverse.

**Rationale**: agents that next modify the component navigate from the data type, not from a Figma file. A flat-prop component requires the agent to reconstruct the data semantics from the component's name and its callers; a typed-prop component is self-evident. `Confidence: medium` from the OpenAI harness-engineering experience that the agent's framework for design decisions needed to evolve too — anything an agent can't access in-context while running effectively doesn't exist; verified at end of bootstrap on real components. `Revisit: 2026-08-01.`

## Belief 2. One composable primitive over three specialised ones

When two related surfaces could share a primitive, build the primitive — even if it costs more upfront. Reason: the agent reads the primitive once and applies it everywhere; three near-duplicate components produce three drift surfaces.

This is why the transcription-viewer is a single shared component with two presentation profiles (Argus, Hermes), not two separate viewers. It is why the evidence-citation component is one component used in Argus verdicts, Metis tickets, and Hermes audit records, not three.

**Rationale**: the OpenAI experience report describes favouring dependencies and abstractions that could be fully internalised and reasoned about in-repo. Technologies often described as "boring" tend to be easier for agents to model due to composability, api stability, and representation in the training set. The same logic applies internal-to-the-repo: agent-internalisable primitives outperform agent-confusing specialisations. `Confidence: medium`.

## Belief 3. Every interactive element has a stable test selector

Every button, link, input, and triggerable surface carries a `data-testid` (or framework equivalent) that survives restyling. Selector strings are stable across visual refactors; only the visual presentation changes when designs evolve.

**Rationale**: the doc-gardener subagent's drift detection works by comparing rendered DOM against design-doc claims about which selectors should exist. Without stable selectors, drift detection is impossible and `verification-status: drifted` cannot be detected mechanically. `Source: ARCHITECTURE.md § 5 UI`. Mechanical enforcement: `stable-test-selectors` lint.

## Belief 4. Action-tier visibility (Hermes-specific) is dual-channel

Hermes Tier-A / Tier-B / Tier-C are colour-coded *and* icon-coded *and* text-labelled. Citizens can never accidentally interpret a Tier-C action as Tier-A because the warning channel is suppressed (e.g., colour blindness, custom CSS, dark mode). The redundancy is the point.

**Rationale**: see `PRODUCT_SENSE.md § Hermes` failure tolerances. Class-C failures may be legally irreversible. The cost of redundant signalling is low; the cost of a citizen confidently authorising a Tier-B action they thought was Tier-A is asymmetrically high. `Source: PRODUCT_SENSE.md § Hermes`.

## Belief 5. Evidence is clickable, not just cited

When the system displays a verdict, finding, step, or action, the citation back to source (transcript turn, calibrated-graph operator, audit record) is interactive — clicking opens the source in context. A footnote-style citation is forbidden.

**Rationale**: `PRODUCT_SENSE.md § Argus` makes evidence-citation non-negotiable. A non-clickable citation forces the user to reconstruct the source location, which is friction that compounds across hundreds of reviews per day. `Confidence: high` from QA-tooling research generally; `Revisit: 2026-08-01` to confirm against actual reviewer behaviour.

## Belief 6. Confirmation flows are content, not chrome

The Tier-B confirmation flow in Hermes (`hermes/action-confirmation.md`) is the actual conversational surface, not a modal that interrupts the conversation. The chat shows: "Here's what I'm about to do — [action card] — confirm?" inline, in conversation flow. The user reads, scrolls if needed, confirms or rejects.

**Rationale**: modal confirmations train users to dismiss reflexively. Inline-conversation confirmations preserve attention. `Confidence: medium`; `Revisit: 2026-09-01` after first user-research session against citizens.

## Belief 7. Loading states surface what is loading and why

When a Hermes step is computing a plan, when an Argus call is being scored, when a Metis triage cycle is running, the loading state names what is happening — not "Loading…" but "Reading the calibrated graph for annual-report procedures" or "Cross-referencing the transcript against rules-version 12". The user can act on the information; an opaque spinner trains learned helplessness.

**Rationale**: the OpenAI experience report observes that "boring tech" wins in part because it is observable; the same applies one layer up to UI states. `Confidence: medium`.

## Belief 8. Drift status is visible, not hidden

When a `design-doc` carries `verification-status: drifted`, the corresponding UI surface displays a subtle "this surface is out of sync with its design spec" indicator visible to internal users, not to citizens. The indicator is removable only by fixing the drift (re-implementing to match the doc, or updating the doc to match implementation).

**Rationale**: drift is usually quiet failure; surfacing it cheaply makes fixes affordable. The indicator is internal-only because drift is a maintenance concern, not a citizen-facing one. `Confidence: low`; `Revisit: 2026-08-01` once the doc-gardener subagent is operational.

## Forbidden phrases

Same set as the rest of the spine. Mechanical enforcement: `forbidden-phrases`.
