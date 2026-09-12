# Synthesis — A/B integration strategy for Argus

Phase 3. Inputs: `report-A.md` (344 L), `report-B.md` (967 L), `constraints.md` (113 L).
Source consulted only to settle §1.3 (the rubric question) and §1.4 (dimension taxonomy).
No file in either repo was modified.

**Recommendation up front: Candidate 3 — "B becomes A's `io/` layer."** Defended in §4.

---

## Section 1 — The comparison that matters

### 1.1 What each codebase *is*

**A is not an eval pipeline. A is a harness plus a rubric compiler plus a logit instrument.**
`report-A.md §2` is unambiguous: of 3,206 LOC in `src/argus/`, 51% is the 9003 rubric compiler,
20% is the 9020 proposer/logit stack, and **0% is S3/S4a/S4b/S5**. All 11 milestones of 9002 are
unchecked (`docs/exec-plans/active/9002-implement-argus-eval-pipeline.md:119-129`). The two modules
CLAUDE.md names as architectural facts — `core/grounding.py`, `core/corroboration.py` — do not
exist. `FindingSet.findings` is hardwired empty (`src/argus/io/local_proposer.py:116`). There is no
`argus eval` command; `src/argus/cli/main.py` registers `version` and still carries template
placeholder help text (`:14`). The import graph is "almost entirely disconnected"
(`report-A.md §4`): `core/` never imports `io/` and the two 9020 core modules import nothing from
`argus` at all.

What A genuinely *has* is a **process harness** (47 structural tests in `.claude/tests/`, hooks,
CI at `.github/workflows/harness.yml`), a **working 9003 compiler** (1,645 LOC, 8 test files
totalling ~3,450 L, genuinely well covered per `report-A.md §6`), and **two pieces of real
invariant machinery**: `tests/test_i8_provenance_separation.py` (209 L, AST-scans the live tree,
with red/green samples proving the checker fires — `report-A.md §8.1`) and
`src/argus/core/escape_sampler.py:117-132`, which makes tranche bias impossible *at the type level*
(`report-A.md §8.2`).

**B is a complete pipeline shape that has never been executed.** Seven stages, straight-line
async, 3,761 LOC across 33 files, one shallow commit. `report-B.md §8.8` is blunt: "a
well-structured, thoughtfully designed **prototype that has never been run end-to-end**." Two
unconditional crashes sit on the only path — `AttributeError` at `agents/qa_agent.py:66`
(`self.kb_builder` never assigned) and `KeyError: 'grade'` at `:125` (a duplicated
`REPORT_SUMMARY_PROMPT` at `models/prompts.py:332` and `:350`, the second shadowing the first).
Both are two-line fixes; neither is covered by any test, because `agents/qa_agent.py` has zero
coverage.

**I want to correct a framing the task prompt offered.** "B's working engine" overstates it. B is
*runnable after two two-line fixes* — not working. 16 of 17 collected tests pass; the one failure
is a real bug (`report-B.md §7.1`): `_verify_roles` returns `should_swap=True` on a transcript
whose labels are already correct, and `core/asr_preprocessor.py:41-42` then inverts every role, so
every 客服 rubric gets checked against customer utterances. A silent, total inversion of the
verdict. B also has a dead branch at `core/fact_checker.py:33` —
`elif q.reliability == "low" if hasattr(q, "reliability") else False:` — where `Subquestion`
(`models/schemas.py:194-208`) has no `reliability` field, so **path C is unreachable** and the
ASR-reliability signal that `core/atomizer.py:58-64` carefully propagates onto atoms never reaches
a verdict. The uncertainty chain `report-B.md §7.2` praises is broken at its last link.

So neither codebase evaluates a call today. A is 0% of the pipeline with a good harness; B is 100%
of the pipeline shape with zero harness and three defects on the happy path. That symmetry is the
whole decision.

### 1.2 The inconvenient findings, stated before they can be smoothed

Five findings cut against the convenient conclusion (that A, the incumbent, absorbs B). All five
are load-bearing and none is dropped later in this document.

1. **B already satisfies I3 and I7.** `report-B.md §2.3` establishes with quoted code that every
   shipped number is re-derived: verdict score from an enum (`core/fact_checker.py:184-186`),
   weight from the rubric constant table (`:193-196`), dimension roll-up and overall by pure
   arithmetic (`core/aggregator.py:53-56`, `:67-69`), veto zeroing and grade banding pure
   (`:76-79`, `:83-88`). The one model-produced float, `confidence`
   (`core/fact_checker.py:111`), affects **routing only** (`:159-165`) and never multiplies into a
   deduction. Stage 6 deliberately shows the model `overall_score="待计算"`
   (`agents/qa_agent.py:126`) — the author kept the number away from the model on purpose.
   `core/aggregator.py` (118 L) has no LLM import at all and is the one module with 4/4 passing
   semantic coverage.
2. **B already satisfies D15.** `report-B.md §4.3`: `grep` finds `write_text` at exactly two
   places, both writing *reports*. No `open(...,"w")`, no `mkdir` under `kb_root`. The only
   knowledge-layer write is a ChromaDB index into a *sibling* directory — and that index is
   write-only dead code nothing ever queries.
3. **A's fences are three-quarters vacuous.** `report-A.md §1.5`: `grounding ✗ proposer`,
   `grounding ✗ matching_model` and `aggregate ✗ model_client` are "NOT ENFORCED — prose only,"
   satisfied solely by the absence of the code they guard. `.importlinter:16-28` has one layers
   contract and **zero `forbidden` contracts**, so it structurally cannot see a third-party import;
   `.claude/tests/test_layering.py:64` explicitly `continue`s on every non-`argus` import.
   The `core ✗ model_client` fence is actually held by `tests/test_local_proposer.py:187-202`, an
   AST walk with a **three-name denylist** — `openai`, `cohere`, `httpx` all pass.
4. **A's I3 is enforced by a grep over a Markdown file.** `tests/test_argus_eval_contract.py:22-58`
   searches `docs/product-specs/argus/fact-checking.md` for the string `score(facts, rubric)` and
   imports no code. Its only executable echo is `types/proposer_diagnostics.py:108`, which is
   literally `adjusted = raw` — precedent application is a no-op. I2, I4, and I6's load-bearing
   half are unenforced entirely.
