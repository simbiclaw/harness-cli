# 9021 — A/B investigation evidence base

The reports that produced ExecPlan 9021. Preserved here because the session that generated them
ran in an ephemeral container, and 9021's Decision Log cites their findings by name.

Read in this order:

| File | What it is | Why you would open it |
|:---|:---|:---|
| `constraints.md` | The hard constraints the decision was made under, plus the dependency evidence | Start here — it is the shortest and frames the rest |
| `report-A.md` | Isolated investigation of `harness-cli` at the 9020 head | The invariant-enforcement ledger: which of I1–I7 are enforced by an artifact and which are prose |
| `report-B.md` | Isolated investigation of `simbiclaw/sim@0c2cccd` | The model-coupling map and the load-bearing/boilerplate split |
| `synthesis.md` | Comparison and three candidate strategies | Why RE-LAYER over Transplant or Absorb; the rubric-complementarity finding |
| `adversarial.md` | A falsification pass against `synthesis.md` | **Read this before trusting synthesis.md** — it falsified five of its mechanism claims |

## Method and its limits

Two investigators analysed one codebase each in isolation, forbidden from reading the other, so
their conclusions could not cross-contaminate. A third compared the reports. A fourth was told to
prove the recommendation wrong. Every load-bearing claim carries a `path:line` citation.

Three limits apply to all five documents:

1. **No test was executed against `harness-cli`.** The pinned index was unreachable, so every
   runtime claim about codebase A is marked `UNVERIFIED (could not execute — no network)`.
   Codebase B's non-`transformers` tests did run and their output is quoted verbatim.
2. **The governing spec was never read.** `docs/PRD` is a dangling symlink in a fresh clone, so all
   four agents worked from CLAUDE.md's operating summary rather than
   `process-derivation-pipeline-spec-v5.html`. A session where that symlink resolves should
   re-check the invariant claims against the spec itself.
3. **`INTENTS/` was never read** — same reason. Whether this repository's `_rubric/` subtree and
   B's L1/L2/L3 business KB are one tree or two is still open (9021 Q7).

## The findings that most affect implementation

- **B's `core/aggregator.py` is not `score(facts, rubric)`.** It is an 8-argument report builder
  that takes model-authored prose and receives no rubric; weight and veto are stamped onto verdicts
  inside modules bound for `io/`. 9021 M10 is a redesign, not a move. (`adversarial.md` F1)
- **Demoting the 9020 proposer to a drift probe fails silently unless keys and units are unified
  first.** Disjoint dimension vocabularies make the probe report "flat" forever.
  (`adversarial.md` F4)
- **Path B evidence cannot be anchored under I2** — its text is model-authored prose, not a quote
  from the cited document, and path B is the accuracy lane containing veto item 27.
  (`adversarial.md` S2)
- **Exact-quote anchoring works for path A.** 17/17 turn texts recovered as exact substrings on the
  sample transcript; the ASR preprocessor mutates turn text only with `.strip()`.
  (`adversarial.md` S2)
- **A and B transcribed the same 27-item rubric** from `docs/PRD/eval/rubric_com_hotline.md`; item
  18 matches clause-for-clause. This is why 9021 merges rather than chooses. (`synthesis.md` §1.3)

`Source: docs/exec-plans/active/9021-relayer-argus-eval-pipeline.md` · `docs/exec-plans/archived/9002-implement-argus-eval-pipeline.md`
