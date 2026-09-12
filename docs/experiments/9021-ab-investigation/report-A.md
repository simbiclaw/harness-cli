# Report — Codebase A (`/home/user/harness-cli`)

Branch `claude/process-derivation-pipeline-docs-nim69g` @ `9057126`. Static reading only.
22 Python files / **3,206 LOC** in `src/argus/`; 34 test files / **6,599 LOC**.

Method note: **no test was executed** — the pinned Tsinghua index (`pyproject.toml:118`) is
unreachable. All runtime behaviour is `UNVERIFIED (could not execute — no network)`.

## Executive summary

**Codebase A does not contain the Argus eval pipeline.** ExecPlan 9002 has 11 milestones,
**all unchecked** (`docs/exec-plans/active/9002-implement-argus-eval-pipeline.md:119-129`).
S3 (ground), S4a (score), S4b (adjust), S5 (route) and the INTENTS Provider are ABSENT.
The two modules CLAUDE.md names by path — `core/grounding.py`, `core/corroboration.py` —
**do not exist**; `src/argus/core/` holds only `divergence.py`, `escape_sampler.py`, `compiler/`.

Of 3,206 LOC in `src/argus/`, **51% is the 9003 rubric compiler** (a *companion*, not Argus),
20% the 9020 proposer/logit stack, and **0% is S3/S4a/S4b/S5**. What runs today:
transcript + dimensions -> per-dimension `proposed_score` — a number that, by I7/D7, may never
be a verdict. `FindingSet.findings` is hardwired empty (`io/local_proposer.py:116`).
The CLI has two commands, `--help` and `version`.

**Enforcement is materially weaker than CLAUDE.md claims.** `.importlinter:16-28` contains
**one layers contract and zero `forbidden` contracts** — it cannot see a third-party import,
so `core X model_client` has no import-linter expression. `.claude/tests/test_layering.py:64`
explicitly `continue`s on every non-`argus` import, so it cannot either. The fence is actually
held by `tests/test_local_proposer.py:187-202`, an AST walk with a **three-name denylist**
(`local_proposer`, `llama_cpp`, `anthropic`) — `openai`, `cohere`, `httpx` all pass.
The other three fences (`grounding X proposer`, `grounding X matching_model`,
`aggregate X model_client`) are **NOT ENFORCED — prose only**, satisfied solely by the absence
of the code they guard.

**I3 is enforced by a grep over a Markdown file** (`tests/test_argus_eval_contract.py:22-58`
searches `fact-checking.md` for the string `score(facts, rubric)`; imports no code).
I2, I4 and I6's load-bearing half are unenforced. The repo's strongest artifact — a real AST
scan of the live tree — enforces **I8**, a tag absent from CLAUDE.md's I1–I7 table
(`tests/test_i8_provenance_separation.py:171-209`).

`INTENTS` is read **nowhere** in `src/`; the root symlink is dangling. No `EPOCH.yaml` reader
exists; `intents_sha` is a string field nothing writes or validates.

## 1. Invariant enforcement — where it actually lives

### 1.1 `.importlinter`, read closely

```
[importlinter:contract:layers]              .importlinter:16
type = layers                               .importlinter:18
layers = cli / core / io / config / types   .importlinter:19-25
exhaustive = false                          .importlinter:28
```

**Catches:** one thing — upward import flow between the five named subpackages.

**Does NOT catch (all pass `lint-imports` clean):**
- **Any third-party import, anywhere.** A layers contract constrains only inter-layer
  `argus.*` edges. `from anthropic import Anthropic` inside `core/grounding.py` is invisible.
  **The `core X model_client` fence has no import-linter expression; a `forbidden` contract is
  the artifact that would do it, and there is none.**
- **`src/argus/hermes/` and `src/argus/providers/`** — not in the layer list, and
  `exhaustive = false` (`:28`) makes unlisted packages a non-error.
  `providers/browser_automation.py:13` imports `argus.hermes.types` ungoverned.
- **Intra-layer coupling.** `core/compiler/signals.py:49` -> `validator.py`; `classify.py:27`
  reaches into validator's **private** `_D16_REF_RE`; `bridge.py:31` -> `agreement.py`.
  All same-layer, all invisible.