5. **B's determinism story is absent, not weak.** `report-B.md §3`: no cache, no seed, no run
   manifest, no input hash, no recorded-fixture replay. Intermediate artefacts (atoms, coverage
   matrix, questions) are discarded; `cli.py:119-122` writes only the final `QAReport`. A report
   cannot be re-derived without re-running all ~40–60 model calls. Nondeterminism is spread across
   **nine of fourteen** non-trivial modules. Plus: `_q_counter`
   (`core/question_generator.py:21-25`) is never reset and `cli.py:127` builds one agent per batch,
   so question IDs leak across transcripts — report *n* gets `RQ-45`, not `RQ-01`.

Held together: **A's invariant advantage is real but much smaller than CLAUDE.md claims, and B's
invariant deficit is real but concentrated in exactly the axes (I2/I4/I5) that are about
*bookkeeping*, not about architecture.** B got the hard architectural invariant (keep the number
away from the model) right by construction. A got the bookkeeping invariants written down but not
built.

### 1.3 The rubric question — SETTLED

The task asks whether A's `AuthoredNode` and B's `config/rubric_items.py` are the same artifact at
different maturity, or different things. I read both. **They are neither. They are the input and
the output of the same compiler, and they were transcribed from the same real upstream source.**

The decisive evidence is item 18. A's pilot input at
`docs/exec-plans/active/9003-pilot-item18/specific-rubric.yaml` reads:

- `id: "18"`, `text: "思路清晰，能根据客户理解程度，灵活的给予合理的处理办法、解释说明和操作指导"`
- `pass_standard: "…适时调整自己的说话方式、指导方法…善于使用资源（例如客服系统、业务手册等）"`
- `fail_standard: "思路混乱、发散或完全无方向…处理或解释死板…不善于使用资源；考虑问题不周，对关联业务判断不足…"`

B's `config/rubric_items.py:220-231` reads:

- `id=18`, `name="思路清晰，能根据客户理解程度灵活给予合理处理办法"`
- `pass_criteria="针对不同用户理解能力适时调整；善于使用资源（客服系统/业务手册）"`
- `fail_criteria="思路混乱；不考虑用户立场；处理死板；不善于使用资源；关联业务判断不足"`

Same id, same criterion, same five failure clauses in the same order. A's header names the source:
`# Pilot: item 18 only — converted from docs/PRD/eval/rubric_com_hotline.md (real rubric).` A also
holds items 20, 21 and a 营销 reconciliation in `docs/retrospectives/item-2*-example-v2.yaml`
(`grep rubric_com_hotline`). **A and B independently transcribed the same internal QA scoring
sheet.**

Now the schema mapping, which is exact:

| A `SpecificRubric.RubricItem` (`src/argus/types/compiler_schemas.py:38-63`) | B `RubricItem` (`/home/user/sim/models/schemas.py:51-63`) |
|---|---|
| `id: str` | `id: int` (1–27) |
| `text` | `name` |
| `pass_standard` | `pass_criteria` |
| `fail_standard` | `fail_criteria` |
| `na_condition` | `na_criteria` |
| `values.named_phrases` | `trigger_keywords` (partial) |
| `values.numeric_thresholds` | — (B leaves `候线≤30秒`, `工单5分钟` inline in prose) |

And A's `SpecificRubric` docstring (`compiler_schemas.py:67-73`) says, verbatim:
*"Human-inspector scored rubric — **27 items** with 1/0/NA judgment (§0.5). The primary compiler
input."* **B has exactly 27 items, ids 1–27** (`report-B.md §6.2`, asserted by
`tests/test_kb_context_builder.py:51`).

The compiler *output* is a different animal. `docs/exec-plans/active/9003-pilot-item18/refined-item-18.json`
is an `AuthoredNode` carrying `node_id: "item-18"`,
`intents_path: "/_rubric/rules_criteria/Problem Resolution/item-18.yaml"`,
`intents_sha: "011c94b91c8cda1aa19009a2054ccbb0ac69f7b5"`, a populated `machine_criterion` (6 keys),
`signals` (2 groups), `facets`, an `agreement` block (5 keys: `tau`, `kappa_sample_plan`,
`escape_sample_plan`, `escape_ceiling`, `current_kappa`), a `gap_rationale`, a `residue_declared`,
`gap_type: "values"` and `escape_tier: "standard"`.

**Verdict.** B's `config/rubric_items.py` is a **27/27 `SpecificRubric` fused with a hand-assigned
judgment layer**. The fields `weight` (2.0 only on ids 6 and 7, `:81`, `:94`), `is_veto` (only id
27, `:345`), `always_check`, `requires_domain_kb` and `category` are *not* SpecificRubric fields —
in A's design they are `AuthoredNode` territory (`deduction`, `severity_map`, `applicability_gate`,
`data_dependency`, `dimension`). **B did by hand, in one Python literal, what A's 9003 compiler is
built to derive with a residue ledger.**

Three consequences, all load-bearing:

- **They are complementary, not redundant.** A has a compiler at 1/27 coverage and no rubric;
  B has the rubric at 27/27 and no compiler. This is the single strongest structural argument for
  merging rather than choosing.
- **B's table structurally cannot satisfy I4 or I5.** It carries no `intents_path` and no
  `intents_sha`. A rubric held as a Python literal has no epoch. Re-running B against "the same
  rubric" is an act of faith about the working tree, not a pinned referent.
- **B's transcription is lossy relative to A's.** A's item-18 `fail_standard` preserves the
  `补充例证` (the 引导延期 counter-example) that B's one-line `fail_criteria` drops. Report-B §7.2
  calls B's table "irreplaceable" and "expensive to rebuild"; that is right about the *27/27
  coverage* and about the machine metadata, and **overstated about fidelity** — A's single compiled
  item is the higher-fidelity transcription of the two. `UNCERTAIN:` whether the upstream
  `docs/PRD/eval/rubric_com_hotline.md` is recoverable — the `docs/PRD` symlink dangles (E1), so
  B's table is the only full transcription available *in these two clones*. Settled by attaching
  the PRD source or asking the human for the original scoring sheet. This matters: if the source is
  recoverable, B's rubric is re-derivable at *higher* fidelity and its "crown jewel" status drops
  a tier.

### 1.4 Every other genuine collision — where one must win

