# 0004 — gc-archive-completed-plans-2026-07-20

## 1. Purpose

Garbage-collector scan detected 1 cleanup theme: **2 fully-completed ExecPlans still in `active/`**. No other candidates across 6 scans (see §8 Clean Checks).

## 2. Big Picture

Both plans are documentation-level work with all milestones checked off. Moving them to `completed/` reduces noise in the active directory and aligns with the ExecPlan lifecycle in PLANS.md. Zero `src/` changes.

## 3. Milestones

### M1 — Archive 0000-upgrade-spine-to-v6.md

7/7 checkboxes flipped. Outcome documented in §8. Move to `docs/exec-plans/completed/0000-upgrade-spine-to-v6.md`.

`Acceptance Test:` `docs/exec-plans/active/0000-upgrade-spine-to-v6.md` no longer exists; file is at `docs/exec-plans/completed/0000-upgrade-spine-to-v6.md`.

### M2 — Archive 0002-doc-garden-2026-07-04.md

6/6 checkboxes flipped. Outcome documented in §8. Move to `docs/exec-plans/completed/0002-doc-garden-2026-07-04.md`.

`Acceptance Test:` `docs/exec-plans/active/0002-doc-garden-2026-07-04.md` no longer exists; file is at `docs/exec-plans/completed/0002-doc-garden-2026-07-04.md`.

## 4. Progress

- [x] M1: Archive 0000-upgrade-spine-to-v6.md
- [x] M2: Archive 0002-doc-garden-2026-07-04.md

## 5. Decision Log

### Decision: archive rather than leave in active/

**Rationale:** `Source: docs/PLANS.md` — completed plans belong in `completed/`. Both 0000 and 0002 have all milestones checked off and outcomes documented. Leaving them in `active/` creates false signals (they appear to be in-flight work). Archival is the correct lifecycle transition.

## 6. Surprises & Discoveries

(none — straightforward archival)

## 7. Awaiting Steering

(empty — archival is within gardener conventions; no Tier C decisions.)

## 8. Clean Checks (no action needed)

| Scan | Result |
|---|---|
| Unused modules (`src/argus/`) | Clean — all 3 non-init modules have active imports |
| Unused exports | Not checked (vulture not installed; low-priority for near-empty codebase) |
| Stale TODOs | Clean — zero TODO/FIXME/XXX/HACK in `src/` or `tests/` |
| Dormant active ExecPlans | Clean — all 6 active plans touched within 14 days (2 at 12 days, approaching) |
| Past-deadline Confidence:low | Clean — no date-based Revisit: deadlines in the past |
| Empty/skipped tests | Clean — 13 test files, all have active test functions, zero all-skipped |
| Orphan/bak/tmp files | Clean — no `.bak`, `.tmp`, `.old`, or `~` files outside `.git/` |
