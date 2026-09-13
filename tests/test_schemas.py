"""Acceptance tests for 9021 M5 — the pipeline's data contracts live in types/.

Two rejections shaped this file, and both lessons are encoded here rather than
remembered.

The first attempt asserted *behaviour*: construct with keyword arguments,
compare a JSON round-trip. Pydantic ignores keyword arguments naming fields a
model no longer has, so eight of ten planted field deletions passed green.

The second attempt asserted *shape*, which caught all of those — but from
hand-written tables. Verification found the tables happened to be correct and
the approach still unsound: they held field *names*, so a changed default, a
widened annotation or a relaxed requirement all passed. One of those, flipping
`RubricItem.weight`'s default from 1.0 to 2.0, doubles every unweighted row's
contribution to the shipped score. And a model dropped from *both* the port and
the table was undetectable — the tables were the only oracle, and they were
maintained by the same hand as the code.

So the oracle is now generated, not written: `tests/fixtures/upstream_schema_snapshot.json`
is produced by `scripts/build_schema_snapshot.py` from the upstream module and
records, per field, requiredness *and* realized default *and* annotation, plus
the complete model and enum sets. Completeness is a property of the snapshot
rather than of anyone's diligence.

Per the milestone's Contract: the binding constraint is I5 — the replay-bearing
record stays separable from diagnostics.
"""

from __future__ import annotations

import enum
import json
import types
from pathlib import Path
from typing import Literal, get_args, get_origin

import pytest
from pydantic import BaseModel

from argus.types import pipeline as p

SNAPSHOT = Path(__file__).resolve().parent / "fixtures" / "upstream_schema_snapshot.json"


def _load_snapshot() -> dict:
    assert SNAPSHOT.exists(), (
        f"schema snapshot missing at {SNAPSHOT}. "
        f"Regenerate with scripts/build_schema_snapshot.py."
    )
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


SNAP = _load_snapshot()


def _norm(annotation: object) -> str:
    """Canonical string for an annotation, comparable across the two modules.

    Upstream writes `typing.List[X]` and `Optional[X]`; the port writes
    `list[X]` and `X | None`. Those are the same type and must compare equal.
    `Literal['customer', 'agent']` and `str` are NOT the same type and must not
    — widening that one drops the constraint M2's role-swap fix rests on.
    """
    text = str(annotation)
    for before, after in (
        ("typing.List[", "list["),
        ("typing.Dict[", "dict["),
        ("typing.Set[", "set["),
        ("typing.Tuple[", "tuple["),
        ("models.schemas.", ""),
        ("argus.types.pipeline.", ""),
        ("<class '", ""),
        ("'>", ""),
    ):
        text = text.replace(before, after)
    if text.startswith("typing.Optional[") and text.endswith("]"):
        text = text[len("typing.Optional[") : -1] + " | None"
    return text


def _default_key(info: object) -> str:
    """Mirror of the snapshot's default encoding, applied to a live field."""
    from pydantic_core import PydanticUndefined

    factory = getattr(info, "default_factory", None)
    if factory is not None:
        try:
            produced = factory()
        except TypeError:
            return "<factory:uncallable>"
        return f"<factory:{type(produced).__name__}>" if produced else repr(produced)
    default = getattr(info, "default", PydanticUndefined)
    if default is PydanticUndefined:
        return "<required>"
    if isinstance(default, enum.Enum):
        return f"{type(default).__name__}.{default.name}"
    return repr(default)


def compare_to_snapshot(namespace: object, snap: dict | None = None) -> list[str]:
    """Every way `namespace` differs from the upstream contract.

    This is the function the live port is judged by, and the one
    `test_the_checks_can_fail` plants a defect against — so a demonstration
    that it fires is a demonstration about the real check, not about `!=`.
    """
    snap = snap or SNAP
    problems: list[str] = []

    for name, spec in sorted(snap["models"].items()):
        model = getattr(namespace, name, None)
        if model is None:
            problems.append(f"model {name}: missing")
            continue
        fields = model.model_fields
        expected = set(spec["fields"])
        actual = set(fields)
        for missing in sorted(expected - actual):
            problems.append(f"{name}.{missing}: missing")
        for extra in sorted(actual - expected):
            problems.append(f"{name}.{extra}: not in the upstream contract")
        if list(fields) != spec["order"] and expected == actual:
            problems.append(f"{name}: field order differs from upstream")
        for fname in sorted(expected & actual):
            want, info = spec["fields"][fname], fields[fname]
            if info.is_required() != want["required"]:
                problems.append(
                    f"{name}.{fname}: required={info.is_required()}, upstream {want['required']}"
                )
            if _default_key(info) != want["default"]:
                problems.append(
                    f"{name}.{fname}: default {_default_key(info)}, upstream {want['default']}"
                )
            if _norm(info.annotation) != _norm(want["annotation"]):
                problems.append(
                    f"{name}.{fname}: annotation {_norm(info.annotation)}, "
                    f"upstream {_norm(want['annotation'])}"
                )

    for name, members in sorted(snap["enums"].items()):
        member = getattr(namespace, name, None)
        if member is None:
            problems.append(f"enum {name}: missing")
            continue
        actual_members = {m.name: m.value for m in member}
        if actual_members != members:
            problems.append(f"enum {name}: {actual_members} != upstream {members}")

    return problems


