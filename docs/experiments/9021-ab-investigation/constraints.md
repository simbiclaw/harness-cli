# Hard constraints for the A/B integration decision

Derived from `/home/user/harness-cli/CLAUDE.md`, the repo conventions, and the human's
answers. The human left the constraints bracket blank; items marked HUMAN are their
explicit answers, items marked DERIVED are read off the repo.

## HUMAN-CONFIRMED

- **H1. B's domain IS the target domain.** Chinese-language customer-service QA
  (客服质检) is what Argus is for. B's rubric encoding, prompts, entity maps and ASR
  heuristics are therefore ON-TARGET domain assets, not throwaway prototype artifacts.
- **H2. Codebase A is anchored to plan 9020, which is COMPLETE.** A's current branch
  state is the 9020 deliverable (continuous proposer + I8 provenance separation).
  9020 is done; 9002 (the eval pipeline) is the open plan.
- **H3. Whether the torch/chromadb/openai stack can be dropped is UNDECIDED by the
  human** — it is to be settled by evidence, not preference. (Evidence is in
  `report-B.md` §9 and the coordinator's own dependency trace; see C7 below.)

## DERIVED — non-negotiable unless the human overrides

- **C1. The seven invariants I1-I7 and the four layer fences govern every edit to
  `src/argus/`.** Note: `report-A.md` §1 establishes that MOST of these are currently
  enforced only by prose, and three of four fences are vacuously true because the code
  they guard does not exist. A plan may not treat a vacuous fence as a satisfied fence.
- **C2. No write path into INTENTS.** Zero code in `src/argus/` may open an INTENTS file
  for writing (D15). Corrections re-enter via upstream write-time epoch commits.
- **C3. Determinism of the pure stages.** `score(facts, rubric)` and `adjust(raw, history)`
  are pure. Same grounded findings + same rubric version + same anchored precedents must
  produce identical `raw` and `adjusted` (I3). `replay_hash` is a function of grounded
  inputs + anchored precedents only, never of `proposed_score` (I5).
- **C4. Model quarantine.** Model nondeterminism may exist ONLY in S2 (the proposer, in
  `io/`). Any module in `core/` importing an LLM client is an architecture violation (I1).
- **C5. Every finding must anchor to a real transcript span (exact-quote verified) and a
  real INTENTS node at a pinned git-SHA epoch, or be routed to a human as `ungrounded`.
  Findings are never silently dropped** (I2).
- **C6. Tier C decisions stop and ask.** Per `docs/conventions/ask-threshold.md`: any new
  top-level dependency, CLI surface change, config schema change, on-disk format change,
  stdout format change, >100 line deletion, or edit to a path in
  `.claude/sensitive-paths.txt` must go to an "Awaiting Steering" section, not be decided
  by the agent. **The integration decision itself is Tier C several times over.**
- **C7. Dependency policy.** Every direct dependency in `pyproject.toml` needs a dep-vet
  record at `docs/decisions/dep-vet-<pkg>.md` plus a Decision Log entry, enforced by
  `.claude/tests/test_dep_decisions.py`. A's current direct deps: typer, pydantic, pyyaml,
  anthropic, python-dotenv, rich (+ llama-cpp-python optional).
- **C8. Verification floor.** Every milestone needs a runnable Acceptance Test exercising
  an externally observable property; no checkbox flips without an independent adversarial
  CONFIRMED verdict; no implementation without a failing test first.
- **C9. Plan collision.** `docs/exec-plans/active/9002-implement-argus-eval-pipeline.md`
  declares a File Scope covering exactly the modules any integration would touch
  (grounding, corroboration, score, adjust, routing, intents_provider, proposer,
  call_record, schemas + their tests). A structural test fails when two active plans'
  declared scopes intersect. So this work either AMENDS 9002 or SUPERSEDES it; it cannot
  be a new parallel plan touching those paths.
- **C10. Four plans are already active** (9002, 9003-pilot-item18, 9008, 9009). CLAUDE.md
  requires asking the human which to pick up.
- **C11. Promotion rule.** A rule violated twice moves left: documentation -> structural
  test -> hook -> CI gate -> architecture. "Try harder to remember" is not an option.

## ENVIRONMENTAL — true of this container, must be designed around

- **E1. `docs/PRD` is a DANGLING symlink** (`../../papers/PLAN`). The spec CLAUDE.md calls
  "the contract" is not in the clone and cannot be read here.
- **E2. `INTENTS` is a DANGLING symlink** to `/Users/prometheus/workspace/INTENTS`, an
  absolute path on one developer's laptop. It dangles in every clone that is not that
  machine. A `simbiclaw/INTENTS` repo exists (private) and could be attached.
- **E3. The network is restricted.** `pyproject.toml:118` pins an unreachable Tsinghua
  index. No dependency can be installed in this environment; A's test suite was never
  executed during investigation. B's non-transformers tests DID run.
- **E4. No GPU.** `utils/nli.py:20` hardcodes `device=0`.
- **E5. Pre-production.** No uptime constraint, no live users, no data migration risk
  identified. Single operator. This is the one axis where the integration is CHEAP —
  there is nothing running in production to break.

## THE DEPENDENCY EVIDENCE (settles H3)

Traced directly, not inferred:

| Dep | Direct import sites | Verdict |
|---|---|---|
| `openai` | **ZERO** — `grep -rn 'openai\|OpenAI' --include=*.py` returns nothing | **Dead declared dependency. Drop, no risk.** |
| `chromadb` | ONE — `knowledge/indexer.py:2,17` | Its only consumer is **write-only dead code that nothing ever reads** (report-B §4.3). **Drop, no functional loss.** |
| `torch` | **ZERO direct imports** | Present only as a transitive requirement of `transformers`. Its fate follows transformers'. |
| `transformers` | ONE — `utils/nli.py:2,17` (62-line wrapper; `batch_score` is dead) | **KEEP — see below.** |
| `anthropic` | `utils/llm_client.py:3,12` | The actual provider. Already an A dependency. |

**Why `transformers` should be KEPT despite being confined to 62 lines:** the local NLI
entailment path is B's only *non-model* verification instrument. `core/fact_checker.py:55-68`
reaches a PASS/FAIL verdict from NLI scores with the API model **not called at all**
(asserted by `tests/test_fact_checker.py:78`). In A's I6 vocabulary this is an
**independent signal (weight 1.0)**, not a correlated or redundant one. Replacing it with
an LLM call would convert an independent instrument into a model-judged one, collapsing
corroboration toward soft(+)soft = 0 (D5) and weakening the I1 quarantine story rather
than strengthening it. Dropping torch/transformers is cheap in lines and expensive in
epistemics.

## THE SINGLE MOST IMPORTANT CROSS-REPORT FACT

**B already satisfies the hardest invariant A exists to enforce.** Report-B §2.3 establishes
with quoted code that B's model proposes labels, evidence, questions and one routing-only
confidence — and **never a score, weight, dimension roll-up or grade**. All arithmetic is
pure Python over rubric constants (`core/aggregator.py`, 118 lines, model-free by
construction, 4/4 tests passing). B also has **no write path into any intent store**
(report-B §4.3).

So B independently arrived at I3/I7-shaped discipline and at D15. This is the fact that
most strongly constrains which integration strategies are honest.

**The counterweight:** B has no anchoring/quote-verification (I2), no epoch pinning (I4),
no replay mechanism at all (I5 — no cache, no seed, no run manifest, no input hash; a
report cannot be re-derived without re-running every model call), and nondeterminism
spread across nine of fourteen modules (I1 — not quarantined to a proposer layer).
B also has two confirmed blocking crashes and one confirmed correctness bug (a
false-positive role swap that silently inverts every evaluation).
