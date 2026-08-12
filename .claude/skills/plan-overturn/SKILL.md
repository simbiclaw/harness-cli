---
name: plan-overturn
description: Overturn an ExecPlan completely and replace it with a new plan, preserving history. Use when a plan's execution has failed structurally (acceptance gate never met, wrong baseline, approach proven wrong) and cannot be fixed by patching milestones — the plan must be superseded by a fresh one. Trigger on "overturn", "推翻", "supersede", "complete redesign", "从头再来", or when the human says a plan is dead, has to be redone from scratch, or that its execution was fake/invalid — even if they don't explicitly say "overturn".
---

# Plan Overturn — Replacing an ExecPlan Completely

Use this when a plan must be **completely overturned** — its core assumption or execution baseline proved wrong, and patching milestones won't fix it. This is different from *cancelling* (abandoning with no successor) and different from *amending* (editing the same plan in place). Overturn = the old plan dies and a new plan inherits its domain.

The discipline: **history is immutable, the future is explicit.** Every step below either preserves what already happened or states the replacement in a way a fresh session can read without chat memory. This discipline exists because real overturns have failed this way: a plan was marked done without its acceptance gate ever running, the mistake survived across sessions, and repairing the record took multiple corrections. Each step prevents one specific failure.

## Step 1 — Archive the original plan (preserve history)

Move the plan out of `active/` — or out of `completed/` if it was falsely shipped — into `archived/`. A plan that reaches `completed/` is a trusted "this shipped" record; an overturned plan must not keep that status, but its history must survive. Per `docs/PLANS.md`:

> If cancelled or absorbed, it moves to `docs/exec-plans/archived/` with a final entry in Outcomes & Retrospective explaining why.

```bash
mkdir -p docs/exec-plans/archived
git mv docs/exec-plans/active/NNNN-<slug>.md docs/exec-plans/archived/NNNN-<slug>.md
# or: git mv docs/exec-plans/completed/NNNN-<slug>.md docs/exec-plans/archived/NNNN-<slug>.md
```

Do NOT delete the file, do NOT squash commits, do NOT rewrite what happened. The git history of the plan file is itself the immutability record. Completed checkboxes stay checked — they are recorded history, even if the acceptance they marked is later found invalid. Why: the replacement plan's Decision Log must be able to cite *what was actually decided and marked done*, and a fresh session must not be able to confuse "what we wish had happened" with "what happened."

Note the next free plan number for the replacement: max over `active/`, `completed/`, `archived/` + 1.

## Step 2 — Record the overturn in the original plan (append, never rewrite)

In the archived plan's **Outcomes & Retrospective** section, **append** a final entry. Do not modify any existing content — checkboxes, Decision Log entries, milestones all stay as they were. The archived plan is evidence, not cleanup. The appended entry states what was never validated and what the successor is:

```markdown
## Outcomes & Retrospective

**Status: SUPERSEDED (completely overturned)**

**Original outcome:**

M0–M2 shipped as planned.

**Overturn reason (YYYY-MM-DD):**

The plan's core assumption — that [X] — was proven wrong. Specifically:

- [Symptom 1: what was never actually executed / validated]
- [Symptom 2: what silently no-opped instead of doing its job]

This invalidated the [gate]: [which milestone] was checked off without its
acceptance criteria ever being met. The failure was structural, not a single
bug — the entire approach needs a redesign, not incremental fixes.

Full mistake inventory with root-cause analysis:
`docs/retrospectives/NNNN-execution-mistakes.md`
(if one exists — fetch it from the execution branch if never merged to main:
`git checkout origin/<branch> -- docs/retrospectives/NNNN-execution-mistakes.md`)

**Replacement plan:** NNNN-<new-slug>

**Lessons learned:**

- [Lesson 1: unit tests passing is not end-to-end validation…]
- [Lesson 2: …]
```

Write the whole plan in English (repository convention).

## Step 3 — Create the replacement plan (explicit lineage)

