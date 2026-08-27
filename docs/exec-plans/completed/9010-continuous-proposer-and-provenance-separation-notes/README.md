# 9010 implementation notes

Per-milestone notes live here as `M<N>.md`, per `docs/conventions/implementation-notes.md`.

**This directory is deliberately empty of `M*.md` files while milestones are in flight.**

`.claude/tests/test_pev_checkbox_flip_gate.py::test_unflipped_milestones_should_not_have_confirmed_notes` treats a notes file for an unflipped milestone as stale leftovers from a dead PEV run, and its `VERDICT_BADGES` pattern matches all four entry badges — `plan-confirmed`, `deviation`, `discovery`, and `human-todo` — not only the one its docstring names. So any well-formed notes entry written *during* execution, which is exactly what the convention asks for, fails the gate.

M0's notes were written, hit the gate, and were relocated into the plan's **Surprises & Discoveries** section, where the deviation is recorded in full devgrid form (what the plan said / what the code revealed / conservative choice / revisit). Its human-todo became **Q7** in Awaiting Steering, which is deadline-tracked by `test_steering_deadlines.py` the same way a notes human-todo would be.

Nothing was lost — it moved. Read the plan's sections 6 and 7 for M0.

The contradiction is parked as **Q8** in the plan's Awaiting Steering. Resolving it means editing `.claude/tests/**`, a sensitive path and a Tier C decision, so it was left for the human rather than fixed in passing. Under the promotion rule this counts as the first violation; a second one across a different ExecPlan should move the rule left rather than repeating this workaround.

When a milestone's checkbox flips, its `M<N>.md` is written at that point and carries the verifier's verdict — which is what the flip gate's companion test requires.
