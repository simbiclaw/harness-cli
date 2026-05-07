# PRODUCT_SENSE.md

Taste, non-goals, failure-mode tolerances, and decision tiebreakers for the three AI applications — Argus (AI QA), Metis (Business Diagnosis), Hermes (Autonomous Service Agent) — and for the cross-product surfaces where they interact.

This document carries the judgement that the PRDs do not. The PRDs say what is built; this file says what we will *not* build, which user wins when two conflict, what counts as good enough to ship, and which classes of failure block release. Architecture decisions in `ARCHITECTURE.md` encode these priorities; design decisions in `DESIGN.md` consume them. When the agent is choosing between two equally-feasible product behaviours, this is the file that breaks the tie.

Each app section follows the same shape: **the user**, **non-goals**, **failure-mode tolerances**, **tiebreakers**. The cross-product section governs cases where outputs of one app feed another.

## § Argus — AI QA

### The user

Argus serves three roles, and the priority order between them is fixed: **QA Reviewer** outranks **QA Supervisor** outranks **Call Center Agent** when the three want incompatible things. Reviewers see the most evidence per call, supervise the system's daily judgements, and bear the consequences of its mistakes; their workflow is the system's primary verification floor. Supervisors aggregate over reviewers and need different views; agents consume the system's verdicts and need the least system access. The conflict this resolves: a UI choice that improves agent self-service at the cost of reviewer evidence density picks the reviewer.

### Non-goals

Argus does not replace human reviewers. Argus does not generate scoring criteria — it consumes the Rules&Criteria expertise module, it does not edit it. Argus does not perform corrective action on agents (no termination, no compensation impact); it produces evidence-cited verdicts and coaching tasks, and humans act on them. Argus does not score calls outside the supported domains in the expertise library (calls outside the digital-certificate, electronic-seal, corporate-registration, annual-reporting, credit-restoration domains return `out-of-scope`, not a low score). Argus does not model agent intent or sentiment beyond what's directly testable against the rule set; "the agent seemed rude" is not an Argus verdict, "the agent failed to deliver the required disclosure at turn 14" is.

### Failure-mode tolerances

A wrong score with cited evidence is *recoverable* — the reviewer overrides it, the override feeds the Error Case Library, the system learns. **A score without traceable evidence to the transcript and the rule that fired is a release-blocker.** Citations are non-negotiable; an Argus verdict that cannot be defended back to its sources is worse than no verdict, because it pollutes the training signal for the self-learning loop. Latency tolerance is generous — a call scored within 24 hours is fine, within 1 hour is great, real-time is not currently in scope.

### Tiebreakers

When evidence density and review speed conflict, evidence density wins; reviewers can scroll, they cannot un-misjudge. When agent privacy and supervisor visibility conflict, follow the policy in `docs/adr/` (see `Awaiting Steering` below — this needs a decision). When the rule set is ambiguous about whether a turn passed, mark it `requires-review`, do not guess; an unreviewed `requires-review` is a better outcome than a confidently-wrong pass-or-fail.

### Awaiting Steering

> **Question**: What is the agent-privacy policy for QA findings? Specifically, can supervisors see per-agent rolling fail rates, or only aggregate-level dashboards with named agents only on individual call review? Options: (a) full per-agent visibility for supervisors, (b) supervisor sees aggregate, named only when reviewing a specific call, (c) named visibility only after a configurable threshold of failed calls in a window.
> **Default if not decided by start of M3 of `0001-bootstrap-the-spine.md`**: option (b).
> **Decided by**: _pending_

## § Metis — Business Diagnosis

### The user

Metis serves business analysts, product managers, and marketing. Among these, the priority is **product manager** outranks **business analyst** outranks **marketing**, because the discovery-to-fix loop's terminus is a code change or a process change, both of which are PM-owned. The conflict this resolves: a feature that reads better as a market-trend dashboard but worse as a triage queue picks the triage queue.

### Non-goals

Metis does not auto-fix anything in production. The PRD describes a closed loop ending in deployment; **the current scope stops at issue-emission to a Kanban surface**. The loop's later stages (human review → code fix → deploy → verify) are explicitly outside the runtime, performed by humans using whatever tools they choose. Architecturally, the system must not preclude later automation, but the current commitment is a Kanban that displays issues with severity scores, sample logs, and suggested investigations. Metis does not silently re-classify customer voice — every triage decision must be reproducible from the input transcripts and the active rule set.

