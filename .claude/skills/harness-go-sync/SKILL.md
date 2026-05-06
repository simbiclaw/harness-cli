---
name: harness-go-sync
description: Use when the knowledge spine needs incremental regeneration after PRD changes — detects drift via PRD_MANIFEST.json, maps changed files to affected stages via stage_affinity, and runs only the needed harness-go stages forward
---

# Harness-Go-Sync

## Overview

Incremental companion to `harness-go`. Instead of running the full bootstrap pipeline (MAP.md, sentinel, 4 artifacts, teardown), this skill detects which PRD files changed and runs only the affected stages forward. Uses the same stage prompts as `harness-go` — does not duplicate them.

## When to use

- `test_prd_spine_drift.py` fails CI and reports specific stages
- Doc-gardener opens a drift ExecPlan
- Manual: "sync the spine with PRD"

Do NOT use for first-time bootstrap — that needs the full `harness-go` pipeline.

## Algorithm

```
1. Run compute_manifest.py to detect changed files
2. If no changes: report "spine is current" and stop
3. Load PRD_MANIFEST.json stage_affinity
4. For each changed file, find all affected stages
5. Determine the earliest affected stage (lowest stage number)
6. Run harness-go prompts from that stage through stage 4, in order
7. Run compute_manifest.py to update hashes
8. Commit with Plan: harness-go-sync trailer
```

## Step 1: Detect changes

```bash
python3 .claude/skills/harness-go/scripts/compute_manifest.py
```

Parse the output. If "no changes" — done. Otherwise, note which files are in `Added:`, `Updated:`, `Removed:` lines.

The script has already updated `docs/PRD_MANIFEST.json` with fresh hashes. But we haven't regenerated the spine yet — we'll run it again after regeneration (Step 3).

## Step 2: Determine earliest affected stage

Load `docs/PRD_MANIFEST.json` and read `stage_affinity`. For each changed file, collect all stages that list that file. Find the numerically earliest stage.

Example: `Fact-Checking.md` changed → stage_affinity says `03-architecture` and `04-quality-score` → earliest is stage 03. Run 03 → 04.

Example: `Hermes.md` changed → stage_affinity says `01-product-sense` → earliest is stage 01. Run 01 → 02 → 03 → 04.

If a changed file is not in any stage_affinity list, flag it and treat as stage 01 (full re-run to be safe).

## Step 3: Run affected stages

For each stage from earliest through 04, dispatch a subagent with the corresponding harness-go prompt:

| Stage | Prompt file |
|-------|------------|
| 01    | `.claude/skills/harness-go/prompts/01-product-sense.md` |
| 02    | `.claude/skills/harness-go/prompts/02-design.md` |
| 03    | `.claude/skills/harness-go/prompts/03-architecture.md` |
| 04    | `.claude/skills/harness-go/prompts/04-quality-score.md` |

Each subagent reads the prompt, loads the specified inputs (which include prior stage outputs), and writes the artifact. Run stages sequentially — each depends on the prior's output.

## Step 4: Finalize

```bash
python3 .claude/skills/harness-go/scripts/compute_manifest.py
```

This updates `docs/PRD_MANIFEST.json` with the post-regeneration hashes. Then commit everything together:

```
harness-go-sync: regenerate <affected artifacts> for PRD change

Changed PRD files: <list>
Stages run: <list>
Manifest updated

Plan: harness-go-sync
Decision: incremental regeneration — only changed-file stages re-run;
          downstream stages chained for artifact consistency.
```

## Output (no changes)

```
harness-go-sync: no PRD changes detected. Spine is current.
  Last synced: <generated_at from manifest>
  Manifest commit: <harness_go_commit from manifest>
```

## Output (changes detected)

```
harness-go-sync: 1 PRD file changed
  Fact-Checking.md → stages: 03-architecture, 04-quality-score
  Starting from: 03-architecture
  Stages to run: 03-architecture, 04-quality-score

[subagent: stage 03...]
[subagent: stage 04...]
[compute_manifest.py: Updated: Fact-Checking.md]
[commit]
```

## Guard rails

- **Never skip downstream stages.** If stage 02 changes, run 02 → 03 → 04. Each builds on the prior.
- **Never touch CLAUDE.md.** This is sync, not bootstrap. No sentinel, no MAP.md.
- **Always verify the manifest after regeneration.** The second `compute_manifest.py` run is load-bearing — it proves the spine artifacts now embed the current PRD content.
- **If a stage fails, stop.** Do not run downstream stages against stale upstream output.