New file at `docs/exec-plans/active/NNNN-<new-slug>.md`. The **Purpose section must open with the lineage statement** — this is what makes the replacement discoverable. A fresh session that sees two plans for the same domain must be able to tell which one wins without reading both. Follow the exact shape below, then continue with the normal `docs/PLANS.md` rubric (Big Picture + File Scope, Milestones with real-data Acceptance Tests, Progress all unchecked, Decision Log, Surprises, Awaiting Steering, Outcomes placeholder):

```markdown
## 1. Purpose

本计划**完全取代并推翻** NNNN（`docs/exec-plans/archived/NNNN-<slug>.md`，已归档）。

**推翻原因：**

原计划的执行方案（[方案描述]）在验收验证中暴露根本缺陷——[S0/S1 从未对真实数据运行、
某阶段是空壳、验收基于 fixture 而非真实数据路径…]。缺陷是结构性的，无法通过局部修正解决，
必须重新设计。

**与旧计划的关键区别：**

| 方面 | 原计划 (NNNN) | 本计划 (NNNN+1) |
|:-----|:--------------|:--------------|
| 输入 | [old] | [new] |
| 核心阶段 | [old behavior] | [new behavior] |
| 验收标准 | [old gate] | [new gate] |
| 代码基线 | [old] | [new] |
```

## Step 4 — Explicit overturn entry in the new plan's Decision Log

The Decision Log **must** contain the overturn decision in this shape — rationale cites evidence, confidence is explicit, consequences are enumerated so a fresh session knows what the overturn actually changed:

```markdown
### Decision: Overturn NNNN and complete redesign

**Rationale:**
- Source: Validation failure in the NNNN [gate] (documented in `docs/exec-plans/archived/NNNN-<slug>.md` Outcomes & Retrospective and `docs/retrospectives/NNNN-execution-mistakes.md`)
- [Evidence: what was never executed / what no-opped / what was misreported]

**Confidence:** high (overturn confirmed by the failed acceptance gate and the revert)

**Consequences:**
- The NNNN execution code on `<branch>` is deprecated and not inherited — scripts and tests are written fresh
- NNNN is archived with its Outcomes recording the overturn; this plan is the sole successor
- Every milestone gates on real-data execution; fixture-only validation is no longer accepted
- [Any other impact: dependencies carried over, design docs that remain valid, etc.]
```

Add any other consequential decisions (code inheritance, dependency carry-over, design-doc validity) as separate entries with `Source:` and `Confidence:` per `docs/conventions/i-dont-know-protocol.md`.

## Step 5 — Commit with trailers

One commit is fine for the whole overturn (archive + append + new plan). Message form per `docs/conventions/commit-hygiene.md`:

```
docs(NNNN): record complete overturn, archive plan, create replacement NNNN

- [one line per artifact: archived plan with overturn reason, retrospective
  fetched from remote if needed, replacement plan with lineage]

Plan: NNNN+1
Decision: overturn-NNNN
```

## Anti-patterns

These mistakes have each cost real overturns multiple rounds. If you recognize any of them, stop and correct before proceeding:

- **Editing the wrong checkout.** The file tools (Read/Write/Edit) and the shell drifted to different directories; edits landed in a stale checkout and had to be re-copied. Before editing, verify `pwd` and the git repo path agree: `git -C <repo> status` must show the same files you just edited. If a directory was renamed mid-session, use absolute paths everywhere and confirm with `git -C`.
- **Marking a milestone done without running the acceptance gate.** Unit tests passing gets reported as "end-to-end pass" when the real input path never ran. The overturn document must state the symptoms explicitly so the replacement plan can't repeat them.
- **Claiming the replacement without a lineage statement.** A new plan that doesn't open with "完全取代并推翻 NNNN" is undiscoverable — a fresh session sees two plans for the same domain and picks the wrong one.
- **Overwriting history when "appending".** `Edit` on the archived plan must target only the Outcomes section; the old checkboxes and Decision Log entries are evidence, not cleanup targets.
- **Not fetching the retrospective.** The mistake inventory often lives on an unmerged execution branch. `git checkout origin/<branch> -- docs/retrospectives/NNNN-execution-mistakes.md` brings it into main so the archived plan can link it.
