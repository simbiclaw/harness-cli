# 9030 — State Reconciliation: What the Tree Already Holds

## 1. Purpose

Seven plans in `active/` describe work that is already on disk. Their Progress boxes read `[ ]`
because no verification ever flipped them, and their milestone text still says "add", "(new)", and
"build" about modules that exist, tests that pass, and — in at least one case — a change that would
turn a CONFIRMED milestone's fidelity floor red. A fresh agent cannot tell *write this* from *this
exists, verify it*, so it will either duplicate landed work or break a verified one. This plan
produces the record that makes the difference visible, one milestone at a time, before any of the
seven is executed.

## 2. Big Picture

**The single focus is a record, not a repair.** This plan asks one question of each of the 23
milestones: *what does the tree hold today, and what does the milestone ask for?* Where the two
agree, the milestone is ready to verify. Where they differ, the difference is written down with its
evidence and handed to the plan that owns it. **Repairing a difference is not this plan's work** —
that is each owner's, and a repair decided here would be a plan editing another plan's commitments,
which is exactly what the split exists to prevent.

**Explicitly out of scope.** Flipping any checkbox: a flip requires a CONFIRMED verdict from
adversarial verification (`docs/PLANS.md`, "How a session uses an ExecPlan"), and nothing here
verifies anything. Changing what any milestone *requires*: the milestone text is its owner's
commitment, and this plan records divergence from it rather than resolving it. Fixing the structural
suite's pre-existing red state — `test_commit_messages.py` on six 2026-09-12 commits, and the two
`test_quality_score_regrade.py` date checks — which is reported and left standing because the first
needs a decision about published history and the second is the doc-gardener's scheduled regrade.

**Why this is not a symptom-by-symptom patch.** Adversarial verification on 2026-09-14 found the
same defect seven times in seven costumes: 9024 M6 instructs a schema change 9025's own floor
forbids; 9025 M12 names three tests that do not exist beside one that does; 9025 M13 claims a
fixture was "specified and never written" when it landed under commit `1536b7d`; 9029 M20 asserts a
skip its code no longer performs; `(new)` marks files that exist. Each is one symptom of a single
event: implementation landed on 2026-09-13 and no plan text was updated afterwards. Fixing the
symptoms one at a time leaves the next divergence undiscovered; recording the state once, from the
tree, is what closes it.

**File Scope:**
- `docs/exec-plans/active/9030-state-reconciliation.md` (this plan)
- `docs/exec-plans/active/9030-state-reconciliation-notes/**` (new — the per-milestone record, one file per successor plan)

**Deliberately not declared: the seven plan files this record is *about*.** The edits that follow
from R2 land in `9023`–`9029` and in the parent, and they are performed by this plan — but
they cannot be *declared* here, because `.claude/tests/test_plan_collisions.py` intersects declared
paths and 9024 declaring `docs/exec-plans/active/9024-port-and-fences.md` collides with itself the
moment this plan names it. The negotiation is therefore sequencing, not declaration: **R2 edits a
sibling only while that sibling is unowned, and the *deferred, not claimed* block — which the
archived 9022 introduced and `9026-rubric-line` still carries — is the precedent for how the
arrangement is written down.** The same constraint is why this is stated in prose
rather than dodged.

## 3. Milestones

### R1 — The per-milestone fact sheet

For each of the 23 milestones, record four lines: the files the milestone's deliverable and
acceptance tests name; which of those exist on the tree and at which commit; which named acceptance
tests exist and pass; and what the plan's own labels (`(new)`, "(modify)") say. No judgement, no
recommendation — a fact sheet a reader can check against the tree in one command.

`Notes:` `git log --oneline --name-only --since=2026-09-12` and `git log -S` recover the landing
commits; `pytest --collect-only -q` recovers which named tests exist. Cite the command, not only the
result, so the next reader re-derives rather than trusts. The 2026-09-13 implementation commits name
their milestones in the subject — `feat(core)`, `test(i8)`, `flip(m5)` — which is the index.

`Acceptance Test:` `tests/test_reconciliation_record.py::test_every_milestone_has_a_fact_sheet` —
all 23 milestones appear exactly once, each with the four lines and a command that reproduces them.

### R2 — Divergence register

