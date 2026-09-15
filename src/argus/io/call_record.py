# argus/io/call_record.py
"""The consumer's half of the seam: build the pipeline's `Session` from the
producer's call record (`INTENTS/**/calls/**/*.json`).

M7's data-flow table, row `Session`: `preprocessor.build_session` is dropped;
the record already carries the turns, roles, timestamps and spans, so building
the `Session` from it is the consumer reading, not re-deriving.

**Decline at intake (Q29, 2026-09-15: 角色必须确立，否则 Argus 不处理).**
Role establishment is an input precondition, not a routing outcome: if ANY
speaker lacks `speaker_role` or `speaker_role_source` — including the partial
case, one speaker attributed and the other not — `build_session` raises
`RolesNotEstablished` before any evaluation exists. A declined call produces
no report, no score, no grade, and specifically not the 0.0/不合格 report that
reads as a judgment. This is why the port's types never see an absent role:
`Turn.role` stays upstream's `Literal["customer", "agent"]`, and the
previously planned absent-role deviation is withdrawn.

**Declared-empty is a third state.** 47 of the 718 archived records carry
`turns` and `segments` as empty *lists* — the record says it holds nothing.
That is well-formed: `build_session` builds an empty-turn `Session`.

Validation is by access, not by schema: fields the consumer reads
(`audio.id`, speaker roles, turn `id`/`speaker`/`text`/`start_sec`/`end_sec`)
are indexed directly, so a record missing one fails with a `KeyError` naming
it. Segments are required to *exist* — the corpus dialect always carries them
— but nothing here reads their contents; the acoustic blocks belong to the
producer's contract and M2/M3's readers. What is deliberately NOT derived:
B's `Preprocessor._extract_metadata` parsed turn text for phone/company
strings into `session.metadata`; nothing downstream reads that metadata, and
re-deriving structure from text is the producer's work. `agent_id` keeps the
`Session` default — the record carries no agent identity.
"""
from argus.types.pipeline import Session, SessionKBContext, Turn


class RolesNotEstablished(Exception):
    """The record's speaker roles were never established; the call is declined.

    Raised before any evaluation exists. This is intake, not routing: there is
    no report, no score, and no human-review verdict to hang a judgment on.
    """


def build_session(record: dict) -> Session:
    """Build the pipeline `Session` from a call record, or decline it.

    Raises `RolesNotEstablished` if any speaker's role or role source is
    missing or null — agent and customer are a pair, so one established role
    is not attribution.
    """
    speakers = record["speakers"]
    turns_raw = record["turns"]
    record["segments"]  # must exist, even as [] — the producer's contract

    unestablished = [
        f"{speaker.get('id', '?')}"
        f"(role={speaker.get('speaker_role')!r}, "
        f"source={speaker.get('speaker_role_source')!r})"
        for speaker in speakers
        if not speaker.get("speaker_role")
        or not speaker.get("speaker_role_source")
    ]
    if unestablished:
        raise RolesNotEstablished(
            "speaker roles not established for: "
            + ", ".join(unestablished)
            + " — role establishment is an input precondition "
            "(9024 §7 Q29, 2026-09-15); the call is declined at intake"
        )

    speaker_roles = {
        speaker["id"]: speaker["speaker_role"] for speaker in speakers
    }

    turns = []
    for raw in turns_raw:
        speaker_id = raw["speaker"]
        if speaker_id not in speaker_roles:
            raise KeyError(
                f"turn {raw.get('id', '?')} references speaker "
                f"{speaker_id!r}, which the record's speakers[] does not "
                "list"
            )
        # start_sec/end_sec: read to validate the consumer contract, then
        # dropped — Stage 1's Turn carries no timestamps (M6's note).
        raw["start_sec"], raw["end_sec"]
        turns.append(Turn(
            id=raw["id"],
            role=speaker_roles[speaker_id],
            text=raw["text"],
        ))

    return Session(
        session_id=record["audio"]["id"],
        duration_sec=record["audio"].get("duration_sec"),
        turns=turns,
    )


def stub_kb_context(record: dict) -> SessionKBContext:
    """Production placeholder until 9025's Provider lands: an empty context —
    no rubric items, no domain summary. Takes the record so the call site
    reads the same when the Provider replaces it."""
    return SessionKBContext()