| # | Collision | A's side | B's side | Who must win, and why |
|---|---|---|---|---|
| **C-a** | **Rubric artifact** | `AuthoredNode` (1/27, compiled, epoch-pinned) | `config/rubric_items.py` (27/27, hand-authored, unpinned) | **Both, in sequence.** B's table becomes `SpecificRubric` *input*; A's compiler produces the runtime nodes. B's hand-assigned weight/veto become **calibration input**, not runtime truth. (§1.3) |
| **C-b** | **Dimension taxonomy** | 4 dimensions (`generic-skill.yaml`: Procedural Accuracy, Empathy & Tone, Problem Resolution, Proactive Value) | 5 categories (`RubricCategory`: 流程遵守 / 态度规范 / 技能技巧 / 特殊项 / 准确性) | **Unresolved and load-bearing.** 流程遵守→Procedural, 态度规范→Empathy, 技能技巧 splits (18/19→Problem Resolution, 20/21→Proactive Value). But **A's 4-dimension template has no home for 准确性 (ids 23–27, including the veto id 27) or 特殊项 (id 22).** A's `AlignMap.entries` permits `None` → `dimension_coverage_gap`; that would put B's veto item into a coverage gap. Tier C. |
| **C-c** | **The scorer** | specified `score(facts, rubric)` + `adjust(raw, history)`; **absent**; stand-in `proposer_diagnostics.py:97-109` where `:108` is `adjusted = raw` | `core/aggregator.py` (118 L), pure, 4/4 tests | **B wins S4a outright.** B's aggregator *is* `score(facts, rubric)` and already satisfies I3's purity half. Neither side has S4b — B has no notion of history or precedent at all. |
| **C-d** | **The proposer (S2)** | `io/local_proposer.py` + `io/logprob_scoring.py` (655 L): llama.cpp KV-rewind, emits `proposed_score`, `findings` hardwired `[]` (`:116`) | 14 Anthropic call sites across 9 modules, emitting labels/evidence/questions/atoms | **B wins the verdict path; A wins the drift-probe path.** A's stack produces a number that by I7/D7 may never be a verdict (`report-A.md §0`); B's produces exactly the findings S3 needs. A's 9020 logit stack survives as the **D7 proposed-vs-derived drift probe**, which is its only invariant-legal role. This is a real demotion of a *completed* plan's deliverable (H2) and must be said out loud. |
| **C-e** | **Data contracts** | `types/proposer_diagnostics.py:10-16`, self-declared "placeholders … which are unstarted"; `GroundedFinding` has no span, quote, anchor or criterion ref (`:43-45`) | `models/schemas.py`, 25 real Pydantic models; `EvidenceItem` (`:215-220`) is `turn_id` XOR `doc_path` — provenance designed in; `Subquestion` carries `hypothesis_pos`/`hypothesis_neg` | **B wins**, and it is not close. B's `EvidenceItem` is the anchor slot I2 needs; it must gain `span`/`quote`/`intents_sha`. A's `_replay_payload` 3-key allowlist (`proposer_diagnostics.py:76-94`) is the one piece worth keeping — it is the executable form of I5. |
| **C-f** | **Routing / deferral** | three `defer_reason` values specified; the strings appear **nowhere in `src/`** (`report-A.md §2`) | `core/fact_checker.py:159-165`, a real five-condition escalation (NEI ∨ conf<0.60 ∨ implied ∨ veto ∨ HUMAN_REVIEW) | **B's mechanism wins; A's vocabulary wins.** B's five conditions map onto `finding_thin` and human routing but have **no `ungrounded` and no `criterion_below_tau`** — B has no grounding gate and no κ/τ. Half of A's router must be built regardless. |
| **C-g** | **Chinese domain logic** | `core/compiler/signals.py` (838 L, Chinese ordered-relation decomposition), `validator.py` (~25 adjectives) — **authoring-time lint over rubric prose** | `AGENT_INDICATORS`, `ENTITY_TO_L1` (27 entries), `INCOMPLETE_PATTERNS`, 12 prompts — **runtime processing of transcripts** | **Not a collision.** Different jobs at different times. Both are kept. Worth stating because a feature table would wrongly mark these as duplicates. |
| **C-h** | **INTENTS access** | read **nowhere** in `src/`; no `EPOCH.yaml` reader; root symlink dangling; `intents_sha` a field nothing populates | `knowledge/intent_retriever.py`, read-only filesystem walk + LLM drill-down, `_load_index` at `:201-203` | **B wins by default — it is the only implementation.** But B's drill-down is *LLM-driven path selection* with no depth cap and no visited set (`:152-174`), which makes referent selection nondeterministic and breaks I4 outright. |
| **C-i** | **CLI + report surface** | `cli/main.py` (34 L, typer, `version` only, placeholder help) | `cli.py` (187 L, argparse, 3 modes, `rich` rendering, JSON dump) | **B wins on function, but this is Tier C twice** (CLI surface + stdout format). A's is a stub; there is nothing to defend. |
| **C-j** | **Packaging / layout** | `src/` layout, `pyproject.toml` pinned to an unreachable Tsinghua index (`:118`, E3) | flat layout, **invalid build backend** `setuptools.backends.legacy:build` (`pyproject.toml:3`) — `pip install -e .` cannot work | **A wins.** A's layout is the one `import-linter` and the layering tests are written against. B's packaging is simply broken. |

### 1.5 Where the reports disagree or leave a gap

- **"INTENTS" means two different things and neither report noticed.** For A it is a git-SHA-pinned
  tree with a `_rubric/` subtree of compiled YAML nodes and an `EPOCH.yaml`
  (`refined-item-18.json` → `intents_path: "/_rubric/rules_criteria/Problem Resolution/item-18.yaml"`).
  For B it is an unversioned Markdown directory of business knowledge addressed by path, each node
  optionally holding `index.md` (`config/settings.py:10`, `report-B.md §4.1`). These may be two
  subtrees of one store or two unrelated stores. **The entire I4 story depends on which.**
  `UNCERTAIN:` settled by attaching the private `simbiclaw/INTENTS` repo (E2) and inspecting
  whether `_rubric/` and B's L1/L2/L3 business tree cohabit.
- **Neither report establishes whether B's `EvidenceItem.turn_id` can support exact-quote
  verification.** `turn_id` points at a turn, not a character span. `CleanTurn`
  (`models/schemas.py:23-37`) carries text but the reports do not say whether offsets survive ASR
  normalisation. I2 needs a span. `UNCERTAIN:` settled by reading `CleanTurn` end-to-end and
  attempting a round-trip quote match on `data/transcripts/sample.txt`.
