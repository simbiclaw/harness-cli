# Generating the harness's knowledge spine from PRD

Before the prompts: the four artifacts aren't four parallel tasks. They have a dependency order, different audiences, and different mechanical checks. 

The right shape is a **chain** where each step's output becomes part of the next step's reading, plus a session-scoped routing aid so the agent knows where it is in the chain. Below: the chain, the per-artifact prompting contract, and where Claude Code's harness primitives (skills, slash commands, hooks, subagents) attach.

## Step 0: borrow CLAUDE.md transactionally; don't rewrite it

Generation of the spine is **session-scoped scaffolding**, not a permanent navigational layer. Once the four artifacts exist and link to one another, the agent navigates by following those links — a top-level "what each file is for" map becomes background noise that pays a context tax forever for a problem that only existed during bootstrap.

So the skill leaves CLAUDE.md's behavioral content untouched and instead **borrows the auto-loaded slot transactionally**: append a sentinel-wrapped pointer at start, remove it at end. Concretely, the skill's first and last actions on every run:

```
<!-- harness-spine-bootstrap:begin -->
read docs/MAP.md first
<!-- harness-spine-bootstrap:end -->
```

The sentinel matters. Append-then-remove is a two-phase commit on a shared file, and crashes, ctrl-C, or signal-kills can leave phase 2 unrun — at which point CLAUDE.md permanently carries a pointer to a routing file that may or may not still be relevant, and every future session pays the cost. With the sentinel: the skill's first action is "remove any pre-existing spine-bootstrap block," its last is "remove the block I added," and even a mid-flight death gets cleaned up by the next invocation. Wrap the work in `trap cleanup EXIT` for belt-and-braces. A CI lint asserting "this block must not exist on `main`" turns the invariant into a mechanical check.

`docs/MAP.md` itself is the actual routing table — one short paragraph per artifact stating *when to read it and when not to*. The "when not to" is load-bearing; without it you get four generic stubs that all sound equally important. MAP.md lives only as long as the bootstrap; once the spine is wired and the artifacts cross-link properly, MAP.md is deleted in the same PR that ships the spine. The artifacts navigate to each other; nobody navigates to MAP.md anymore.

## Step 1: PRODUCT_SENSE.md and `docs/product-specs/`

**Role.** PRODUCT_SENSE.md is the analog of teammate onboarding on product principles. It carries judgment the PRD does not — what the product *won't* do, which user is the priority when two conflict, what "good enough" looks like for shipping, what failure modes are acceptable vs. unacceptable. The PRD is *what*; PRODUCT_SENSE is *taste*. `product-specs/` is the per-feature elaboration, mirroring the article's structure (`index.md`, `new-user-onboarding.md`, etc.).

**Why first.** Architecture decisions encode product priorities. Generating ARCHITECTURE.md before PRODUCT_SENSE.md means the agent invents priorities to make the architecture coherent and you never see those invented priorities until they're load-bearing. This is the most common ordering failure I'd expect.

**Inputs.** PRD, plus a list of out-of-context sources you can name (Slack threads, Linear tickets, Figma — for each, decide encode-into-repo or explicitly-out-of-scope). Instruction shape:

> Read PRD.md. Produce `docs/PRODUCT_SENSE.md` and a `docs/product-specs/` directory with one file per distinct user-visible feature in the PRD plus an `index.md`. PRODUCT_SENSE.md must contain (a) **the user we are building for** stated as a single sentence with the conflicts that sentence resolves, (b) **non-goals** — explicit things this product will not do — at least as long as the goals section, (c) **failure-mode tolerances** stating which classes of bug block release and which do not, (d) **decision tiebreakers** for the three most likely product trade-offs that will recur. Each `product-specs/<feature>.md` states the user job, the acceptance behavior an end user can observe, and the open questions that need human steering. Anywhere you would write "best practice" or "industry standard," stop and instead cite a source, name an experiment, or mark the claim `Confidence: low`. If the PRD is silent on something a reasonable agent would need to decide, surface it as an `Awaiting Steering:` block — do not paper over.

**Mechanical checks.** Linter fails CI if the non-goals section is shorter than the goals section. Hook rejects the file if it contains forbidden phrases. Required cross-link from every `product-specs/<feature>.md` back into a tiebreaker rule in PRODUCT_SENSE.md — orphan specs flagged.

## Step 2: DESIGN.md and `docs/design-docs/`

