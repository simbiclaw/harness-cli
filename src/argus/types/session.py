"""The S1 read shape (9031 M2).

`io/call_record.py` builds these from the producer's call record and S2
consumes them. They formerly arrived via the ported contract
(`types/pipeline.py`); the port is retired, so the consumer's read shape is
Argus-owned. These are deliberately minimal — anything S1 does not yet
populate stays out until the Provider (M3) and span addressing (M4) land.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class Turn(BaseModel):
    """One speaker turn of a call. The former 'no timestamps' note is
    superseded: 9031 M4 re-plumbs the record's positional data
    (segments/start_sec/end_sec) for span addressing."""

    id: str
    role: Literal["customer", "agent"]
    text: str


class Session(BaseModel):
    """A call as the pipeline sees it: identity, duration, ordered turns."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_id: str = "UNKNOWN"
    duration_sec: int | None = None
    turns: list[Turn] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
