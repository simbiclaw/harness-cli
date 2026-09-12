# Adversarial verification — synthesis.md, Candidate 3 (RE-LAYER)

**Verdict: CONFIRMED WITH CONDITIONS.** No finding breaks the *choice* of C3 over C1/C2 — its two
load-bearing structural arguments (rubric complementarity; B's `CleanTurn` as an I2 anchor slot)
both survived direct testing against source, one by execution. But the recommendation's **effort
estimate is wrong by roughly a factor of two**, its **effort-based ranking must be withdrawn
entirely**, and **five mechanism claims are falsified** — including the claim that B's aggregator
can be promoted to `core/score.py` with its tests, and the claim that four `forbidden` contracts
repair I1. Section 5's Tier C ledger also under-counts hook-blocked sensitive paths and is written
in a format the harness's own steering test cannot parse.

Method: read both trees; executed B's test suite and a quote round-trip experiment; could not
execute A's suite (E3 confirmed — see F9).

---

## Falsified claims

### F1 — "B's `core/aggregator.py` **is** `score(facts, rubric)`" is false. It is an 8-argument report builder that takes model prose.

Synthesis §1.4 C-c, §2 C3 phase 4, §3 invariant row, §4 fact 1.

`/home/user/sim/core/aggregator.py:17-27`:

```python
def aggregate(self, verdicts, questions, intent, clean_transcript,
              kb_context, summary: str, suggestions: list[str], session) -> QAReport:
```

`summary` and `suggestions` are **model output** — produced by `REPORT_SUMMARY_PROMPT` at
`/home/user/sim/agents/qa_agent.py:124` and passed straight through to
`/home/user/sim/core/aggregator.py:117-118`. The synthesis's own I3 statement requires
`raw = score(facts, rubric)`. Three separate breaks:

1. **There is no `rubric` argument.** The rubric's `weight` reaches the arithmetic pre-stamped onto
   each `Verdict` by `/home/user/sim/core/fact_checker.py:193-196` (`_get_weight` → `RUBRIC_BY_ID`),
   called from `_build_verdict` at `:185` and `_path_c` at `:132`. `is_veto` is stamped at
   `/home/user/sim/core/question_generator.py:110`. Both stamping sites are in the modules the
   synthesis sends to `io/` (phase 3). So under RE-LAYER the deduction weight is applied **inside
   the quarantine**, and `score()` receives no rubric at all. The synthesis's fact_checker split
   (§2: model call + NLI → `io/`, routing table `:29-44` and escalation `:159-165` → `core/route.py`)
   names neither `_get_weight` (`:193-196`) nor `_build_verdict` (`:153-191`).
2. **"Its 4 tests come with it and become I3's first *executable* enforcement" is false.** All four
   tests construct all eight arguments — `/home/user/sim/tests/test_aggregator.py:68-73` passes
   `IntentInference`, `CleanTranscript`, `SessionKBContext`, `"测试总结"`, `["建议1"]`, `Session`.
   Every one breaks on the signature change to `score(facts, rubric)`. They are tests of
   `aggregate`, not of `score`.
3. **B's scoring policy contradicts A's deferral rules.** `/home/user/sim/core/fact_checker.py:185`
   scores `NEI` as **0.5** and `:185` gives it a non-zero weight, so an unverifiable item contributes
   half a point to the shipped number and stays in the denominator. `_path_c`
   (`/home/user/sim/core/fact_checker.py:129-132`) does the same for forced-human-review items.
   A's rules say an ungrounded finding routes to a human and blocks auto-final. The aggregator
   cannot move "nearly wholesale"; its policy needs re-litigating.

**Consequence for the recommendation:** §1.4 C-c's "B wins S4a outright" and §3's "B's already-pure
aggregator converts I3 from a Markdown grep into an executable fence" are both overstated. Phase 4
is a redesign of the S4a boundary, not a file move.

### F2 — "Four `forbidden` contracts convert quarantine from accident to artifact" is incomplete, and collides with A's own layering rule.

Synthesis §2 C3 phase 3, §3 row 1, §4 fact 2.

Two problems, both in source:

1. **`core` is permitted to import `io`.** `docs/conventions/layering.md:41` — "`argus.core` … May
   import from `types/`, `config/`, and `io/`." `.importlinter:21-26` encodes the same order
   (`cli / core / io / config / types`). An import-linter `forbidden` contract reports **indirect**
   import chains by default. So `core.grounding → io.proposer → anthropic` would fail a
   `core ✗ anthropic` contract. To make the fence pass, `core/` must stop importing `io/` entirely
   — a revocation of `layering.md:41` that is itself an edit to a convention doc and to
   `.importlinter`. Set `allow_indirect_imports = True` instead and the contract catches only direct
   imports, i.e. it is the same *kind* of weak check as the 3-name denylist at
   `tests/test_local_proposer.py:187-202` that §1.2.3 rightly criticises. The synthesis does not
   choose, and the choice is load-bearing for its central claim.
2. **`include_external_packages` is missing and un-runnable here.** `.importlinter:14-16` has no
   `include_external_packages` setting. Without it, external packages are not in the grimp graph, so
   a `forbidden_modules = anthropic` contract has nothing to match. `UNCERTAIN:` I could not execute
   this — import-linter is not installed (`pip3 show import-linter` → not found) and the pinned index
   is unreachable (F9). Settled by `uv sync --extra dev && uv run lint-imports` against a reachable
   index. Even granting it, grimp must *resolve* the external package, which means `transformers`
   and `anthropic` must be installed — impossible in this container (F9). **The artifact on which
   the entire I1-repair thesis rests cannot be evaluated in the environment the work happens in.**

### F3 — T4's new-dependency list is wrong on two of four entries.

Synthesis §5 T4: "Additions under C3: `transformers`, `torch` (transitive), `rich`, `pytest-asyncio`."

- `rich>=13.0` is **already** a direct dependency: `pyproject.toml:19`. Dep-vet record exists:
  `docs/decisions/dep-vet-rich.md`.
- `pytest-asyncio>=0.23` is **already** a dev dependency: `pyproject.toml:33`. Record exists:
  `docs/decisions/dep-vet-pytest-asyncio.md`.
- `anthropic>=0.30` already present at `pyproject.toml:17` with `docs/decisions/dep-vet-anthropic.md`.

The only genuinely new top-level dependency is `transformers`. This *helps* C3's case and should be
corrected upward, not smoothed — but it means T4's stated decision is partly fictitious, and an
"Awaiting Steering" item that asks the human to approve something already approved wastes the one
resource the harness is designed to conserve.

### F4 — The 9020 demotion (T6) hands `core/divergence.py` a probe that fails silently. Key *and* unit mismatch.

The task asked whether `core/divergence.py` genuinely consumes what `io/local_proposer.py` produces.
Type-shape: yes. Semantics: no.

- Proposed side: `src/argus/io/local_proposer.py:146-160` keys `dimension_logits` by the strings in
  `ProposerCall.dimensions` (`:102`); `src/argus/io/logprob_scoring.py:49-65` turns those into
  `ProposedScores.scores: dict[str, float]` on the **same keys**, each a value in `[0, k-1]` — an
  index on the ordered letter scale (`logprob_scoring.py:25-46`).
- Derived side under RE-LAYER: `/home/user/sim/core/aggregator.py:33-39` groups by `q.dimension`,
  which `/home/user/sim/models/schemas.py:205` documents as one of
  `流程遵守|态度规范|技能技巧|特殊项|准确性`. The number is `overall` on a **0–100** scale
  (`/home/user/sim/core/aggregator.py:69`).
- `src/argus/core/divergence.py:52-56`: `per_call_divergence` iterates `proposed` and **silently
  skips** any dimension absent from `derived`. Disjoint key vocabularies ⇒ `{}` ⇒
  `window_divergence` ⇒ `divergence_trend([])` → `"flat"` (`:77-78`) → `calibration_injection=False`
  forever. The drift probe reports "stable" by construction.
- If the key vocabularies *are* unified (T12, unresolved Tier C), the probe then computes
  `abs(3.2 − 87.5)` — an ordinal scale index diffed against a percentage — and reports a
  well-formed, meaningless number.

This is the **exact failure mode** the synthesis itself names in §3 row 4 when arguing *against* C2:
"`_scale_slice` … fails silently: wrong tokens yield a well-formed, meaningless `proposed_score`"
(`src/argus/io/local_proposer.py:170-181`, whose docstring at `:178-180` concedes the placeholder).
The synthesis applies that criticism to a rival candidate and not to its own T6 default. T6 as
written does not preserve 9020's deliverable; it parks it somewhere it cannot be observed to be
broken.

### F5 — C9 is assumed away, not resolved, and amending 9002 risks a *new* collision with 9008.

Synthesis T2: "*Default:* amend — C3's phases 5–9 are 9002's M3/M3.5/M4.5/M5/M5.5 essentially
unchanged."

9002's declared File Scope (`docs/exec-plans/active/9002-implement-argus-eval-pipeline.md`, the
`**File Scope:**` block) names 22 paths. It names **`src/argus/io/proposer.py`**, and none of:

