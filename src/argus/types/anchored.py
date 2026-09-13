"""Evidence anchored to an exact location in the source transcript (9021 M6).

I2: every finding references a real transcript span, exact-quote verified, and
a real INTENTS node at the pinned git-SHA epoch — or it is moved to the
`ungrounded` bucket and routed to a human. Findings are never silently dropped.

This module supplies the slot. The gate that enforces it is M12's
`core/grounding.py`; what lives here is the shape a finding must have before
that gate can say anything about it, plus the one check that is a property of
the record itself rather than of the pipeline: does the quote actually appear
where the span says it does.

Three decisions, each made deliberately:

**Beside the port, not inside it.** `types/pipeline.py` is a faithful copy of
the upstream contract, and M5's snapshot test rejects any field upstream does
not have. Putting `span` there would fail that test, correctly. The port stays
a port; the Argus-side extension lives here.

**A character span, not a timestamp.** The plan's prose says to re-plumb
timestamps through stage 1. Stage-1 `Turn` carries none — but the deeper point
is that a timestamp cannot satisfy exact-quote verification. Seconds locate
audio; I2 needs offsets into the text that was actually read. Timestamps remain
useful for audio alignment and are a different milestone's concern.

**Frozen.** Once a record carries `intents_sha`, a plain attribute write would
let it claim an epoch it was never derived against, and I4's pinned referent
would be a convention rather than a constraint. The failure would surface only
on replay, long after the evidence was written.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

# A git object name: exactly 40 lowercase hex characters. "latest", a short
# sha, or an empty string would make the pin decorative.
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class Span(BaseModel):
    """A half-open character range `[start, end)` into the raw transcript.

    Half-open so `transcript[start:end]` is the quote directly, with no
    off-by-one at the call site. Empty and inverted ranges are rejected: a
    range that cannot name a substring is not a span, and accepting one would
    let an unanchorable finding through the gate looking anchored.
    """

    model_config = ConfigDict(frozen=True)

    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def _non_empty(self) -> Span:
        if self.end <= self.start:
            raise ValueError(f"span [{self.start}, {self.end}) is empty or inverted")
        return self

    def __len__(self) -> int:
        return self.end - self.start


class AnchoredEvidence(BaseModel):
    """Evidence that names where it came from, precisely enough to re-check.

    The fields mirror the ported `EvidenceItem` — `turn_id` XOR `doc_path` for
    provenance, plus the text, score and direction — and add the three I2
    requires: the span, the quote as read, and the epoch the referent was
    resolved at.

    `quote` is stored rather than derived by searching for `text`, because
    short turns repeat. A five-character acknowledgement can occur a dozen
    times in one call, and a search would anchor to whichever came first.
    """

    model_config = ConfigDict(frozen=True)

    turn_id: str | None = None
    doc_path: str | None = None
    text: str
    score: float
    supports: bool

    span: Span
    quote: str
    intents_sha: str

    @model_validator(mode="after")
    def _epoch_is_a_commit(self) -> AnchoredEvidence:
        if not SHA_RE.match(self.intents_sha):
            raise ValueError(
                f"intents_sha {self.intents_sha!r} is not a 40-character git object "
                f"name; an epoch that is not a commit cannot pin anything (I4)"
            )
        if len(self.quote) != len(self.span):
            raise ValueError(
                f"quote is {len(self.quote)} characters but its span covers "
                f"{len(self.span)}; they cannot describe the same text"
            )
        return self


def resolve_quote(evidence: AnchoredEvidence, transcript: str) -> str:
    """Return the quoted text, having verified it is there verbatim.

    Raises rather than returning a falsy value. A caller that forgets to check
    a boolean ships an unanchored finding as an anchored one, which is the
    failure I2 exists to prevent; an exception cannot be forgotten.

    The gate in M12 catches this and routes the finding to `ungrounded` — it
    does not drop it. Findings are never silently dropped.
    """
    span = evidence.span
    if span.end > len(transcript):
        raise ValueError(
            f"span [{span.start}, {span.end}) falls outside a transcript of "
            f"{len(transcript)} characters"
        )
    found = transcript[span.start : span.end]
    if found != evidence.quote:
        raise ValueError(
            f"quote does not match the transcript at its span: "
            f"stored {evidence.quote!r}, found {found!r}"
        )
    return found
