# DESIGN.md

The design contract for the three apps. This file is the **index**: design system tokens, the component vocabulary, navigation primitives, accessibility floor, and one-line links to deeper docs in `docs/design-docs/`. The agent-first design principles live in `docs/design-docs/core-beliefs.md`; read that first when making design choices, then come here for the lookup.

## Component vocabulary

The three apps share three categories of UI surface; each category has a small fixed set of components used across apps. Categories:

**Evidence-citing components** consumed by all three apps. When the system displays a verdict, a triage finding, or a procedural step, every claim is rendered with a citation back to its source — a transcript turn for Argus, a cluster of transcripts for Metis, a compute-graph node for Hermes. The citation is a clickable artefact, not a footnote. See `docs/design-docs/shared/evidence-citing.md`.

**Transcription viewers** consumed by Argus and Hermes. Argus shows a single call with rule-fired highlights; Hermes shows a procedural conversation with action-tier indicators. Same underlying viewer, two presentation profiles. See `docs/design-docs/shared/transcription-viewer.md`.

**Expertise browsers** consumed by Argus, Metis (selectively), and Hermes. The seven expertise modules surface here — readers, not editors. See `docs/design-docs/shared/expertise-browser.md`.

App-specific surfaces sit on top of these:

- **Argus**: QA review surface (`docs/design-docs/argus/qa-review-surface.md`), coaching task list (`docs/design-docs/argus/coaching-task-list.md`).
- **Metis**: triage Kanban (`docs/design-docs/metis/triage-kanban.md`).
- **Hermes**: citizen chat (`docs/design-docs/hermes/citizen-chat.md`), action confirmation (`docs/design-docs/hermes/action-confirmation.md`).

## Design tokens

Tokens are defined once and consumed everywhere. The token set is intentionally small.

| Category | Tokens |
|---|---|
| **Spacing** | `xs` (4px), `sm` (8px), `md` (16px), `lg` (24px), `xl` (32px), `2xl` (48px). No other spacing values. |
| **Type scale** | `body-sm`, `body`, `body-lg`, `heading-3`, `heading-2`, `heading-1`. No arbitrary font sizes. |
| **Colour — semantic** | `bg-primary`, `bg-elevated`, `text-primary`, `text-secondary`, `text-muted`, `border`, `accent`, `accent-emphasis`, `success`, `warning`, `danger`. Semantic only — no raw hex values in components. |
| **Action-tier colour (Hermes-specific)** | `tier-a-read` (neutral), `tier-b-confirmed` (accent), `tier-c-autonomous` (warning). The Tier-C colour is `warning` deliberately — Tier-C actions should look conspicuous. |
| **Radius** | `sm`, `md`, `lg`, `full`. |
| **Motion** | `fast` (120ms), `default` (240ms), `slow` (480ms). Timer values are configurable per surface but selected from this set. |

Tokens are defined in a single source file (location TBD; M3 of `0001-bootstrap-the-spine.md` decides between CSS variables, design-token JSON, or a typed module — whichever the front-end stack chosen in the boring-tech ledger uses).

## Navigation primitives

Three navigation patterns across the apps. Each is named so design-docs can refer to them rather than inventing new ones per surface.

**Tabbed inspection**: a primary tab strip across the top of a fixed-content surface; tabs swap content but preserve scroll position per tab. Argus QA review and Hermes action audit log use this.

**Filterable column list**: a single vertical list with a filter rail on the left and a sort selector on top. Metis Kanban uses this; Argus coaching task list uses this.

**Linear conversation**: a single scrolling conversation with optional inline action confirmations. Hermes citizen chat is the only surface with this pattern; it does not have tabs and does not have a filter rail — adding either would compromise the action-confirmation flow.

These three patterns are exhaustive. New navigation patterns require an ADR.

## Accessibility floor

Every interactive element is keyboard-reachable. Every non-decorative image has alt text or aria-label. Colour is never the only signal; shape, position, or text co-conveys every meaning. Action-tier indicators specifically use both colour (`tier-a-read` neutral / `tier-b-confirmed` accent / `tier-c-autonomous` warning) **and** an icon and text label — Tier-C actions never rely on the warning colour alone to convey their stakes. Focus indicators meet WCAG AA contrast against every legal background.

Mechanical enforcement: `axe-core` runs in CI against rendered surfaces from the component library; failures block merge.

## Verification status

This file's contents are themselves marked with verification status. Per-design-doc files in `docs/design-docs/<app>/` carry their own `verification-status:` field; the values are:

- `proposed` — design exists in this doc, no implementation yet.
- `implemented` — design exists in this doc and matching components exist in the codebase with stable test selectors.
- `drifted` — design here disagrees with what the running app does; the doc-gardener flagged this and a fix-up is pending.
- `obsolete` — design here is no longer in use; doc kept for history but not consumed.

The doc-gardener subagent re-scans `implemented` design-docs against rendered DOM and screenshots on a schedule and flips status to `drifted` when they disagree.

This file (DESIGN.md) status: **proposed**, last reviewed bootstrap. The status flips to `implemented` when the component library matches and the lints (`stable-test-selectors`, `axe-core`) pass on every shipped surface.

## Forbidden phrases

Same forbidden-phrase set as the rest of the spine: "best practice", "industry standard", "clean architecture", "follows convention" require citation, experiment, or `Confidence: low` marker. Mechanical enforcement: `forbidden-phrases` lint applies to this file.
