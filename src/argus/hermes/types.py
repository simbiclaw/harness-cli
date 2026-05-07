"""Hermes domain types — ActionDescriptor and action-tier discriminated types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ActionTier(StrEnum):
    A = "A"  # Read-only: DOM inspection, screenshot, navigation
    B = "B"  # Confirmed: user explicitly accepted, Hermes executes
    C = "C"  # Autonomous: Hermes acts without per-action confirmation


@dataclass
class ActionDescriptor:
    """Every Hermes action MUST have an explicit tier. No default."""

    tier: ActionTier
    name: str
    target: str
    params: dict[str, Any] | None = None
    confirmation_id: str | None = None


# Tier-C allowlist: call sites allowed to dispatch Tier-C actions.
# Starts empty per PRODUCT_SENSE.md Hermes tiebreakers.
TIER_C_ALLOWLIST: set[str] = set()