**Role.** DESIGN.md is the contract for *how the product is shaped* — UX patterns, interaction model, visual hierarchy, design system tokens, accessibility floor. The article specifies that design documentation is catalogued and indexed, including verification status and a set of core beliefs that define agent-first operating principles — which is why `design-docs/core-beliefs.md` and `design-docs/index.md` appear as siblings. DESIGN.md is the lookup; `design-docs/` is the deep reference.

**Why second.** Design decisions consume product priorities (from PRODUCT_SENSE) and produce constraints architecture must accommodate (component boundaries, state ownership, navigation model). Inverting design and architecture means the architecture invents a UX without knowing it.

**Inputs.** PRD + PRODUCT_SENSE.md + product-specs/. Instruction shape:

> Read MAP.md, PRD.md, PRODUCT_SENSE.md, and all of `docs/product-specs/`. Produce `docs/DESIGN.md` plus `docs/design-docs/index.md` and `docs/design-docs/core-beliefs.md`. DESIGN.md is the **index**: design system tokens, component vocabulary, navigation primitives, accessibility floor, and one-line links to deeper docs in `design-docs/`. core-beliefs.md states the **agent-first operating principles for design** — for example: "components are legible to the agent if their props mirror the data shape, not the visual shape," "we prefer one composable primitive over three specialized ones because the agent reads the primitive once," "every interactive element has a stable test selector that survives restyling." Each belief carries a Rationale shaped as cited / experimental / explicit-low-confidence. Add a `verification-status:` field at the top of each design-doc file with values `proposed | implemented | drifted | obsolete`. Generate one design-doc file per product-spec that has UI surface area. If a product-spec has no UI surface, do not invent design content for it; note the absence.

**Mechanical checks.** Linter fails if any `design-docs/<file>.md` is missing its `verification-status:`, or if status is `proposed` for more than 14 days without movement, or if it claims `implemented` but no test references its named selectors. A doc-gardener subagent periodically re-scans implemented design-docs against the running app (DOM/screenshot comparison) and flips status to `drifted` when output diverges, opening a corrective PR. Cross-link integrity: every belief in core-beliefs.md must be cited by at least one design-doc, otherwise it gets demoted to `archive/`.

## Step 3: ARCHITECTURE.md

**Role.** The most leveraged of the four. [The article(read document)](harness-engineering-llm.md)  says architecture documentation provides a top-level map of domains and package layering, and shows the layered model (Types → Config → Repo → Service → Runtime → UI, with Providers as the explicit cross-cutting interface). The point isn't the diagram — it's that the layering is **mechanically enforced** by custom linters and structural tests, and the linter error messages inject remediation guidance into the agent's next turn. ARCHITECTURE.md and the lints it generates are a single artifact: text documenting an invariant, plus tests that fail when the invariant breaks. see [a demonstration (read document)](architecture-ref.md) for the structure of `ARCHITECTURE.md`

