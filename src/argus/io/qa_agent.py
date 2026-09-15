# argus/io/qa_agent.py
"""Ported from simbi `agents/qa_agent.py` @ 929d5a7 — **rewired**, per M7.

B's `run()` chained Stage -1 (ASR parse) → Stage 0 (kb context) → Stage 1
(session build) → Stages 2–6. The first three are dropped: their products are
supplied. The orchestrator's wiring is: call record → `Session`
(`argus.io.call_record`); Provider → `SessionKBContext` (until 9025 lands, a
stub built by the caller); then the proposer's own stages — atoms, the
within-call intent step, questions, verification, score — and it keeps its
shape as the single entry point.

Three pieces of dropped modules are **absorbed here as private functions**,
under the same rationale the plan states for the aggregator: the seven-module
list is binding, and each absorbed piece is the proposal half's own work, not
a producer decision.

- `_infer_intent` — B's `core/intent_inferrer.py`, the consumer's own
  within-call proposal step. Its output feeds the implied-question prompt and
  the report's `multi_intent_detected`/`unresolved_intents`, exactly as B fed
  them; the call-level attribution stays with the manifest.
- `_filter_na_rubrics` / `_llm_check_applicability` — B's
  `core/kb_context_builder.py` Step C. This ran inside B before question
  generation and shaped the M4 baseline (rules whose trigger keywords never
  appear in the transcript generate no question); a port that trusts
  `applicable_rubrics` blindly diverges from it. It is idempotent over an
  already-filtered set of `always_check`/keyword-verified rules; what happens
  when 9025's Provider supplies compiled applicability that this transcript
  check would drop is that milestone's reconciliation, noted here.
- `_aggregate` — B's `core/aggregator.py` (Stage 6), the proposal half's own
  score assembly. Later milestones replace it with `core/score` per the
  two-stage contract.

Dropped with the ingest stages and not absorbed: the human-review callback
(the rewired signature receives nothing to call; `human_items` is still
computed — the summary prompt counts them), and B's
`Preprocessor._extract_metadata` (it parsed turn *text* for phone/company
strings into `session.metadata`, which nothing downstream reads; the call
record is the structure now, and `build_session` does not re-derive it).

`nli_model` is accepted because the interface pins it, but the constructed
`nli` object is authoritative: production constructs
`argus.io.nli.NLIModel(nli_model_name)` and passes it; tests pass a fake.
"""
import asyncio
import json
import logging

from argus.types.pipeline import (
    QAReport, Session, SessionKBContext, Atom, CoverageRelation,
    IntentInference, IntentSwitch, Verdict, Subquestion, DimensionScore,
    VerdictResult,
)
from argus.io.prompts import (
    INTENT_INFERENCE_PROMPT, REPORT_SUMMARY_PROMPT,
)
from argus.io.atomizer import Atomizer
from argus.io.question_generator import QuestionGenerator
from argus.io.fact_checker import FactChecker

logger = logging.getLogger(__name__)

GRADE_THRESHOLDS = {
    90: "优秀", 80: "良好", 60: "合格"
}


def run_session(
    session: Session,
    kb_context: SessionKBContext,
    llm_client,
    nli_model: str,
    nli,
) -> QAReport:
    """Run the proposer's stages over a consumer-built session.

    `nli_model` names the cross-encoder for whoever constructs `nli`; the
    constructed object is what the pipeline calls.
    """
    return asyncio.run(
        _run_pipeline(session, kb_context, llm_client, nli)
    )


