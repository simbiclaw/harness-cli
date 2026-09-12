# Codebase B — `/home/user/sim` (`simbiclaw/sim`) — Investigation Report

Subject: "AI 客服质检系统 v2.0" (AI customer-service QA inspection system), a Chinese-language
call-centre QA evaluator. Single shallow commit `0c2cccd initial`.

Scope note: this report describes only `/home/user/sim`. Description, not prescription.

Environment note: `transformers`, `torch`, `chromadb`, `anthropic` are NOT installed and the network
is restricted. Anything requiring them is marked `UNVERIFIED (could not execute)`. `pytest`,
`pydantic` and `python-dotenv` WERE available, so the non-`transformers` portion of the test suite
was actually executed and its output is quoted verbatim in §7.

Total Python: 3,761 lines across 33 files.

---

## 0. Executive orientation — three headline findings

1. **It cannot run end-to-end today.** Two independent hard crashes sit on the single happy path,
   both confirmed by execution: `AttributeError` at `agents/qa_agent.py:66` (Stage 0) and
   `KeyError: 'grade'` at `agents/qa_agent.py:125` (Stage 6). See §8.
2. **The model never produces the shipped number.** Every score, weight, dimension roll-up and grade
   is computed in pure Python from rubric constants and verdict enums. The one number that does come
   from a model response (`confidence`, `core/fact_checker.py:111`) is used only for evidence
   ranking and human-review routing, never as a deduction. See §2.
3. **There is no write path into any intent store.** Every intent-related module is read-only, or
   writes only to its own derived ChromaDB cache — which nothing ever reads. See §4.

---

## 1. Architecture map

### 1.1 Real dependency graph (built from imports)

```
cli.py
 ├─ agents.qa_agent.QAAgent           cli.py:10
 ├─ config.settings.CONFIG            cli.py:11
 ├─ utils.llm_client.AnthropicClient  cli.py:12
 └─ knowledge.indexer.KBIndexer       cli.py:157   (lazy, only for --build-index)

agents/qa_agent.py
 ├─ models.schemas                        qa_agent.py:4
 ├─ models.prompts.REPORT_SUMMARY_PROMPT  qa_agent.py:5
 ├─ core.asr_preprocessor                 qa_agent.py:6
 ├─ core.preprocessor                     qa_agent.py:7
 ├─ core.atomizer                         qa_agent.py:8
 ├─ core.intent_inferrer                  qa_agent.py:9
 ├─ core.question_generator               qa_agent.py:10
 ├─ core.fact_checker                     qa_agent.py:11
 ├─ core.aggregator                       qa_agent.py:12
 ├─ (knowledge.intent_retriever)          qa_agent.py:13  ← COMMENTED OUT
 ├─ core.kb_context_builder               qa_agent.py:14
 └─ utils.logger                          qa_agent.py:16

core/kb_context_builder.py
 ├─ knowledge.intent_retriever.IntentAwareRetriever  kb_context_builder.py:4
 └─ config.rubric_items.RUBRIC_ITEMS                 kb_context_builder.py:5

core/fact_checker.py
 ├─ utils.nli.NLIModel                fact_checker.py:9   → transformers  (utils/nli.py:2)
 └─ config.rubric_items.RUBRIC_BY_ID  fact_checker.py:10

knowledge/indexer.py → chromadb       indexer.py:2
utils/llm_client.py  → anthropic      llm_client.py:2
```

Notable layering fact: `config/rubric_items.py` imports only `models.schemas`
(`config/rubric_items.py:2`), and `core/aggregator.py` imports only schemas plus rubric constants
(`core/aggregator.py:2-7`). The aggregator has **no** LLM import at all.

### 1.2 Module-by-module

| Module | Lines | What it does |
|---|---|---|
| `cli.py` | 187 | argparse entry; three modes — `--build-index`, `--batch`, `--transcript` (`cli.py:177-184`). Builds the Anthropic client and injects it into `CONFIG` (`cli.py:18-23`). Renders a `rich` report (`cli.py:26-100`), dumps JSON (`cli.py:119-122`). |
| `config/settings.py` | 20 | One `CONFIG` dict: NLI model name, `kb_root`, confidence thresholds 0.85/0.60, Anthropic model `claude-3-5-sonnet-20241022`, `temperature: 0.0` (`config/settings.py:7-21`). |
| `config/rubric_items.py` | 353 | The 27-item QA rubric as `RubricItem` objects + four derived indexes (`:350-354`). **Domain crown jewel** — §7. |
| `models/schemas.py` | 273 | 25 Pydantic v2 models + enums, organised by pipeline stage. Complete data contract. |
| `models/prompts.py` | 376 | 12 prompt templates (one duplicated — §8). All Chinese, all demanding JSON output. |
| `agents/qa_agent.py` | 153 | Orchestrator. Constructs seven stage objects (`:27-40`), runs them in fixed order in `run()` (`:42-154`). Straight-line async, not an agent loop. |
| `core/asr_preprocessor.py` | 178 | Stage −1. Parses three transcript formats, detects swapped speaker labels, flags ASR noise, grades ASR quality. |
| `core/preprocessor.py` | 50 | Stage 1. `CleanTranscript` → `Session`; regex metadata (`:26-51`). |
| `core/kb_context_builder.py` | 163 | Stage 0 coordinator: retriever + 27 rubrics + NA pre-filter → `SessionKBContext`. |
| `knowledge/intent_retriever.py` | 213 | Filesystem hierarchical KB retriever: entity extraction (LLM) → L1 keyword classification → recursive L2/L3 drill-down (LLM) → cascade-load `index.md` → coverage score. |
| `knowledge/indexer.py` | 68 | Offline ChromaDB index builder. **Never read** — §4.3. |
| `core/atomizer.py` | 100 | Stage 2. Two parallel LLM calls for client/agent atoms; a third for the coverage matrix. Propagates `reliability=low` from noisy turns to atoms (`:58-64`). |
| `core/intent_inferrer.py` | 88 | Stage 3. One LLM call → surface/deep intent, behaviour pattern, tension, switches, unresolved intents. JSON-decode fallback (`:63-71`). |
| `core/question_generator.py` | 235 | Stage 4. Three parallel paths (rubric-driven RQ, atom-literal LQ, atom-implied IQ) producing NLI-ready hypothesis pairs. |
| `core/fact_checker.py` | 195 | Stage 5. Routes each subquestion to path A (NLI), B (LLM-over-KB) or C (forced human review); builds `Verdict`s with derived scores. |
| `core/aggregator.py` | 118 | Stage 6. **Pure function.** Dimension grouping, weighted score, veto zeroing, grade banding. |
| `core/evidence_retriever.py` | **0** | Empty. Never imported. |
| `report/report_generator.py` | 92 | Markdown renderer + JSON/MD saver. **Never imported** — `cli.py:119-122` inlines its own `json.dumps`. |
| `utils/llm_client.py` | 26 | Thin `anthropic.AsyncAnthropic` wrapper; one method `complete()`. |
| `utils/nli.py` | 62 | `transformers` text-classification pipeline returning P(entailment). Hardcoded `device=0` (`:20`). |
| `utils/logger.py` | 15 | stdlib logging boilerplate. |

Six `__init__.py` files are empty (`agents/`, `core/`, `data/`, `knowledge/`, `report/`, `tests/`).

---

## 2. Model coupling map  ← PRIORITY

### 2.1 Provider

Anthropic only. `utils/llm_client.py:2` imports `anthropic`; `:12` constructs
`anthropic.AsyncAnthropic`. Model `claude-3-5-sonnet-20241022` at `config/settings.py:16`.

