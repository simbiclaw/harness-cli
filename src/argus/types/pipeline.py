"""The evaluation pipeline's data contracts.

A faithful port of `simbiclaw/sim@0c2cccd` `models/schemas.py` — same classes,
same field names, same defaults, same enum members and wire values, same stage
order. The only changes are mechanical: `Optional[X]` written as `X | None`,
`List[X]` as `list[X]`, and mutable literal defaults (`[]`, `{}`) expressed as
`default_factory`, which pydantic already treated as per-instance.

**Nothing here is redesigned, and that is deliberate.** The first attempt at
this port renamed enum members, invented two that exist nowhere upstream,
dropped three that live code emits, and relaxed required fields — including an
atom's own provenance. It was rejected. The contracts a working system already
writes to disk are not the place to improve on it; a port that cannot read the
upstream system's output is a format change wearing a refactor's clothes.

Two constraints this module deliberately does **not** encode:

- **I2 anchoring.** `EvidenceItem` accepts a bare item with neither `turn_id`
  nor `doc_path`, exactly as upstream does. Rejecting that is a real
  requirement, but it belongs to M6, which extends this contract with span and
  quote, and to M12's grounding gate — not to a port whose job is fidelity.
- **Immutability.** Fields are freely assignable, as upstream. When M6 adds
  `intents_sha`, the epoch pin becomes mutable after construction and I4 needs
  `validate_assignment` or `frozen` to be more than a convention. Recorded here
  so M6 inherits the problem knowingly.

Note on the name `RubricItem`: `argus.types.compiler_schemas` also defines one.
That is the SpecificRubric row the 9003 compiler consumes, keyed on a string
id; this is the upstream scoring-sheet row, keyed on an int. They describe the
same 27-row sheet at different maturities. Reconciling them is M15's decision.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

# ══════════════════════════════════════
# Stage -1: ASR preprocessing
# ══════════════════════════════════════


class ASRQuality(str, Enum):
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class TurnFlag(str, Enum):
    INCOMPLETE = "INCOMPLETE"
    ASR_ERROR = "ASR_ERROR"
    ROLE_SWAPPED = "ROLE_SWAPPED"
    NORMAL = "NORMAL"


class CleanTurn(BaseModel):
    id: str
    role: Literal["customer", "agent"]
    text: str  # verbatim — upstream mutates it only by stripping whitespace,
    # which is what lets M6 recover an exact character span (I2)
    flags: list[TurnFlag] = Field(default_factory=list)
    reliability: Literal["high", "low"] = "high"
    timestamp_start: int | None = None
    timestamp_end: int | None = None


class CleanTranscript(BaseModel):
    session_id: str
    turns: list[CleanTurn]
    asr_quality: ASRQuality
    role_swap_detected: bool = False
    low_reliability_turn_ids: list[str] = Field(default_factory=list)


# ══════════════════════════════════════
# Stage 0: knowledge-base context
# ══════════════════════════════════════


class RubricCategory(str, Enum):
    """Column headings on the scoring sheet, not evaluation dimensions."""

    PROCESS = "流程遵守"
    ATTITUDE = "态度规范"
    SKILL = "技能技巧"
    SPECIAL = "特殊项"
    ACCURACY = "准确性"


class RubricItem(BaseModel):
    """One row of the upstream scoring sheet. See the module docstring on the
    name collision with `compiler_schemas.RubricItem`."""

    id: int
    category: RubricCategory
    name: str
    pass_criteria: str
    fail_criteria: str
    na_criteria: str | None = None
    is_weighted: bool = False
    weight: float = 1.0
    always_check: bool = True
    requires_domain_kb: bool = False
    trigger_keywords: list[str] = Field(default_factory=list)
    is_veto: bool = False


class KBContent(BaseModel):
    path: str
    content: str
    level: int
    node_type: Literal["primary", "parent", "sibling"]


class SessionKBContext(BaseModel):
    primary_intent_path: str | None = None
    secondary_intent_paths: list[str] = Field(default_factory=list)
    kb_contents: list[KBContent] = Field(default_factory=list)
    domain_knowledge_summary: str = ""

    all_rubric_items: list[RubricItem] = Field(default_factory=list)
    applicable_rubrics: list[RubricItem] = Field(default_factory=list)

    coverage_score: float = 0.0
    low_coverage_warning: bool = False
    unmatched_entities: list[str] = Field(default_factory=list)


# ══════════════════════════════════════
# Stage 1: structural preprocessing
# ══════════════════════════════════════


class Turn(BaseModel):
    """Note for M6: unlike `CleanTurn`, this carries no timestamps. Stage 1
    drops them, so re-plumbing time through to a span is a real change here."""

    id: str
    role: Literal["customer", "agent"]
    text: str
    reliability: Literal["high", "low"] = "high"
    flags: list[TurnFlag] = Field(default_factory=list)


class Session(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_id: str = "UNKNOWN"
    duration_sec: int | None = None
    turns: list[Turn] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ══════════════════════════════════════
# Stage 2: atomisation
# ══════════════════════════════════════


class ClientAtomType(str, Enum):
    FACT_CLAIM = "事实声明"
    FAULT_DESCRIPTION = "故障描述"
    EXPLICIT_REQUEST = "明确诉求"
    HISTORICAL_CLAIM = "历史声称"
    INFERRED_CLAIM = "推断声称"
    OBJECTION = "异议"


class AgentAtomType(str, Enum):
    BUSINESS_JUDGMENT = "业务判断"
    FACT_STATEMENT = "事实陈述"
    POLICY_CITATION = "政策引用"
    FAULT_DIAGNOSIS = "故障定性"
    SOLUTION_OFFER = "解决方案"
    OPERATION_GUIDE = "操作指引"
    SERVICE_PROMISE = "服务承诺"
    CLOSING_ACTION = "结案行为"
    SERVICE_ACTION = "服务行为"


class Atom(BaseModel):
    id: str
    source_turn_ids: list[str]  # required upstream: this is the atom's anchor
    role: Literal["client", "agent"]
    atom_type: str
    content: str
    decontextualized: str
    reliability: Literal["high", "low"] = "high"
    intent_group: str | None = None


class CoverageStatus(str, Enum):
    RESPONDED = "responded"
    PARTIAL = "partial"
    IGNORED = "ignored"


class CoverageRelation(BaseModel):
    client_atom_id: str
    agent_atom_id: str | None = None
    status: CoverageStatus
    note: str | None = None


# ══════════════════════════════════════
# Stage 3: intent inference
# ══════════════════════════════════════


class IntentSwitch(BaseModel):
    turn_id: str
    from_intent: str
    to_intent: str
    agent_recognized: bool


class IntentInference(BaseModel):
    customer_surface_intent: str
    customer_deep_intent: str
    agent_behavior_pattern: str
    key_tension: str
    intent_switches: list[IntentSwitch] = Field(default_factory=list)
    unresolved_intents: list[str] = Field(default_factory=list)


# ══════════════════════════════════════
# Stage 4: subquestion generation
# ══════════════════════════════════════


class ClaimType(str, Enum):
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


# ══════════════════════════════════════
# Stage 5: fact-checking
# ══════════════════════════════════════


class EvidenceItem(BaseModel):
    """Accepts a bare item, as upstream. M6 adds the anchor; M12 enforces it."""

    turn_id: str | None = None
    doc_path: str | None = None
    text: str
    score: float
    supports: bool


class VerdictResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    NEI = "NEI"
    NA = "NA"
    HUMAN_REVIEW = "human_review"


class Verdict(BaseModel):
    """`score` and `confidence` originate upstream from a model-calling module.
    Neither is marked non-replay-bearing here; M21 must keep them out of the
    replay hash, which is why that hash takes an explicit allowlist (I5)."""

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


# ══════════════════════════════════════
# Stage 6: report
# ══════════════════════════════════════


class DimensionScore(BaseModel):
    name: str
    applicable_count: int
    passed_count: int
    weighted_score: float
    total_weight: float


class QAReport(BaseModel):
    session_id: str
    agent_id: str
    overall_score: float
    grade: str
    veto_triggered: bool
    veto_items: list[str]
    dimension_scores: list[DimensionScore]
    verdicts: list[Verdict]
    questions: list[Subquestion]

    requires_human_review: bool
    human_review_items: list[str]
    asr_quality_warning: bool
    role_swap_detected: bool
    multi_intent_detected: bool
    unresolved_intents: list[str]
    low_kb_coverage_warning: bool

    summary: str
    improvement_suggestions: list[str]
