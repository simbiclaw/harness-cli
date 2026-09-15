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
That is well-formed, and it is **not processable**: `build_session` raises
`NoTurnsDeclared`. It used to build an empty-turn `Session`, which was the
decline's absence read as consent — the pipeline happily scored it 0.0/不合格
with 24 FAIL verdicts and no evidence (Q29's fabrication, reached through a
different door than the missing role).

So a record has three dispositions, and they are distinguishable:

- **malformed** — a required field is absent, or a turn names a speaker the
  record does not list. Fails loudly, as it always has: `KeyError`, naming it.
- **declared-empty** — `turns: []`. Well-formed, declined at the precondition
  (`NoTurnsDeclared`).
- **unattributed** — roles absent, or the agent/customer pair incomplete.
  Declined (`RolesNotEstablished`).

The two declines share a base — `CallDeclined` — because "well-formed but not
processable" is one disposition reached for two reasons.

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


class CallDeclined(Exception):
    """Well-formed but not processable: the call is declined at intake.

    The same disposition as a malformed record — no evaluation, no report, no
    score, no grade, no routed verdict — reached without a crash. A malformed
    record is a *different* disposition and still fails loudly; this base means
    "the record is fine, Argus will not process it".

    One disposition, two reasons, so a caller that wants the disposition
    catches this and a caller that wants the reason catches a subclass.
    """


class NoTurnsDeclared(CallDeclined):
    """Declared-empty: `turns` is an empty list — the record holds nothing.

    Well-formed (47 of the 718 archived records carry this shape) and not
    processable: there is nothing to attribute and nothing to atomize, so any
    report built over it carries a score, a grade and a set of verdicts that no
    evidence backs. I2 forbids unanchored findings; this declines before one
    can be manufactured.
    """


class RolesNotEstablished(CallDeclined):
    """The record's speaker roles were never established; the call is declined.

    Raised before any evaluation exists. This is intake, not routing: there is
    no report, no score, and no human-review verdict to hang a judgment on.
    """


def _established(speaker: dict) -> bool:
    """One speaker entry is attributed: it names a role *and* where it came from."""
    return bool(speaker.get("speaker_role") and speaker.get("speaker_role_source"))


def build_session(record: dict) -> Session:
    """Build the pipeline `Session` from a call record, or decline it.

    Processable is stated positively, as three requirements: the record carries
    at least one turn, at least one speaker is established as `agent`, and at
    least one is established as `customer`. Established means both
    `speaker_role` and `speaker_role_source` are present; every *listed*
    speaker must be established too, since a turn resolving to an anonymous
    speaker would hand `Turn.role` a null.

    The witness requirements are what make this non-vacuous. The previous form
    — "flag each speaker lacking a role" — is a universal over `speakers`, and
    a universal over an empty list is true: `speakers: []` sailed through and
    the fabricated report followed. "Some speaker holds the customer role"
    cannot be satisfied by a list that holds no one, so the empty list and the
    incomplete pair are unreachable by construction rather than by enumerating
    the shapes that were noticed.

    Declines with `NoTurnsDeclared` or `RolesNotEstablished` (both
    `CallDeclined`). Structure is validated first: a record missing `turns`,
    `segments` or `speakers` is malformed, not declared-empty, and raises
    `KeyError` naming the field — as does a turn naming a speaker the record
    does not list. When a record is both empty and unattributed, the turn count
    is reported; the record's statement about its own payload is the more
    specific fact, and the roles surface on the next submission.
    """
    speakers = record["speakers"]
    turns_raw = record["turns"]
    record["segments"]  # must exist, even as [] — the producer's contract
    audio_id = record["audio"].get("id", "?")  # read here so the declines
    # below cannot raise: a record missing `audio` is malformed, not declined.

    if not turns_raw:
        raise NoTurnsDeclared(
            f"record {audio_id!r} declares turns: [] — the record says it "
            "captured nothing, so there is nothing to evaluate; declined at "
            "intake (9024 §7 Q29, 2026-09-15)"
        )

    anonymous = [s for s in speakers if not _established(s)]
    roles_held = {s["speaker_role"] for s in speakers if _established(s)}
    roles_missing = [r for r in ("agent", "customer") if r not in roles_held]
    if anonymous or roles_missing:
        raise RolesNotEstablished(
            "speaker roles not established"
            + (
                " for: " + ", ".join(
                    f"{s.get('id', '?')}(role={s.get('speaker_role')!r}, "
                    f"source={s.get('speaker_role_source')!r})"
                    for s in anonymous
                )
                if anonymous else ""
            )
            + ("; no speaker established as " + " and ".join(roles_missing)
               if roles_missing else "")
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