`openai>=1.0.0` is declared (`pyproject.toml:13`, `requirements.txt:2`) and `OPENAI_API_KEY` is in
`.env.example:2`, but `grep -rn "openai\|OpenAI" --include=*.py .` returns **zero hits**. Dead
dependency.

Exactly one call site into the provider: `utils/llm_client.py:18-24`. Everything else calls
`self.llm.complete(...)`.

### 2.2 Every module that calls the LLM

| # | Module | `path:line` | Prompt | Returns |
|---|---|---|---|---|
| 1 | `core/asr_preprocessor.py` | `:158` | `ROLE_DETECTION_PROMPT` | `should_swap` bool, `confidence` float |
| 2 | `knowledge/intent_retriever.py` | `:66` | `ENTITY_EXTRACTION_PROMPT` | entity lists |
| 3 | `knowledge/intent_retriever.py` | `:149` | inline f-string L1 classifier | directory names |
| 4 | `knowledge/intent_retriever.py` | `:161` | `L2_CLASSIFICATION_PROMPT` | child directory names |
| 5 | `core/kb_context_builder.py` | `:158` | inline f-string applicability check | `applicable` bool |
| 6 | `core/atomizer.py` | `:36` | `ATOMIZE_CLIENT_PROMPT` | client atom array |
| 7 | `core/atomizer.py` | `:41` | `ATOMIZE_AGENT_PROMPT` | agent atom array |
| 8 | `core/atomizer.py` | `:76` | `COVERAGE_MATRIX_PROMPT` | coverage relations |
| 9 | `core/intent_inferrer.py` | `:42` | `INTENT_INFERENCE_PROMPT` | intent structure |
| 10 | `core/question_generator.py` | `:79` | `RUBRIC_TO_QUESTION_PROMPT` | question + hypothesis pair + `applicability` |
| 11 | `core/question_generator.py` | `:145` | `GENERATE_ACCURACY_LITERAL_Q_PROMPT` | question + hypothesis pair + `claim_type` |
| 12 | `core/question_generator.py` | `:204` | `GENERATE_IMPLIED_Q_PROMPT` | implied question array |
| 13 | `core/fact_checker.py` | `:97` | `WIKICHAT_VERIFY_PROMPT` | `verdict` enum, `confidence` float, `key_evidence` |
| 14 | `agents/qa_agent.py` | `:124` | `REPORT_SUMMARY_PROMPT` | `summary`, `improvement_suggestions` |

**Modules with NO model coupling:** `core/aggregator.py`, `core/preprocessor.py`,
`config/rubric_items.py`, `models/schemas.py`, `report/report_generator.py`, `utils/nli.py` (local
transformer, not an API model), `utils/logger.py`, `knowledge/indexer.py`.

Nondeterminism is spread across **nine of fourteen** non-trivial modules — it is not quarantined to
a proposer layer. But the aggregation layer is clean.

### 2.3 THE DECISIVE QUESTION — does the model propose scores?

**No. Every shipped number is re-derived in code.**

**(a) Per-verdict score — derived from an enum, in code:**

```python
# core/fact_checker.py:184-186
score=1.0 if result == VerdictResult.PASS else
      0.5 if result == VerdictResult.NEI else 0.0,
```

The model contributes `result`, a categorical label mapped through a lookup table
(`core/fact_checker.py:105-110`):

```python
result_map = {
    "Supported": VerdictResult.PASS,
    "Refuted":   VerdictResult.FAIL,
    "NEI":       VerdictResult.NEI
}
result = result_map.get(r["verdict"], VerdictResult.NEI)
```

The `.get(..., NEI)` default degrades an unrecognised model string to NEI rather than trusting it.

**(b) Per-verdict weight — from the rubric constant table, never the model:**

```python
# core/fact_checker.py:193-196
def _get_weight(self, rubric_id: int | None) -> float:
    if rubric_id and rubric_id in RUBRIC_BY_ID:
        return RUBRIC_BY_ID[rubric_id].weight
    return 1.0
```

`RUBRIC_BY_ID` is built at import time from the hand-authored table (`config/rubric_items.py:350`).
Weight 2.0 appears only at `config/rubric_items.py:81` (rule 6) and `:94` (rule 7).

**(c) Path A verdict — local NLI plus pure comparison; the API model is not called at all:**

```python
# core/fact_checker.py:55-68
s_pos = self.nli.score(turn.text, q.hypothesis_pos)
s_neg = self.nli.score(turn.text, q.hypothesis_neg)
...
if best_pos > best_neg:
    result = VerdictResult.PASS
```

The test suite asserts this: `tests/test_fact_checker.py:78`
`mock_llm_supported.complete.assert_not_called()` — "LLM 不应被调用（纯NLI路径）".

**(d) Dimension and overall score — pure arithmetic:**

```python
# core/aggregator.py:53-56
total_weight   = sum(v.weight for v in applicable)
weighted_score = sum(v.score * v.weight for v in applicable)
# core/aggregator.py:67-69
total_w = sum(d.total_weight for d in dimension_scores)
total_s = sum(d.weighted_score for d in dimension_scores)
overall = round((total_s / total_w * 100) if total_w > 0 else 0, 1)
```

**(e) Veto zeroing and grading — pure, driven by the rubric flag:**

```python
# core/aggregator.py:76-79
if q and q.is_veto and v.result == VerdictResult.FAIL:
    veto_triggered = True
    overall = 0.0
# core/aggregator.py:83-88; GRADE_THRESHOLDS = {90:"优秀",80:"良好",60:"合格"} at :10-12
```

**(f) The one model-produced float, and what it is for.** `core/fact_checker.py:111`:

```python
confidence = r["confidence"]
```

Raw number lifted from model JSON. Carried into `Verdict.confidence` and `EvidenceItem.score`
(`core/fact_checker.py:118`) — but it never multiplies into the score. Its only behavioural effect
is routing:

```python
# core/fact_checker.py:159-165
requires_review = (
    result == VerdictResult.NEI or
    confidence < LOW_CONF or          # LOW_CONF = 0.60, fact_checker.py:13
    q.q_type == "implied" or
    q.is_veto or
    result == VerdictResult.HUMAN_REVIEW
)
```

A model-proposed confidence can send an item to a human. It cannot change the deduction. Path A's
confidence is the NLI entailment probability (`core/fact_checker.py:65-66`), also routing-only.

**(g) Stage 6 summary.** `agents/qa_agent.py:124-137` asks for prose only. It passes
`overall_score="待计算"` — the literal string "to be calculated" (`qa_agent.py:126`) — i.e. the model
is deliberately shown no score, and its output goes to `aggregator.aggregate(summary=...,
suggestions=...)` (`qa_agent.py:145-146`) where neither field touches the arithmetic. The summary
narrates a score it was never shown: a prose-coherence defect, but *evidence* the author kept the
number away from the model.

**Conclusion, precisely:** the model proposes *labels, evidence text, questions, atoms, and one
routing-only confidence*. It never proposes a score, weight, dimension roll-up or grade. The
arithmetic layer (`core/aggregator.py`, all 118 lines) is model-free by construction.

One caveat: the model *does* decide `applicability` (`core/question_generator.py:98`,
`if r["applicability"] == "NA": continue`) and NA pre-filtering
(`core/kb_context_builder.py:118-127`). Dropping a rubric item removes it from the denominator
(`core/aggregator.py:46-53`; `core/fact_checker.py:148` sets `weight=0.0`). So the model
*indirectly* moves the score by changing which items are scored, though it never writes a number.

---

## 3. Determinism and reproducibility

**Same inputs → same output? No.**