### 1.2 `.claude/tests/test_layering.py`, read closely

`test_layer_imports_flow_upward` (`:52-74`) AST-walks and applies the *same* rank comparison
(`LAYER_RANK[tgt_layer] > LAYER_RANK[src_layer]`, `:65`) as import-linter — a backstop for the
same rule, not an additional rule.

- `:64` `if tgt_layer is None: continue` — **every non-`argus.*` import is explicitly skipped.**
  `anthropic`/`llama_cpp` are `tgt_layer is None`. Structurally incapable of catching a model
  client in `core/`.
- `:36` — files outside the five layers (`hermes/`, `providers/`) return `None`, skipped at `:60`.
- `:53-54` `if not SRC.exists(): return` — silent pass on a missing tree.

### 1.3 What *does* catch `core X model_client`

| Artifact | Coverage |
|---|---|
| `tests/test_local_proposer.py:187-202` | AST-walks `src/argus/core/**`, flags imports containing `local_proposer` or rooted at `llama_cpp`/`anthropic` (`:199`). **The real enforcer.** Denylist of three. |
| `tests/test_divergence.py:96-107` | Same idea, **scoped to `core/divergence.py` alone**; forbidden roots `anthropic, llama_cpp, random, time, datetime, secrets` (`:105`) — also bans clock and RNG. |

Both run in the `application-tests` CI job (`.github/workflows/harness.yml:23-31`), so they are CI-gated.

### 1.4 I1–I7 ledger

| Inv. | Enforced by | Verdict |
|---|---|---|
| **I1** Quarantine | `tests/test_local_proposer.py:187-202`; `tests/test_divergence.py:96-107`. **Not** `.importlinter`, **not** `test_layering.py:64`. | **(a) PARTIAL** — real but a 3-name denylist. Holds today mainly because nothing else is built. |
| **I2** Anchor-or-quarantine | **Nothing.** `verify_quote`/`resolve_anchor` specified `9002:71`, M3 unchecked `9002:122`. No `ungrounded` bucket in `src/`. | **(f) NOT ENFORCED — prose only.** |
| **I3** score->adjust purity | `tests/test_argus_eval_contract.py:22-58` — **a string search over `docs/product-specs/argus/fact-checking.md`.** `:30` asserts `score(facts,rubric)` is in the *document*; `:36-47` assert the history variant is not. Imports no code. Only executable echo: `types/proposer_diagnostics.py:97-109`, where `:108` is literally `adjusted = raw` — precedent application is a **no-op**, acknowledged `:102-103`. | **(f) NOT ENFORCED — a doc grep.** |
| **I4** Pinned referents | No `EPOCH.yaml` reader in `src/`. `intents_sha` is a declared field only (`compiler_schemas.py:203`, `proposer_diagnostics.py:61`); nothing populates or validates it. Epoch *format* validated for the calibration manifest only (`io/calibration_io.py:34`, `:78-88`) — a different artifact. | **(f) NOT ENFORCED for INTENTS.** |
| **I5** Replayability | `types/proposer_diagnostics.py:76-94` — `_replay_payload` returns a 3-key dict (`:82-88`) that structurally cannot carry the proposed score. Tested by `tests/test_proposer_diagnostics.py`. | **(e)+(a) ENFORCED — over a provisional object** (`:10-16` "placeholders for 9002's real `FindingGraph`"). |
| **I6** Corroboration weighting | **Aggregator absent** — `core/corroboration.py` specified `9002:77`, M3.5 unchecked `9002:123`. Only *labelling* exists: `classify.py:92-156` assigns independence classes; `agreement.py:41` holds `_W_C = 0.4`; `validator.py:215` rejects `redundant`. **No noisy-OR, no weighted arithmetic, no `defer_reason` anywhere in `src/`.** D4 orthogonality has no code. | **(a) PARTIAL — labelling only.** Load-bearing half NOT ENFORCED. |
| **I7** Ground evidence, not numbers | `tests/test_i8_provenance_separation.py:171-209` AST-scans the **live** `core/` tree: no logit-derived symbol assigned into a disposer sink (`:41-44`), and only `divergence.py`/`escape_sampler.py` may even mention one (`:183`). Red/green samples `:119-168` prove the checker fires. Reinforced by `core/divergence.py:29-41` + `tests/test_divergence.py:79-93` asserting `DriftAssessment` fields are exactly `{demote, calibration_injection, reason}`. | **(a)+(e) GENUINELY ENFORCED** — strongest artifact in the repo. Filed under **I8**, a tag absent from CLAUDE.md's table. |