For each milestone whose fact sheet disagrees with its plan text, write the disagreement down:
what the plan says, what the tree holds, the commit that made them differ, and which of three kinds
it is — *stale label* (the plan's `(new)` is wrong, the work stands), *stale premise* (the plan
asserts a fact about the code that is no longer true, as 9029 M20 does), or *unexecutable
instruction* (following the milestone as written breaks something verified, as 9024 M6 would break
M5's floor). The kind decides who fixes it and how, so the classification is the deliverable.

`Acceptance Test:` `tests/test_reconciliation_record.py::test_every_divergence_names_its_owner` —
every registered divergence names its owning plan, its evidence commit, and one of the three kinds.

### R3 — Hand each divergence to its owner

Each entry in the register is written into the owning plan at the site the divergence concerns,
dated, with the fact sheet behind it — for a stale premise, as a correction at the sentence; for an
unexecutable instruction, as a note that names the verified artifact the instruction would break;
for a stale label, at the label. Nothing is deleted: a correction records what the text said and
why it changed, because the *next* reader's question is not "what is true" but "did anyone check".

`Acceptance Test:` `tests/test_reconciliation_record.py::test_no_divergence_is_recorded_in_its_own_plan_only`
— every register entry has its counterpart in the owning plan, matched by the divergence id.

## 4. Progress

- [ ] R1: The per-milestone fact sheet  (created 2026-09-14)
- [ ] R2: Divergence register  (created 2026-09-14)
- [ ] R3: Hand each divergence to its owner  (created 2026-09-14)

## 5. Decision Log

### Decision: The reconciliation is its own plan rather than a repair inside the seven

**Rationale:** `Source:` the human's ruling of 2026-09-14 — *"开一个对账计划"* — taken after
round-3 adversarial verification returned REJECTED with the same defect in seven costumes. The
alternative was to patch each symptom where it stands; the reason not to is that the symptoms share
one cause (implementation landing on 2026-09-13 without a plan-text update), and patching seven
symptoms leaves the eighth undiscovered. `docs/PLANS.md` "Not write-once" allows editing a plan
whose scope turned out wrong — that is what R3 does to each sibling, one dated correction at a
time — and this plan is what makes those edits answerable to a record instead of to memory.

**Confidence:** high on the split of *record* from *repair*; `Confidence: low` on whether R3's
per-sibling edits stay inside the collision rule as the siblings' own checkboxes start flipping —
`Revisit:` when the first sibling flips a box while this plan is open, which is when two plans will
be touching one file.

## 6. Surprises & Discoveries

**The split carried a stale state faithfully, which made the staleness look authored (2026-09-14).**
The archive's Progress showed `[ ]` for every milestone but M5, so the successors show the same, and
a reader concludes the work is unstarted. It is not: `core/{grounding,replay,route,adjust,corroboration,escape_rate}.py`
and their tests landed on 2026-09-13 under commits whose subjects name the milestones. **Unverified
and unstarted are indistinguishable in a checkbox**, and the rule that keeps boxes unchecked until
CONFIRMED is right — which is why the fix is a record beside the boxes, not a change to them.

**A CONFIRMED milestone's floor can be the reason a later milestone is unexecutable.** 9024 M6 tells
an implementer to add `span`, `quote` and `intents_sha` to `EvidenceItem`; M5's landed
`test_port_matches_the_upstream_contract_exactly` rejects any field upstream does not have, and the
implementation put the anchor in `types/anchored.py` instead — a decision recorded only in a test
docstring. Verifying one milestone can make the next one's instruction wrong, and nothing in the PEV
loop checks the neighbours when a floor lands.

## 7. Awaiting Steering

*None open.* R2 classifies divergences and R3 records them at their sites; neither decides anything
the human has reserved. If R2 finds a divergence whose repair is itself Tier C, it does not resolve
it — it becomes an entry here, and this section is not empty any more.

## 8. Outcomes & Retrospective

*Written at completion or cancellation.*


---

**Status: SUPERSEDED (9021 family overturn, human ruling 2026-09-16 — "no simbi at all").**

Reason and full record: the parent plan's overturn entry in this directory
(`9021-relayer-argus-eval-pipeline.md`, Outcomes & Retrospective — OVERTURN RECORD).
Checkbox history above stands as recorded.

**Disposition of this plan's work:**
This plan reconciled family bookkeeping. Its open items (QUALITY_SCORE regrade staleness, the Tier-1 floor bell on bare `Plan: 9021` trailer commits) die with the family they bookkept; the new plan's Decision Log carries the rulings forward. Nothing here survives as a dependency.