- the ~11 new `src/argus/io/*` modules B contributes (asr_preprocessor, preprocessor, atomizer,
  intent_inferrer, question_generator, kb_context_builder, intent_retriever, llm_client, nli,
  prompts, qa_agent);
- `src/argus/types/proposer_diagnostics.py` (deleted under T11);
- `src/argus/cli/main.py` (rewritten under T7; also `.claude/sensitive-paths.txt:8`);
- `pyproject.toml`, `.importlinter`, `docs/decisions/dep-vet-transformers.md`.

Phases 5–9 map onto 9002 cleanly. **Phases 1–4 — the entire integration — map onto nothing in it.**
Amending the File Scope to cover them roughly doubles it, which is a plan rewrite, not an amendment.

Worse: `.claude/tests/test_plan_collisions.py:56-84` (`_paths_overlap`) does **pure pattern
intersection with no read/write distinction**, and `:126-138` checks every active pair. 9008 declares
`INTENTS/**` (modify). If the amended 9002 declares any INTENTS path — which phase 6
(`io/intents_provider.py` + `EPOCH.yaml` reader, T15) plausibly requires — the structural test fails
and both plans block. The synthesis does not name this.

### F6 — Section 5's Tier C ledger is invisible to the harness, and under-counts hook-blocked paths by five.

