# Implementation Notes

Per-milestone structured log that captures deviations, discoveries, and decisions during implementation. Replaces free-text Surprises & Discoveries for mid-build deviation tracking — instead of letting surprises vanish into the scrollback, every deviation from the plan is logged as it happens, so the surprises become inputs to the next Plan iteration.

Structural reference: `docs/references/html-artifacts-template/B1-Implementation notes.html` (visual template showing entry types and devgrid sub-fields).

## File location

One file per milestone, per plan:

```
docs/exec-plans/active/NNNN-notes/M<N>.md
```

Example: `docs/exec-plans/active/9005-notes/M3.md`.

The notes directory sits beside the plan file. When the plan moves to `completed/` or `archived/`, the notes directory moves with it.

## Entry types

Every entry has a type badge, a timestamp, a title, and a body. Four types:

### `plan-confirmed`

What was confirmed about the plan before or during implementation. Step proceeded exactly as planned.

```markdown
### [plan-confirmed] 14:02 — Step 1: export job model and queue wiring, as planned

Added `ExportJob` in `apps/api/src/exports/exportJob.ts`, enqueued on the
existing BullMQ `media-tasks` queue. Migration matches the plan's schema
exactly.
```

### `discovery`

New information surfaced during implementation that does NOT contradict the plan but is worth recording for future readers.

```markdown
### [discovery] 14:29 — `Review.duration_ms` is denormalized and occasionally stale

Three fixture reviews have `duration_ms` that disagrees with the source
asset's probe data. Export reads duration from `MediaAsset.probe.duration`
instead. No plan change, just noting the trap.
```

### `deviation`

Plan assumption contradicted by code reality. The most important entry type — this is what feeds the repair loop. Every deviation has four devgrid sub-fields:

| Field | Description |
|---|---|
| **What the plan said** | Original assumption quoted or paraphrased from the plan |
| **What the code revealed** | Actual state discovered during implementation |
| **Conservative choice** | Decision made given uncertainty — always the conservative option |
| **Revisit** | Milestone, date, or condition under which to reconsider |

```markdown
### [deviation] 14:41 — Legacy annotations don't always have frame timestamps

- **What the plan said:** Every annotation has a `frame_ts`; burn-in renderer
  can sort and place them all on the timeline.
- **What the code revealed:** ~12% of rows in `annotations` predate migration
  `0087` and have `frame_ts = NULL`.
- **Conservative choice:** Exclude null-timestamp annotations from video
  burn-in; include them in CSV sidecar with a `legacy_comment` flag. Nothing
  silently dropped.
- **Revisit:** Could interpolate timestamp from `created_at` offset — decide
  whether that's honest enough to show in video. Revisit at M5.
```

### `human-todo`

Items requiring human judgment. The agent cannot resolve these — they pause the autonomous repair loop until the human decides.

```markdown
### [human-todo] 16:33 — Decide the guest-reviewer export policy

Current behavior (from Deviation 4): guests get `403` on every export format.
If you want guests to export the annotation CSV without media, it's a ~10-line
change in `exportPolicy.ts` — but it changes what "can't download assets"
means to customers, so it should be your call.
```

## How the repair loop consumes notes

On REJECTED verdict from subagent B:

1. The repair loop reads the milestone's notes file.
2. It classifies each unresolved deviation's failure class:
   - `mechanical` — auto-repair (fix test, adjust assertion, retry)
   - `semantic` — add `human-todo` entry, pause milestone for human
   - `constraint-violation` — auto-repair + update milestone constraints
3. `plan-confirmed` and `discovery` entries are informational only — they don't trigger repair.

## Fold back into the plan

At milestone completion (or plan archival), the notes file's deviations and human-todos are summarized into the plan's Outcomes & Retrospective section, under a "What this changes about the next attempt" heading — three lines the next plan or prompt should carry forward so the next run doesn't rediscover today's surprises.

## What this replaces

- **Surprises & Discoveries** still exists in the ExecPlan for cross-milestone surprises and verifier-failure records. Implementation notes handle the per-milestone, mid-build deviation stream.
- Free-text "we hit a snag" narrative is replaced by typed entries with devgrid fields — machine-parseable for the repair loop.

## Enforcement

`.claude/tests/test_implementation_notes.py` validates:
- Notes file exists for milestones with recorded deviations.
- Entries carry valid type badges.
- Deviation entries have all four devgrid fields.

---
Last reviewed: 2026-07-28.
