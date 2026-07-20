---
name: doc-gardener
description: Recurring custodial agent. Walks docs/conventions/, CLAUDE.md,
  and docs/PLANS.md for staleness, broken cross-references, and
  past-deadline Confidence-low entries. Also verification-status staleness,
  QUALITY_SCORE.md regrade staleness, and cross-doc link integrity.
  Opens an ExecPlan if any check fails.
---

# Doc-Gardener Skill

## When to use this skill

Weekly via cron. Also on-demand when a human says "review the docs".

## Checks

### Cross-reference integrity
For every Markdown file under `docs/` and `CLAUDE.md`:
- Every relative link to another file in the repo resolves.
- Every code reference (`path:line` or `path:line-range`) still points at
  relevant code (the file exists; the line range is in bounds).
- Every `https://` URL returns a 2xx or 3xx status (HEAD request, max 3
  redirect hops).

### Last-reviewed staleness
Every convention doc, the PLANS.md rubric, and CLAUDE.md have a
`Last reviewed: 2026-07-20 footer. Anything >90 days old is flagged.

### Past-deadline Confidence-low entries
Walk every Decision Log entry with `Confidence: low`. If the corresponding
`Revisit:` deadline has passed (date or named milestone reached), flag it.

### Citation domain quality
For `Source:` URLs in Decision Log entries, flag domains that look like
aggregators rather than primary sources: medium.com, dev.to,
geeksforgeeks.org, freecodecamp.org, w3schools.com, tutorialspoint.com.
This is a soft warning, not a failure — the human reviews and decides.

### dep-override audit
Walk `git log --grep='\[dep-override-approved-by-human\]'` and confirm
each override commit corresponds to an ExecPlan section explaining why
the override was necessary. Flag any unexplained overrides.

### Verification-status staleness
For every file under `docs/` with a `verification-status:` field:
- `proposed` older than 14 days without movement → flag.
- `implemented` where rendered DOM doesn't match design-doc claimed selectors → flag as `drifted`.
- `obsolete` older than 90 days → flag for archival review.

### Cross-doc link integrity
Every `docs/product-specs/` file must reference `PRODUCT_SENSE.md` in a tiebreaker context. Every `docs/design-docs/` file must link to its corresponding product-spec. Missing cross-references are flagged.

### Forbidden hand-edits
Files under `docs/generated/` must not be hand-edited. Hand-edits are detected by comparing the file's content against its declared generation source. Flag any mismatch.

### QUALITY_SCORE.md regrade staleness
If `QUALITY_SCORE.md` has a `Next regrade` date in the past and no active exec-plan covers the regrade, flag it. Also flag any hand-edited grade without inline evidence (reinforcing the `quality-grade-evidence-required` lint).

### PRD-to-spine drift
If `docs/PRD_MANIFEST.json` exists:
- Resolve the `docs/PRD` symlink to its target directory.
- For each file in the manifest's `files` key, compute its current SHA256
  hash and compare against the stored hash.
- Flag any mismatches, new `.md` files not in the manifest, or manifest
  entries pointing to files that no longer exist.
On drift: add a milestone to the ExecPlan to run harness-go-sync for the
affected stages (from `stage_affinity`). Mismatch severity is
**regeneration-recommended** — the spine may be stale but is not known to
be wrong.

## Output

If ANY check fails, open
`docs/exec-plans/active/NNNN-doc-garden-<date>.md` listing the failures as
Milestones. Each milestone has a clear remediation (update the link,
refresh the doc, run the experiment, etc.). Many failures = many
milestones in one ExecPlan, not many ExecPlans.

## What this skill must NOT do

- Modify documentation autonomously (only humans approve doc changes).
- Modify hooks, structural tests, or CI workflows.

Last reviewed: 2026-07-20