**Format.** `.claude/tests/test_steering_deadlines.py:44-48` parses Awaiting Steering entries with
`STEERING_Q_RE = r"\*\*Q\d+:\s*(.+?)\*\*\s*—\s*Deadline:\s*(\d{4}-\d{2}-\d{2})\.?\s*(.+?)"` inside a
`## <n>. Awaiting Steering` section (`:41-43`). Synthesis §5 uses `**T1 — …**` with **no deadlines**.
Transcribed as written, the regex matches zero entries: the test passes green while all 23 Tier C
items go unregistered. CLAUDE.md's own rule ("the question, the options, and a
default-if-not-decided **deadline**") is not met by any of the 23.

**Under-count.** `.claude/hooks/pre_tool_use.py:68-77` blocks an edit to any path in
`.claude/sensitive-paths.txt` unless an active plan contains the literal string
`"Awaiting Steering: resolved"` *and* the path. `.claude/sensitive-paths.txt` lists, beyond the
`src/argus/config/**` the synthesis names at T9:

- `:11` `pyproject.toml` — required by T4/T5 (add transformers, drop none of A's).
  Independently Tier C per `docs/conventions/ask-threshold.md:30`: "Any change to `pyproject.toml`
  outside of `[dependency-groups]`" — and A has no `[dependency-groups]` table.
- `:12` `.importlinter` — **required by phase 3, the milestone on which the whole I1 thesis rests.**
- `:16` `.claude/tests/**` — required by T20 (promotion).
- `:18` `.github/workflows/**` — required to run B's suite in CI.
- `:21` `CLAUDE.md` — its "Argus eval pipeline" section names `core/grounding.py` and
  `core/corroboration.py` as facts and would need rewriting.

Five additional hook-blocked, Tier-C-automatic paths, none flagged.

### F7 — The 9003 compiler's one shipped output contains a polarity-blind FAIL signal, and §1.3's own field mapping would propagate it to six of B's items.

The synthesis treats the compiler as the thing that *upgrades* B's rubric (§3, domain-asset row:
"Rubric is *upgraded* by passing through the 9003 compiler"). Its single compiled artifact says
otherwise.

`docs/exec-plans/active/9003-pilot-item18/specific-rubric.yaml` gives
`values.named_phrases: ["客服系统", "业务手册", "思路混乱", "引导延期"]`. Two of those
(`客服系统`, `业务手册`) appear in the item's **pass_standard** — "善于使用资源（例如客服系统、业务手册等）".

`src/argus/core/compiler/signals.py:353-361` appends them, unconditionally and without polarity
check, as a single **fail** signal at `severity="high"`:

```python
if named_phrases:
    fail.append(make_signal(
        "transcript contains one of the named phrases: " + "、".join(named_phrases),
        True, severity="high"))
```

The result is in the shipped node: `refined-item-18.json` → `signals.fail[0]` id `18-S01`,
`"checkable": true`, `"audit_result": "pass"`. A transcript in which the agent correctly consults
the 客服系统 activates a high-severity FAIL on the item that rewards consulting it.

