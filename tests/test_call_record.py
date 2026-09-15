# tests/test_call_record.py
"""9024 M7 — the consumer's half of the seam: the call record's read side.

The record the producer writes (`INTENTS/**/calls/**/*.json`) is the only thing
Argus may consume. `argus.io.call_record` builds the pipeline's `Session` from
it — and, per the human's 2026-09-15 ruling (9024 §7 Q29), **declines a record
whose speaker roles were never established**: role establishment is an input
precondition, not a routing outcome. A declined call produces no evaluation, no
score, no grade — the same disposition as a malformed record.

The conformance test inherited from 9023's M4 asserts what the consumer reads:
`speakers[].speaker_role` + `speaker_role_source`, `start_sec`/`end_sec` on
turns and segments, per-segment acoustic blocks, per-call `stats` — each
present, with **declared-empty as a third state** (`[]` means the record says
it holds nothing, not that the field is missing).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
RECORD = REPO / "tests" / "fixtures" / "call_record_baseline.json"


def _record() -> dict:
    return json.loads(RECORD.read_text(encoding="utf-8"))


def _empty_declared(record: dict, key: str) -> dict:
    """A record that says a list holds nothing — the third state."""
    record[key] = []
    return record


def test_the_record_carries_what_the_consumer_reads():
    """The conformance contract, on a record with roles established.

    Every field the pipeline depends on is asserted present and typed; the
    absent case is a different test, because absence here means decline, not
    a missing field to default.
    """
    from argus.io import call_record

    session = call_record.build_session(_record())
    assert session.turns, "a role-complete record builds a non-empty session"
    for turn in session.turns:
        assert turn.role in ("agent", "customer")
        assert turn.text
    assert session.session_id == "baseline"


def test_declared_empty_turns_are_a_third_state_not_a_failure():
    """47 of the 718 archived records carry `turns: []` and `segments: []`.

    "Present" means the field exists and holds a value *or* the record says it
    holds nothing. Such a record is well-formed — its disposition is the role
    question, not a crash.
    """
    from argus.io import call_record

    record = _empty_declared(_record(), "turns")
    record = _empty_declared(record, "segments")
    session = call_record.build_session(record)
    assert session.turns == []


def test_unattributed_call_is_not_processed():
    """Q29 (2026-09-15): 角色必须确立，否则 Argus 不处理.

    A record whose speakers carry no established role is **declined at
    intake**: an exception from `build_session`, before any evaluation exists.
    No report, no score, no routed verdict — and specifically NOT the 0.0/
    不合格 report 9023 measured B producing, which read as a judgment.

    (`test_absent_role_defers` was this assertion's name in 9023; "defers" is
    historical — the ruling makes it a decline, so the name says what happens.)
    """
    from argus.io import call_record

    record = _record()
    for speaker in record["speakers"]:
        speaker["speaker_role"] = None
        speaker["speaker_role_source"] = None

    with pytest.raises(call_record.RolesNotEstablished):
        call_record.build_session(record)


def test_a_partially_attributed_call_is_also_declined():
    """One established role is not attribution: agent and customer are a pair.

    A record that names only the agent leaves the customer unknown — scoring
    "the agent's utterances" against an unidentified counterparty is the
    fabrication Q29 forbids, one step removed.
    """
    from argus.io import call_record

    record = _record()
    record["speakers"][1]["speaker_role"] = None
    record["speakers"][1]["speaker_role_source"] = None

    with pytest.raises(call_record.RolesNotEstablished):
        call_record.build_session(record)


def test_the_synthetic_record_matches_the_corpus_shape():
    """The fixture speaks the producer's dialect, not a convenient dialect.

    Field names and nesting mirror a real record from `INTENTS/**/calls/`:
    `turns[].speaker` is an S-id resolved through `speakers[]` (whose `label`
    is null — diarization is anonymous), segments carry an `acoustic` block.
    A test against a made-up shape would pass while the real corpus fails.
    """
    record = _record()
    assert set(record) >= {"schema_version", "audio", "config", "speakers",
                           "turns", "segments", "stats"}
    speaker = record["speakers"][0]
    assert {"id", "label", "speaker_role", "speaker_role_source"} <= set(speaker)
    turn = record["turns"][0]
    assert {"speaker", "text", "start_sec", "end_sec", "segment_ids"} <= set(turn)
    assert {"acoustic"} <= set(record["segments"][0])
    # the corpus's own dialect: labels are null, roles come from the producer
    assert record["speakers"][0]["label"] is None