### 1.5 The four layer fences

| Fence | Verdict |
|---|---|
| `core X model_client` | **(a) PARTIAL** — `tests/test_local_proposer.py:187-202`, 3-name denylist. No `forbidden` contract exists in `.importlinter`. |
| `grounding X proposer` | **NOT ENFORCED — prose only.** `core/grounding.py` does not exist. Vacuously true. |
| `grounding X matching_model` | **NOT ENFORCED — prose only.** Vacuously true. |
| `aggregate X model_client` | **NOT ENFORCED — prose only.** `core/corroboration.py` does not exist. Vacuously true. |

**Three of four fences are satisfied only by the absence of the code they guard.** They become
live, unguarded surfaces the moment S3/S3+ land — no artifact watches a path that would then exist.

### 1.6 Hard prohibitions

| Prohibition | Enforcement |
|---|---|
| No write path into INTENTS (D15, S1 fixture) | **NOT ENFORCED.** S1 fixture specified `9002:53` under M0 — unchecked `9002:119`. No such test file. Vacuously true. |
| No Argus-vs-Argus voting / soft+soft | **(a) PARTIAL** — `validator.py:215` + `classify.py:57` `_REDUNDANT_TYPES = ("soft_text",)`. Catches the schema form only. |
| No per-call residue gate | **(f) prose only.** |
| Resample variance never touches routing | **(a)** — `test_i8_provenance_separation.py:199-202`; `tests/test_divergence.py:86-92`. |
| No precedent in the raw lane (runtime assert) | **NOT ENFORCED.** No `score()` exists; no assert-based purity guard in `src/`. |

### 1.7 What the harness enforces instead

`.claude/tests/` holds **47 structural tests**, CI-gated (`harness.yml:20-21`): `test_pev_*` x13,
`test_commit_*` x3, `test_execplan_structure.py`, `test_promotion_*` x2,
`test_milestone_constraints.py`, `test_decision_log_evidence.py`, `test_no_forbidden_phrases.py`.
**Exactly one (`test_layering.py`) concerns `src/argus/` architecture, and 1.2 shows its limits.**
The harness is instrumented on *process*, not on the seven invariants; the invariant tests live
in `tests/` mixed with the application suite.

Hooks (`.claude/hooks/pre_tool_use.py:369-441`) gate sensitive paths, dep-vet records, force-push.
`.claude/sensitive-paths.txt:7-9` covers `src/argus/io/secrets/**`, `src/argus/config/**`,
`src/argus/cli/main.py` — **not `src/argus/core/**`**. No hook touches invariant enforcement.

## 2. Stage implementation ledger

Scope per `9002:11`: enforced stages S2, S3, S4a, S4b, S5; S0 and S6 are other tiers.