Metis does not have Claude Code as a runtime production dependency. Coding agents may be used in development, but the production path is human-driven.

### Failure-mode tolerances

A miscategorised issue is *recoverable* — the analyst recategorises, the recategorisation feeds the triage rules. **A duplicated issue is worse than a missed issue**, because duplicates poison the Kanban faster than gaps. The system should err toward consolidation: when two clusters of customer voice look like the same underlying problem, prefer one ticket with high evidence count over two tickets that each look thin. Latency tolerance is moderate — daily triage cycle is the target, hourly is unnecessary, real-time is not in scope.

### Tiebreakers

When precision and recall conflict in triage, precision wins; a Kanban full of false positives loses analyst attention faster than a Kanban that misses a few real issues. When severity score and evidence count disagree (a low-evidence high-severity claim vs. a high-evidence low-severity claim), prefer surfacing the high-evidence item first; severity without evidence is speculation. Cross-product: when Metis discovers an issue that is also a QA finding in Argus, route the Argus finding's evidence into the Metis ticket — see cross-product tiebreakers below.

### Awaiting Steering

> **Question**: What is the deduplication policy across the Kanban? When two analysts independently categorise overlapping clusters, does the system merge automatically, prompt one of them, or leave both?
> **Default if not decided by start of M4 of `0001-bootstrap-the-spine.md`**: prompt the second analyst with the prior ticket's link.
> **Decided by**: _pending_

## § Hermes — Autonomous Service Agent

### The user

Hermes serves citizens navigating government and enterprise services in the supported RegTech domains. There is one user role; there is no priority conflict within the user base. The primary conflict for Hermes is between **the user's request** and **the system's safety floor** — the user can ask for anything, but the system has actions it will not perform and confirmations it will not skip.

### Non-goals

Hermes does not perform actions outside the supported domains. Hermes does not modify or create accounts the user does not own (no acting on behalf of someone other than the authenticated session). Hermes does not bypass official confirmation dialogs in target systems — if the underlying system asks the user to confirm, Hermes asks the user to confirm too, even if Hermes could mechanically dismiss the dialog. Hermes does not silently retry actions that failed; failed actions surface to the user with the failure reason. Hermes does not store credentials beyond the session.

### Failure-mode tolerances

This is the section that distinguishes Hermes from the other two and shapes the architecture most aggressively. Three classes of failure with very different tolerances:

**Class A — read-only failures** (DOM inspection, screenshot, navigation that does not commit state). Recoverable. Hermes retries, falls back, reports the failure to the user, and continues. No release blocker.

**Class B — confirmed-action failures** (user explicitly accepted a proposed action; Hermes executed it; the action failed mid-execution). Recoverable but requires careful state surfacing — the user must be told *exactly* what got committed and what did not, with citations to the underlying system's confirmation receipts. A Class B failure with vague status reporting is a release-blocker; a Class B failure with precise status reporting is acceptable behaviour.

**Class C — autonomous-action failures** (Hermes took action without explicit per-action user confirmation, and the action committed wrong state). **A Class C failure in the RegTech domains may be legally irreversible**: a wrong corporate-registration change, a wrong filing, a wrong fee payment. Class C failures are the highest-severity failure mode in the entire three-app system and the architecture must make Class C actions *structurally rare*, not merely conventionally rare. The action-tier system in `ARCHITECTURE.md` enforces this.

### Tiebreakers

When user convenience and confirmation friction conflict, confirmation wins — Hermes asks again rather than acts ambiguously. When a workflow could be completed via a single autonomous batch or a series of confirmed steps, prefer confirmed steps unless every action in the batch is read-only. When the user expresses urgency ("just do it, I trust you"), the urgency does not lower the confirmation tier of an action — Hermes acknowledges the urgency, accelerates by minimising prompts within the same tier, but does not promote Tier-B actions to Tier-C on the user's verbal say-so.

### Awaiting Steering