This compounds with §1.3's mapping table, which maps B's `trigger_keywords` → A's
`values.named_phrases` "(partial)". Those are **not the same field**. In B, `trigger_keywords` is an
*applicability gate* — `/home/user/sim/core/kb_context_builder.py:107-114`: a rubric whose keywords
miss is marked NA and leaves the denominator — plus an evidence filter
(`/home/user/sim/core/question_generator.py:63-77`). Only 6 of 27 items have any
(`grep -c "trigger_keywords=" config/rubric_items.py` → 6). Feed them in as `named_phrases` at
phase 7 and item 22's `["投诉","不满","怎么这样","算了"]` compiles into a high-severity fail signal
on the empathy item, i.e. a customer saying 投诉 fails the agent. In A's design this field belongs
in `AuthoredNode.applicability_gate` — which is exactly T17's subject, and T17 never connects to the
§1.3 mapping.

### F8 — Minor citation errors that propagate.

- `pyproject.toml:118` is cited for the Tsinghua index pin in `report-A.md`, `constraints.md` E3 and
  `synthesis.md` §1.4 C-j. The pin is at **`pyproject.toml:132`**; the file is 138 lines. `:118` is
  pytest config.
- Synthesis §1.1 and §1.3 cite "47 structural tests in `.claude/tests/`". There are **46 files**
  (`ls .claude/tests/*.py | wc -l` → 46) containing **195** test functions. Neither number is 47.
- `src/argus/io/local_proposer.py:116` is cited for "`FindingSet.findings` is hardwired empty"
  (§1.1, §4 fact 3). The field is at **`:120`**; `:116` is inside the docstring.
- §1.1 and §1.2.2 call `core/escape_sampler.py:117-132` a guarantee "at the type level". It is a
  runtime `isinstance` guard (`src/argus/core/escape_sampler.py:123-128`), and
  `pyproject.toml:96-98` sets `ignore_errors = true` for `argus.core.*` under mypy, so no static
  check applies to `core/` at all. The nominal-typing discipline is real; "type level" is not.

---

## Survived claims — what I attacked and could not break

### S1 — Rubric complementarity (§1.3). Attacked hard; it holds, and holds beyond item 18.

- **Item count.** `grep -c "RubricItem("` in `/home/user/sim/config/rubric_items.py` → **27**; ids run
  1…27 consecutively (`config/rubric_items.py:8, 21, …, 335`). A's docstring claim is at
  `src/argus/types/compiler_schemas.py:66-73`, verbatim "27 items". The test citation
  `tests/test_kb_context_builder.py:51` (`assert len(result.all_rubric_items) == 27`) is correct.
- **Item 18.** `/home/user/sim/config/rubric_items.py:220-231` vs
  `docs/exec-plans/active/9003-pilot-item18/specific-rubric.yaml`. Same id, same criterion, same
  five failure clauses in the same order (思路混乱 / 不考虑用户立场 / 处理死板 / 不善于使用资源 /
  关联业务判断不足). A's header names the source. Confirmed.
- **I checked other items, as instructed.** Items 20 and 21 are in A independently at
  `docs/retrospectives/item-20-example-v2.yaml` and `item-21-example-v2.yaml`, both with
  `来源/Inputs: rubric_com_hotline.md :: Item 20/21`. Item 20's text
  ("能准确快速抓住营销机会并加以引导") matches `/home/user/sim/config/rubric_items.py:247` exactly.
  Item 21 ("积极、灵活营销") matches `:259`. The NA carve-outs line up too — A's item-20 marketing-NA
  and B's `na_criteria="电话中没有合适营销机会；对方已明显反感；用户主动询问"` (`:252`). **Independent
  transcription of one upstream source is established on four items, not one.**
- **Field mapping.** `/home/user/sim/models/schemas.py:51-63` vs
  `src/argus/types/compiler_schemas.py:38-63`: `id`/`name`/`pass_criteria`/`fail_criteria`/
  `na_criteria` ↔ `id`/`text`/`pass_standard`/`fail_standard`/`na_condition` — exact on five rows.
  The sixth row is falsified (F7). The seventh (`numeric_thresholds` ↔ —) is correctly marked absent.