# --- The contract itself ----------------------------------------------------


def test_port_matches_the_upstream_contract_exactly():
    """Field sets, order, requiredness, defaults, annotations, and every enum."""
    assert compare_to_snapshot(p) == []


def test_no_upstream_model_or_enum_is_missing():
    """Completeness — the defect a hand-written table structurally cannot catch.

    A model deleted from the port *and* from an expectation table vanishes
    silently. The snapshot is generated from upstream, so it still knows.
    """
    assert len(SNAP["models"]) == 16
    assert len(SNAP["enums"]) == 10
    missing = [n for n in SNAP["models"] if not hasattr(p, n)]
    missing += [n for n in SNAP["enums"] if not hasattr(p, n)]
    assert not missing, f"absent from the port: {missing}"


def test_the_checks_can_fail():
    """Plant each defect class against the *live* comparison and watch it fire.

    The previous version of this test built two throwaway classes and asserted
    they differed from a table it had written itself. It passed against a
    zero-byte module. This one mutates the real port and runs the real
    comparison, so what it demonstrates is what actually guards the tree.
    """

    def stand_in(**replacements) -> types.ModuleType:
        ns = types.ModuleType("stand_in")
        ns.__dict__.update(vars(p))
        ns.__dict__.update(replacements)
        return ns

    class MissingField(BaseModel):  # CleanTurn without timestamp_end
        id: str
        role: Literal["customer", "agent"]
        text: str
        flags: list[p.TurnFlag] = []
        reliability: Literal["high", "low"] = "high"
        timestamp_start: int | None = None

    class ChangedDefault(BaseModel):  # the score-doubling mutation
        id: int
        category: p.RubricCategory
        name: str
        pass_criteria: str
        fail_criteria: str
        na_criteria: str | None = None
        is_weighted: bool = False
        weight: float = 2.0  # upstream is 1.0
        always_check: bool = True
        requires_domain_kb: bool = False
        trigger_keywords: list[str] = []
        is_veto: bool = False

    class WidenedAnnotation(BaseModel):  # Literal dropped to str
        id: str
        role: str
        text: str
        reliability: Literal["high", "low"] = "high"
        flags: list[p.TurnFlag] = []

    class RelaxedRequirement(BaseModel):  # hypothesis pair made optional
        turn_id: str | None = None
        doc_path: str | None = None
        text: str = ""
        score: float = 0.0
        supports: bool = False

    class WrongWire(str, enum.Enum):
        INCOMPLETE = "INCOMPLETE"
        ASR_ERROR = "asr_error"  # upstream is "ASR_ERROR"
        ROLE_SWAPPED = "ROLE_SWAPPED"
        NORMAL = "NORMAL"

    # Baseline first. Without this the whole test passes vacuously against an
    # empty module — every mutation "fires" because everything is missing, which
    # is the tautology this test exists to have escaped.
    assert compare_to_snapshot(stand_in()) == [], (
        "the unmutated stand-in is already dirty, so nothing below proves anything"
    )

    for label, target, mutation in [
        ("deleted field", "CleanTurn", {"CleanTurn": MissingField}),
        ("changed default", "RubricItem", {"RubricItem": ChangedDefault}),
        ("widened annotation", "Turn", {"Turn": WidenedAnnotation}),
        ("relaxed requirement", "EvidenceItem", {"EvidenceItem": RelaxedRequirement}),
        ("changed wire value", "TurnFlag", {"TurnFlag": WrongWire}),
    ]:
        problems = compare_to_snapshot(stand_in(**mutation))
        assert problems, f"the comparison did not catch: {label}"
        # And it is *this* mutation being caught, not ambient breakage.
        assert any(target in line for line in problems), (
            f"{label}: comparison complained, but not about {target}: {problems}"
        )

    # And a whole model removed.
    gone = types.ModuleType("gone")
    gone.__dict__.update({k: v for k, v in vars(p).items() if k != "Session"})
    assert any("Session" in line for line in compare_to_snapshot(gone)), (
        "the comparison did not catch a removed model"
    )


# --- Round-tripping, for every contract rather than a sample ----------------


def _sample(annotation: object):
    """A valid value for a field, derived from its annotation."""
    origin = get_origin(annotation)
    if origin is Literal:
        return get_args(annotation)[0]
    if origin in (list, set, tuple):
        inner = get_args(annotation)
        return [_sample(inner[0])] if inner else []
    if origin is dict:
        return {}
    args = get_args(annotation)
    if args and type(None) in args:  # X | None -> produce the X
        return _sample(next(a for a in args if a is not type(None)))
    if isinstance(annotation, type):
        if issubclass(annotation, enum.Enum):
            return list(annotation)[0]
        if issubclass(annotation, BaseModel):
            return _instance(annotation)
        for typ, value in ((bool, True), (int, 1), (float, 1.0), (str, "x")):
            if issubclass(annotation, typ):
                return value
    return "x"


