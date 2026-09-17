"""Argus's own scoring vocabulary (9031 M2).

These three types formerly arrived via the ported contract
(`types/pipeline.py`). The port is retired — the human ruling of 2026-09-16
retires all upstream-ported code — and what `core/` consumes is now
Argus-owned. Nothing here is a faithful copy of anything: the shapes serve
the spec's stages, and no upstream snapshot constrains them.

`HUMAN_REVIEW` in particular changes status: under the port it was a deviation
signed against an upstream pin. As an Argus-native type it is simply the
disposition `core/score.py` keys `_CREDIT` and `_DEFERRALS` on, and the spec's
§3.4 calls `meta_verdict: escalate` — a verdict that must go to a human.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class VerdictResult(str, Enum):
    """The outcome a scored criterion can carry."""

    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    NEI = "NEI"
    NA = "NA"
    HUMAN_REVIEW = "human_review"


class RubricCategory(str, Enum):
    """Column headings on the QA scoring sheet — not evaluation dimensions.
    The four dimensions live in the compiled `_rubric/` gates; this enum names
    the source rubric's own 分类 column."""

    PROCESS = "流程遵守"
    ATTITUDE = "态度规范"
    SKILL = "技能技巧"
    SPECIAL = "特殊项"
    ACCURACY = "准确性"


class RubricItem(BaseModel):
    """One row of the QA scoring sheet. Distinct from
    `compiler_schemas.RubricItem` (the compiled judgment node); this is the
    readable scoring-sheet row keyed on an int, which `core/score.py`'s Rubric
    carries."""

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