| Source | `path:line` | Notes |
|---|---|---|
| Anthropic API sampling | `utils/llm_client.py:18-23` | `temperature` threaded through, set to `0.0` (`config/settings.py:19`, `cli.py:21`). Greedy is **not** a determinism guarantee across serving stacks. Nine modules depend on it. |
| `max_tokens` mismatch | `config/settings.py:20` sets 4096; `utils/llm_client.py:16` defaults 4096; the config value is never read. Truncated JSON → `json.loads` crash, input-dependent. |
| `asyncio.gather` | `core/atomizer.py:35`; `core/question_generator.py:38,94,157`; `core/fact_checker.py:44` | `gather` preserves result order, so no reordering. Does mean one failure aborts the stage. |
| NLI model | `utils/nli.py:17-23` | Deterministic given identical weights/hardware, but weights are fetched by Hub name (`config/settings.py:9`) with **no revision pin**. `device=0` hardcoded (`utils/nli.py:20`) → differs GPU vs CPU, fails on CPU-only hosts. |
| ChromaDB index | `knowledge/indexer.py:17-25` | Would be a nondeterminism source **except it is never read** (§4.3). |
| Filesystem ordering | `knowledge/intent_retriever.py:48` (`rglob`), `:52` (`iterdir`); `knowledge/indexer.py:28` | OS/filesystem-dependent order; `children` lists feed verbatim into the L2 prompt (`intent_retriever.py:164`), so directory order perturbs the prompt. |
| Batch file ordering | `cli.py:133` `batch_dir.glob("*.txt")` | Affects report ordering. |
| `uuid4` session id | `models/schemas.py:100` | Fires only when `session_id` omitted. `--session-id` is optional (`cli.py:171`), so it can be `None` → `"unknown"` (`core/asr_preprocessor.py:79`). |
| Question-ID counter | `core/question_generator.py:21-25` | `_q_counter` is instance state, never reset. `cli.py:127` builds ONE agent for the whole batch, and `QuestionGenerator` is constructed once (`qa_agent.py:35`) — so **question IDs keep incrementing across transcripts**: report *n* gets `RQ-45`, not `RQ-01`. Order-dependent output. |
| Dict ordering | `core/aggregator.py:33-39` | Insertion-ordered in 3.7+; deterministic given deterministic verdict order. Not a real source. |
| Clock | — | No `datetime`/`time` in scoring. `utils/logger.py:11` uses `%(asctime)s` for log lines only. Clean. |
| RNG | — | No `random` import anywhere. Clean. |

**Caching / seeding / replay: none.** No response cache, no seed, no recorded-fixture replay, no run
manifest, no input hash. `cli.py:119-122` writes only the final `QAReport`; intermediate artefacts
(atoms, coverage matrix, questions) are discarded — a report cannot be re-derived or audited without
re-running every model call.

The single deterministic island is `core/aggregator.py`: given fixed `list[Verdict]` and
`list[Subquestion]` it is a pure function, which is why its four tests pass reliably (§7).

---

## 4. INTENTS coupling  ← PRIORITY

### 4.1 What "INTENTS" means here

**A directory of Markdown files on disk** — not a graph, not a database, not a shared memory.
Configured at `config/settings.py:10`:

```python
"kb_root": "./data/knowledge_base/INTENTS",
```

Expected shape: a nested directory tree where each node may contain an `index.md`
(`knowledge/intent_retriever.py:202`; `knowledge/indexer.py:28`). Depth is semantic:
`KBContent.level` is documented `1=L1, 2=L2, 3=L3, 4=L4` (`models/schemas.py:68`).

**The directory does not exist in the repo.** Confirmed by execution:
`Path(".../data/knowledge_base/INTENTS").exists()` → `False`; `rglob("*")` yields `[]` without
raising. Consequence: `_build_directory_index` (`intent_retriever.py:46-59`) returns `{}`,
`_cascade_load` returns `[]` (`:176-199`), `domain_knowledge_summary` becomes `""` (`:99-103`),
`_assess_coverage` returns `0.0` (`:205-208`) → `low_coverage_warning=True` (`:116`). Path B then
short-circuits to NEI for every accuracy question (`core/fact_checker.py:90-96`). The system
degrades to "everything needs a human" rather than crashing. (Missing data is an expected condition;
recorded as a finding.)

### 4.2 READ paths (three, all read-only)

1. **Directory-structure read** — `knowledge/intent_retriever.py:46-59`. Walks `kb_root` with
   `rglob("*")`, recording each directory's child names, whether `index.md` exists, and depth. Built
   **in `__init__`** (`:44`), once per `QAAgent`, never invalidated.
2. **Content read** — `knowledge/intent_retriever.py:201-203`:
   ```python
   def _load_index(self, path: str) -> str | None:
       p = self.kb_root / path / "index.md"
       return p.read_text(encoding="utf-8") if p.exists() else None
   ```
   Called by `_cascade_load` for the matched node **and its parent** (`:180`, `:191`), tagged
   `node_type="primary"` / `"parent"` (`:186`, `:197`). Only `primary` content reaches
   `domain_knowledge_summary` (`:99-103`) — parent content is loaded and then effectively unused.
3. **Indexer read** — `knowledge/indexer.py:28-29`, `rglob("index.md")` + `read_text`.

Path-selection logic — a keyword table plus recursive LLM drill-down:

- `ENTITY_TO_L1` (`knowledge/intent_retriever.py:9-36`) — hand-built 27-entry map from Chinese
  business entities (`USB-Key`, `CA锁`, `汇信`, `年报`, `政采云`, `信用修复`, `经营异常`,
  `行政处罚`, …) to nine L1 categories.
- `_classify_l1` (`:123-131`) — substring match, order-preserving dedup.
- `_llm_classify_l1` (`:133-150`) — LLM fallback over discovered L1 directory names.
- `_drill_down` (`:152-174`) — recursive: stop if no children or the node has its own `index.md`
  (`:158-159`), else ask the LLM to pick a child and recurse. **No depth cap, no visited set** (§8).

### 4.3 WRITE paths

**There is no write path into INTENTS.** `grep` over all `*.py` finds `write_text` at exactly two
places, both writing *reports*:

- `cli.py:119` / `cli.py:144` — report JSON into `--output`.
- `report/report_generator.py:87` / `:92` — report JSON/MD (dead code; never imported).

`knowledge/intent_retriever.py` opens files read-only (`:203`). No `open(..., "w")`, no `mkdir`
under `kb_root`, no `touch`, no shutil.

The only knowledge-layer write is the ChromaDB index, into a *sibling* directory:

```python
# knowledge/indexer.py:17-19
self.client = chromadb.PersistentClient(
    path=str(self.kb_root.parent / "chroma_db")
)
# knowledge/indexer.py:48-52
collection.upsert(documents=docs, metadatas=metas, ids=ids)
```

`kb_root.parent` is `data/knowledge_base/`, so the artefact lands at
`data/knowledge_base/chroma_db`. INTENTS itself is untouched.

**Critical: the indexer is write-only dead code.** `grep -rn "chromadb\|chroma" --include=*.py .`
returns exactly three hits, all inside `knowledge/indexer.py` (`:2`, `:17`, `:18`). Nothing ever
calls `get_collection` or `query`. `IntentAwareRetriever` uses no vectors at all — it walks the
filesystem and asks the LLM to pick directory names. So:

- `README.md:14-15` tells the user to run `python cli.py --build-index data/knowledge_base/INTENTS/`
  as a required first step;
- `cli.py:156-160` dutifully builds the index;
- **no retrieval path ever reads it.**

A documented-vs-actual divergence, and a dead 68-line module carrying a heavy dependency
(`chromadb`, `pyproject.toml:17`).

### 4.4 `core/intent_inferrer.py` — a different sense of "intent"