- **Fidelity.** A's item-18 `fail_standard` does preserve `补充例证：未确认清楚企业问题，查客服系统
  发现过期就直接引导延期` which B's one-line `fail_criteria` drops. §1.3's correction of report-B's
  "irreplaceable" framing is right.

### S2 — The acknowledged soft spot: I2 anchoring via `CleanTurn`. **Settled by execution, in the synthesis's favour — for path A only.**

I ran the round-trip the synthesis asked for.

`/home/user/sim/core/asr_preprocessor.py` performs **no normalisation of turn text**. The only
mutation in all three parser branches is `content.strip()` (`:106`, `:121`, `:135`). `CleanTurn.text`
is annotated "原始文本，不修改" (`/home/user/sim/models/schemas.py:26`) and Step 3 (`:57-65`) copies
it through unchanged. The role-swap bug mutates `role` (`:41-42`), never `text`.

Experiment on `/home/user/sim/data/transcripts/sample.txt` (693 chars, 17 turns):

```
recoverable spans: 17 / 17   ambiguous (multi-occurrence): 0
```

Every `CleanTurn.text` is an exact verbatim substring of the raw transcript; character offsets are
recomputable deterministically. **ASR normalisation does not destroy the mapping. The synthesis's
`UNCERTAIN:` in §1.5 and its second "what would change my mind" bullet both resolve in its favour,
and its main structural argument does not collapse.**

Three qualifications, each real:

1. **Path B evidence is not anchorable at all.** `/home/user/sim/core/fact_checker.py:119-125`
   builds `EvidenceItem(doc_path=kb_context.primary_intent_path, text=r["key_evidence"], …)` — the
   text is **model-authored free prose** from `WIKICHAT_VERIFY_PROMPT`, not a quote from any
   document, and `doc_path` names one node while the text was generated from
   `domain_knowledge_summary[:3000]`, a concatenation over cascade-loaded nodes
   (`/home/user/sim/knowledge/intent_retriever.py:99-103`, `:176-199`). Exact-quote verification
   against `doc_path` will fail for essentially every path-B finding. Path B is the accuracy lane —
   `ClaimType.EXTERNAL_FACT | INTERNAL_POLICY` (`core/fact_checker.py:36-39`) — i.e. the 准确性
   category containing the veto item 27. §2's "B's `EvidenceItem` XOR-provenance as the anchor slot"
   is half true: the `turn_id` arm is a usable slot, the `doc_path` arm is populated with
   unanchorable content.
2. **Path A evidence is a whole turn, not a span**, and it carries no offsets:
   `core/fact_checker.py:70-79` sets `text=txt` where `txt` is `turn.text` entire. A turn is a legal
   contiguous span, so I2 is satisfiable — but "gains `span`" is a real plumbing change.
3. **Timestamps are dropped at Stage 1.** `CleanTurn` has `timestamp_start`/`timestamp_end`
   (`models/schemas.py:29-30`) but `Turn` (`:92-97`) has neither, and
   `/home/user/sim/core/preprocessor.py:10-16` copies only `id/role/text/reliability/flags`.
   `fact_checker` is handed `session`, not `clean_transcript`
   (`/home/user/sim/agents/qa_agent.py`), so time anchoring requires re-plumbing Stage 1. Phase 2 is
   larger than "`EvidenceItem` gains span/quote/`intents_sha`".

### S3 — B's aggregator imports nothing impure (the narrow I1 question). Holds, with one caveat.

Transitive closure of `/home/user/sim/core/aggregator.py:2-7`: `models.schemas` →
{pydantic, typing, enum, uuid}; `config.rubric_items` → `models.schemas`. **No LLM client, direct or
transitive.** A `forbidden` contract `core.score ✗ anthropic` would pass on the aggregator itself.
I tried to find a path that drags a client in and could not.

Caveat the synthesis should carry: `models/schemas.py:5` imports `uuid` and `:100` uses
`Field(default_factory=lambda: str(uuid.uuid4())[:8])` for `Session.session_id`, which
`aggregator.py:97` writes into `QAReport.session_id`. That is an RNG in the `types/` layer — not a
model client, so the I1 contract does not see it, but it is a determinism source for any hash over
the record (C3/I5). A's comparable guard bans `random, time, datetime, secrets` in one module only
(`tests/test_divergence.py:105`) and does not list `uuid`.

### S4 — B's three defects are real and reproducible; the role swap is worse than reported.

`python3 -m pytest tests/ --ignore=tests/test_fact_checker.py` in `/home/user/sim`:
`1 failed, 16 passed`. (`tests/test_fact_checker.py` cannot even be collected —
`ModuleNotFoundError: No module named 'transformers'` via `core/fact_checker.py:9` →
`utils/nli.py:2`. So it is 16/16 of what runs, not 16/17.)

report-B left `UNCERTAIN:` which branch causes the false role swap. **Settled.** The fixture's first
turn is `客户: 您好，我在登录时显示CA锁未绑定。` — text length **17** (measured), `< 20`, containing
`您好` ∈ `AGENT_OPENING`. `/home/user/sim/core/asr_preprocessor.py:149-151` therefore returns
`(True, 0.90)` on the rule layer, before the LLM is consulted. This is not a marginal heuristic miss:
**any transcript in which the customer opens with a short greeting inverts every role**, which in
Chinese call-centre audio is the common case. §2's phase 1 and T19 are correctly prioritised; if
anything they are under-stated.

### S5 — A's fences really are three-quarters vacuous; I could not rehabilitate them.

`.importlinter` is 29 lines with exactly one `[importlinter:contract:layers]` block (`:18-29`) and
**zero `forbidden` contracts**. `.claude/tests/test_layering.py:64` does `continue` on every
non-`argus` import. `tests/test_argus_eval_contract.py:20-58` reads `SPEC.read_text()` and asserts
string membership; it imports no `argus` module. `src/argus/types/proposer_diagnostics.py:108` is
literally `adjusted = raw`. §1.2.3 and §1.2.4 survive verbatim.

---

## New risks the synthesis did not name

**R1 — A's dimension taxonomy is internally inconsistent, so T12 is worse than a 4-vs-5 choice.**
§1.4 C-b and T12 treat A as having four dimensions. A actually carries **three** competing
vocabularies simultaneously:
- English four, in the pilot: `docs/exec-plans/active/9003-pilot-item18/generic-skill.yaml`
  (Procedural Accuracy / Empathy & Tone / Problem Resolution / Proactive Value), echoed in
  `refined-item-18.json` → `"dimension": "Problem Resolution"` and in its
  `intents_path: "/_rubric/rules_criteria/Problem Resolution/item-18.yaml"`.
- Chinese, in the compiled retrospectives: `docs/retrospectives/item-18-example-v2.yaml:49-52`
  → `dimension: name: "问题理解与解决", weight: 3, deduction_weight: 0.12`;
  `docs/retrospectives/item-20-example-v2.yaml:97-99` and `item-21-example-v2.yaml:22-24`
  → `"业务引导"`, `weight: 1`, `deduction_weight: 1.0`.
- B's five categories: `/home/user/sim/models/schemas.py:44-49`.

Note the **deduction weights disagree too** — 0.12 vs 1.0 on artifacts from the same compiler.
Because the dimension string is embedded in the `intents_path` (an on-disk format), T12 does not
have a safe default; option (a) "add a fifth dimension" leaves the Chinese-vs-English and the
0.12-vs-1.0 splits unresolved.

**R2 — B's `models/schemas.py` lands in the one layer A type-checks strictly.**
`pyproject.toml:93-98` sets `ignore_errors = true` for `argus.core.*`, `argus.io.*`, `argus.cli.*`
under `strict = true` — so the 1,644 lines moving into `io/` face no mypy at all, and
`[tool.ruff.lint.per-file-ignores]` at `:78-79` already disables `ANN` there. Good news for the
estimate. But `argus.types.*` has **no** `ignore_errors` override and its ruff ignore list
(`pyproject.toml:77`) is only `["RUF003","RUF001","UP042","S105"]` — it does **not** disable `UP`
(pyupgrade). B's schemas use `Optional[str]`, `List[...]`, `Dict[str, Any]` throughout
(`/home/user/sim/models/schemas.py:3` and passim), all of which UP006/UP007 will flag, under
`mypy --strict`. Phase 2 is a 273-line rewrite, not a port.

**R3 — CI cost and CI feasibility.** `.github/workflows/harness.yml` runs `uv sync --extra dev` in
six jobs (`:19, :29, :39, :49, :58`). Adding `transformers` pulls `torch` (~2–3 GB) into every one.
And `/home/user/sim/utils/nli.py:20` hardcodes `device=0`, so `FactChecker.__init__`
(`/home/user/sim/core/fact_checker.py:19`) fails on any CPU runner — T18's default fixes the device
but the model itself is fetched by Hub name with no revision pin
(`/home/user/sim/config/settings.py:9`), ~1.6 GB per job.

**R4 — The dead path C is not a two-line fix.** §1.1 and phase 1 treat
`/home/user/sim/core/fact_checker.py:33` as a precedence bug. The `hasattr` guard is dead because
`Subquestion` (`/home/user/sim/models/schemas.py:194-208`) genuinely has **no** `reliability` field.
Repairing it requires adding the field, propagating it from atom → question in
`core/question_generator.py` (three separate generation paths at `:38`, `:94`, `:157`), and adding
tests — a milestone, not a line.

**R5 — B's fan-out has no `return_exceptions`.** `core/fact_checker.py:44`,
`core/question_generator.py:38,94,157`, `core/atomizer.py:35` all use bare `asyncio.gather`. One
malformed model reply among ~27 rubric questions aborts the whole evaluation, and seven call sites
parse JSON unguarded. Under I2 ("findings are never silently dropped") a stage that aborts wholesale
is arguably worse than one that drops findings; this needs a decision and is not in §5.

---

## Corrections to the effort estimate

The synthesis says **~9–10 milestones**, and §3 uses that to rank C3 above C1 (~14) and C2 (~14).
My count, applying C8 (failing test first, runnable Acceptance Test per milestone, independent
adversarial CONFIRMED):

| Phase | Synthesis | Mine | Why |
|---|---|---|---|
| 1 — stabilise B | ~1 | **4** | (a) `kb_builder` + duplicated prompt; (b) role-swap heuristic + confidence floor (T19, behavioural, Tier C); (c) path C, which needs a new schema field and propagation through three generator paths (R4); (d) the first E2E test — B has zero integration tests and `transformers` is not installable (F9), so this needs a fake LLM covering 14 call sites *and* a stub NLI. |
| 2 — contracts into `types/` | 1 | **2** | 273-line rewrite under `mypy --strict` + `UP` (R2); `EvidenceItem` span/quote/`intents_sha`; re-plumbing timestamps through Stage 1 (S2 qualification 3). |
| 3 — move to `io/` + forbidden contracts | 1 | **3** | 11 modules re-namespaced; `.importlinter` edit is hook-blocked (F6) and its semantics are unsettled (F2); `pyproject.toml` edit hook-blocked and Tier C (F6); dep-vet `transformers`. |
| 4 — aggregator → `core/score.py` | 1 | **2** | Not a move (F1): redesign the `score(facts, rubric)` boundary, relocate `_get_weight`/`is_veto` out of the quarantine, re-litigate NEI=0.5, rewrite all four tests. |
| 5–9 — S3, intents provider, compile, S3⁺/S4b/S5, replay | 5 | **6–8** | 9002 budgets its own M0/M3/M3.5/M4.5/M5/M5.5 at six. Phase 7 ("run B's 27 items through A's 9003 compiler") is one bullet for a compiler exercised on **one** item whose sole output carries a demonstrable defect (F7), driven by a Planner/Generator/Evaluator loop per the `rubric-compiler` skill. Two to four milestones on its own. |
| Not costed at all | 0 | **2–3** | 9002 File Scope amendment + collision renegotiation with 9008 (F5); CLI surface (T7, sensitive path); config schema (T9, sensitive path); on-disk record format (T10); CI (`.github/workflows/**`, sensitive path). |

**Corrected total: 19–22 milestones.** Roughly **2×** the stated figure.

**The consequence is not that C3 loses — it is that the effort axis stops discriminating.** C2 was
costed at 14 by the same document, on the same optimism (it says "every one of B's 14 modules
rewritten from scratch" and prices that at 11 milestones plus 3 ingest). C1's 14 is inflated in the
other direction: only **five** files under `.claude/` reference `src/argus` paths
(`test_plan_collisions.py`, `test_pev_repair.py`, `test_arbiter_autonomy.py`,
`test_pre_execution_gate.py`, `test_layering.py`, plus `.claude/hooks/pre_execution_gate.py`), not 47
tests, so §2 C1's "re-pointing 47 structural tests, hooks and CI" and §3's matching cell are not
evidenced.

**§3's "Total work" row must be withdrawn.** The recommendation should rest on the invariant-integrity
and domain-asset rows, where C3 still wins on the evidence I could verify.

---

## Does any finding make a different candidate correct?

**No — but one comes close, and it is worth stating plainly.** F1 removes most of what C3 was
getting "nearly wholesale" from B at S4a: the aggregator is a report builder, its tests do not
transfer, its scoring policy conflicts with A's deferral rules, and the rubric enters the arithmetic
from inside the quarantine. That is the single largest concrete asset C3 claimed over C2. If the
human weights milestone count heavily, C2 and C3 are now much closer than §3 suggests.

What still separates them, and what I could not break, is S2 and the prompt/routing co-design:
B's 14 model call sites, the 9-type agent taxonomy in `models/prompts.py:81-137` consumed by the
selector at `/home/user/sim/core/question_generator.py:126-133`, and `RUBRIC_TO_QUESTION_PROMPT`'s
prose→NLI-hypothesis-pair bridge. Nothing in A produces a finding at all
(`src/argus/io/local_proposer.py:120`). C2 re-derives all of that with no oracle. That asymmetry is
real and it is what carries the recommendation.

---

## Conditions for the recommendation to be sound

1. **Re-cost the plan at 19–22 milestones and withdraw §3's effort row.** Present the decision on
   invariant integrity and domain-asset preservation, which is where the evidence actually points.
2. **Re-write phase 4.** State that `score(facts, rubric)` is a new pure function extracted from
   `aggregate()`; that `_get_weight` (`/home/user/sim/core/fact_checker.py:193-196`) and `is_veto`
   (`/home/user/sim/core/question_generator.py:110`) must move out of the modules going to `io/`;
   that NEI=0.5-in-denominator is a Tier C policy question; and that the four aggregator tests are
   rewritten, not inherited.
3. **Decide the `core → io` question before phase 3.** Either `core/` stops importing `io/` (and
   `docs/conventions/layering.md:41` is amended — itself Tier C) or the contracts carry
   `allow_indirect_imports = True` and the synthesis's "fact-by-artifact" claim is downgraded.
   Add `include_external_packages = True` to `.importlinter:14-16` and prove `lint-imports` runs
   green *and* red against a planted violation, in an environment where `anthropic` and
   `transformers` are installed. The contracts are not enforcement until that red test exists.
4. **Add the five missing sensitive-path steering entries** (`.importlinter`, `pyproject.toml`,
   `.claude/tests/**`, `.github/workflows/**`, `CLAUDE.md`) and **reformat all Tier C items** to
   `**Q<n>: …** — Deadline: YYYY-MM-DD.` under a `## <n>. Awaiting Steering` heading, or
   `.claude/tests/test_steering_deadlines.py` will register none of them.
5. **Rewrite T6.** Before demoting 9020, unify the dimension key vocabulary (T12) *and* the score
   unit, and add a red test that `per_call_divergence` raises rather than returns `{}` on disjoint
   keys (`src/argus/core/divergence.py:52-56`). Otherwise the demotion silently retires the plan
   rather than repurposing it.
6. **Correct T4** to name `transformers` as the single new top-level dependency.
7. **Fix §1.3's `trigger_keywords` → `named_phrases` row before phase 7**, and fix the
   polarity-blind fail signal at `src/argus/core/compiler/signals.py:353-361`, with item 18 as the
   regression case. Compiling 27 items through a compiler with this defect manufactures 27 wrong
   rubrics faster than a human can review them.
8. **Declare path B unanchorable under I2** and route every path-B finding to the `ungrounded`
   bucket until `WIKICHAT_VERIFY_PROMPT` is changed to return a verbatim span. This is the accuracy
   lane and it contains the veto item; treating model-authored `key_evidence` as an anchor would
   violate C5 on exactly the findings that matter most.
9. **Resolve C9 before opening any milestone:** amend 9002's File Scope to the full ~37-path set and
   check the amended scope against 9008's `INTENTS/**` under
   `.claude/tests/test_plan_collisions.py`.

---

## Residual uncertainty

- `UNCERTAIN:` whether an import-linter `forbidden` contract naming an external package resolves
  without `include_external_packages = True`, and whether it can resolve a package that is not
  installed. Not executable here — import-linter is absent and the index is unreachable. Settled by
  `uv sync --extra dev && uv run lint-imports` against a reachable index, with a planted
  `from anthropic import Anthropic` in a `core/` module as the red case.
- `UNCERTAIN:` whether `find()`-based span recovery stays unambiguous on real transcripts. My
  experiment found 0/17 ambiguous on the only transcript in either repo
  (`/home/user/sim/data/transcripts/sample.txt`), but short turns (`我姓王。`, `嗯`) will collide on
  longer calls. Settled by recording `(start, end)` at parse time in
  `/home/user/sim/core/asr_preprocessor.py:_parse_raw` rather than recovering them later — which is
  the right fix anyway and is one line per branch.
- `UNCERTAIN:` whether A's own suite passes. E3 confirmed by measurement: the pinned index
  (`pyproject.toml:132`) returns HTTP 000 while `https://pypi.org/pypi/transformers/json` returns
  200. So dep-vetting `transformers` is possible here; installing it is not, and no milestone that
  imports it can have a runnable Acceptance Test in this container (C8).
- `UNCERTAIN:` whether A's `_rubric/` subtree and B's L1/L2/L3 business KB cohabit in
  `simbiclaw/INTENTS`. Both symlinks confirmed dangling: `INTENTS -> /Users/prometheus/workspace/INTENTS`,
  `docs/PRD -> ../../papers/PLAN`. The synthesis's §1.5 and T15 are correct to make this blocking.