async def _run_pipeline(
    session: Session,
    kb_context: SessionKBContext,
    llm_client,
    nli,
) -> QAReport:

    logger.info(f"[{session.session_id}] Pipeline start")

    # ── Stage 0 remainder: NA 预过滤 (absorbed) ──────────────
    # B's Stage 0 filtered `applicable_rubrics` before any question was
    # proposed; the check is the proposer's own within-call applicability
    # decision. Runs on a copy — the caller's context object is not mutated.
    full_text = "\n".join(
        f"{'客户' if t.role=='customer' else '客服'}：{t.text}"
        for t in session.turns
    )
    applicable = await _filter_na_rubrics(
        kb_context.applicable_rubrics, full_text, llm_client
    )
    kb_context = kb_context.model_copy(
        update={"applicable_rubrics": applicable}
    )
    logger.info(
        f"规则适用情况: {len(applicable)}/"
        f"{len(kb_context.all_rubric_items)} 条适用"
    )

    # ── Stage 2 ──────────────────────────────────────
    logger.info("Stage 2: Atomization")
    atomizer = Atomizer(llm_client)
    client_atoms, agent_atoms = await atomizer.atomize(
        session, kb_context
    )
    coverage_matrix = await atomizer.build_coverage_matrix(
        client_atoms, agent_atoms, session, kb_context
    )
    unresponded_count = sum(
        1 for r in coverage_matrix
        if r.status.value in ["partial", "ignored"]
    )
    logger.info(
        f"Atoms: {len(client_atoms)}C / {len(agent_atoms)}A, "
        f"Unresponded: {unresponded_count}"
    )

    # ── Stage 3 (absorbed: the consumer's own proposal step) ─
    logger.info("Stage 3: Intent inference")
    intent = await _infer_intent(
        llm_client, session, client_atoms, agent_atoms,
        coverage_matrix, kb_context
    )

    # ── Stage 4 ──────────────────────────────────────
    logger.info("Stage 4: Question generation (3 paths)")
    generator = QuestionGenerator(llm_client)
    questions = await generator.generate_all(
        session.turns, agent_atoms, client_atoms,
        coverage_matrix, intent, kb_context
    )
    literal_count = sum(1 for q in questions if q.q_type == "literal")
    implied_count = sum(1 for q in questions if q.q_type == "implied")
    logger.info(
        f"Questions: {literal_count} literal, {implied_count} implied"
    )

    # ── Stage 5 ──────────────────────────────────────
    logger.info("Stage 5: Fact-checking (path A)")
    checker = FactChecker(nli, llm_client)
    verdicts = await checker.verify_all(
        questions, session, kb_context
    )

    human_items = [v for v in verdicts if v.requires_human_review]

    # ── Stage 6 ──────────────────────────────────────
    logger.info("Stage 6: Aggregation & report")
    summary_raw = await llm_client.complete(
        REPORT_SUMMARY_PROMPT.format(
            # The live template is the "完整版" that shadows the dead first
            # definition in io/prompts.py, which needs seven keys. The caller
            # was written against the dead one, which needs five. Two of the
            # missing ones are results this stage has not computed yet — the
            # summary is written before `_aggregate` runs — so they are
            # marked pending the same way `overall_score` already was.
            # (`grade` is a label and `veto_triggered` a flag; neither is a
            # score, but both share `overall_score`'s reason for being unset
            # here.)
            overall_score="待计算",
            grade="待计算",
            veto_triggered="待计算",
            dimension_scores_json="{}",
            failed_items_json=json.dumps(
                [v.question_id for v in verdicts
                 if v.result.value == "fail"],
                ensure_ascii=False
            ),
            human_review_count=len(human_items),
            unresolved_intents=intent.unresolved_intents
        )
    )
    summary_data = json.loads(summary_raw)

    report = _aggregate(
        verdicts=verdicts,
        questions=questions,
        intent=intent,
        kb_context=kb_context,
        summary=summary_data["summary"],
        suggestions=summary_data["improvement_suggestions"],
        session=session
    )

    logger.info(
        f"[{session.session_id}] Done. Score={report.overall_score} "
        f"Grade={report.grade}"
    )
    return report


# ── absorbed: core/intent_inferrer.py ─────────────────────────


async def _infer_intent(
    llm,
    session: Session,
    client_atoms: list[Atom],
    agent_atoms: list[Atom],
    coverage_matrix: list[CoverageRelation],
    kb_context: SessionKBContext
) -> IntentInference:

    unresponded = [
        r for r in coverage_matrix
        if r.status.value in ["partial", "ignored"]
    ]
    atom_map = {a.id: a for a in client_atoms}
    unresponded_atoms = [
        atom_map[r.client_atom_id]
        for r in unresponded
        if r.client_atom_id in atom_map
    ]

    transcript = "\n".join(
        f"[{t.id}] {'客户' if t.role=='customer' else '客服'}"
        f"：{t.text}"
        for t in session.turns
    )

    raw = await llm.complete(
        INTENT_INFERENCE_PROMPT.format(
            transcript=transcript,
            client_atoms_json=json.dumps(
                [a.dict() for a in client_atoms],
                ensure_ascii=False
            ),
            agent_atoms_json=json.dumps(
                [a.dict() for a in agent_atoms],
                ensure_ascii=False
            ),
            unresponded_atoms_json=json.dumps(
                [a.dict() for a in unresponded_atoms],
                ensure_ascii=False
            ),
            domain_knowledge_summary=(
                kb_context.domain_knowledge_summary[:1000]
            )
        )
    )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return IntentInference(
            customer_surface_intent="解析失败",
            customer_deep_intent="解析失败",
            agent_behavior_pattern="解析失败",
            key_tension="解析失败"
        )

    return IntentInference(
        customer_surface_intent=data.get(
            "customer_surface_intent", ""
        ),
        customer_deep_intent=data.get(
            "customer_deep_intent", ""
        ),
        agent_behavior_pattern=data.get(
            "agent_behavior_pattern", ""
        ),
        key_tension=data.get("key_tension", ""),
        intent_switches=[
            IntentSwitch(**sw)
            for sw in data.get("intent_switches", [])
        ],
        unresolved_intents=data.get("unresolved_intents", [])
    )


# ── absorbed: core/kb_context_builder.py Step C ───────────────