| Stage | Status | Evidence |
|---|---|---|
| **S1** INTENTS read / no-write | **ABSENT** | M0 specified `9002:49-53`, **unchecked** `:119`. No `io/intents_provider.py`. |
| **S2** proposer | **PARTIAL** | `io/local_proposer.py` (225 L): `propose()` batch-shaped `:136-138`; `_propose_one` prefills once `:146-148`, rewinds `n_tokens` per dimension `:160`; `LlamaLogitModel` `:184-225` with lazy import `:193`. Plus `io/logprob_scoring.py:25-65`. **The actual proposing is missing:** `FindingSet.findings` defaults `[]` (`:120`), docstring "M1 returns it empty" (`:114-116`). S2 emits *scores*, never *findings*. `_scale_slice` `:170-181` is a self-declared "placeholder scale" (`:180`). |
| **S3** ground | **ABSENT** | Specified `9002:69-71`. M3 unchecked `:122`. No `core/grounding.py`. |
| **S3+** corroborate | **ABSENT** | Specified `9002:75-77`. M3.5 unchecked `:123`. No `core/corroboration.py`. |
| **S4a** score | **ABSENT** | M4 unchecked `:124`. Stand-in `proposer_diagnostics.py:97-109` — `raw = 1.0 - sum(deductions)`, clamped; "Provisional stand-in" `:100`. |
| **S4b** adjust | **ABSENT** | M4.5 unchecked `:125`. `:108` is `adjusted = raw`. |
| **S5** route | **ABSENT** | M5 unchecked `:126`. No routing module, no `auto_final`, no coverage/health gate. The three `defer_reason` values appear **nowhere in `src/`**. |
| **S5 tail** escape/health | **PARTIAL** | `core/escape_sampler.py` (132 L): `split_tranches` `:87-114` partitions by SHA-256 of `call_id` `:72-75`; `compute_escape_rate` `:117-132` enforces random-tranche-only **by type** (`TypeError` `:123-128`). "9002 M5.5 owns the real one" `:23-24`. `CriterionHealth` absent. M5.5 unchecked `:127`. |
| **S6** epoch commit | **ABSENT (by design)** | Out of scope `9002:11`. Nearest: `io/calibration_io.py:110-150` re-anchors **calibration-manifest** epochs — a different channel (`:10-13`), not INTENTS write-back. |

**Extra built surface:** 9003 compiler in `core/compiler/` — `validator.py` 680 L (`:127-660`),
`signals.py` 838 L, `classify.py` 347 L, `bridge.py` 236 L, `agreement.py` 144 L =
**1,645 LOC, 51% of `src/argus/`** — the *companion* that CLAUDE.md says must land before
M5's gates activate.

**Where the 3,206 lines go:** 9003 compiler 1,645 (51%) / 9020 stack 655 (20%) / types 393 (12%) /
calibration io 189 (6%) / Hermes+providers 79 (2%) / CLI+`__init__`s 57 (2%) /
**eval pipeline S3/S4a/S4b/S5: 0 (0%)**.

## 3. Public interfaces and data contracts

**3.1 `IntentsNode` — DOES NOT EXIST.** Grep returns only comments:
`types/compiler_schemas.py:6, :159, :192, :198`. No `class IntentsNode`. `AuthoredNode` inlines
the base fields instead.

**3.2 `AuthoredNode`** — `types/compiler_schemas.py:191-239`, pydantic.
*Base (`:200-207`):* `node_id: str`, `category: str`, `intents_path: str`, `intents_sha: str`,
`layer: Literal["compliance","judgment"]="judgment"`, `required_evidence: dict={}`,
`fail_condition: dict={}`, `deduction: float=1.0`.
*Required (`:211-212`):* `authored_by: str`, `dimension: str`.
*Optional, all `=None` (`:216-234`):* `human_version`, `machine_criterion`,
`signals: dict[str,list[dict]]`, `facets`, `corroborators: list[dict]`, `gap_rationale`,
`residue_declared`, `agreement: dict`, `proposed_score_hook: bool`,
`source_binary_items: list[str]`, `dimension_ref`, `applicability_gate`, `severity_map: str`,
`data_dependency`, `gap_type`, `escape_tier`, `iteration_policy`.
*Patch-2 (`:238-239`):* `companion_docs: list[dict]`, `depends_on: list[str]`.
CLAUDE.md's v6 claim (judgment fields Optional/`None`) **holds** — verified line by line.

**3.3 `FindingGraph`/`EvaluationResult` — PROVISIONAL STAND-INS.**
`types/proposer_diagnostics.py:10-16` declares them "placeholders ... which are unstarted."
- `ProposedScores` `:26-36`: `scores: dict[str,float]`, `g_used: int`.
- `GroundedFinding` `:39-49`: `dimension: str`, `deduction: float`. **Missing vs. I2:** no span,
  quote, anchor, criterion ref, or `intents_sha` (acknowledged `:43-45`).
