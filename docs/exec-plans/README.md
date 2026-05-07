# docs/exec-plans/

ExecPlans, partitioned by lifecycle. See `docs/PLANS.md` for the rubric every plan follows.

- **`active/`** — currently in flight. Read by every new Claude Code session as the first action.
- **`completed/`** — shipped. Kept indefinitely for audit and retrospective reference.
- **`archived/`** — cancelled, superseded, or absorbed into another plan. Final entry in Outcomes & Retrospective explains the move.

Plan files are named `NNNN-<slug>.md`, where `NNNN` is the next free four-digit number across all three lifecycle directories. Numbers are never reused.
