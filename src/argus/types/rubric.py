"""Rubric contracts — the human scoring sheet as a typed structure.

Ported from `simbiclaw/sim@0c2cccd` `config/rubric_items.py` and
`models/schemas.py` under 9021 M5.

Two things this module deliberately does not decide:

- **How many items are scored.** The sheet carries 27 rows; items 6 and 7 are
  excluded for data dependency, so 25 are scored. That exclusion is expressed
  as `data_dependency`, not by deleting rows, so the reason stays auditable and
  restoring them is a gate change rather than a rubric edit.
- **What a weight means at runtime.** `weight` is carried here because it is
  the rubric's own property. It reaches the arithmetic through `score()`, which
  takes the rubric as an argument — never stamped onto a verdict inside the
  proposer quarantine (I3).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RubricCategory(str, Enum):
    """The scoring sheet's own column headings.

    These are *columns on the sheet*, not evaluation dimensions. The mapping
    from category to dimension is the align map's job and is not one-to-one:
    ACCURACY splits across three dimensions by primary failure axis.
    """

    PROCESS = "流程遵守"
    ATTITUDE = "态度规范"
    SKILL = "技能技巧"
    SPECIAL = "特殊项"
    ACCURACY = "准确性"


class RubricItem(BaseModel):
    """One scored criterion."""

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

    # Why this item cannot be scored from a transcript alone, when it cannot.
    # Set on items 6 and 7, which need a service-record store and a workflow
    # system Argus does not read. An item carrying this never reaches the
    # denominator; it is not deleted, so the exclusion stays auditable.
    data_dependency: str | None = None

    @property
    def scorable(self) -> bool:
        """False when an external system this evaluator cannot reach is needed."""
        return self.data_dependency is None
