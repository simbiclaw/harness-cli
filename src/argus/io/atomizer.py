# argus/io/atomizer.py
"""Ported from simbi `core/atomizer.py` @ 929d5a7, re-namespaced. Verbatim."""
import json
import asyncio
from argus.types.pipeline import (
    Session, Atom, CoverageRelation, CoverageStatus,
    SessionKBContext
)
from argus.io.prompts import (
    ATOMIZE_CLIENT_PROMPT, ATOMIZE_AGENT_PROMPT,
    COVERAGE_MATRIX_PROMPT
)


class Atomizer:

    def __init__(self, llm_client):
        self.llm = llm_client

    def _format_transcript(self, session: Session) -> str:
        return "\n".join(
            f"[{t.id}] {'客户' if t.role=='customer' else '客服'}："
            f"{t.text}"
            for t in session.turns
        )

    async def atomize(
        self,
        session: Session,
        kb_context: SessionKBContext
    ) -> tuple[list[Atom], list[Atom]]:

        transcript = self._format_transcript(session)

        # 并行提取双方原子
        client_raw, agent_raw = await asyncio.gather(
            self.llm.complete(
                ATOMIZE_CLIENT_PROMPT.format(
                    transcript=transcript
                )
            ),
            self.llm.complete(
                ATOMIZE_AGENT_PROMPT.format(
                    transcript=transcript,
                    domain_knowledge_summary=(
                        kb_context.domain_knowledge_summary[:1500]
                    )
                )
            )
        )

        client_atoms = [
            Atom(**a) for a in json.loads(client_raw)
        ]
        agent_atoms = [
            Atom(**a) for a in json.loads(agent_raw)
        ]

        return client_atoms, agent_atoms

    async def build_coverage_matrix(
        self,
        client_atoms: list[Atom],
        agent_atoms: list[Atom],
        session: Session,
        kb_context: SessionKBContext
    ) -> list[CoverageRelation]:

        raw = await self.llm.complete(
            COVERAGE_MATRIX_PROMPT.format(
                domain_knowledge_summary=(
                    kb_context.domain_knowledge_summary[:1500]
                ),
                client_atoms_json=json.dumps(
                    [a.dict() for a in client_atoms],
                    ensure_ascii=False
                ),
                agent_atoms_json=json.dumps(
                    [a.dict() for a in agent_atoms],
                    ensure_ascii=False
                ),
                transcript=self._format_transcript(session)
            )
        )

        return [
            CoverageRelation(
                client_atom_id=r["client_atom_id"],
                agent_atom_id=r.get("agent_atom_id"),
                status=CoverageStatus(r["status"]),
                note=r.get("note")
            )
            for r in json.loads(raw)
        ]
