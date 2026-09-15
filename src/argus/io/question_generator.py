# argus/io/question_generator.py
"""Ported from simbi `core/question_generator.py` @ 929d5a7, re-namespaced.

Verbatim except one deletion: the source's dead import
`from config.rubric_items import RUBRIC_ITEMS, RUBRIC_BY_ID`. Neither name is
used in the module body — the generator reads its rubrics from
`kb_context.applicable_rubrics` / `kb_context.all_rubric_items` — and
`config/rubric_items.py` is not on M7's import list. (The weight lookup that
*does* read B's config table lives in the fact-checker; the port rebuilds it
from the kb context there — see io/fact_checker.py.)
"""
import json
import asyncio
from argus.types.pipeline import (
    Subquestion, SessionKBContext, Atom,
    CoverageRelation, IntentInference,
    ClaimType, QuestionSource
)
from argus.io.prompts import (
    RUBRIC_TO_QUESTION_PROMPT,
    GENERATE_ACCURACY_LITERAL_Q_PROMPT,
    GENERATE_IMPLIED_Q_PROMPT
)


class QuestionGenerator:

    def __init__(self, llm_client):
        self.llm = llm_client
        self._q_counter = {"RQ": 0, "LQ": 0, "IQ": 0}

    def _next_id(self, prefix: str) -> str:
        self._q_counter[prefix] += 1
        return f"{prefix}-{self._q_counter[prefix]:02d}"

    async def generate_all(
        self,
        session_turns: list,
        agent_atoms: list[Atom],
        client_atoms: list[Atom],
        coverage_matrix: list[CoverageRelation],
        intent: IntentInference,
        kb_context: SessionKBContext
    ) -> list[Subquestion]:

        # 三路并行生成
        rubric_qs, literal_qs, implied_qs = await asyncio.gather(
            self._rubric_driven(
                session_turns, agent_atoms, kb_context
            ),
            self._atom_driven_literal(
                agent_atoms, kb_context
            ),
            self._atom_driven_implied(
                coverage_matrix, client_atoms,
                intent, kb_context
            )
        )

        return rubric_qs + literal_qs + implied_qs

    async def _rubric_driven(
        self,
        turns: list,
        agent_atoms: list[Atom],
        kb_context: SessionKBContext
    ) -> list[Subquestion]:
        """路径一：规则驱动"""
        questions = []
        tasks = []

        for rubric in kb_context.applicable_rubrics:
            relevant_atoms = [
                a for a in agent_atoms
                if any(kw in a.decontextualized
                       for kw in rubric.trigger_keywords)
            ] if rubric.trigger_keywords else agent_atoms[:5]

            relevant_turns = [
                f"[{t.id}] {t.text}"
                for t in turns
                if any(kw in t.text
                       for kw in rubric.trigger_keywords)
            ][:5] if rubric.trigger_keywords else [
                f"[{t.id}] {t.text}" for t in turns[:5]
            ]

            tasks.append(self.llm.complete(
                RUBRIC_TO_QUESTION_PROMPT.format(
                    rubric_id=rubric.id,
                    rubric_name=rubric.name,
                    pass_criteria=rubric.pass_criteria,
                    fail_criteria=rubric.fail_criteria,
                    na_criteria=rubric.na_criteria or "无",
                    relevant_agent_atoms=json.dumps(
                        [a.dict() for a in relevant_atoms[:3]],
                        ensure_ascii=False
                    ),
                    relevant_turns="\n".join(relevant_turns)
                )
            ))

        results = await asyncio.gather(*tasks)

        for rubric, raw in zip(kb_context.applicable_rubrics, results):
            r = json.loads(raw)
            if r["applicability"] == "NA":
                continue
            questions.append(Subquestion(
                id=self._next_id("RQ"),
                question=r["question"],
                q_type="literal",
                source=QuestionSource.RUBRIC_DRIVEN,
                claim_type=ClaimType.DIALOGUE_CONSISTENCY,
                rubric_id=rubric.id,
                hypothesis_pos=r["hypothesis_pos"],
                hypothesis_neg=r["hypothesis_neg"],
                dimension=rubric.category.value,
                is_veto=rubric.is_veto,
                applicability="applicable",
                source_atom_ids=[
                    a.id for a in agent_atoms[:3]
                ]
            ))

        return questions

    async def _atom_driven_literal(
        self,
        agent_atoms: list[Atom],
        kb_context: SessionKBContext
    ) -> list[Subquestion]:
        """路径二：业务准确性子问题"""
        questions = []
        accuracy_atom_types = [
            "政策引用", "故障定性", "业务判断", "事实陈述"
        ]
        accuracy_atoms = [
            a for a in agent_atoms
            if a.atom_type in accuracy_atom_types
        ]

        if not accuracy_atoms or not kb_context.domain_knowledge_summary:
            return questions

        accuracy_rubrics_text = "\n".join(
            f"规则{r.id}: {r.name} - {r.pass_criteria[:100]}"
            for r in kb_context.all_rubric_items
            if r.requires_domain_kb
        )

        tasks = [
            self.llm.complete(
                GENERATE_ACCURACY_LITERAL_Q_PROMPT.format(
                    agent_atom_json=json.dumps(
                        a.dict(), ensure_ascii=False
                    ),
                    kb_content=kb_context.domain_knowledge_summary[:2000],
                    accuracy_rubrics=accuracy_rubrics_text
                )
            )
            for a in accuracy_atoms
        ]

        results = await asyncio.gather(*tasks)

        for atom, raw in zip(accuracy_atoms, results):
            r = json.loads(raw)
            questions.append(Subquestion(
                id=self._next_id("LQ"),
                question=r["question"],
                q_type="literal",
                source=QuestionSource.ATOM_LITERAL,
                claim_type=ClaimType(r.get(
                    "claim_type", "internal_policy"
                )),
                hypothesis_pos=r["hypothesis_pos"],
                hypothesis_neg=r["hypothesis_neg"],
                dimension="准确性",
                source_atom_ids=[atom.id]
            ))

        return questions

    async def _atom_driven_implied(
        self,
        coverage_matrix: list[CoverageRelation],
        client_atoms: list[Atom],
        intent: IntentInference,
        kb_context: SessionKBContext
    ) -> list[Subquestion]:
        """路径三：Implied子问题"""
        unresponded = [
            r for r in coverage_matrix
            if r.status.value in ["partial", "ignored"]
        ]
        if not unresponded:
            return []

        atom_map = {a.id: a for a in client_atoms}
        unresponded_atoms = [
            atom_map[r.client_atom_id]
            for r in unresponded
            if r.client_atom_id in atom_map
        ]

        rubrics_summary = "\n".join(
            f"规则{r.id}: {r.name}"
            for r in kb_context.applicable_rubrics[:10]
        )

        raw = await self.llm.complete(
            GENERATE_IMPLIED_Q_PROMPT.format(
                unresponded_atoms_json=json.dumps(
                    [a.dict() for a in unresponded_atoms],
                    ensure_ascii=False
                ),
                intent_inference_json=json.dumps(
                    intent.dict(), ensure_ascii=False
                ),
                domain_knowledge_summary=(
                    kb_context.domain_knowledge_summary[:1500]
                ),
                qa_rubrics_summary=rubrics_summary
            )
        )

        questions = []
        for item in json.loads(raw):
            questions.append(Subquestion(
                id=self._next_id("IQ"),
                question=item["question"],
                q_type="implied",
                source=QuestionSource.ATOM_IMPLIED,
                claim_type=ClaimType.DIALOGUE_CONSISTENCY,
                hypothesis_pos=item["hypothesis_pos"],
                hypothesis_neg=item["hypothesis_neg"],
                dimension="隐性服务能力",
                implied_q_type=item["implied_q_type"],
                source_atom_ids=[item.get("source_atom_id", "")],
                applicability="applicable"
            ))

        return questions