**Why third.** It must absorb product non-goals (so domain boundaries don't grow speculative scope) and design constraints (so component boundaries align with state ownership). Generated first, it tends to be a generic three-tier stack regardless of the actual product.

**Instruction shape.**

> Read MAP.md, PRD.md, PRODUCT_SENSE.md, all of `product-specs/`, DESIGN.md, and `design-docs/core-beliefs.md`. Produce `ARCHITECTURE.md` containing: (a) a **domain inventory** listing each business domain with one sentence justifying it from PRODUCT_SENSE non-goals — domains exist because something is intentionally separated, name what; (b) a **layered model** specifying the permitted layer set within a domain and the directional dependency rule, plus the explicit cross-cutting boundary (the analog of "Providers"); (c) a **dependency matrix** as a table where rows are domains and columns are domains, every cell either `none`, `via providers`, or names the specific interface — no implicit edges; (d) a **boring-tech ledger** of dependencies chosen for agent legibility, each with the alternative that was rejected and the reason; (e) a **section per layer** stating the parsing-at-boundary rule, the logging contract, and the testing floor. Then produce a sibling `tools/lint/` proposal: for every architectural rule you state in prose, name the structural test or custom lint that mechanically enforces it. Rules without a corresponding lint are not rules — mark them `Aspiration:` and date them with a `Revisit:`. Forbid the words "best practice," "standard," and "clean architecture" anywhere in the file.

**Mechanical checks.** The corresponding linter and structural-test suite — generated in the same task. CI fails on any cross-domain edge not in the matrix. CI fails on any layer reaching backward. CI fails on any `Aspiration:` rule whose `Revisit:` date is past. A doc-gardener subagent compares the current import graph against the matrix monthly and opens a PR either tightening the matrix or fixing the imports.

## Step 4: QUALITY_SCORE.md

**Role.** Per the article, a quality document grades each product domain and architectural layer, tracking gaps over time. The only artifact whose contents are *graded*, not authored. The empirical feedback loop that keeps the other three honest.

**Why last.** It scores against ARCHITECTURE.md's domains and layers and PRODUCT_SENSE.md's non-goals. Generated earlier, it has nothing to score.

**Instruction shape.**

> Read all four prior artifacts plus the actual codebase (or, if pre-implementation, the planned scaffold). Produce `QUALITY_SCORE.md` as a graded table: rows are every domain × layer cell from ARCHITECTURE.md's matrix; columns are `coverage`, `boundary-respect`, `boring-tech-adherence`, `doc-freshness`, `test-floor-met`. Each cell is `A | B | C | D | F` plus a one-sentence justification linking to evidence (a file path, a test name, a linter output). Below the table, list the **top five gaps** ordered by leverage — where a small fix raises multiple grades. Do not produce a "weighted average" or any other single number; the point is to see uneven decay. End with a `Last graded:` timestamp and a `Next regrade:` date no further than 14 days out.

**Mechanical checks.** This is the artifact most aggressively wired to subagents. A grader subagent regenerates the file on a schedule, diffs against the previous version, posts the deltas — improvements and regressions — as a PR comment on the next changeset that touched any cell that moved. A hook fails CI if any cell carries D or F older than its `Next regrade:` date without an exec-plan in `docs/exec-plans/active/` whose Big Picture section names the failing cell.

## Step 5: tear down the scaffolding

The skill's final action, before removing the sentinel block from CLAUDE.md: delete `docs/MAP.md` and commit the deletion in the same PR that ships the spine. The artifacts now cross-link to each other; the bootstrap routing aid has nothing left to route. Leaving MAP.md in the repo creates exactly the rot pattern the article warns against — a file that *was* the source of truth for one phase becoming a stale parallel index that future agents have to reconcile against the real artifacts. Kill it cleanly. The CI lint asserting the sentinel block is absent on `main` confirms phase 2 ran.

## How to actually drive this from Claude Code

A few harness-shaped suggestions that integrate with the primitives you have:

**Each generation step runs as a subagent with a narrow context.** PRODUCT_SENSE generation does not need the codebase; ARCHITECTURE generation does not need the PRD's marketing prose. Subagent delegation keeps each window clean, which materially improves output quality on long documents. Pass only the upstream artifacts the prompt names.

**A skill — `harness-knowledge-spine` — owns the prompts, the sentinel-wrapped CLAUDE.md borrow, and the MAP.md teardown.** Each artifact's full instruction shape lives in the skill, not in the slash command, so revisions ship as PRs against the skill rather than as one-off edits. The skill also owns the linter scaffolding for each artifact's mechanical checks — keeping the document and its enforcement co-located. The skill's lifecycle is: clean any pre-existing sentinel block → append fresh sentinel block → run the chain → delete MAP.md → remove sentinel block → commit. `trap cleanup EXIT` ensures the sentinel removal runs on signal or crash.

**A PostToolUse hook checks cross-link integrity on every write.** When any of the four artifacts (or their satellite directories) is modified, the hook re-runs the linter that validates: every product-spec has a tiebreaker citation; every design-doc has a verification-status; every ARCHITECTURE rule has a corresponding lint or an unexpired Aspiration; every QUALITY_SCORE D/F has an active exec-plan. Failure reverts the write and writes to the active plan's Surprises & Discoveries section.

**A scheduled doc-gardener subagent runs nightly.** Re-grades QUALITY_SCORE; flips drifted design-doc statuses; flags PRODUCT_SENSE tiebreakers that haven't been cited by any plan in 30 days as candidates for archival; and — crucially — fails loudly if it finds either a stale sentinel block in CLAUDE.md or a MAP.md still on disk after a successful spine ship. This is the garbage-collection loop the article describes, extended to cover the bootstrap scaffolding itself.

The thing to resist throughout: treating these documents as deliverables. They are *contracts* with the agent — every line either earns its keep by changing the agent's next decision, or it's noise that crowds out the lines that do. The mechanical checks are what tell you which is which. And the bootstrap scaffolding earns its keep only during bootstrap; the discipline of removing it is the same discipline that keeps the spine itself honest.