async def _filter_na_rubrics(
    rubrics: list,
    transcript_text: str,
    llm,
) -> list:
    """
    NA 预过滤：对有 na_criteria 且非 always_check 的规则项，
    根据对话内容判断是否适用。

    过滤逻辑：
      always_check=True  → 直接保留，无需判断
      na_criteria=None   → 直接保留，无 NA 条件
      其余               → 用规则关键词或 LLM 判断是否触发

    目的：减少 Stage 4 生成无效子问题，
          减少 Stage 5 对 NA 项的无效计算。
    """
    applicable = []

    for rubric in rubrics:
        # always_check 项直接保留
        if rubric.always_check:
            applicable.append(rubric)
            continue

        # 无 NA 条件直接保留
        if not rubric.na_criteria:
            applicable.append(rubric)
            continue

        # 有触发关键词：用关键词快速判断
        if rubric.trigger_keywords:
            if any(kw in transcript_text for kw in rubric.trigger_keywords):
                applicable.append(rubric)
            else:
                logger.debug(
                    f"规则{rubric.id}({rubric.name}): "
                    f"关键词未命中，标记为 NA"
                )
            continue

        # 无关键词但有 NA 条件：LLM 判断
        is_applicable = await _llm_check_applicability(
            llm, rubric, transcript_text
        )
        if is_applicable:
            applicable.append(rubric)
        else:
            logger.debug(
                f"规则{rubric.id}({rubric.name}): LLM 判断为 NA"
            )

    return applicable


async def _llm_check_applicability(
    llm,
    rubric,
    transcript_text: str
) -> bool:
    """
    对无触发关键词但有 NA 条件的规则项，
    用 LLM 判断本通电话是否触发该规则。

    例：规则7（问题升级）的 NA 条件为"电话中未涉及到问题升级"，
        若对话中没有"升级/远程/回访/工单"等内容，
        该规则应标记为 NA，不生成子问题。
    """
    prompt = f"""
判断以下质检规则是否适用于本通电话。

质检规则：{rubric.name}
NA标准（以下情况不适用）：{rubric.na_criteria}

对话内容摘要（前500字）：
{transcript_text[:500]}

若对话满足 NA 标准，该规则不适用，返回 false。
否则返回 true。

输出JSON：{{"applicable": true/false, "reason": "..."}}
"""
    try:
        raw = await llm.complete(prompt)
        result = json.loads(raw)
        return result.get("applicable", True)
    except Exception:
        # 解析失败时保守处理：保留该规则
        return True


# ── absorbed: core/aggregator.py (Stage 6) ────────────────────


def _aggregate(
    verdicts: list[Verdict],
    questions: list[Subquestion],
    intent: IntentInference,
    kb_context,
    summary: str,
    suggestions: list[str],
    session: Session
) -> QAReport:

    q_map = {q.id: q for q in questions}
    v_map = {v.question_id: v for v in verdicts}

    # ── 维度分组 ──────────────────────────────────────
    dim_groups: dict[str, list[Verdict]] = {}
    for v in verdicts:
        q = q_map.get(v.question_id)
        if not q:
            continue
        dim = q.dimension
        dim_groups.setdefault(dim, []).append(v)

    # ── 各维度得分 ────────────────────────────────────
    dimension_scores = []
    for dim, dim_verdicts in dim_groups.items():
        # NA项不计入
        applicable = [
            v for v in dim_verdicts
            if v.result != VerdictResult.NA
        ]
        passed = [
            v for v in applicable
            if v.result == VerdictResult.PASS
        ]
        total_weight = sum(v.weight for v in applicable)
        weighted_score = sum(
            v.score * v.weight for v in applicable
        )

        dimension_scores.append(DimensionScore(
            name=dim,
            applicable_count=len(applicable),
            passed_count=len(passed),
            weighted_score=weighted_score,
            total_weight=total_weight
        ))

    # ── 总分（0-100）────────────────────────────────
    total_w = sum(d.total_weight for d in dimension_scores)
    total_s = sum(d.weighted_score for d in dimension_scores)
    overall = round((total_s / total_w * 100) if total_w > 0 else 0, 1)

    # ── 一票否决检测 ──────────────────────────────────
    veto_triggered = False
    veto_items = []
    for v in verdicts:
        q = q_map.get(v.question_id)
        if q and q.is_veto and v.result == VerdictResult.FAIL:
            veto_triggered = True
            veto_items.append(v.question_id)
            overall = 0.0  # 一票否决归零

    # ── 评级 ─────────────────────────────────────────
    grade = "不合格"
    for threshold, label in sorted(
        GRADE_THRESHOLDS.items(), reverse=True
    ):
        if overall >= threshold:
            grade = label
            break

    # ── 人工复核汇总 ──────────────────────────────────
    human_items = [
        v.question_id for v in verdicts
        if v.requires_human_review
    ]

    return QAReport(
        session_id=session.session_id,
        agent_id=session.agent_id,
        overall_score=overall,
        grade=grade,
        veto_triggered=veto_triggered,
        veto_items=veto_items,
        dimension_scores=dimension_scores,
        verdicts=verdicts,
        questions=questions,
        requires_human_review=len(human_items) > 0,
        human_review_items=human_items,
        multi_intent_detected=(
            len(intent.intent_switches) > 0
        ),
        unresolved_intents=intent.unresolved_intents,
        low_kb_coverage_warning=kb_context.low_coverage_warning,
        summary=summary,
        improvement_suggestions=suggestions
    )