- **Report-B calls `config/rubric_items.py` "the single most valuable file in the repository" and
  "expensive to lose"; report-A never mentions a rubric asset at all** because A's rubric lives in
  `docs/`, not `src/`. Neither report saw the other's copy of item 18. §1.3 closes that gap.
- **No disagreement on facts.** The two reports are consistent everywhere they overlap. The gaps
  are gaps of scope, not conflicts.

---

## Section 2 — Candidate strategies

### Candidate 1 — **TRANSPLANT** (the uncomfortable one): port A's invariants and harness onto B, retire `src/argus/` application code

**Description.** Take seriously that A's pipeline is 0% built and that its `src/` is a compiler
companion plus a llama.cpp-bound proposer whose output can never be a verdict. Declare B the Argus
implementation. Move A's *harness* — `.claude/tests/` (47 structural tests), `.claude/hooks/`,
`.github/workflows/harness.yml`, the ExecPlan spine in `docs/`, `tests/test_i8_provenance_separation.py`,
`core/escape_sampler.py`, `_replay_payload` — onto B's tree. Retire `src/argus/io/local_proposer.py`,
`logprob_scoring.py`, `types/proposer_diagnostics.py`, `cli/main.py`, `hermes/`, `providers/`.
Keep the 9003 compiler as a separate companion package.

**What physically moves.** ~6,600 L of A's tests + hooks + CI + 1,645 L of compiler move *into* B's
repo (or B's 3,761 L move into A's repo as a new top-level package that is not `src/argus/`).
B's flat layout is converted to `src/` and its build backend fixed.

**Kept:** all of B; A's harness; A's I8 checker; A's escape sampler; A's 9003 compiler.
**Rewritten:** B's packaging; B's config into A's `config/` layer.
**Discarded:** A's `io/` proposer stack (655 L), A's `types/proposer_diagnostics.py` stand-ins,
A's CLI stub, A's `hermes/`+`providers/` (79 L) — well over the 100-line Tier C deletion threshold.

**Phases.** (1) Fix B's three defects and add the missing E2E test. (2) Convert B to `src/` layout
and a valid backend. (3) Port the harness and CI. (4) Re-point `import-linter` at the new tree and
write the four `forbidden` contracts A never had. (5) Retire A's `io/` stack under a Tier C
deletion decision. (6) Build I2/I4/I5 bookkeeping onto B.

**Invariant story.** I3/I7/D15 are inherited as-built from B (§1.2). I1 is the problem: B's
nondeterminism is in nine of fourteen modules and none of them is called `io/`. Enforcing I1 means
either a large directory reorganisation or accepting that the quarantine boundary is drawn somewhere
new. I2/I4/I5/I6 are built from scratch either way. This strategy ends with I1 *weaker* than today
unless the reorganisation happens — and if the reorganisation happens, this strategy has converged
onto Candidate 3.

**Effort.** ~14 milestones.

**Strongest argument against.** *It moves the larger, better-tested, invariant-bearing asset into
the smaller, untested, broken-packaging one.* A's harness is ~8,300 L of tests, hooks, CI and
compiler that a structural test suite depends on path-by-path; B is one shallow commit with 17
tests, zero integration tests, and a build backend that does not exist. It also breaks C9 and C10
structurally: 9002's declared File Scope names `src/argus/` modules, and the harness's own
plan-scope collision test is written against that layout. And it discards A's git history and
`docs/` spine, which CLAUDE.md declares **the system of record**. Candidate 1's honest merit is
that it forces the question "is `src/argus/` worth keeping?" — and the answer, examined, is that
its *harness and invariant machinery* are worth keeping while its *application code* mostly is not.
Candidate 3 captures that conclusion without the repo migration.

### Candidate 2 — **ABSORB**: A keeps its architecture; B is mined for data and discarded as code

**Description.** Execute 9002 as written. Extract B's domain assets as *data* into A: the 27-item
rubric becomes `SpecificRubric` YAML fed to the 9003 compiler; `models/prompts.py` becomes prompt
templates under A's `io/`; `ENTITY_TO_L1` and `AGENT_INDICATORS` become data files. B's code is not
imported.

**What physically moves.** Four data assets: `config/rubric_items.py` (353 L) → YAML;
`models/prompts.py` (376 L) → templates; `knowledge/intent_retriever.py:9-36` `ENTITY_TO_L1` (27
entries) → a map file; `core/asr_preprocessor.py`'s `AGENT_INDICATORS` + `INCOMPLETE_PATTERNS` →
heuristics config. **Kept:** all of A. **Rewritten:** every one of B's 14 modules, from scratch, in
A's layering. **Discarded:** B's schemas, aggregator, fact-checker routing, atomiser, retriever, CLI.

**Phases.** (1) Ingest the four data assets (3 milestones). (2) All 11 milestones of 9002.

**Invariant story.** The best on paper: everything lands inside A's layer model, `core/` is pure by
construction, `io/` holds the model. But "on paper" is the operative phrase — A's fences are
prose (§1.2.3) and building the pipeline is exactly what makes three of them live. The invariants
end up enforced only if the promotion work (C11) is done, which is orthogonal to this strategy.

**Effort.** ~14 milestones, and the highest re-derivation risk of the three.

**Strongest argument against.** *It is the maximum-work option dressed as the safe one.* A's
pipeline is 0% built; "A absorbs B" means A still writes S2's finding extraction, S3, S3+, S4a,
S4b and S5 from zero — all 11 milestones — while *also* re-deriving the thing B already has.
Report-B §7.2 shows B's prompt taxonomies and the routing that consumes them were **co-designed**:
`ATOMIZE_AGENT_PROMPT`'s 9-type agent taxonomy exists precisely so
`core/question_generator.py:126-133` can select 政策引用/故障定性/业务判断/事实陈述 for accuracy
checking. Extracting the prompts as "data" and rewriting the consumers reproduces the co-design
problem without the six rounds of iteration that solved it. Worse, it throws away the one thing A
most conspicuously lacks — a finding producer — while `FindingSet.findings` stays `[]`.

### Candidate 3 — **RE-LAYER**: B's model-facing pipeline becomes A's `io/` layer; A's pure stages are built fresh on top; A's application stand-ins are retired