**Nothing to do with the INTENTS directory.** It imports no knowledge module
(`core/intent_inferrer.py:1-7`) and never touches `kb_root`. It performs *conversational* intent
inference over one transcript: surface intent, deep intent, agent behaviour pattern, key tension,
intent switches, unresolved intents (`:73-89`), via one LLM call (`:42`). It consumes
`kb_context.domain_knowledge_summary[:1000]` as context (`:57-59`) — its only, indirect, read-only
link to the KB. Output is per-session and discarded after the report; nothing is persisted back.

**Summary:** B is a pure consumer of an on-disk Markdown intent tree, addressed by directory path,
with a hand-tuned entity→L1 keyword map and LLM drill-down. It writes nothing back under any path.

---

## 5. End-to-end pipeline trace

### 5.1 Runtime shape

**Sequential, straight-line async — not an agent loop, not a batch job.** `QAAgent.run()`
(`agents/qa_agent.py:42-154`) is a single coroutine executing seven stages in fixed order with no
branching, retries, planner or tool-calling. The only concurrency is `asyncio.gather` *within*
stages (`core/atomizer.py:35`; `core/question_generator.py:38,94,157`; `core/fact_checker.py:44`).
"Batch" mode (`cli.py:126-153`) is a plain `for` loop awaiting one full pipeline per file
(`cli.py:136-139`).

The only human-in-the-loop hook is an optional callback (`agents/qa_agent.py:46`, invoked
`:116-120`) which `cli.py` never supplies — so in the shipped CLI `human_review_callback` is always
`None` and flagged items are reported, never resolved.

### 5.2 Ordered stages and data between them

```
argv ──► cli.main()                         cli.py:163-184
       ► cli.run_single()                   cli.py:103-123
         └ reads transcript file (or treats the arg as literal text)  cli.py:104-106
       ► cli.build_agent()                  cli.py:17-23
         └ AnthropicClient → CONFIG["llm_client"] → QAAgent(CONFIG)

QAAgent.run(transcript_text, session_id)    qa_agent.py:42

 Stage -1  ASRPreprocessor.process()        qa_agent.py:53   → CleanTranscript
           _parse_raw (3 formats)           asr_preprocessor.py:88-138
           _verify_roles (rules → LLM)      asr_preprocessor.py:140-166
           noise flags + asr_quality band   asr_preprocessor.py:48-76
           OUT: CleanTranscript{turns[CleanTurn], asr_quality,
                role_swap_detected, low_reliability_turn_ids}

 Stage 0   KBContextBuilder.build(full_text) qa_agent.py:66  → SessionKBContext
           full_text rebuilt "客户：…/客服：…"  qa_agent.py:61-64
           A IntentAwareRetriever.build_context  kb_context_builder.py:41
             ├ ENTITY_EXTRACTION (LLM)      intent_retriever.py:66
             ├ _classify_l1 (keyword map)   intent_retriever.py:77
             ├ _drill_down (recursive LLM)  intent_retriever.py:86
             ├ _cascade_load index.md       intent_retriever.py:93
             └ _assess_coverage             intent_retriever.py:96
           B all 27 RUBRIC_ITEMS loaded     kb_context_builder.py:51
           C NA pre-filter (keyword → LLM)  kb_context_builder.py:55, 76-128
           OUT: SessionKBContext{primary_intent_path, kb_contents,
                domain_knowledge_summary, all_rubric_items,
                applicable_rubrics, coverage_score, low_coverage_warning}

 Stage 1   Preprocessor.build_session()     qa_agent.py:70   → Session
           regex metadata phone/company     preprocessor.py:26-51

 Stage 2   Atomizer.atomize()               qa_agent.py:74   → (client_atoms, agent_atoms)
           2 parallel LLM calls             atomizer.py:35-49
           low-reliability propagation      atomizer.py:58-64
           Atomizer.build_coverage_matrix() qa_agent.py:77   → list[CoverageRelation]
           1 LLM call                       atomizer.py:76

 Stage 3   IntentInferrer.infer()           qa_agent.py:91   → IntentInference
           1 LLM call, JSON fallback        intent_inferrer.py:42, 63-71

 Stage 4   QuestionGenerator.generate_all() qa_agent.py:98   → list[Subquestion]
           ├ RQ rubric-driven  1 LLM call per applicable rubric  question_generator.py:79
           ├ LQ atom-literal   1 LLM call per accuracy atom      question_generator.py:145
           └ IQ atom-implied   1 LLM call total                  question_generator.py:204

 Stage 5   FactChecker.verify_all()         qa_agent.py:110  → list[Verdict]
           routing                          fact_checker.py:29-44
           path A: local NLI, 2 scores × N turns  fact_checker.py:46-84
           path B: 1 LLM call over KB text        fact_checker.py:86-122
           path C: forced human review, score 0.5 fact_checker.py:124-137
           NA:     weight 0.0                     fact_checker.py:139-151

 (optional) human_review_callback           qa_agent.py:115-120  (never wired in cli.py)

 Stage 6   LLM summary prose                qa_agent.py:124-137
           Aggregator.aggregate()           qa_agent.py:139-148 → QAReport  [PURE]

cli.render_report(report)                   cli.py:26-100  rich console
json.dumps(report.dict())                   cli.py:119-122 → --output
```

**LLM calls per evaluation** (`UNCERTAIN:` depends on rubric filtering): 1 role detection + 1 entity
extraction + up to 2 drill-downs × depth + up to ~10 NA checks + 3 atomizer + 1 intent +
N_applicable rubric questions (≤27) + M accuracy atoms + 1 implied + K path-B checks + 1 summary.
Order 40–60 calls for a 17-turn transcript. No batching.

---

## 6. Data contracts

### 6.1 Input — transcript

Three formats, all regex-parsed in `core/asr_preprocessor.py:88-138`:

1. **Timestamped** (`:98`): `[1s -> 20s]客户: …` — regex
   `\[(\d+)s\s*->\s*(\d+)s\]\s*(客户|坐席|客服)[：:]\s*(.+?)(?=\[\d+s|$)`. IDs synthesised `T01`,
   `T02`… (`:105`).
2. **Numbered** (`:113`): `[T01] 坐席：…` — `\[?(T\d+)\]?\s*(客户|坐席|客服)[：:]…`. IDs from text.
3. **Bare** (`:126-137`): line-per-turn, prefix in `{客户, 坐席, 客服}`, split on `：` or `:`.

Role mapping: `客户` → `customer`, else (`坐席`/`客服`) → `agent` (`:102`, `:117`, `:130`). Both
fullwidth `：` and ASCII `:` accepted throughout — a real robustness detail.

**The real file.** `data/transcripts/sample.txt` — 1,555 bytes, 17 turns, timestamped format. A
genuine-looking 金华市公共资源交易中心 (Jinhua public resource trading centre) call about an expired
enterprise CA certificate: the agent asks 贵姓, the customer answers 王, the agent explains renewal
documents (营业执照副本、经办人身份证、原CA证书), the walk-in address (金华市双龙南街858号), the fee
(200元), and closes with 满意请按1. A well-formed **positive** example that would score highly —
there is no failing/adversarial transcript in the repo.

`design/Examples/` holds six further `.txt` files (6–53 lines) plus `transcript.md` (44 lines) —
design-time material, not wired into any code path.

### 6.2 Input — rubric

The operative rubric is **Python, not data**: `config/rubric_items.py:4` defines
`RUBRIC_ITEMS: list[RubricItem]` with exactly 27 entries, ids 1–27, asserted by
`tests/test_kb_context_builder.py:51`.

`RubricItem` schema (`models/schemas.py:51-63`): `id`, `category` (5-value enum, `:44-49`), `name`,
`pass_criteria`, `fail_criteria`, `na_criteria`, `is_weighted`, `weight`, `always_check`,
`requires_domain_kb`, `trigger_keywords`, `is_veto`.

