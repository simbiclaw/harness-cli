---
name: doc-gardener
description: Recurring custodial agent. Walks docs/conventions/, CLAUDE.md,
  and docs/PLANS.md for staleness, broken cross-references, and
  past-deadline Confidence-low entries. Opens an ExecPlan if any check fails.
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
`Last reviewed: YYYY-MM-DD` footer. Anything >90 days old is flagged.

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
`docs/plans/active/NNNN-doc-garden-<date>.md` listing the failures as
Milestones. Each milestone has a clear remediation (update the link,
refresh the doc, run the experiment, etc.). Many failures = many
milestones in one ExecPlan, not many ExecPlans.

## What this skill must NOT do

- Modify documentation autonomously (only humans approve doc changes).
- Modify hooks, structural tests, or CI workflows.

Last reviewed: 2026-05-01