**Description.** The layer boundary A specifies and B ignores turns out to fall almost exactly
where B's module graph already splits. B's stages −1 through 5 are *proposal*: they consume a
transcript and emit labels, atoms, questions, evidence pointers and one routing confidence. B's
stage 6 (`core/aggregator.py`) is *derivation*: pure arithmetic over rubric constants. Move the
first group into `src/argus/io/` verbatim (module-for-module), move the aggregator into
`src/argus/core/score.py`, and build `core/grounding.py`, `core/corroboration.py`, `core/adjust.py`
and `core/route.py` in the gap between them that neither codebase has. **I1 becomes a directory
move rather than a rewrite** — that is the strategy's whole thesis.

**What physically moves.**
- B `agents/`, `core/asr_preprocessor.py`, `core/preprocessor.py`, `core/atomizer.py`,
  `core/intent_inferrer.py`, `core/question_generator.py`, `core/kb_context_builder.py`,
  `knowledge/intent_retriever.py`, `utils/llm_client.py`, `utils/nli.py`, `models/prompts.py`
  → **`src/argus/io/`** (the quarantine). ~1,600 L.
- B `core/fact_checker.py` **splits**: the model call and the NLI call (`:55-68`, `:86-122`) go to
  `io/`; the routing table (`:29-44`) and the escalation rule (`:159-165`) go to `core/route.py`.
- B `core/aggregator.py` → **`src/argus/core/score.py`** — this is `score(facts, rubric)`.
- B `models/schemas.py` → **`src/argus/types/`**, replacing `proposer_diagnostics.py`'s stand-ins;
  `EvidenceItem` gains `span`, `quote`, `intents_sha`.
- B `config/rubric_items.py` → **`docs/`, as `SpecificRubric` YAML**, fed to A's 9003 compiler;
  its `weight`/`is_veto`/`always_check` metadata becomes compiler input and calibration, not runtime
  constants.
- A `io/local_proposer.py` + `logprob_scoring.py` → retained, **demoted to the D7 drift probe**,
  feeding `core/divergence.py` which already exists and already refuses to emit a score.
- **New, in `core/`:** `grounding.py` (exact-quote verify + INTENTS node resolve),
  `corroboration.py` (the independence-weighted aggregator), `adjust.py`, `route.py`,
  `io/intents_provider.py`.

**Kept:** A's harness, 9003 compiler, I8 checker, escape sampler, `_replay_payload`; all of B's
domain assets and all of B's model-facing code.
**Rewritten:** B's `fact_checker` split; B's packaging; `EvidenceItem`.
**Discarded:** A's `types/proposer_diagnostics.py` stand-ins (`:39-109`), A's `cli/main.py` stub,
B's `knowledge/indexer.py` (68 L, write-only dead code), B's `report/report_generator.py` (92 L,
never imported), B's `core/evidence_retriever.py` (0 L), the `openai` and `chromadb` dependencies.
Deletions exceed 100 lines → Tier C.

**Phases.**
1. **Stabilise B in place.** Fix the two blockers, the role-swap false positive, and the dead
   path-C branch. Add the first E2E test (B has none). *This must happen before any move* — moving
   broken code hides the defects in the diff.
2. **Freeze the contracts.** Port B's `models/schemas.py` into `types/`, extend `EvidenceItem`
   with span/quote/`intents_sha`. This is the seam everything else attaches to.
3. **Move the proposal half into `io/`** unchanged, and **write the four `forbidden`
   `import-linter` contracts A never had** in the same milestone. The fences go live at the moment
   the code they guard arrives, not after.
4. **Move the aggregator into `core/score.py`.** Its 4 tests come with it and become I3's first
   *executable* enforcement, replacing the Markdown grep.
5. **Build `core/grounding.py`** — exact-quote verify against `CleanTurn`, resolve the INTENTS node
   at a pinned epoch, `ungrounded` bucket. This is I2, and it is new code in both codebases.