Distribution: 流程遵守 ids 1–7; 态度规范 8–14; 技能技巧 15–21; 特殊项 22; 准确性 23–27.
Weight 2.0 only on ids 6 and 7 (`:80-81`, `:93-94`). `is_veto=True` only on id 27 (`:345`).
`requires_domain_kb=True` on ids 18, 19, 20, 21, 23, 24, 25 (`:228`, `:240`, `:252`, `:264`, `:293`,
`:306`, `:318`).

Derived indexes at `config/rubric_items.py:350-354`: `RUBRIC_BY_ID`, `ALWAYS_CHECK_RUBRICS`,
`DOMAIN_KB_RUBRICS`, `WEIGHTED_RUBRICS`, `VETO_RUBRICS`.

**`data/knowledge_base/QA_RUBRICS/rubrics.md` is EMPTY — 0 lines, 0 bytes** (`wc -l`). The README
advertises it as "质检规则原文" (`README.md:37`). No code reads it: `grep` finds no reference to
`QA_RUBRICS` or `rubrics.md` in any `.py`. The rubric exists only as Python constants.

### 6.3 Input — knowledge base

Expected: a nested tree under `data/knowledge_base/INTENTS/`, each node optionally carrying
`index.md` (§4.1). **Not present.** The whole of `data/` contains four files: `data/__init__.py`,
`data/transcripts/sample.txt`, `data/knowledge_base/QA_RUBRICS/rubrics.md` (empty), and nothing else.

### 6.4 Intermediate contracts (`models/schemas.py`)

25 models, stage-banner organised. Load-bearing ones:

- `CleanTurn` / `CleanTranscript` (`:23-37`) — `reliability: Literal["high","low"]`,
  `flags: List[TurnFlag]` where `TurnFlag ∈ {INCOMPLETE, ASR_ERROR, ROLE_SWAPPED, NORMAL}` (`:17-21`).
- `Atom` (`:132-140`) — the WikiChat-style unit: `content` (verbatim) **and** `decontextualized`
  (self-contained restatement), plus `source_turn_ids` for traceability. This dual field is the
  whole point of the atomiser.
- `CoverageRelation` (`:147-151`) — `client_atom_id` → `agent_atom_id` with
  `status ∈ {responded, partial, ignored}` (`:142-145`).
- `Subquestion` (`:194-208`) — carries `hypothesis_pos` **and** `hypothesis_neg` (the NLI pair),
  `claim_type` (the fact-checking router key, `:177-181`), and `rubric_id` (the weight key).
- `Verdict` (`:230-240`) — `result` (6-value enum, `:222-228`), `confidence`, `score`, `weight`,
  `evidence`, `requires_human_review`, `review_reason`, `checking_path ∈ {A,B,C}`.
- `EvidenceItem` (`:215-220`) — `turn_id` XOR `doc_path`: every piece of evidence points at either a
  transcript turn or a KB document. Provenance is designed in.

### 6.5 Output

`QAReport` (`models/schemas.py:254-274`): `session_id`, `agent_id`, `overall_score` (float 0–100),
`grade` (优秀/良好/合格/不合格), `veto_triggered`, `veto_items`, `dimension_scores`, full `verdicts`
and `questions`, plus meta-flags (`requires_human_review`, `human_review_items`,
`asr_quality_warning`, `role_swap_detected`, `multi_intent_detected`, `unresolved_intents`,
`low_kb_coverage_warning`) and `summary` / `improvement_suggestions`.

Serialised `json.dumps(report.dict(), ensure_ascii=False, indent=2)` (`cli.py:120`). Markdown output
exists (`report/report_generator.py:10-76`) but is unreachable.

`agent_id` is always `"UNKNOWN"` — the schema default (`models/schemas.py:101`); nothing ever sets
it (`core/preprocessor.py:20-24` does not pass it).

---

## 7. What is load-bearing  ← PRIORITY

### 7.1 Test suite — actual results

Executed. `transformers` absent, so `tests/test_fact_checker.py` cannot even be collected:

```
ERROR collecting tests/test_fact_checker.py
tests/test_fact_checker.py:8: in <module>
    from core.fact_checker import FactChecker
core/fact_checker.py:9: in <module>
    from utils.nli import NLIModel
utils/nli.py:2: in <module>
    from transformers import pipeline
E   ModuleNotFoundError: No module named 'transformers'
```

The remaining 17 tests DID run
(`python3 -m pytest tests/ -v --ignore=tests/test_fact_checker.py`), verbatim:

```
tests/test_aggregator.py::test_basic_aggregation PASSED                  [  5%]
tests/test_aggregator.py::test_weighted_item PASSED                      [ 11%]
tests/test_aggregator.py::test_na_not_counted PASSED                     [ 17%]
tests/test_aggregator.py::test_veto_triggers_zero PASSED                 [ 23%]
tests/test_asr_preprocessor.py::test_timestamp_parsing FAILED            [ 29%]
tests/test_asr_preprocessor.py::test_role_swap_detection PASSED          [ 35%]
tests/test_asr_preprocessor.py::test_asr_quality_assessment PASSED       [ 41%]
tests/test_atomizer.py::test_atomize_returns_both_sides PASSED           [ 47%]
tests/test_atomizer.py::test_decontextualized_not_empty PASSED           [ 52%]
tests/test_atomizer.py::test_low_reliability_turns_flagged PASSED        [ 58%]
tests/test_atomizer.py::test_coverage_matrix_structure PASSED            [ 64%]
tests/test_kb_context_builder.py::test_build_returns_session_kb_context PASSED [ 70%]
tests/test_kb_context_builder.py::test_na_prefilter_removes_na_items PASSED [ 76%]
tests/test_kb_context_builder.py::test_na_prefilter_keeps_triggered_items PASSED [ 82%]
tests/test_kb_context_builder.py::test_always_check_always_kept PASSED   [ 88%]
tests/test_kb_context_builder.py::test_low_coverage_warning PASSED       [ 94%]
tests/test_kb_context_builder.py::test_llm_parse_failure_defaults_to_applicable PASSED [100%]

=================== 1 failed, 16 passed, 2 warnings in 0.09s ===================
```

The failure is a **genuine bug**, not an environment artefact:

```
tests/test_asr_preprocessor.py:35: AssertionError
>       assert result.turns[0].role == "customer"
E       AssertionError: assert 'agent' == 'customer'
```

Input `SAMPLE_WITH_TIMESTAMP` (`tests/test_asr_preprocessor.py:6-10`) begins
`[1s -> 20s]客户: 您好，我在登录时显示CA锁未绑定。`. What is certain from the assertion: `_verify_roles`
(`core/asr_preprocessor.py:140-166`) returns `should_swap=True` on a transcript whose labels are
already correct, and the swap at `core/asr_preprocessor.py:41-42` then inverts every role.
`UNCERTAIN:` which branch fires — the `AGENT_INDICATORS` check (`:146-148`) or the `AGENT_OPENING`
short-utterance check (`:149-151`). Settling it: instrument `_verify_roles` and print
`(role_swap, confidence)` for that fixture. **A false-positive role swap silently inverts the entire
evaluation** — every 客服 rubric would be checked against customer utterances. This is the most
consequential defect in the otherwise-working code.

Also surfaced: a real `DeprecationWarning: invalid escape sequence '\-'` at
`core/asr_preprocessor.py:177`, and two `PydanticDeprecatedSince20` warnings for `.dict()` at
`core/atomizer.py:82` and `:86`. `.dict()` is used throughout (`core/intent_inferrer.py:46,50,54`;
`core/question_generator.py:87,148,208,211`; `cli.py:120`; `report/report_generator.py:88`) and will
break on Pydantic v3.