> **Question 1**: What is the canonical action-tier classification for the supported domain operations? A first cut is in `docs/product-specs/hermes/action-execution.md`, but the policy needs human sign-off because the cost of getting this wrong is asymmetric (Class C failures are the worst-case failure mode in the system).
> **Default if not decided by start of M5 of `0001-bootstrap-the-spine.md`**: every action defaults to Tier B (requires explicit per-action user confirmation) unless the action surface explicitly classifies it as Tier A (read-only); Tier C is initially empty.
> **Decided by**: _pending_
>
> **Question 2**: Authentication model. Does Hermes operate in the user's authenticated browser session (the user is already logged in, Hermes inherits the session), or does Hermes require its own credentials with delegated authority? The PRD does not specify and the implications differ — session inheritance is simpler but couples Hermes to whatever session lifecycle the target system uses; delegation is more robust but requires per-target integration.
> **Default if not decided by start of M5 of `0001-bootstrap-the-spine.md`**: session inheritance via Playwright MCP / CDP attaching to a user-launched browser, with explicit "Hermes is now driving" indicator in the UI.
> **Decided by**: _pending_
>
> **Question 3**: Audit trail and reversibility surface. Every Tier B and Tier C action must produce an audit record. What is the user-facing surface for "show me what Hermes did on my behalf today" and what is the retention policy?
> **Default if not decided by start of M6 of `0001-bootstrap-the-spine.md`**: per-session audit log visible in the Hermes UI, persisted for the session's duration plus 30 days, exportable as plain text.
> **Decided by**: _pending_

## § Cross-product tiebreakers

The three apps share infrastructure and occasionally share findings. The rules below govern the cases where one app's output feeds another.

**Calibration authority is bottom-up.** When the intents-tree (derived from the support-call corpus, representing the behavioural reality of how citizens actually phrase requests) and the compute-graph (derived from operation manuals, representing the official documentation of how procedures are supposed to work) disagree, **the intents-tree wins**. The compute-graph is updated to match. The reason is that support calls are the behaviour corpus from human agents performing real work; the operation manual is documentation, which is always partial and frequently stale. Documentation calibrates against reality, not the other way around. This is enforced architecturally: the calibration module's API requires intents-tree as the dominant input and structurally refuses to produce output where the resolution direction is reversed. See `ARCHITECTURE.md` for the mechanical check; see `docs/product-specs/shared/calibration.md` for the contract.

**Argus findings feed Metis triage when systemic.** When Argus discovers the same rule-fail across more than N agents in a window (configurable, initial default N=5), the finding is forwarded to Metis as a candidate process-or-product issue. The rule violation is a per-call symptom; the systemic pattern is a per-product issue. Metis decides whether to open a Kanban ticket; Argus does not unilaterally escalate.

**Hermes consumes the calibrated compute-graph; Hermes does not write to it.** Hermes is a downstream consumer of the bottom-up + top-down knowledge spine. When Hermes encounters a procedural state the compute-graph does not cover, the gap is logged for offline review (and feeds Metis as a documentation-gap issue), not papered over by Hermes inventing a path. Hermes refuses to act on speculative graph extensions.

**The expertise library is read-only at runtime.** All three apps consume the expertise modules (Rules&Criteria, Acoustic Feature, Product Introduction, Dynamic Knowledge Base, Best Practice Cookbook, Error Case Library, Phrase&Keyword Library). None of them write to it at runtime. The Error Case Library updates via a separate offline pipeline that ingests reviewer overrides; this is a deliberate separation that prevents runtime feedback loops from inflating the library's authority.

**Forbidden phrases.** This document, like the rest of the spine, may not contain the phrases "best practice", "industry standard", "clean architecture", or "follows convention" without an immediately-following citation, experiment reference, or explicit `Confidence: low` marker. Unjustified appeals to authority are a defect class, enforced by structural test in CI.

## Status

| Section | Status | Last reviewed |
|---|---|---|
| § Argus | proposed | bootstrap |
| § Metis | proposed | bootstrap |
| § Hermes | proposed | bootstrap |
| § Cross-product | proposed | bootstrap |

All sections are `proposed` until the listed `Awaiting Steering` blocks resolve and an ADR is written for each. Sections move to `accepted` when their corresponding ADR exists in `docs/adr/`.
