"""Evaluation contracts — atoms, questions, evidence and verdicts.

Ported from `simbiclaw/sim@0c2cccd` `models/schemas.py` under 9021 M5.

The stage decomposition these types encode is the part worth preserving:
atoms carry which turns they came from, questions carry a positive and a
negative hypothesis so a non-model instrument can judge them, and evidence
carries provenance. That chain is what makes a verdict traceable back to a
span of the call rather than to a model's say-so.

`EvidenceItem` is the anchor slot I2 attaches to. It is constrained here to
name a source — a turn or a document — because evidence that names neither
cannot be anchored by any later gate, and a finding that cannot be anchored
must be routed to a human rather than silently scored.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ClientAtomType(str, Enum):
    FACT_CLAIM = "事实声明"
    FAULT_REPORT = "故障描述"
    EXPLICIT_REQUEST = "明确诉求"
    HISTORY_CLAIM = "历史声称"
    INFERRED_CLAIM = "推断声称"
    OBJECTION = "异议"


class AgentAtomType(str, Enum):
    BUSINESS_JUDGMENT = "业务判断"
    FACT_STATEMENT = "事实陈述"
    POLICY_CITATION = "政策引用"
    FAULT_DIAGNOSIS = "故障定性"
    SOLUTION = "解决方案"
    OPERATION_GUIDE = "操作指引"
    SERVICE_COMMITMENT = "服务承诺"
    CLOSING_ACTION = "结案行为"
    SERVICE_BEHAVIOR = "服务行为"


class Atom(BaseModel):
    """One decontextualised proposition lifted out of the transcript."""

    id: str
    source_turn_ids: list[str] = Field(default_factory=list)
    role: Literal["client", "agent"]
    atom_type: str
    content: str
    decontextualized: str
    reliability: Literal["high", "low"] = "high"
    intent_group: str | None = None


class CoverageStatus(str, Enum):
    COVERED = "covered"
    PARTIAL = "partial"
    UNCOVERED = "uncovered"


class CoverageRelation(BaseModel):
    """Whether an agent atom answers a client atom."""

    client_atom_id: str
    agent_atom_id: str | None = None
    status: CoverageStatus
    note: str | None = None


class ClaimType(str, Enum):
    """Which instrument can judge this claim.

    `DIALOGUE_CONSISTENCY` is judgeable against the transcript alone.
    `EXTERNAL_FACT` and `INTERNAL_POLICY` need a document. `ASR_UNCERTAIN`
    rests on text the recogniser was not confident about and routes to a human.
    """

    DIALOGUE_CONSISTENCY = "dialogue_consistency"
    EXTERNAL_FACT = "external_fact"
    INTERNAL_POLICY = "internal_policy"
    ASR_UNCERTAIN = "asr_uncertain"


class ImpliedQType(str, Enum):
    DOMAIN_KNOWLEDGE = "DOMAIN_KNOWLEDGE"
    CONTEXT = "CONTEXT"
    IMPLICIT_MEANING = "IMPLICIT_MEANING"
    STATISTICAL_RIGOR = "STATISTICAL_RIGOR"


class QuestionSource(str, Enum):
    RUBRIC_DRIVEN = "rubric_driven"
    ATOM_LITERAL = "atom_literal"
    ATOM_IMPLIED = "atom_implied"


class Subquestion(BaseModel):
    """A yes/no question plus the hypothesis pair a non-model check can score.

    The `hypothesis_pos` / `hypothesis_neg` pair is what lets an entailment
    model judge this without the proposer being consulted again — an
    independent instrument in I6's sense rather than a second model-judged
    reading of the same span.
    """

    id: str
    question: str
    q_type: Literal["literal", "implied"]
    source: QuestionSource
    claim_type: ClaimType
    rubric_id: int | None = None
    source_atom_ids: list[str] = Field(default_factory=list)
    hypothesis_pos: str
    hypothesis_neg: str
    dimension: str
    is_veto: bool = False
    implied_q_type: ImpliedQType | None = None
    applicability: Literal["applicable", "NA"] = "applicable"
    na_reason: str | None = None


class EvidenceItem(BaseModel):
    """A piece of evidence, and where it came from.

    Exactly one provenance arm is expected: `turn_id` for something said in the
    call, `doc_path` for something a document says. Neither is a construction
    error — see the module docstring.
    """

    turn_id: str | None = None
    doc_path: str | None = None
    text: str
    score: float
    supports: bool

    @model_validator(mode="after")
    def _requires_provenance(self) -> EvidenceItem:
        if self.turn_id is None and self.doc_path is None:
            raise ValueError(
                "EvidenceItem names no source: set turn_id or doc_path. "
                "Evidence that names neither cannot be anchored (I2)."
            )
        return self


class VerdictResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    NEI = "NEI"
    NA = "NA"
    HUMAN_REVIEW = "human_review"


class Verdict(BaseModel):
    """One judged subquestion.

    `weight` is carried so a verdict can be read on its own, but it is the
    rubric's property and `score()` reads it from the rubric it is passed —
    not from here. See `argus.types.rubric`.
    """

    question_id: str
    rubric_id: int | None = None
    result: VerdictResult
    confidence: float
    score: float
    weight: float = 1.0
    evidence: list[EvidenceItem] = Field(default_factory=list)
    requires_human_review: bool = False
    review_reason: str | None = None
    checking_path: Literal["A", "B", "C"] = "A"