**Coverage assessment.** 17 tests over 3,761 lines. Covered: aggregator arithmetic (4 tests,
genuinely good — weighted items, NA exclusion, veto zeroing), ASR quality/role logic (3), atomiser
parsing and reliability propagation (4), NA pre-filter (6). **Not** covered:
`knowledge/intent_retriever.py` (0 tests — the most intricate module), `core/question_generator.py`
(0), `agents/qa_agent.py` (0 — exactly why the two blockers in §8 survived), `cli.py` (0),
`report/report_generator.py` (0). No integration test, no end-to-end test, no replay test.

`tests/test_atomizer.py:132` also mis-names its unpacking — `agent_atoms, _ = await
atomizer.atomize(...)` takes the *client* list (the function returns `(client, agent)`,
`core/atomizer.py:66`). It passes because the mock's first `side_effect` value is the agent atom; it
asserts the right thing about the wrong variable.

### 7.2 Irreplaceable — high domain value, expensive to lose

**`config/rubric_items.py` (353 lines) — the single most valuable file in the repository.** Not code:
an encoded operational QA standard for a Chinese government-services call centre, transcribed at
high fidelity from what is evidently a real internal scoring sheet. Evidence it is real rather than
invented:

- Idiosyncratic, unguessable specifics: `除88234732外` — a literal internal phone number carved out
  of the privacy rule (`:339`); `市监电话称呼老师` (address 市监 callers as "teacher", `:24`);
  `>2次询问贵姓` as a fail condition (`:25`); `候线≤30秒` (`:49`); `工单5分钟内完成` (`:75`);
  `非客服原因30秒以上空白或客服原因15秒以上空白` — asymmetric silence tolerances (`:213`).
- Domain vocabulary errors enumerated as failures: `USB-Key叫U盘/年报叫年检` (`:103`).
- Practitioner-only NA carve-outs: `系统原因导致未能听到起接语` (`:13`);
  `系统问题不能做记录/通话时长<1分30秒` (`:77`); `对方已明显反感；用户主动询问` as marketing-NA (`:250`).
- Escalation checklist split by channel:
  `远程需确认：具体问题/QQ/企业名称；电话需确认：具体问题/回访电话/姓名/回访时间` (`:87`).

Rebuilding this needs access to the client's QA team, not engineering time. The machine metadata
layered on top (`trigger_keywords`, `always_check`, `requires_domain_kb`, `is_weighted`, `is_veto`)
is itself a designed mapping from prose criteria to automatable gates — also not mechanical.

**`models/prompts.py` (376 lines) — substantial, non-obvious prompt engineering.**

- `ATOMIZE_CLIENT_PROMPT` / `ATOMIZE_AGENT_PROMPT` (`:81-137`) encode a 6-type client taxonomy
  (事实声明/故障描述/明确诉求/历史声称/推断声称/异议) and a 9-type agent taxonomy
  (业务判断/事实陈述/政策引用/故障定性/解决方案/操作指引/服务承诺/结案行为/服务行为). These taxonomies
  are the discriminator that later routes atoms to accuracy checking
  (`core/question_generator.py:126-133` selects exactly 政策引用/故障定性/业务判断/事实陈述). Taxonomy
  and routing were co-designed.
- Explicit decontextualisation instruction (`:86-89`: 消解所有代词和指代，"这个"→具体内容) with a
  matching schema field and a matching test assertion (`tests/test_atomizer.py:96`:
  `len(decontextualized) > len(content)`).
- `RUBRIC_TO_QUESTION_PROMPT` (`:212-243`) — converts a prose rubric criterion into a yes/no question
  **plus a positive and negative NLI hypothesis pair**. This bridge from human rubric prose to
  machine-verifiable entailment premises is the conceptual core of the design.
- `WIKICHAT_VERIFY_PROMPT` (`:307-330`) — explicit closed-book instruction
  ("不要使用你自己的知识，只基于提供的文档") with three-way Supported/Refuted/NEI output.
- `GENERATE_IMPLIED_Q_PROMPT` (`:271-304`) — four implied-question types
  (DOMAIN_KNOWLEDGE / CONTEXT / IMPLICIT_MEANING / STATISTICAL_RIGOR), mirrored as an enum
  (`models/schemas.py:183-187`).

**`core/asr_preprocessor.py` (178 lines) — real, hard-won ASR heuristics.**

- `AGENT_INDICATORS` (`:11-15`) — eleven Chinese phrases only an agent says (`您贵姓`, `满意请按1`,
  `请对本次服务`, `我这边帮您`, `我这边查一下`). This is the substance of speaker-role
  disambiguation without diarisation metadata.
- Three-format parser (`:88-138`) tolerating fullwidth/ASCII colons and three ID conventions — the
  kind of thing that accretes from contact with real ASR output.
- `INCOMPLETE_PATTERNS` (`:19-22`): `r"^[^，。！？…]{1,5}$"` (too-short fragment) and
  `r"(.{2,5})\1{2,}"` (stutter detection, e.g. 那个那个那个). Compact and effective.
- `good/fair/poor` banding at ratio 0.1 / 0.3 (`:72-76`), and propagation of `reliability=low` from
  turn → atom (`core/atomizer.py:58-64`) → path C forced human review
  (`core/fact_checker.py:124-137`). A designed, coherent uncertainty policy.

Caveat: this file also contains the one failing test (§7.1), so the role-swap heuristic is
valuable-but-buggy, not valuable-and-correct. And see §8.6 — the reliability chain is broken at the
last link.

**`knowledge/intent_retriever.py` (213 lines), specifically `ENTITY_TO_L1` (`:9-36`).** The 27-entry
Chinese entity→business-line map (`汇信`→法人数字证书业务; `政采云`→政采云平台业务;
`经营异常`→信用修复业务; `行政处罚`→大综合一体化业务) is domain knowledge, not code. The hierarchical
drill-down around it (`:152-174`) is reimplementable; the map is not.

**`core/aggregator.py` (118 lines).** Small and rewritable *as code*, but it encodes the scoring
policy — NA excluded from the denominator (`:44-53`), weighted items, veto→0 (`:76-79`), grade bands
90/80/60 (`:10-12`). It is the only module with real, passing coverage of its semantics (4/4).
Cheap to rewrite; the *policy* is part of the rubric asset.

**`core/fact_checker.py` routing policy (`:29-44`, `:159-165`).** The claim-type → path A/B/C table
and the five-condition human-review escalation rule are design decisions with operational
consequences (every implied question and every veto item goes to a human, by construction). Short
code; considered policy.

### 7.3 Boilerplate — rewritable in an afternoon

- `utils/logger.py` (15) — stdlib logging setup.
- `utils/llm_client.py` (26) — a 9-line try/except around one SDK call.
- `utils/nli.py` (62) — thin `transformers.pipeline` wrapper. The *choice* of
  `cross-encoder/nli-deberta-v3-large` (`config/settings.py:9`) is one line of judgement; the
  wrapper is trivial. `batch_score` (`:38-62`) is dead — never called;
  `core/fact_checker.py:55-56` loops `score()` in Python despite the docstring at `utils/nli.py:42`
  saying "批量打分，避免逐条调用".
- `core/preprocessor.py` (50) — three regexes. `duration_sec` extraction (`:43-49`) is dead: it
  reads `t.timestamp_end` from `Turn`, but `Turn` (`models/schemas.py:92-97`) has no such field;
  `hasattr` guards it so it silently never fires, and `Session.duration_sec`
  (`models/schemas.py:102`) is never populated.