def _instance(model: type[BaseModel]) -> BaseModel:
    return model(
        **{
            name: _sample(info.annotation)
            for name, info in model.model_fields.items()
            if info.is_required()
        }
    )


@pytest.mark.parametrize("name", sorted(SNAP["models"]))
def test_every_contract_roundtrips(name):
    """The Contract says *every* contract round-trips. All sixteen, not a sample."""
    model = getattr(p, name)
    original = _instance(model)
    assert model.model_validate_json(original.model_dump_json()) == original


def test_upstream_output_loads():
    """The port reads what the upstream system actually writes.

    The first attempt could not: it had invented TurnFlag members and dropped
    ASR_ERROR and ROLE_SWAPPED, both emitted by live code at
    core/asr_preprocessor.py:46,54.
    """
    on_disk = (
        '{"session_id":"S-0001",'
        '"turns":[{"id":"T01","role":"customer","text":"您好，我在登录时显示CA锁未绑定。",'
        '"flags":["ASR_ERROR","ROLE_SWAPPED"],"reliability":"low",'
        '"timestamp_start":1,"timestamp_end":20}],'
        '"asr_quality":"fair","role_swap_detected":true,'
        '"low_reliability_turn_ids":["T01"]}'
    )
    t = p.CleanTranscript.model_validate_json(on_disk)
    assert t.turns[0].flags == [p.TurnFlag.ASR_ERROR, p.TurnFlag.ROLE_SWAPPED]
    assert t.turns[0].timestamp_end == 20

    coverage = '{"client_atom_id":"CA-01","agent_atom_id":"AA-01","status":"responded"}'
    assert p.CoverageRelation.model_validate_json(coverage).status is p.CoverageStatus.RESPONDED


def test_unknown_keys_are_dropped_not_preserved():
    """Recorded because it is upstream behaviour and it will bite M6.

    `extra` is at pydantic's default, which is `ignore` — unknown keys are
    silently discarded rather than preserved. That is exact upstream parity, so
    the port keeps it; `forbid` would reject payloads carrying keys this layer
    does not know, which is the on-disk break the first attempt was rejected for.

    But note what it costs: `span`, `quote` and `intents_sha` are precisely the
    keys M6 adds, and until M6 lands, anything writing them loses them on the
    first pass through here, with no error. M6 must land the fields before
    anything upstream starts emitting them.
    """
    payload = (
        '{"turn_id":"T01","text":"片段","score":0.9,"supports":true,'
        '"span":[0,5],"intents_sha":"deadbeef"}'
    )
    item = p.EvidenceItem.model_validate_json(payload)
    assert "span" not in item.model_dump_json()
    assert "intents_sha" not in item.model_dump_json()


def test_two_rubric_item_classes_remain_distinct():
    """`argus.types` holds two classes named `RubricItem`, deliberately.

    `compiler_schemas.RubricItem` is a SpecificRubric row keyed on a string id;
    `pipeline.RubricItem` is the upstream scoring-sheet row keyed on an int.
    They describe the same 27-row sheet at different maturities, and
    reconciling them is M15's decision, not M5's.

    The annotation pin is the part with teeth — it catches an `id` retype. The
    real mitigation is that `types/__init__.py` re-exports nothing, so both must
    be module-qualified; that is asserted here so a future convenience export
    fails loudly rather than making them silently interchangeable.
    """
    from argus.types import compiler_schemas as cs

    assert cs.RubricItem.model_fields["id"].annotation is str
    assert p.RubricItem.model_fields["id"].annotation is int

    import argus.types as pkg

    assert not hasattr(pkg, "RubricItem"), (
        "argus.types re-exports RubricItem — with two incompatible classes of "
        "that name in the package, an unqualified import is a coin flip."
    )


def test_replay_payload_still_excludes_proposed_score():
    """I5 — the port did not widen what the replay hash sees.

    This exercises 9020's module, not M5's: nothing in `pipeline.py` reaches a
    replay payload yet because nothing builds a FindingGraph from it. Tying the
    two together is M21's work. The live risk in the gap is `Verdict.score` —
    model-produced upstream, unbounded, and unmarked here.
    """
    from argus.types.proposer_diagnostics import (
        GroundedFinding,
        ProposedScores,
        QuarantinedFindingGraph,
        replay_hash,
    )

    grounded = [GroundedFinding(dimension="准确性", deduction=0.25)]
    bare = QuarantinedFindingGraph(
        grounded=grounded, intents_sha="a" * 40, rubric_version="v1"
    )
    with_scores = QuarantinedFindingGraph(
        grounded=grounded,
        intents_sha="a" * 40,
        rubric_version="v1",
        proposed_scores=ProposedScores(scores={"准确性": 12.03}, g_used=20),
        proposer_id="qwen3.5-27b-4bit",
    )
    assert replay_hash(bare) == replay_hash(with_scores)
