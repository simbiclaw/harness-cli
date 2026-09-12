"""Transcript contracts — what a call looks like once ASR output is cleaned.

Ported from `simbiclaw/sim@0c2cccd` `models/schemas.py` under 9021 M5.

One property is load-bearing and easy to lose in a refactor: `CleanTurn.text`
is the raw text, unmodified. The upstream preprocessor mutates it only by
stripping surrounding whitespace, which is what lets M6 recover an exact
character span back into the source transcript. Any normalisation added here —
punctuation folding, full-width conversion, stutter removal — breaks I2's
exact-quote verification for every finding that rests on a turn.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ASRQuality(str, Enum):
    """Banding for how much of the transcript is trustworthy."""

    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class TurnFlag(str, Enum):
    """Per-turn ASR annotations."""

    INCOMPLETE = "incomplete"
    UNCERTAIN = "uncertain"
    STUTTER = "stutter"


class CleanTurn(BaseModel):
    """One speaker turn. `text` is verbatim — see the module docstring."""

    id: str
    role: Literal["customer", "agent"]
    text: str
    flags: list[TurnFlag] = Field(default_factory=list)
    reliability: Literal["high", "low"] = "high"
    timestamp_start: int | None = None
    timestamp_end: int | None = None


class CleanTranscript(BaseModel):
    """A whole call, post-cleaning, with the quality signals downstream reads."""

    session_id: str
    turns: list[CleanTurn] = Field(default_factory=list)
    asr_quality: ASRQuality = ASRQuality.GOOD
    role_swap_detected: bool = False
    low_reliability_turn_ids: list[str] = Field(default_factory=list)