- `report/report_generator.py` (92) — Markdown string builder. Entirely unreferenced.
- `knowledge/indexer.py` (68) — write-only dead code (§4.3).
- `core/evidence_retriever.py` (0) — empty.
- `models/schemas.py` (273) — mechanical *as Pydantic*, but the stage decomposition it encodes
  (atoms → coverage → questions → verdicts, with `hypothesis_pos`/`hypothesis_neg` and
  `turn_id`/`doc_path` provenance) *is* the architecture. The types are cheap; the decomposition is
  not.
- `cli.py` (187) — argparse + `rich`. Pleasant, replaceable.

### 7.4 Design corpus

`design/` holds 6,839 lines of Markdown including `history_1_0.md` (2,813) and `history_2_0.md`
(2,593). `design/13_data-pipeline.md` is an accurate ASCII rendering of the intended pipeline;
`design/modules_relation.md` correctly describes Stage 0. `design/19_limitation.md:1-22` states
limitations honestly (implied questions always need human review; KB coverage gates path B; ASR
quality degrades everything; cross-call consistency needs CRM). Valuable as rationale — but it
describes the system as designed, and §8 shows the code diverges.

---

## 8. Maturity and quality

### 8.1 Does it run end-to-end? No. Two confirmed blocking defects.

**Blocker 1 — `AttributeError` in Stage 0.** `agents/qa_agent.py:31` assigns
`self.kb_context_builder = KBContextBuilder(...)`, but `agents/qa_agent.py:66` calls:

```python
kb_context = await self.kb_builder.build(full_text)
```

`self.kb_builder` is never assigned. Confirmed by execution: `"self.kb_context_builder =" in src` →
`True`; `"self.kb_builder" in src` → `True`. The pipeline raises
`AttributeError: 'QAAgent' object has no attribute 'kb_builder'` on the first Stage-0 call. This is
a half-finished refactor — lines 13 and 28-30 are the commented-out `IntentAwareRetriever` wiring it
replaced.

**Blocker 2 — `KeyError: 'grade'` in Stage 6.** `models/prompts.py` defines `REPORT_SUMMARY_PROMPT`
**twice** — `:332-347` and again `:350-377`. The second silently shadows the first and requires two
extra placeholders, `{grade}` (`:355`) and `{veto_triggered}` (`:360`). `agents/qa_agent.py:125-135`
supplies only five of the seven. Confirmed by execution:

```
placeholders: ['dimension_scores_json', 'failed_items_json', 'grade',
               'human_review_count', 'overall_score', 'unresolved_intents',
               'veto_triggered']
supplied by qa_agent.py: ['dimension_scores_json', 'failed_items_json',
               'human_review_count', 'overall_score', 'unresolved_intents']
format FAILS with KeyError: 'grade'
```

Both are two-line fixes, but both sit on the only path, and neither is covered by any test —
`agents/qa_agent.py` has zero coverage.

**UNVERIFIED (could not execute): the full pipeline beyond these points.** Even patched, a real run
needs `ANTHROPIC_API_KEY`, network, `transformers` + `torch` with a CUDA device
(`utils/nli.py:20` hardcodes `device=0`), and a populated `INTENTS/` tree. None available here.
What is certain is that the code reaches an unconditional `AttributeError` before any of that
matters.

### 8.2 Packaging defect

```toml
# pyproject.toml:2-3
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends.legacy:build"
```

`setuptools.backends.legacy:build` is not a valid setuptools build backend (correct:
`setuptools.build_meta`). `README.md:4-5` instructs `pip install -e ".[dev]"`, which would fail.
`UNVERIFIED (could not execute)` — cannot run pip here to show the exact error — but the backend
string corresponds to no real setuptools entry point. There is also no `[tool.setuptools] packages`
declaration and the layout is flat (top-level `core/`, `models/`, `agents/`… not under `src/`), so
even with a valid backend an editable install needs explicit package discovery config.

### 8.3 Dead and orphaned code

| Item | Evidence |
|---|---|
| `core/evidence_retriever.py` | 0 lines; never imported |
| `report/report_generator.py` | never imported (`grep ReportGenerator` hits only its definition) |
| `knowledge/indexer.py` / chromadb | built by `cli.py:156-160`, never queried (§4.3) |
| `utils/nli.py:38-62` `batch_score` | never called; `core/fact_checker.py:55-56` loops instead |
| `models/prompts.py:55-65` `LLM_L1_CLASSIFY_PROMPT` | never imported; `knowledge/intent_retriever.py:140-148` uses an inline duplicate |
| `models/prompts.py:332-347` first `REPORT_SUMMARY_PROMPT` | shadowed by `:350` |
| `agents/qa_agent.py:13, 28-30` | commented-out retriever wiring |
| `core/preprocessor.py:43-49` `duration_sec` | reads a field `Turn` lacks; `hasattr`-guarded, never fires |
| `openai` dependency | `pyproject.toml:13`; zero `.py` references |
| `config/settings.py:11-14` `confidence` | duplicated as constants in `core/fact_checker.py:12-13`; config values never read |
| `config/settings.py:20` `max_tokens` | never read; `utils/llm_client.py:16` uses its own default |
| `Session.agent_id` | always `"UNKNOWN"` (`models/schemas.py:101`); never set |

### 8.4 Error handling

Thin and inconsistent. Model JSON is parsed with no guard in seven places and will raise
`json.JSONDecodeError` on any malformed reply:

- `core/asr_preprocessor.py:165` then `result["should_swap"]` (`:166`)
- `core/atomizer.py:52/55` and `:100`
- `core/question_generator.py:97`, `:160`, `:221` — plus unguarded `r["question"]`,
  `r["hypothesis_pos"]`
- `core/fact_checker.py:103` then `r["verdict"]` (`:110`), `r["confidence"]` (`:111`)
- `knowledge/intent_retriever.py:69`, `:150`, `:169`
- `agents/qa_agent.py:137` then `summary_data["summary"]` (`:145`)

Two modules do guard: `core/intent_inferrer.py:63-71` (returns a `解析失败` placeholder) and
`core/kb_context_builder.py:157-163` (conservatively keeps the rubric on parse failure, with a test
at `tests/test_kb_context_builder.py:138-154`). The inconsistency is the finding: the same failure
mode is handled in two places and ignored in seven.

`utils/llm_client.py:25-27` logs and re-raises. `cli.py:152-153` catches per-file exceptions in
batch mode only — a single-transcript run has no top-level handler.

Because all stage-internal fan-out uses bare `asyncio.gather` (no `return_exceptions=True`), one bad
model reply among 27 rubric questions aborts the whole evaluation.

### 8.5 Hardcoded values

- `utils/nli.py:20` `device=0` — hard GPU requirement; the comment says "改为 -1 使用 CPU" but there
  is no switch.
- `core/fact_checker.py:12-13` `HIGH_CONF = 0.85` / `LOW_CONF = 0.60`, duplicating
  `config/settings.py:12-13`. `HIGH_CONF` is defined and never used.
- Truncation magic numbers, unexplained and inconsistent: `[:1500]` (`core/atomizer.py:45,79`;
  `core/question_generator.py:213`), `[:1000]` (`core/intent_inferrer.py:58`), `[:2000]`
  (`core/question_generator.py:150`; `knowledge/intent_retriever.py:100`), `[:3000]`
  (`core/fact_checker.py:101`), `[:500]` (`core/kb_context_builder.py:150`;
  `knowledge/intent_retriever.py:87`), `[:300]` (`models/prompts.py:60`).
- `turns[:10]` for role detection (`core/asr_preprocessor.py:144`, `:156`).
- `agent_atoms[:5]` / `[:3]` / `turns[:5]` fallbacks (`core/question_generator.py:68`, `:75-77`,
  `:87`, `:113`) — a rubric with no `trigger_keywords` silently gets the first five atoms as
  context regardless of relevance.