6. **Build `io/intents_provider.py` + `EPOCH.yaml` reader.** I4.
7. **Compile the rubric.** Run B's 27 items through A's 9003 compiler to `_rubric/` AuthoredNodes.
   Until then every soft criterion correctly returns `deferred` (CLAUDE.md's own v6 rule).
8. **Build `core/corroboration.py`** (I6) and **`core/adjust.py` + `core/route.py`** (I3's second
   half, the three `defer_reason` values, the two-axis auto-final gate).
9. **Replay.** Persist the FindingGraph + `intents_sha` + rubric version; `replay_hash` over
   grounded inputs only. I5.

**Invariant story — enforced, not aspired to.**
- **I1**: satisfied by the phase-3 move *and* by four new `forbidden` contracts in `.importlinter`,
  which is the artifact that can actually see a third-party import — closing the gap report-A §1.1
  identifies. The three-name denylist in `tests/test_local_proposer.py:187-202` is superseded, not
  relied on.
- **I2**: `core/grounding.py` + an `ungrounded` bucket, with B's `EvidenceItem` XOR-provenance as
  the anchor slot. New code, but with a designed slot to attach to.
- **I3**: B's aggregator is already pure and already has 4 passing semantic tests; moving it to
  `core/score.py` under the `aggregate ✗ model_client` forbidden contract turns the Markdown grep
  into a real fence. `adjust(raw, history)` is genuinely new — neither codebase has any notion of
  precedent.
- **I4/I5**: new in both. Phases 6 and 9.
- **I6**: `core/corroboration.py` new; but A's `classify.py:92-156` independence labelling and
  `agreement.py:41`'s `W_C` already exist to feed it, and B's local NLI is a genuine
  weight-1.0 independent instrument (constraints, dependency evidence).
- **I7**: inherited as-built from B, and A's `test_i8_provenance_separation.py:171-209` — the
  repo's strongest artifact — re-points at the new `core/` tree and finally has real code to scan
  instead of an almost-empty directory.

**Effort.** ~9–10 milestones. Lower than either alternative because B supplies S2 wholesale and
S4a nearly wholesale; the spend concentrates on S3, S4b, S5 and the I4/I5 bookkeeping, which is
irreducible under any strategy.

**Strongest argument against.** *It imports 1,600 lines of never-executed code into a repo whose
entire value proposition is verification discipline, and calls the result quarantined.* B has no
integration test, zero coverage on `agents/qa_agent.py`, `cli.py`, `question_generator.py` and
`intent_retriever.py`, and three confirmed defects — of which one (the role swap) silently inverts
every verdict and one (the dead path C) silently discards the ASR-reliability signal. Moving code
into `io/` satisfies I1 *as a layering claim* while leaving the imported modules exactly as
unverified as they were; the directory is a quarantine for *nondeterminism*, not for *bugs*. C8
(verification floor) would demand an Acceptance Test per imported module, which is real work this
estimate may under-count. A secondary objection: it demotes the deliverable of 9020, a plan the
human has confirmed COMPLETE (H2), from the proposer to a drift probe — spending a finished asset.

---

## Section 3 — Tradeoffs, head to head

| Axis | C1 Transplant | C2 Absorb | C3 Re-layer |
|---|---|---|---|
| **Invariant integrity** (I1–I7 enforced by artifacts) | I3/I7/D15 inherited; **I1 ends weaker** unless the nine nondeterministic modules are reorganised — and that reorganisation *is* C3. I2/I4/I5/I6 new. Harness survives but its path assumptions break. | Cleanest layer model, but every invariant is enforced only after 11 milestones of new code; A's fences stay prose until then (§1.2.3). Highest *stated* integrity, latest *actual* integrity. | **Best.** Fences go live in the same milestone as the code they guard (phase 3). B's already-pure aggregator converts I3 from a Markdown grep into an executable fence. I8 checker gets a real tree to scan. |
| **Domain-asset preservation** | Total — B is untouched. | **Worst.** B's 14 modules are rewritten; the prompt/routing co-design (`report-B.md §7.2`) is re-derived from extracted "data". Rubric prose survives; the mechanism around it does not. | Total — B's code, prompts, entity map and ASR heuristics move intact. Rubric is *upgraded* by passing through the 9003 compiler rather than frozen as a literal. |
| **Total work** | ~14 milestones, dominated by repo migration and re-pointing 47 structural tests, hooks and CI at a new layout — work that produces no invariant. | ~14 milestones, dominated by re-deriving B. | **~9–10.** Spend concentrates on S3/S4b/S5/I4/I5, which are irreducible. |
| **Risk of silent wrongness** | High and *displaced*: B's role-swap inversion and dead path C travel with the code; the harness that would catch them is being rebuilt at the same time. | **Lowest for imported bugs** (nothing is imported) but **highest for re-derivation bugs** — a rewritten atomiser taxonomy that no longer matches the routing selector fails silently, exactly like A's `_scale_slice` placeholder (`local_proposer.py:170-181`) which "fails silently: wrong tokens yield a well-formed, meaningless `proposed_score`." | Medium, and **localisable**: phase 1 fixes the three known defects *before* the move, so the import is of known-state code. The residual risk is B's untested modules, addressed by C8 per-module Acceptance Tests. |
| **Reversibility** | **Lowest.** Repo migration, discarded history, retired `src/argus/`. Reverting means a second migration. | High — nothing of A is disturbed; the extracted data files are cheap to re-extract. | **High.** Every phase is a file move plus a contract; phases 1–4 are revertible by `git revert`. Phases 5–9 are additive new modules. |
| **What it forecloses** | The 9003 compiler's role in the runtime (it becomes an orphan companion in a repo organised around B's flat layout); A's ExecPlan spine as the system of record. | B's engine, permanently — once rewritten, B is dead code and the rewrite's fidelity is unauditable against it. Also forecloses the cheap path to a first end-to-end run. | Demotes A's 9020 logit proposer to a drift probe (recoverable — `core/divergence.py` is its legitimate consumer). Commits Argus to zh-CN customer-service QA (H1 says that is the target, so this costs nothing today). Commits to Anthropic as the S2 provider. |

Two cross-cutting observations.

**The "safe" option is not the incumbent-preserving one.** C2 preserves A perfectly and is the
*riskiest* on silent wrongness, because re-derivation failures are invisible: there is no oracle
for "did the rewritten atomiser taxonomy still match the routing selector?" C3's risks are named
defects in identified files.

**Every strategy pays the same irreducible bill.** S3 (grounding), S4b (adjust), S5 (route), I4
(epoch pinning) and I5 (replay) exist in *neither* codebase. No strategy avoids building them.
The only thing the strategies differ on is how much *else* they also pay for.

---

## Section 4 — Recommendation

**Candidate 3 — RE-LAYER.** B's model-facing pipeline moves into `src/argus/io/`; B's aggregator
becomes `core/score.py`; A's pure stages are built fresh in the gap; A's harness, 9003 compiler and
invariant machinery are retained and finally pointed at real code; A's `proposer_diagnostics.py`
stand-ins and CLI stub are retired; A's 9020 logit stack is demoted to the D7 drift probe.

**Why, plainly.** Three facts decide it.

1. **The two codebases are complementary at exactly the seam the architecture specifies.** §1.3
   settles it for the rubric: B holds a 27/27 `SpecificRubric`, A holds the compiler that turns one
   into an epoch-pinned `AuthoredNode`. The same complementarity holds for the pipeline: B holds
   S2 and S4a, A holds the harness and the type-level invariant machinery, and *neither* holds S3,
   S4b, S5, I4 or I5. A strategy that chooses one repo over the other is discarding an asset that
   the other cannot supply.
2. **I1 is the only invariant that a merge could plausibly damage, and the merge is precisely the
   operation that repairs it.** B's nondeterminism in nine of fourteen modules is a *layering*
   problem, not a behavioural one — those nine modules are already the proposal half of the
   pipeline and already never touch the arithmetic (`report-B.md §2.3`). Moving them into `io/`
   and writing the four `forbidden` contracts converts a fact-by-accident into a fact-by-artifact.
3. **A's incumbency confers much less than CLAUDE.md implies.** Three of four fences are vacuous,
   I3 is a grep over Markdown, I2/I4 and half of I6 are unenforced, the pipeline is 0% built, and
   `FindingSet.findings` is hardwired empty. The parts of A that are genuinely load-bearing — the
   I8 provenance checker, the type-enforced escape sampler, `_replay_payload`, the 9003 compiler,
   and the 47-test process harness — are all *retained* under C3. Nothing worth keeping is spent.

**The single strongest reason someone would disagree.** *You are importing 1,600 lines of code that
has never successfully executed into the repository whose entire premise is that nothing ships
without adversarial verification.* B's defect profile is not theoretical: a false-positive role swap
that inverts every verdict, a dead branch that silently discards the ASR-reliability signal the
atomiser works to propagate, and zero coverage on the orchestrator, the CLI, the question generator
and the retriever. Placing that code in a directory named `io/` satisfies I1 as a claim about
imports while satisfying nothing about correctness. The objection is correct on its own terms, and
phase 1 is the answer to it — fix and test B *in place, before the move* — but phase 1 is also the
phase most likely to be under-estimated, and if it is skipped the objection becomes fatal.