- `QuarantinedFindingGraph` `:51-64`: `grounded`, `intents_sha`, `rubric_version`,
  `proposed_scores|None`, `proposer_id|None`.
- `EvaluationResult` `:67-73`: `raw`, `adjusted`, `replay_hash`. **No `defer_reason`,
  no `applied_precedents`, no routing verdict** — though `test_argus_eval_contract.py:52`
  asserts the *document* mentions `applied_precedents`.

**3.4 Contracts and INTENTS.**
- Proposer in: `ProposerCall(call_id, transcript: str, dimensions)` (`local_proposer.py:97-103`)
  — bare `str`, no speaker/time/prosody, no span indices.
- Proposer out: `FindingSet(call_id, proposer_id, sampling_params, dimension_logits, findings=[])`
  (`:106-120`); `findings` always empty.
- Compiler in: `SpecificRubric` `:66-73`, `GenericEvaluatorSkill` `:96-108`, `AlignMap` `:116-123`.
  Out: `AuthoredNode` list + `ResidueManifest` `:276-284`.
- **The only real file reader in `src/argus/`** is `io/calibration_io.py:49-107`,
  `yaml.safe_load(path.read_text())` at `:72`.
- **INTENTS is never read.** Only `intents_sha` field declarations and a docstring
  (`calibration_io.py:122`). No `EPOCH.yaml` reader. Root symlink
  `INTENTS -> /Users/prometheus/workspace/INTENTS` is **dangling**.

## 4. Architecture map — real import graph

```
types/   compiler_schemas.py    pydantic              -> (no argus imports)
         proposer_diagnostics.py hashlib,json :21-22  -> (no argus imports)
config/  EMPTY (__init__.py, 4 lines)
io/      calibration_io.py  copy,re,yaml :24,25,29  -> types.compiler_schemas :31
         local_proposer.py  math :34 [UNUSED]       -> (none); llama_cpp lazy :193
         logprob_scoring.py math :19                -> types.proposer_diagnostics :22
core/    divergence.py      dataclasses             -> (no argus imports at all)
         escape_sampler.py  hashlib :33             -> (no argus imports at all)
         compiler/validator.py functools,re :19-20  -> types.compiler_schemas :22
                  signals.py   re :47               -> compiler.validator :49 (private syms)
                                                    -> types.compiler_schemas :54
                  classify.py  re :25               -> compiler.validator._D16_REF_RE :27
                  agreement.py math :28             -> (no argus imports)
                  bridge.py    math :29             -> compiler.agreement :31
cli/     main.py            typer :10               -> argus.__version__ :28 (lazy)
hermes/  types.py    [OUTSIDE layer model]          -> (no argus imports)
providers/browser_automation.py [OUTSIDE]           -> hermes.types :13 (TYPE_CHECKING)
```

- **The graph is almost entirely disconnected.** No path from `cli` to anything.
  `cli/main.py` registers one command, `version` (`:25-30`); help text is still the template
  placeholder (`:14`).
- **`core/` never imports `io/` and vice versa.** The two 9020 core modules import **nothing
  from argus** — bare dicts and local dataclasses. Pure in the strongest sense, and entirely unwired.
- **`config/` is empty** yet hook-protected (`sensitive-paths.txt:8`). Deferred by design —
  `local_proposer.py:61-63` explains `ProposerConfig` lives in `io/` because "the config-layer
  landing is Tier C (Q3) and deferred."
- **Latent defect:** `local_proposer.py:157` calls `model.scores[...]`, but the `LogitModel`
  Protocol (`:39-55`) declares only `n_vocab, tokenize, reset, eval, n_tokens` — **`scores` is
  not in the protocol.** `LlamaLogitModel` supplies it (`:215-217`); a conforming third-party
  implementation would `AttributeError`. `import math` at `:34` appears unused.

## 5. Assumptions baked into the code