- `l1_paths[:2]` — at most two business lines per call (`knowledge/intent_retriever.py:85`).
- `applicable_rubrics[:10]` in the implied-question prompt (`core/question_generator.py:201`).
- Grade bands `{90, 80, 60}` (`core/aggregator.py:10-12`).
- Chroma path derived as `kb_root.parent / "chroma_db"` (`knowledge/indexer.py:18`).

### 8.6 Other defects

- **Unbounded recursion**: `_drill_down` (`knowledge/intent_retriever.py:152-174`) recurses with no
  depth limit and no visited set; it terminates only if the LLM eventually returns empty `selected`
  or hits a leaf. `UNCERTAIN:` whether real directory structures make this reachable; settling it
  needs a populated `INTENTS/` tree plus a stub LLM returning a cyclic child name.
- **Stale directory index**: built once in `__init__` (`knowledge/intent_retriever.py:44`); in batch
  mode the agent is constructed once (`cli.py:127`) so mid-run KB changes are invisible.
- **Cross-transcript ID leakage in batch mode**: `_q_counter` never reset (§3).
- **Dead-branch precedence bug** — `core/fact_checker.py:33`:
  ```python
  elif q.reliability == "low" if hasattr(q, "reliability") else False:
  ```
  `Subquestion` (`models/schemas.py:194-208`) has no `reliability` field, so `hasattr` is always
  `False` and **path C is unreachable via this route**. Path C is therefore dead in practice —
  meaning the ASR-reliability signal that `core/atomizer.py:58-64` carefully propagates onto atoms
  never reaches a verdict. A break in the middle of the uncertainty chain praised in §7.2.
- **`_has_asr_error` regex** (`core/asr_preprocessor.py:177`) uses a non-raw escape `\-` inside a
  character class and includes smart quotes; emits a real `DeprecationWarning` (§7.1) and will
  become a `SyntaxError` in a future Python.
- **`fail_criteria=""`** on rubric id 1 (`config/rubric_items.py:12`) — an empty failure standard is
  fed verbatim into `RUBRIC_TO_QUESTION_PROMPT` (`core/question_generator.py:84`).
- **Summary prose contradicts the score** (§2.3g).
- **No `data/reports/`** although `README.md:19-20` writes there; `cli.py:118` does
  `mkdir(parents=True)` so it self-heals.
- **`.env` handling is correct**: `.gitignore:2-4` excludes `.env`; `.env.example:1-2` holds only
  placeholders; `config/settings.py:5` calls `load_dotenv()`. No secrets in the repo.
- **No TODO/FIXME markers anywhere** (`grep` finds none) — the incompleteness is silent rather than
  annotated, which is why the two blockers read as finished code.

### 8.7 README vs. code — divergences

| README claim | Reality |
|---|---|
| `README.md:4-5` `pip install -e ".[dev]"` | invalid build backend (`pyproject.toml:3`) |
| `README.md:14-15` build the index as a required step | the index is never read (§4.3) |
| `README.md:35-36` KB at `data/knowledge_base/INTENTS/` | directory absent |
| `README.md:37` `QA_RUBRICS/` holds 质检规则原文 | file present but empty (0 bytes), and unread by code |
| `README.md:18-24` run QA on a transcript | crashes at `agents/qa_agent.py:66` |
| `README.md:27-33` "Pipeline 概览", 7 stages | matches the code's stage sequence exactly |
| `README.md:29` "Stage 0 知识库上下文构建（业务KB + 质检规则）" | matches `core/kb_context_builder.py` |
| `README.md:40-44` 27 rules / 5 dimensions / (*) items 6&7 doubled / NA excluded / id 27 veto / implied→human | **all five verified true in code** (`config/rubric_items.py:80-81`, `:93-94`, `:345`; `core/aggregator.py:44-53`; `core/fact_checker.py:162`) |

The scoring-policy half of the README is accurate. The setup/data half is not.

### 8.8 Overall maturity

A well-structured, thoughtfully designed **prototype that has never been run end-to-end.** The
architecture is coherent and the domain encoding is serious; the integration is unfinished.
Evidence it was never executed: two unconditional crashes on the only path, an empty module, a dead
index, a shadowed prompt, and a dead path-C branch — none of which survive a single successful run.
The unit tests that exist are real and mostly pass, but they test *parts*, and no test ever
constructs a `QAAgent`.

---

## 9. Dependencies

`pyproject.toml:10-19` and `requirements.txt:1-10` declare the same eight runtime packages (the
requirements file additionally inlines the two dev packages).

| Package | Constraint | Used at | Verdict |
|---|---|---|---|
| `anthropic` | `>=0.30.0` | `utils/llm_client.py:2,12,18` | **Used.** Sole model provider. |
| `openai` | `>=1.0.0` | — | **Unused.** Zero references. |
| `transformers` | `>=4.40.0` | `utils/nli.py:2,17` | **Used**, load-bearing for path A. **HEAVY.** |
| `torch` | `>=2.0.0` | never imported directly | **Used transitively** as the `transformers` backend. **HEAVY** (~2–3 GB with CUDA). |
| `pydantic` | `>=2.0.0` | `models/schemas.py:2` and everywhere | **Used.** Core data contract. `.dict()` is the v1 API and emits deprecation warnings (§7.1). |
| `python-dotenv` | `>=1.0.0` | `config/settings.py:3,5` | **Used.** Trivial. |
| `chromadb` | `>=0.5.0` | `knowledge/indexer.py:2,17` | **Written to, never read.** **HEAVY** (onnxruntime, an embedding model, a vector store). Removable without behavioural change. |
| `rich` | `>=13.0.0` | `cli.py:6-9` | **Used.** Console rendering only. |
| `pytest` | `>=8.0.0` (dev) | test suite | **Used.** |
| `pytest-asyncio` | `>=0.23.0` (dev) | `pyproject.toml:28` `asyncio_mode = "auto"` | **Used.** |

**Heavy-dependency summary.** Three of eight runtime deps are heavyweight: `torch`, `transformers`,
`chromadb`. Of those, `chromadb` serves no live code path, and `torch` exists only to run one
cross-encoder. Beyond packages, two undeclared runtime requirements:

1. **A model download**: `cross-encoder/nli-deberta-v3-large` (`config/settings.py:9`) fetched from
   the HuggingFace Hub at `NLIModel.__init__` (`utils/nli.py:17-23`) — ~1.6 GB, **no revision pin**,
   needs network on first use.
2. **A CUDA device**: `device=0` hardcoded (`utils/nli.py:20`). On a CPU-only host
   `FactChecker.__init__` (`core/fact_checker.py:19`) fails.

`UNVERIFIED (could not execute)`: neither the download nor the CUDA requirement could be exercised
here; both are read directly off the cited source lines.

---

## 10. Uncertainties

- `UNCERTAIN:` the exact branch in `core/asr_preprocessor.py:140-166` producing the false
  `should_swap=True` in `test_timestamp_parsing`. Settled by instrumenting `_verify_roles`.
- `UNCERTAIN:` whether `_drill_down`'s unbounded recursion (`knowledge/intent_retriever.py:152-174`)
  is reachable in practice. Settled with a populated `INTENTS/` tree and a stub LLM returning a
  cyclic child name.
- `UNCERTAIN:` the precise per-evaluation LLM call count (§5.2) — depends on how many rubrics survive
  NA pre-filtering and how many accuracy atoms the atomiser emits. Settled by instrumenting
  `AnthropicClient.complete` with a counter over a real run.
- `UNVERIFIED (could not execute):` any behaviour requiring `anthropic`, `transformers`, `torch`,
  `chromadb`, a CUDA device, network access, or a populated `INTENTS/` tree.
- `UNVERIFIED (could not execute):` the exact failure from `pip install -e ".[dev]"` given the
  invalid build backend (`pyproject.toml:3`).