**What would change my mind.**

- **If the upstream `docs/PRD/eval/rubric_com_hotline.md` is recoverable** and turns out to be a
  structured artifact A's compiler can ingest directly, B's largest irreplaceable asset drops to
  "27 hand-assigned weight/veto/always_check judgments," which is a day of human review, not a
  rebuild. C2 becomes materially more attractive. (§1.3, E1.)
- **If B's `CleanTurn` cannot support exact-quote verification with character offsets** — if ASR
  normalisation destroys the mapping back to the raw transcript — then B's `EvidenceItem` is not
  the I2 anchor slot I am treating it as, the main structural argument for importing B's contracts
  collapses, and C2's clean-room schema looks better.
- **If `simbiclaw/INTENTS` turns out to hold two unrelated trees** — A's `_rubric/` and B's L1/L2/L3
  business KB with no common root or epoch — then C3's phases 6–7 are two separate provider
  implementations rather than one, and the effort estimate is wrong by 2–3 milestones. That would
  not flip the recommendation but would change the phasing.
- **If the human intends Argus to be multi-tenant or multi-language**, C3's commitment to B's
  zh-CN-specific heuristics is a foreclosure rather than a free choice, and C2's data-extraction
  posture is the better bet. H1 currently says the opposite.

---

## Section 5 — Tier C decisions (the "Awaiting Steering" section)

Per constraints C6. Triggers: new top-level dependency, CLI surface change, config schema change,
on-disk format change, stdout format change, >100 line deletion, sensitive-path edit. Each item
below fires at least one.

**T1 — The integration strategy itself.** *Trigger: architecture; all six others downstream.*
Options: C1 Transplant / C2 Absorb / **C3 Re-layer**. *Default if not decided:* none — this must be
answered before any milestone opens. Blocking.

**T2 — 9002: amend or supersede?** *Trigger: C9 — 9002's File Scope names exactly the modules any
integration touches, and a structural test fails when two active plans' scopes intersect.*
Options: (a) amend 9002 in place, keeping its 11 milestones and inserting the import phases;
(b) supersede it via `plan-overturn`, preserving history. *Default:* amend — C3's phases 5–9 are
9002's M3/M3.5/M4.5/M5/M5.5 essentially unchanged.

**T3 — Which of the four active plans is picked up?** *Trigger: C10 + CLAUDE.md's explicit "ask the
human" rule.* Active: 9002, 9003-pilot-item18, 9008-audio2tree-rebuild, 9009-doc-garden.
*Default:* none — CLAUDE.md forbids an agent choosing.

**T4 — New top-level dependencies.** *Trigger: C7; each needs a dep-vet record and a Decision Log
entry.* Additions under C3: `transformers`, `torch` (transitive), `rich`, `pytest-asyncio`.
*Default:* adopt `transformers`+`torch` — the constraints file argues the local NLI path is B's only
weight-1.0 independent instrument under I6, and replacing it with an LLM call collapses
corroboration toward soft⊕soft = 0 (D5). Adopt `rich`/`pytest-asyncio` as low-risk.

**T5 — Dependency removals.** *Trigger: C7 + pyproject edit.* Drop `openai` (zero import sites) and
`chromadb` (one site, write-only dead code, `report-B.md §4.3`). *Default:* drop both — evidence is
unambiguous.

**T6 — Demote or retire A's 9020 logit proposer.** *Trigger: >100 line change to the deliverable of
a COMPLETED plan (H2).* Options: (a) demote `io/local_proposer.py`+`logprob_scoring.py` (655 L) to
the D7 drift probe feeding `core/divergence.py`; (b) retire outright and drop the optional
`llama-cpp-python`; (c) keep as a second proposer behind a flag. *Default:* (a).

**T7 — CLI surface.** *Trigger: explicit C6 item.* A's typer `argus version` stub vs B's argparse
`--transcript / --batch / --build-index`. *Default:* adopt B's three modes under A's typer entry
point, drop `--build-index` (its index is never read).

**T8 — stdout format.** *Trigger: explicit C6 item.* B renders a `rich` console report
(`cli.py:26-100`). *Default:* keep, but add a `--json` mode that is the machine contract.

**T9 — Config schema.** *Trigger: explicit C6 item + `src/argus/config/**` is in
`.claude/sensitive-paths.txt:8`, so the hook blocks the edit without a resolved steering entry.*
A's `config/` is empty and deliberately deferred (`local_proposer.py:61-63` names it Q3);
B's `config/settings.py` is a 20-line dict with three values nothing reads
(`max_tokens`, the two confidence thresholds). *Default:* land a typed `ProposerConfig` +
`RoutingConfig` in `config/`, resolving Q3 in the same decision.

**T10 — On-disk format for the evaluation record.** *Trigger: explicit C6 item.* B writes
`QAReport` JSON only and discards all intermediates, so nothing is replayable
(`report-B.md §3`). I5 requires persisting the FindingGraph + `intents_sha` + rubric version.
Options: extend `QAReport` / add a sidecar run manifest / a content-addressed store.
*Default:* a sidecar run manifest — leaves B's report format intact.

**T11 — Deletions over 100 lines.** *Trigger: explicit C6 item.* Under C3:
`types/proposer_diagnostics.py:39-109` stand-ins; B `report/report_generator.py` (92 L, never
imported); B `knowledge/indexer.py` (68 L, write-only dead code); B `core/evidence_retriever.py`
(0 L); A `cli/main.py` (34 L). Aggregate > 100 L. *Default:* delete all five; keep
`_replay_payload` (`proposer_diagnostics.py:76-94`) as the executable form of I5.

**T12 — Dimension taxonomy: 4 or 5?** *Trigger: on-disk format (`_rubric/` node paths embed the
dimension) + it decides where the veto item lives.* A's `generic-skill.yaml` has four dimensions
and **no home for B's 准确性 (ids 23–27, including the veto id 27) or 特殊项 (id 22)**; A's
`AlignMap` would route them to `dimension_coverage_gap`. Options: (a) add a fifth
"Factual Accuracy" dimension; (b) accept two coverage gaps; (c) re-map 23–27 across the existing
four. *Default:* (a) — routing the veto criterion into a declared coverage gap is not a defensible
starting position. Note this contradicts the "four judgment dimensions" wording in
`compiler_schemas.py:80` and CLAUDE.md's Q1 nine-vs-eight flag; both need reconciling.