- **Provider: llama.cpp specifically.** `LlamaLogitModel.__init__` `:192-201` hard-requires
  `logits_all=True` ("an M0 finding" `:189`) and mutates `_llm.n_tokens` `:223-225` to rewind the
  KV cache. Breaks on vLLM/TGI/any hosted API. `anthropic>=0.30` is declared
  (`pyproject.toml:19`) but **imported nowhere in `src/`**.
- **Score scale is a placeholder.** `_scale_slice` `:170-181` takes `logits[:g]`, assuming
  position *i* is score-letter *i* (`:180` admits a real deployment must map letter-token vocab
  ids). Fails **silently**: wrong tokens yield a well-formed, meaningless `proposed_score`.
- **Filesystem:** exact filename `calibration-manifest.<epoch>.yaml` (`calibration_io.py:67-71`),
  filename epoch must equal `epoch_id` (`:81-88`), epoch rigidly `YYYY-MM-DD-<40 hex>` (`:34`).
- **Git:** assumed only as the source of a 40-hex string. **No code shells out to git or reads
  `EPOCH.yaml`.** Epoch pinning is convention carried in strings.
- **Two criterion-id conventions:** bare numeric `^\d+$` for `affected_criterion` (`:46`,
  `:101-106`) vs. `C`-prefixed `criterion_id` stripped at `:172-179`.
- **Language:** `signals.py:71-98` hardcodes Chinese ordered patterns and a protected-word list
  (`:98`); `validator.py:28-66` hardcodes ~25 adjectives across simplified/traditional Chinese and
  English; `classify.py:186,188` emit Chinese punctuation and terms. Other languages degrade to
  `model_based`/`correlated` rather than fail.
- **Environment:** `tests/test_local_proposer.py:204-206` skips the real-model test unless
  `/home/user/models/tiny-llama-random.gguf` exists — absolute path.
- **Index:** `pyproject.toml:118` pins the Tsinghua mirror — this is why no test ran here.

## 6. Maturity assessment

**End-to-end? No, and not close.** Three of five links in S2->S3->S4a->S4b->S5 are missing.
To evaluate one transcript you would need: an INTENTS reader (absent), a finding extractor
(`findings` hardwired empty, `local_proposer.py:116`), a grounding gate (absent), a scorer
(absent), an adjuster (absent), a router (absent). What works today: transcript + dimensions ->
per-dimension `proposed_score` (`local_proposer.py:136` -> `logprob_scoring.py:48`) — **a number
that by I7/D7 is explicitly not a verdict.** There is no `argus eval`.

**Coverage by reading:** 34 files / 6,599 LOC. **15 import `argus`; 19 do not** (they grep
Markdown/ADRs/plans). Heavily tested: the 9003 compiler — `test_validator.py` 834 L,
`test_signals.py` 615 L, `test_compiler_schemas.py` 524 L, `test_compiler_pipeline.py` 446 L,
`test_classify.py` 345 L, `test_manifest_channel.py` 317 L, `test_bridge.py` 227 L,
`test_agreement_seed.py` 142 L — genuinely well covered. Moderate: 9020 —
`test_local_proposer.py` 220 L, `test_i8_provenance_separation.py` 209 L,
`test_logprob_capability.py` 144 L, `test_escape_sampler.py` 117 L, `test_divergence.py` 107 L,
`test_proposer_diagnostics.py` 74 L, `test_logprob_scoring.py` 71 L.
**Untested because absent:** grounding, corroboration, score, adjust, route, INTENTS provider,
defer-reason, coverage/health gates.

**Doc-vs-code divergences (stated loudly):**
1. CLAUDE.md names `core/grounding.py` and `core/corroboration.py` as architectural facts.
   **Neither exists.**
2. CLAUDE.md calls the four fences "load-bearing." Three have no enforcing artifact.
3. CLAUDE.md's promotion ladder implies import-linter enforces architecture. `.importlinter` has
   one layers contract and **zero forbidden contracts**.
4. CLAUDE.md's I1–I7 table omits **I8**, the repo's best-enforced invariant.
5. `tests/test_argus_eval_contract.py` is named an eval-contract test but tests a Markdown file.

## 7. What A does NOT have

