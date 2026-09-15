# tests/test_call_record.py
"""9024 M7 — the consumer's half of the seam: the call record's read side.

The record the producer writes (`INTENTS/**/calls/**/*.json`) is the only thing
Argus may consume. `argus.io.call_record` builds the pipeline's `Session` from
it — and, per the human's 2026-09-15 ruling (9024 §7 Q29), **declines a record
whose speaker roles were never established**: role establishment is an input
precondition, not a routing outcome. A declined call produces no evaluation, no
score, no grade — the same disposition as a malformed record.

Processable is stated positively: at least one turn, a speaker established as
`agent`, a speaker established as `customer`. A record with `turns: []` is
**well-formed and not processable** — the third state — and is declined for
that reason (`NoTurnsDeclared`), not for its roles. The negative form of the
same precondition ("no speaker lacks a role") is true of `speakers: []`, and
that vacuity is what let a never-attributed call produce a scored, graded,
24-verdict report with no evidence behind any of them.

The conformance test inherited from 9023's M4 asserts what the consumer reads:
`speakers[].speaker_role` + `speaker_role_source`, `start_sec`/`end_sec` on
turns and segments, per-segment acoustic blocks, per-call `stats` — each
present, with **declared-empty as a third state** (`[]` means the record says
it holds nothing, not that the field is missing — and a record that holds
nothing is declined rather than scored).
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

    The third state is **well-formed but not processable** — distinct from
    malformed (a required field absent, which still fails loudly with a
    `KeyError` naming it) and from unattributed (roles never established,
    `RolesNotEstablished`). "Present" means the field exists and holds a value
    *or* the record says it holds nothing; the decline is about the record
    holding nothing to evaluate, not about the field being missing.

    This test used to assert `session.turns == []` — that an empty-turn
    `Session` was returned. An empty session is not a neutral object: the
    pipeline scored it 0.0/不合格 with 24 FAIL verdicts and no evidence
    (Q29's fabrication, reached through this door rather than the missing
    role). Asserting the named decline is the honest form of the same claim.
    """
    from argus.io import call_record

    record = _empty_declared(_record(), "turns")
    record = _empty_declared(record, "segments")
    with pytest.raises(call_record.NoTurnsDeclared):
        call_record.build_session(record)


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


def test_a_speaker_list_that_holds_no_one_is_declined():
    """The guard's vacuity, isolated: `speakers: []` with the turns left in place.

    The previous guard flagged each speaker lacking a role, and a universal
    over an empty list is true — so `speakers: []` produced nothing to flag and
    the call was processed (with `speakers: []` *and* `turns: []`, the guard
    never fired at all; the reproduction that found this ran the full pipeline
    to 0.0/不合格 with 24 evidence-free FAIL verdicts).

    Here the turns are present, so the difference is visible as a disposition:
    a record that names nobody is **unattributed** (`RolesNotEstablished`), not
    malformed. The turn loop would raise `KeyError` for every turn — but it is
    never reached, because attribution is checked first. That is what makes the
    precondition positive rather than an enumeration of noticed shapes: "some
    speaker holds the customer role" cannot be satisfied by a list holding no
    one.
    """
    from argus.io import call_record

    record = _record()
    record["speakers"] = []

    with pytest.raises(call_record.RolesNotEstablished):
        call_record.build_session(record)


def test_a_pair_without_a_customer_is_declined():
    """Two agents are not a pair either: the docstring's rationale, applied.

    "Agent and customer are a pair, so one established role is not
    attribution" cut one way and not the other — every speaker *was* attributed
    here, so the old guard passed the record through and the turns of the
    unlabelled counterparty were scored as the agent's (a mis-attributed call
    graded 100.0/优秀).
    """
    from argus.io import call_record

    record = _record()
    record["speakers"][1]["speaker_role"] = "agent"

    with pytest.raises(call_record.RolesNotEstablished):
        call_record.build_session(record)


def test_the_three_dispositions_are_distinguishable():
    """Malformed, declared-empty and unattributed are three states, not one.

    A single "declined" verdict would be less useful than the crash it
    replaced: malformed means the producer's writer is broken, declared-empty
    means the call captured nothing, unattributed means the roles were never
    established. The two declines share the `CallDeclined` disposition (no
    evaluation, no score, no grade, no verdict) and not each other's type.
    """
    from argus.io import call_record

    malformed = _record()
    del malformed["turns"]

    empty = _empty_declared(_record(), "turns")

    unattributed = _record()
    for speaker in unattributed["speakers"]:
        speaker["speaker_role"] = None

    with pytest.raises(KeyError):
        call_record.build_session(malformed)

    with pytest.raises(call_record.NoTurnsDeclared) as empty_exc:
        call_record.build_session(empty)

    with pytest.raises(call_record.RolesNotEstablished):
        call_record.build_session(unattributed)

    assert isinstance(empty_exc.value, call_record.CallDeclined)
    assert not isinstance(empty_exc.value, call_record.RolesNotEstablished)
    assert not issubclass(KeyError, call_record.CallDeclined)
