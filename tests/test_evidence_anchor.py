"""Acceptance tests for 9021 M6 — evidence that resolves to an exact location.

M6's Contract: *Deliverable* — evidence traceable to an exact location in the
source transcript. *Binding constraint* — I2: every finding references a real
transcript span, exact-quote verified, or it is routed to a human. *Acceptance
property* — any stored evidence item resolves to a verbatim substring of the
raw transcript, and an unresolvable one fails rather than passing.

Three decisions this milestone makes, each visible in the tests below:

**The anchor lives beside the port, not inside it.** `types/pipeline.py` is a
faithful copy of the upstream contract and M5's snapshot test rejects any field
upstream does not have. Adding `span` there would fail that test — correctly.
So the anchored form is its own type, and the port stays a port.

**A character span, not a timestamp.** The plan's prose says to re-plumb
timestamps through stage 1. That was written before anyone looked: stage-1
`Turn` carries no timestamps at all, and more importantly a timestamp cannot
satisfy I2. Exact-quote verification needs character offsets into the text that
was actually read; seconds locate audio, which is a different provenance axis
and a different milestone's problem.

**Anchored evidence is frozen.** Once M6 puts `intents_sha` on a record,
`e.intents_sha = other` would be a plain attribute write and I4's pinned epoch
would be a convention rather than a constraint. Verification flagged exactly
this after M5. Freezing costs nothing here and closes it.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from argus.types.anchored import AnchoredEvidence, Span, resolve_quote

TRANSCRIPT = (
    "[1s -> 20s]客户: 您好，我在登录时显示CA锁未绑定。\n"
    "[20s -> 25s]客服: 您好，很高兴为您服务。\n"
    "[25s -> 30s]客户: 嗯。\n"
    "[30s -> 40s]客服: 请问您贵姓？\n"
    "[40s -> 45s]客户: 嗯。\n"
)
QUOTE = "您好，我在登录时显示CA锁未绑定。"
START = TRANSCRIPT.index(QUOTE)


def _anchored(**overrides) -> AnchoredEvidence:
    kwargs = {
        "turn_id": "T01",
        "text": QUOTE,
        "score": 0.91,
        "supports": True,
        "span": Span(start=START, end=START + len(QUOTE)),
        "quote": QUOTE,
        "intents_sha": "a" * 40,
    }
    kwargs.update(overrides)
    return AnchoredEvidence(**kwargs)


def test_the_anchor_fields_are_required_not_defaulted():
    """A defaulted anchor is an unanchored finding wearing an anchor's name.

    Verification found that M5's harness would not have noticed `intents_sha`
    landing as `str = ""`, because the field name would be present. So this is
    asserted directly rather than left to the shape check.
    """
    for field in ("span", "quote", "intents_sha"):
        info = AnchoredEvidence.model_fields[field]
        assert info.is_required(), f"{field} must be required, not defaulted"


def test_a_resolving_quote_verifies():
    """The ordinary case: the span points at the quote, verbatim."""
    ev = _anchored()
    assert resolve_quote(ev, TRANSCRIPT) == QUOTE


def test_a_quote_that_does_not_match_its_span_fails():
    """I2's exact-quote requirement, in its failing direction.

    The span is real and the quote is plausible, but they disagree. This is the
    case that must not pass quietly: a finding whose quote was paraphrased,
    re-tokenised or lifted from a different turn.
    """
    ev = _anchored(quote="您好，我在登录时显示CA锁已绑定。")  # 未 -> 已
    with pytest.raises(ValueError, match="does not match"):
        resolve_quote(ev, TRANSCRIPT)


def test_a_span_outside_the_transcript_fails():
    """An anchor pointing past the end is unresolvable, not empty."""
    ev = _anchored(span=Span(start=10_000, end=10_010))
    with pytest.raises(ValueError, match="outside"):
        resolve_quote(ev, TRANSCRIPT)


def test_a_repeated_quote_is_still_unambiguous():
    """Short turns repeat. The span is what disambiguates them.

    Verification of the anchoring evidence warned that short turns will collide
    on longer calls — `嗯` appears twice here. Recovering a span by searching
    for the quote would be ambiguous; carrying the span makes it exact, which
    is why the span is stored rather than derived.
    """
    assert TRANSCRIPT.count("嗯") == 2
    second = TRANSCRIPT.rindex("嗯")
    ev = _anchored(text="嗯", quote="嗯", span=Span(start=second, end=second + 1))
    assert resolve_quote(ev, TRANSCRIPT) == "嗯"
    assert ev.span.start == second  # the later one, not the first match


def test_an_inverted_or_empty_span_is_rejected_at_construction():
    """A span that cannot name a substring is not a span."""
    with pytest.raises(ValidationError):
        Span(start=10, end=4)
    with pytest.raises(ValidationError):
        Span(start=5, end=5)
    with pytest.raises(ValidationError):
        Span(start=-1, end=3)


def test_anchored_evidence_is_frozen():
    """I4 — the pinned epoch cannot be rewritten after the fact.

    Without this, `e.intents_sha = other` succeeds silently and the record
    claims an epoch it was never derived against.
    """
    ev = _anchored()
    with pytest.raises(ValidationError):
        ev.intents_sha = "b" * 40
    with pytest.raises(ValidationError):
        ev.span = Span(start=0, end=1)


def test_the_anchor_survives_a_round_trip():
    """The fields are known to this model, so they persist.

    M5 recorded that the ported `EvidenceItem` drops unknown keys silently, and
    that `span`/`quote`/`intents_sha` were exactly the keys at risk. Once they
    are declared here, a round-trip keeps them — that is the point of declaring
    them rather than smuggling them through as extras.
    """
    ev = _anchored()
    restored = AnchoredEvidence.model_validate_json(ev.model_dump_json())
    assert restored == ev
    assert restored.span == ev.span
    assert restored.intents_sha == ev.intents_sha


def test_an_intents_sha_must_look_like_an_epoch():
    """A pin that is not a commit is not a pin.

    I4 pins the tree at a single git-SHA epoch. Accepting `"latest"` or `""`
    would make the pin decorative, and the failure would surface only on replay.
    """
    for bad in ("", "latest", "a" * 39, "z" * 40, "A" * 40):
        with pytest.raises(ValidationError):
            _anchored(intents_sha=bad)


def test_the_port_is_untouched():
    """M6 extends alongside the port; it does not edit it.

    `types/pipeline.py` mirrors the upstream contract and M5's snapshot test
    rejects fields upstream does not have. If a later change moves these fields
    into the port, that test fails — as it should. This assertion states the
    boundary so the failure reads as intended rather than as a puzzle.
    """
    from argus.types import pipeline

    for field in ("span", "quote", "intents_sha"):
        assert field not in pipeline.EvidenceItem.model_fields