**T13 — Rubric authority: hand-assigned or compiled?** *Trigger: on-disk format + it decides what
"the rubric" is at runtime.* B assigns `weight=2.0` (ids 6, 7), `is_veto` (id 27), `always_check`
and `requires_domain_kb` by hand in a Python literal with no `intents_sha`. A's design derives
`deduction`/`severity_map`/`applicability_gate`/`data_dependency` through the 9003 compile loop with
a residue manifest. Options: (a) B's table is `SpecificRubric` input only, all judgment fields
recompiled; (b) B's assignments are frozen as authoritative and the compiler is bypassed for them;
(c) hybrid — compile, then diff against B's assignments and treat divergences as findings.
*Default:* (c) — it preserves the human policy *and* audits it, and produces a useful first
calibration signal. Under (a) or (c), **B's 27 items cannot ship as runtime truth until compiled**;
until then CLAUDE.md's own v6 rule says every soft criterion correctly returns `deferred`.

**T14 — Rubric fidelity.** *Trigger: correctness of the domain asset.* A's item-18 `fail_standard`
preserves `补充例证` that B's one-line `fail_criteria` drops (§1.3); B's id 1 has
`fail_criteria=""`, an empty failure standard fed verbatim into `RUBRIC_TO_QUESTION_PROMPT`
(`report-B.md §8.6`). Question: is the upstream `rubric_com_hotline.md` available, and does B's
27-item transcription get re-verified against it? *Default:* re-verify all 27 against the source
before compiling; if the source is unrecoverable, flag `Confidence: low` on every item and proceed.

**T15 — Attach `simbiclaw/INTENTS`?** *Trigger: E2 — the symlink dangles in every clone; the repo
is private.* Also: **are A's `_rubric/` subtree and B's L1/L2/L3 business KB the same tree?**
(§1.5 — unresolved, load-bearing for I4.) *Default:* attach and inspect before opening phase 6.

**T16 — Is LLM-driven KB path selection permissible under I4?** *Trigger: invariant interpretation.*
B's `_drill_down` (`knowledge/intent_retriever.py:152-174`) picks the INTENTS node by asking the
model, with no depth cap and no visited set. Even with a pinned epoch, referent *selection* is
nondeterministic, so re-running does not reproduce grounding outcomes. Options: (a) record the
selected path in the run manifest and replay it (selection becomes S2 output, grounding verifies
it); (b) replace drill-down with deterministic retrieval; (c) accept and narrow I4 to "the tree is
pinned," not "the path is." *Default:* (a) — it keeps the model in `io/` and makes the path a
grounded, replayable artifact.

**T17 — Is model-decided applicability/NA permitted?** *Trigger: invariant interpretation with a
direct effect on the shipped number.* `report-B.md §2.3` caveat: the model decides `applicability`
(`core/question_generator.py:98`) and NA pre-filtering (`core/kb_context_builder.py:118-127`), and
dropping an item removes it from the denominator (`core/aggregator.py:46-53`). **The model never
writes a number but it moves one.** Options: (a) accept as an S2 proposal that S3 must ground;
(b) move applicability into a pure `applicability_gate` on the AuthoredNode; (c) route every
model-NA'd item to a human. *Default:* (b) — `AuthoredNode.applicability_gate` exists for exactly
this and is currently `null` on the pilot node.

**T18 — NLI model pinning and device.** *Trigger: new dependency + reproducibility + E4 (no GPU).*
`cross-encoder/nli-deberta-v3-large` is fetched by Hub name with **no revision pin**
(`config/settings.py:9`) and `utils/nli.py:20` hardcodes `device=0`, so
`FactChecker.__init__` fails on a CPU-only host. *Default:* pin a revision SHA and make the device
configurable, defaulting to CPU.

**T19 — Fixing the role-swap bug changes evaluation outputs.** *Trigger: behavioural change on the
only path.* `_verify_roles` (`core/asr_preprocessor.py:140-166`) returns `should_swap=True` on a
correctly-labelled transcript and `:41-42` then inverts every role. Options: fix the heuristic /
gate the swap behind a confidence threshold / remove auto-swap and route to a human. *Default:*
fix the heuristic *and* require a confidence floor, because a silent total inversion is exactly the
failure mode the deferred-verdict machinery exists to catch.

**T20 — Which unenforced invariants get promoted now, and does promotion block the merge?**
*Trigger: C11, the promotion rule.* Currently prose-only: I2, I4, I6's load-bearing half, three of
four fences, "no write path into INTENTS" (the S1 fixture specified at `9002:53` was never written),
"no per-call residue gate," and the raw-lane purity assert. Options: (a) promote the four
`forbidden` contracts and the D15 fixture as a gate on phase 3; (b) promote incrementally per
phase; (c) defer promotion to a follow-up plan. *Default:* (a) for the fences and D15 — they are
cheap and they are precisely what stops C3's central risk — (b) for the rest.

**T21 — Repository topology.** *Trigger: >100 line moves + git history.* Options: B's code moves
into `/home/user/harness-cli` as `src/argus/io/**` (one repo, B's single shallow commit is
squashed in with provenance recorded in the Decision Log); or B is vendored as a submodule; or two
repos with a package boundary. *Default:* one repo, single squashed import commit citing
`simbiclaw/sim@0c2cccd`, because C9/C10 and the 47 structural tests all assume one tree.

**T22 — `W_C = 0.4 PROVISIONAL`.** *Trigger: it changes routing outcomes.* Still unmeasured
(`core/compiler/agreement.py:41-45`); the correct value is `1 − corr(matcher_error, proposer_error)`
on a human-labelled sample, which requires labelled data that neither repo has. *Default:* keep 0.4,
keep the debt logged, and open the labelling question as its own steering item — corroboration
gates (`finding_thin`) cannot be trusted until it is measured.

**T23 — Language scope.** *Trigger: forecloses a product direction.* C3 commits Argus to zh-CN
customer-service QA at the code level (B's `AGENT_INDICATORS`, `ENTITY_TO_L1`, 12 Chinese prompts;
A's `signals.py:71-98` and `validator.py:28-66` already hardcode Chinese). H1 says this is the
target domain. *Default:* accept the commitment and state it in the plan, so a future
multi-language requirement is recognised as a rewrite rather than a configuration.

---

*Strategy only. No implementation plan — that is the next phase.*