- **All 11 milestones of 9002 unchecked** (`9002:119-129`), created 2026-07-08, still open.
- Four active plans (`9002`, `9008-audio2tree-rebuild.md`, `9009-doc-garden-2026-08-17.md`,
  `9003-pilot-item18/`). CLAUDE.md's "ask which to pick up if more than one" rule is already tripped.
- Completed: `9003-implement-soft-criteria-compiler.md`,
  `9020-continuous-proposer-and-provenance-separation.md`, `0000-upgrade-spine-to-v6.md`.
  **Every completed application plan is a companion or substrate — none is the eval pipeline.**
- `NotImplementedError` x9, all in `providers/browser_automation.py:21-50` (Hermes scaffold).
- `PROVISIONAL`: `W_C = 0.4` (`agreement.py:41-45`); `classify.py:43`.
- Self-declared provisional pending 9002: `proposer_diagnostics.py:10-16`, `divergence.py:17-21`,
  `escape_sampler.py:23-28`, `local_proposer.py:177-181`.
- Empty: `src/argus/config/`, `core/compiler/__init__.py` (0 bytes).
- Absent entirely: **Metis** (no module anywhere), S0 audio ingest.

## 8. Load-bearing vs. disposable

**Load-bearing — hard-won invariant logic, expensive to re-derive:**
1. `tests/test_i8_provenance_separation.py` (209 L) — `i8_violations` AST checker `:73-114`,
   symbol/sink vocabularies `:33-44`, red/green pairs `:119-168`, live-tree scan with a *reasoned*
   allowlist `:171-209`. This is the invariant machinery.
2. `core/escape_sampler.py:117-132` — **type-enforced** random-tranche-only. Makes bias impossible
   at the type level rather than by convention (`:15-17`); `_partition_key` `:72-75` decorrelating
   via SHA-256 with no RNG.
3. `core/divergence.py:29-41` — `DriftAssessment`'s three-field shape. The invariant is encoded
   *in the absence of fields* (`:35-37`); paired with `tests/test_divergence.py:86-92`.
4. `types/proposer_diagnostics.py:76-94` — `_replay_payload`'s explicit 3-key allowlist; small,
   but the executable form of I5.
5. `core/compiler/validator.py` (680 L) — AUTH-1..10 + patch-2, with orthographic-mutation
   defenses `:68-71`, `:74-84`. ~40 documented adversarial findings baked into branches.
6. `core/compiler/signals.py` (838 L) — Chinese ordered-relation decomposition; header `:24-42`
   enumerates six adversarial fix rounds. Painful to re-derive; also the most brittle thing here.
7. `io/local_proposer.py:140-167` — the KV-cache rewind pattern (`prefix_len` `:148`, restore
   `:160`) and the batch-shaped boundary `:136-138` that makes the serving stack swappable.

**Disposable / scaffolding:**
- `cli/main.py` (34 L) — template stub, placeholder help `:14`.
- `providers/browser_automation.py` (50 L) — nine `NotImplementedError`s.
- `hermes/types.py` (29 L) — three dataclasses + an empty allowlist `:29`.
- `proposer_diagnostics.py:39-109` — stand-ins by their own admission `:10-16`; only
  `_replay_payload`'s discipline survives.
- `divergence.py:87-111` `assess_drift` — "provisional detector" `:90`.
- `local_proposer.py:170-181` `_scale_slice` — placeholder scale.
- `io/calibration_io.py:34-46` regex/filename validation — trivially re-derivable.
- `.claude/tests/test_layering.py` — redundant re-implementation of `.importlinter`'s one contract.
- All 19 non-`import argus` test files — they pin prose, not behavior.

## 9. Uncertainties

- `UNCERTAIN:` whether the suite passes — settled by `uv sync --extra dev && uv run pytest`
  with a reachable index.
- `UNCERTAIN:` whether `FakeLogitModel` supplies `.scores`; if so the Protocol gap
  (`local_proposer.py:39-55` vs `:157`) is latent, not live.
- `UNCERTAIN:` the real INTENTS tree's shape — symlink dangling.
- `UNCERTAIN:` measured coverage vs. `fail_under = 80`.
