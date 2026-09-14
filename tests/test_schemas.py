"""Acceptance tests for 9021 M5 — the pipeline's data contracts live in types/.

Three rejections shaped this file, and each lesson is encoded here rather than
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

The fourth pass closed the gap between what the snapshot *records* and what
this file *reads*. The builder had gained aliases, constraints, `model_config`,
validator buckets, enum bases and member order — and the comparison still
walked three facts per field plus an order-blind enum map, so seven mutations
of the newest kinds passed green. The comparison is now mechanical: it walks
every recorded fact and diffs it, so a fact is compared because it is
recorded, not because someone remembered it. The class set is compared for
exact equality in both directions — a model smuggled into the port that
upstream lacks is precisely the name I5 and I7 keep out of this contract. And
the fixture's provenance — pinned commit, source digest, document digest — is
asserted against constants held in this file, not imported from the builder
that wrote them.

Round-4's verification then found two more survivors, and both were the
namespace behaving worse than the facts record. A one-line re-export
(`from argus.types.compiler_schemas import SpecificRubric`) binds a foreign
contract class into the port namespace, where the `__module__` ownership
filter — and the exact-set check built on it — quietly steps over it; the
same shadow hides a class whose `__module__` is laundered before it binds.
So the comparison now also refuses contract-shaped bindings the namespace
cannot explain: anything pydantic-or-enum shaped, owned by no module the
snapshot owns, and inherited by nothing is named. And an enum's behaviour
hooks were unwatched entirely — a `_missing_` added to TurnFlag silently
coerces `TurnFlag("garbage")` to INCOMPLETE where upstream raises — so every
callable an enum defines is now a recorded fact.

Round-5's verification found the same failure one level up, in the filters
themselves. A filtered record is an attack surface: `model_post_init` lives
in no decorator bucket, a plain mixin overriding `__setattr__` appears in no
recorded fact, and a hook assigned after the class with its `__module__`
forged to `enum` passes a defining-module filter by claiming to be
machinery. So the class-level facts went raw — every callable on every
contract class, models and enums alike, recorded by name under whatever
module it claims (a forge cannot erase a name; the claiming is the diff),
plus every MRO base name per class. Raw means upstream's machinery is
recorded too, and since both sides run the same interpreter it is identical
and cancels in the diff.

Per the milestone's Contract: the binding constraint is I5 — the replay-bearing
record stays separable from diagnostics.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import inspect
import json
import types
import uuid
from pathlib import Path
from typing import Literal, get_args, get_origin

import pytest
from pydantic import BaseModel, Field, field_validator, model_validator

from argus.types import compiler_schemas
from argus.types import pipeline as p

SNAPSHOT = Path(__file__).resolve().parent / "fixtures" / "upstream_schema_snapshot.json"

# Held here, deliberately not imported from scripts/build_schema_snapshot.py:
# a fixture stamped with a different commit must fail against a copy of the
# truth the builder cannot edit. If the pin ever moves, it moves in both files
# in the same commit, and the diff shows it.
UPSTREAM_COMMIT = "0c2cccd178a5696c59ffa90dca129511af5ae5c0"
UPSTREAM_SOURCE_SHA256 = "4685ad54cea2b68587bc496d2d1289810023c71ad9d186328cba729b4fa7b15d"


def _load_snapshot() -> dict:
    assert SNAPSHOT.exists(), (
        f"schema snapshot missing at {SNAPSHOT}. "
        f"Regenerate with scripts/build_schema_snapshot.py."
    )
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


SNAP = _load_snapshot()


# --- Mirror of the snapshot's encoders ---------------------------------------
#
# These functions re-implement, on purpose, what
# scripts/build_schema_snapshot.py does when it writes the fixture. Importing
# the builder instead would let a regression in the encoder move both sides
# together and cancel out — the exact shape that let a shared session_id
# through in the third pass, and the reason the named regression test below
# pins the encodings themselves.


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
            # Mirror of the builder's one-argument-factory encoding: the code
            # object's constants and names. Upstream has no such factory; this
            # is a floor for the day it grows one.
            code = getattr(factory, "__code__", None)
            body = repr((code.co_consts, code.co_names)) if code else repr(factory)
            return f"<factory:validated-data:{body}>"
        if type(produced) in (list, dict, set):
            # Identity probe — `[] == []` whether the factory hands every
            # caller the same object or a new one, so value-equality cannot
            # see shared mutability and identity can. Immutable empties keep
            # the value path below: CPython legally interns them, and sharing
            # an immutable is harmless.
            second, third = factory(), factory()
            shared = produced is second or second is third or produced is third
            kind = "shared-empty" if shared else "fresh-empty"
            return f"<factory:{type(produced).__name__}:{kind}>"
        if not produced:
            # An empty immutable container is its own value, so `= ()` and
            # `default_factory=tuple` compare equal, as they should.
            return repr(produced)
        # A statistical proxy with a documented floor, not an entropy
        # guarantee: twenty-four draws, all distinct, collide with p ~= 7e-8
        # over a 16**8 space and with certainty over a sixteen-value alphabet.
        # That is the discrimination the contract needs — upstream's
        # session_id is uuid4 hex and the mutation to catch is a low-entropy
        # substitute — and it is all this check claims to be.
        draws = {repr(produced)} | {repr(factory()) for _ in range(23)}
        if len(draws) == 1:
            kind = "constant"
        elif len(draws) == 24:
            kind = "fresh"
        else:
            kind = "weak"
        return f"<factory:{type(produced).__name__}:{kind}>"
    default = getattr(info, "default", PydanticUndefined)
    if default is PydanticUndefined:
        return "<required>"
    if isinstance(default, enum.Enum):
        return f"{type(default).__name__}.{default.name}"
    if type(default) in (list, dict, set) and not default:
        # Literal mutable defaults are fresh per instance by construction —
        # pydantic deep-copies them — so upstream's `= []` and the port's
        # `default_factory=list` are one fact and share one key.
        return f"<factory:{type(default).__name__}:fresh-empty>"
    return repr(default)


def _field_facts(info: object) -> dict:
    """Mirror of the snapshot's per-field record: all fourteen facts."""
    return {
        "required": info.is_required(),
        "default": _default_key(info),
        "annotation": _norm(info.annotation),
        "alias": info.alias,
        "validation_alias": None if info.validation_alias is None else str(info.validation_alias),
        "serialization_alias": info.serialization_alias,
        "constraints": [repr(c) for c in info.metadata],
        "frozen": info.frozen,
        "exclude": info.exclude,
        "repr": info.repr,
        "validate_default": info.validate_default,
        "kw_only": info.kw_only,
        "discriminator": None if info.discriminator is None else str(info.discriminator),
        "title": info.title,
    }


# Read off the dataclass the same way the builder reads it, so a pydantic
# upgrade that adds a decorator bucket is picked up on both sides together.
_DECORATOR_BUCKETS = tuple(
    f.name for f in dataclasses.fields(BaseModel.__pydantic_decorators__)
)


def _model_facts(model: type[BaseModel]) -> dict:
    """Mirror of the snapshot's per-model record."""
    return {
        "order": list(model.model_fields),
        "config": {k: repr(v) for k, v in sorted(model.model_config.items())},
        "decorators": {
            bucket: sorted(getattr(model.__pydantic_decorators__, bucket))
            for bucket in _DECORATOR_BUCKETS
        },
        "fields": {name: _field_facts(info) for name, info in model.model_fields.items()},
    }


def _defined_module(value: object) -> str | None:
    """Mirror of the builder's descriptor unwrap for a callable's module."""
    if isinstance(value, property):
        value = value.fget
    elif isinstance(value, (classmethod, staticmethod)):
        value = value.__func__
    return getattr(value, "__module__", None)


def _callables_of(cls: type) -> dict[str, str | None]:
    """Mirror of the snapshot's raw callable record.

    Deliberately unfiltered: a defining-module filter is the hole a forged
    `__module__` walks through. The name is recorded under whatever module it
    claims; upstream and the port run the same interpreter, so machinery
    cancels in the diff and only contract-level differences survive. The
    predicate includes the descriptor forms — a classmethod object is not
    callable, and it is precisely the shape an in-body `_missing_` takes.
    """
    return {
        name: _defined_module(value)
        for name, value in vars(cls).items()
        if callable(value) or isinstance(value, (classmethod, staticmethod, property))
    }


def _model_facts(model: type[BaseModel]) -> dict:
    """Mirror of the snapshot's per-model record."""
    return {
        "bases": [c.__name__ for c in model.__mro__[1:]],
        "callables": _callables_of(model),
        "order": list(model.model_fields),
        "config": {k: repr(v) for k, v in sorted(model.model_config.items())},
        "decorators": {
            bucket: sorted(getattr(model.__pydantic_decorators__, bucket))
            for bucket in _DECORATOR_BUCKETS
        },
        "fields": {name: _field_facts(info) for name, info in model.model_fields.items()},
    }


def _enum_facts(member_type: type[enum.Enum]) -> dict:
    """Mirror of the snapshot's per-enum record."""
    return {
        "bases": [c.__name__ for c in member_type.__mro__[1:]],
        # __members__, not iteration: iteration skips aliases, so a member
        # added under a second name would be invisible to the record.
        "members": [[name, m.value] for name, m in member_type.__members__.items()],
        # Raw, unfiltered: a `_missing_` with a forged `__module__` passes a
        # defining-module filter as machinery, but a name cannot be erased.
        "callables": _callables_of(member_type),
    }


def _snapshot_module(module: object, owned: set[str] | None = None) -> dict:
    """Mirror of the builder's module walk.

    `owned` is the set of defining module names a class must belong to to
    count as part of the contract; it defaults to `module` itself. The
    mutation battery runs this over stand-in namespaces whose original classes
    still carry `__module__ == "argus.types.pipeline"` while the replacement
    classes are defined in this test module — so it passes both, or the
    stand-ins snapshot empty and every mutation "passes" vacuously.
    """
    owned = owned or {getattr(module, "__name__", "")}
    models: dict[str, dict] = {}
    enums: dict[str, dict] = {}
    for name, obj in vars(module).items():
        if not inspect.isclass(obj) or obj.__module__ not in owned:
            continue
        if issubclass(obj, BaseModel):
            models[name] = _model_facts(obj)
        elif issubclass(obj, enum.Enum):
            enums[name] = _enum_facts(obj)
    return {"models": models, "enums": enums}


def _canonical(doc: dict) -> str:
    """Mirror of the byte form the fixture file is written in."""
    return json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True)


def _digest_of(doc: dict) -> str:
    """Mirror of the builder's digest: sha256 over every fact but the digest."""
    body = {k: v for k, v in doc.items() if k != "digest"}
    return "sha256:" + hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


# --- The comparison ----------------------------------------------------------


def diff_facts(path: str, upstream: object, port: object, problems: list[str]) -> None:
    """One line per recorded fact that differs, recursively.

    Dicts are walked key by key, and a key present on only one side is itself
    a difference — so an encoder that grows a fact the mirror lacks (or the
    other way round) fails loudly instead of comparing a subset. Lists compare
    with order intact, because field order and enum member order and
    constraint order are all observable. Scalars compare as themselves.
    """
    if isinstance(upstream, dict) and isinstance(port, dict):
        for key in sorted(set(upstream) | set(port)):
            if key not in upstream:
                problems.append(f"{path}.{key}: recorded by the port snapshot, not upstream's")
            elif key not in port:
                problems.append(f"{path}.{key}: recorded upstream, absent from the port snapshot")
            else:
                diff_facts(f"{path}.{key}", upstream[key], port[key], problems)
    elif upstream != port:
        problems.append(f"{path}: {port!r}, upstream {upstream!r}")


def diff_documents(upstream: dict, port: dict) -> list[str]:
    """Every way one contract document differs from another, one line each.

    Mechanical by design: it diffs what was *recorded*, all of it, rather than
    a hand-listed subset of it. The fourth pass's lesson is exactly that a
    snapshot can record fourteen facts per field while the comparison reads
    three.
    """
    problems: list[str] = []
    for section, kind in (("models", "model"), ("enums", "enum")):
        up, down = upstream[section], port[section]
        for name in sorted(up.keys() | down.keys()):
            if name not in down:
                problems.append(f"{kind} {name}: missing from the port")
            elif name not in up:
                problems.append(f"{kind} {name}: not in the upstream contract")
            else:
                diff_facts(f"{kind} {name}", up[name], down[name], problems)
    return problems


def unexplained_bindings(namespace: object, owned: set[str]) -> list[str]:
    """Contract-shaped classes the namespace binds that nothing accounts for.

    The `__module__` ownership filter is what keeps imported machinery out of
    a snapshot — and exactly what a smuggle abuses. A one-line re-export
    (`from argus.types.compiler_schemas import SpecificRubric`) binds a foreign
    BaseModel into the namespace; the filter skips it, the snapshot never sees
    it, and the exact-set check built on the snapshot waves it through. The
    same shadow hides a class defined here whose `__module__` is laundered
    before it binds. So flip the filter around and audit what it skips: a
    pydantic-or-enum shaped class owned by no module in `owned` is legitimate
    only as machinery the namespace's own classes actually inherit from —
    BaseModel under every model, Enum under every enum. Anything else is
    concrete, inherited by nothing, and bound here for no honest reason.

    This is the completeness check the two snapshot-based checks structurally
    cannot make: they can only judge what the filter let through.
    """
    own = [
        obj
        for obj in vars(namespace).values()
        if inspect.isclass(obj) and obj.__module__ in owned
    ]
    problems: list[str] = []
    for name, obj in vars(namespace).items():
        if not inspect.isclass(obj) or obj.__module__ in owned:
            continue
        if not (issubclass(obj, BaseModel) or issubclass(obj, enum.Enum)):
            continue
        if any(obj in cls.__mro__ for cls in own):
            continue  # machinery in actual use by the contract classes
        problems.append(
            f"{name}: a {obj.__qualname__} from {obj.__module__} is bound in "
            "this namespace but defined by none it owns — contract-shaped, "
            "inherited by nothing"
        )
    return problems


def compare_to_snapshot(namespace: object, owned: set[str] | None = None) -> list[str]:
    """Every way `namespace` differs from the upstream contract.

    This is the function the live port is judged by, and the one
    `test_the_checks_can_fail` plants defects against — so a demonstration
    that one fires is a demonstration about the real check, not about `!=`.
    It diffs the snapshot the filter produced *and* audits what the filter
    skipped: the diff alone is blind to anything the ownership filter hides.
    """
    port = _snapshot_module(namespace, owned=owned)
    problems = diff_documents(SNAP, port)
    problems.extend(unexplained_bindings(namespace, owned or {getattr(namespace, "__name__", "")}))
    return problems


# --- The encodings themselves ------------------------------------------------

_SHARED_LIST: list = []
_SHARED_DICT: dict = {}


def test_a_generated_value_is_guarded_by_its_freshness_not_its_type():
    """A factory's value cannot be snapshotted, so its behaviour is — in the key.

    A factory's value would never match twice (a uuid), so it was once
    recorded by type alone. That made `lambda: "FIXED"` and
    `lambda: str(uuid.uuid4())[:8]` the same string, and a port giving every
    `Session` one shared id passed all 23 tests green. `session_id` is what
    `QAReport` keys on (`simbiclaw/sim@0c2cccd core/aggregator.py:98`) and
    what M21's replay record carries, so two different calls would have been
    indistinguishable in storage.

    The fourth pass added two more properties the type cannot carry: whether
    an empty container is shared, and whether "changes every call" actually
    carries entropy. This test pins every key form directly rather than
    leaving it to the mutation sweep — the encoder is duplicated by the
    snapshot script and this comparison, so a regression in one would move
    both together and cancel out.
    """

    class Fresh(BaseModel):
        v: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])

    class Constant(BaseModel):
        v: str = Field(default_factory=lambda: "FIXED")

    class Weak(BaseModel):
        v: str = Field(default_factory=lambda: str(uuid.uuid4())[:1])

    class FreshList(BaseModel):
        v: list[str] = Field(default_factory=list)

    class LiteralList(BaseModel):
        v: list[str] = []

    class SharedList(BaseModel):
        v: list[str] = Field(default_factory=lambda: _SHARED_LIST)

    class FreshDict(BaseModel):
        v: dict[str, str] = Field(default_factory=dict)

    class SharedDict(BaseModel):
        v: dict[str, str] = Field(default_factory=lambda: _SHARED_DICT)

    class FreshSet(BaseModel):
        v: set[str] = Field(default_factory=set)

    assert _default_key(Fresh.model_fields["v"]) == "<factory:str:fresh>"
    assert _default_key(Constant.model_fields["v"]) == "<factory:str:constant>"
    assert _default_key(Weak.model_fields["v"]) == "<factory:str:weak>", (
        "sixteen distinct values must not key as fresh — three draws called "
        "uuid4()[:1] fresh, which is the blind spot the middle tier closes"
    )
    assert _default_key(FreshList.model_fields["v"]) == "<factory:list:fresh-empty>"
    # Upstream writes `= []`; the port writes `default_factory=list`. Pydantic
    # deep-copies literal mutables per instance, so both spellings are the
    # same fact and must share one key.
    assert _default_key(LiteralList.model_fields["v"]) == "<factory:list:fresh-empty>"
    assert _default_key(FreshDict.model_fields["v"]) == "<factory:dict:fresh-empty>"
    assert _default_key(FreshSet.model_fields["v"]) == "<factory:set:fresh-empty>"
    assert _default_key(SharedList.model_fields["v"]) == "<factory:list:shared-empty>"
    assert _default_key(SharedDict.model_fields["v"]) == "<factory:dict:shared-empty>"

    # The property behind the shared-empty key: value-equality cannot see it,
    # identity can — two instances must not share one mutable object.
    a, b = SharedList(), SharedList()
    a.v.append("leaked")
    assert b.v == ["leaked"], "the shared-empty key names a real aliasing defect"
    a, b = FreshList(), FreshList()
    a.v.append("kept")
    assert b.v == [], "a fresh-empty factory must give per-instance state"

    # And the shipped snapshot records the real contract under these keys.
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    fields = snap["models"]["Session"]["fields"]
    assert fields["session_id"]["default"] == "<factory:str:fresh>"
    assert fields["turns"]["default"] == "<factory:list:fresh-empty>"
    assert fields["metadata"]["default"] == "<factory:dict:fresh-empty>"

    # The class-level fact forms, pinned raw (round 5). The encoder is
    # duplicated by the builder and this file, so these pins are what stop a
    # regression from moving both sides together and cancelling out.
    class PinnedFlag(str, enum.Enum):
        INCOMPLETE = "INCOMPLETE"

    def _coerce(value):
        return PinnedFlag.INCOMPLETE

    _coerce.__module__ = "enum"  # the forge: claiming to be machinery
    PinnedFlag._missing_ = _coerce
    pinned = _enum_facts(PinnedFlag)
    assert pinned["callables"]["_missing_"] == "enum", (
        "a forged module must not erase the name from the raw record"
    )
    assert pinned["callables"]["__new__"] == "enum", (
        "machinery is recorded too — that is why it cancels in the diff"
    )

    class Freeze:
        def __setattr__(self, name, value):
            raise AttributeError("frozen")

    class PinnedVerdict(Freeze, BaseModel):
        question_id: str
        score: float

    pinned_model = _model_facts(PinnedVerdict)
    assert pinned_model["bases"] == ["Freeze", "BaseModel", "object"], (
        "a plain mixin must show up in the MRO record"
    )
    assert pinned_model["callables"] == {}, (
        "an honest model's own dict holds no callables"
    )

    class PinnedDefault(BaseModel):
        v: float = Field(default=1.0, validate_default=True)

    pinned_field = _field_facts(PinnedDefault.model_fields["v"])
    assert pinned_field["validate_default"] is True
    assert pinned_field["kw_only"] is None
    assert pinned_field["discriminator"] is None
    assert pinned_field["title"] is None

    # And the shipped snapshot carries the same raw shape for the real
    # contract: machinery on the enums, bare MROs on the models.
    assert snap["enums"]["TurnFlag"]["callables"]["__new__"] == "enum"
    assert snap["models"]["Verdict"]["bases"] == ["BaseModel", "object"]


# --- Provenance --------------------------------------------------------------


def test_the_snapshot_is_the_pinned_commit_and_has_not_been_hand_edited():
    """Provenance is asserted, not stamped (Group A defect 7).

    The builder refuses to write unless the upstream tree is at the pinned
    commit and the file it imported is byte-identical to that path at that
    commit. This test's half of the guarantee: the fixture *claims* that
    commit — against a constant held in this file, not imported from the
    builder — the source bytes hash to the value recorded, and the digest
    over every fact still matches. So a fact edited by hand in the JSON,
    without rerunning the gated builder, fails here before it can re-baseline
    the oracle. Plainly, the limit: the digest anchors against laziness — the
    hand-edit, the stale re-baseline — not against forgery; an adversary who
    edits the facts and re-derives the digest defeats it, which is why the
    builder's write path is gated and the constants checked here are held in
    this file, not imported from the builder.
    """
    assert SNAP["source"]["commit"] == UPSTREAM_COMMIT
    assert SNAP["source"]["sha256"] == UPSTREAM_SOURCE_SHA256
    assert SNAP["digest"] == _digest_of(SNAP), (
        "the fixture's digest does not cover its own content — it has been "
        "hand-edited since the builder wrote it"
    )


# --- The contract itself -----------------------------------------------------


def test_port_matches_the_upstream_contract_exactly():
    """Every recorded fact, on the live port: field sets and order, all
    fourteen per-field facts, config, validators, MRO bases, ordered members,
    every callable each class defines, raw — and no contract-shaped binding
    in the namespace that nothing accounts for."""
    assert compare_to_snapshot(p) == []


def test_the_port_declares_exactly_the_upstream_set():
    """Completeness, in both directions (Group B defect 10).

    The old check iterated the snapshot and asked whether the port had
    everything upstream has — so a `class SmuggledScore(BaseModel):
    proposed_score: float = 0.0` in the port passed green, and proposed_score
    is precisely the name I5 and I7 keep out of this contract. The sets are
    now equal, not a superset test: missing and extra both fail, named.

    The retired `len(...) == 16` / `== 10` counts were the hand-written-table
    failure shape relocated from names to numbers — a rename in the port *and*
    the snapshot kept both counts green.
    """
    port = _snapshot_module(p)
    snap_keys = set(SNAP["models"]) | set(SNAP["enums"])
    port_keys = set(port["models"]) | set(port["enums"])
    assert port_keys == snap_keys, (
        f"missing from the port: {sorted(snap_keys - port_keys)}; "
        f"in the port but not upstream: {sorted(port_keys - snap_keys)}"
    )
    # And the snapshot's own story must hang together: what the import
    # snapshotted is what the upstream *text* declares. The AST parse is an
    # independent mechanism from the import; if they disagree, the fixture is
    # untrustworthy and no comparison against it means anything.
    assert snap_keys == set(SNAP["declared_classes"]), (
        "snapshot keys disagree with the upstream text's declared classes — "
        "the fixture cannot be trusted"
    )


def test_the_checks_can_fail():
    """Plant each defect class against the *live* comparison and watch it fire.

    An earlier version of this test built two throwaway classes and asserted
    they differed from a table it had written itself. It passed against a
    zero-byte module. This one mutates the real port and runs the real
    comparison, so what it demonstrates is what actually guards the tree —
    one plant per fact class the snapshot records, plus the namespace-level
    plants for what the ownership filter skips.
    """

    # Original classes keep `__module__ == "argus.types.pipeline"` through the
    # `vars(p)` copy; every replacement below is defined in this test module.
    # The snapshot must own both, or the stand-ins snapshot empty and every
    # mutation "fires" against nothing at all.
    owned = {"argus.types.pipeline", __name__}

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

    class ConstantFactory(BaseModel):  # a fresh id turned into a shared one
        session_id: str = Field(default_factory=lambda: "FIXED")
        agent_id: str = "UNKNOWN"
        duration_sec: int | None = None
        turns: list[p.Turn] = Field(default_factory=list)
        metadata: dict[str, object] = Field(default_factory=dict)

    class WrongWire(str, enum.Enum):
        INCOMPLETE = "INCOMPLETE"
        ASR_ERROR = "asr_error"  # upstream is "ASR_ERROR"
        ROLE_SWAPPED = "ROLE_SWAPPED"
        NORMAL = "NORMAL"

    class AliasedField(BaseModel):  # Group A #1: the wire key silently moves
        id: str
        role: Literal["customer", "agent"]
        text: str = Field(alias="body")
        flags: list[p.TurnFlag] = Field(default_factory=list)
        reliability: Literal["high", "low"] = "high"
        timestamp_start: int | None = None
        timestamp_end: int | None = None

    class ConstrainedWeight(BaseModel):  # Group A #2: FieldInfo.metadata gains ge=
        id: int
        category: p.RubricCategory
        name: str
        pass_criteria: str
        fail_criteria: str
        na_criteria: str | None = None
        is_weighted: bool = False
        weight: float = Field(default=1.0, ge=0.0)
        always_check: bool = True
        requires_domain_kb: bool = False
        trigger_keywords: list[str] = Field(default_factory=list)
        is_veto: bool = False

    class ForbiddingConfig(BaseModel):  # Group A #3: extra="forbid"
        id: str
        role: Literal["customer", "agent"]
        text: str
        flags: list[p.TurnFlag] = Field(default_factory=list)
        reliability: Literal["high", "low"] = "high"
        timestamp_start: int | None = None
        timestamp_end: int | None = None

        model_config = {"extra": "forbid"}

    class ZeroingValidator(BaseModel):  # Group A #4a: every shipped score is 0.0
        question_id: str
        rubric_id: int | None = None
        result: p.VerdictResult
        confidence: float
        score: float
        weight: float = 1.0
        evidence: list[p.EvidenceItem] = Field(default_factory=list)
        requires_human_review: bool = False
        review_reason: str | None = None
        checking_path: Literal["A", "B", "C"] = "A"

        @field_validator("score")
        @classmethod
        def _zero(cls, v: float) -> float:
            return 0.0

    class EvidenceClearer(BaseModel):  # Group A #4b: every anchor stripped
        question_id: str
        rubric_id: int | None = None
        result: p.VerdictResult
        confidence: float
        score: float
        weight: float = 1.0
        evidence: list[p.EvidenceItem] = Field(default_factory=list)
        requires_human_review: bool = False
        review_reason: str | None = None
        checking_path: Literal["A", "B", "C"] = "A"

        @model_validator(mode="after")
        def _clear(self):
            self.evidence = []
            return self

    class WrongBase(enum.Enum):  # Group A #5: (str, Enum) -> (Enum)
        INCOMPLETE = "INCOMPLETE"
        ASR_ERROR = "ASR_ERROR"
        ROLE_SWAPPED = "ROLE_SWAPPED"
        NORMAL = "NORMAL"

    class ReorderedFlag(str, enum.Enum):  # Group A #6: order is observable
        NORMAL = "NORMAL"
        INCOMPLETE = "INCOMPLETE"
        ASR_ERROR = "ASR_ERROR"
        ROLE_SWAPPED = "ROLE_SWAPPED"

    class AliasedFlag(str, enum.Enum):  # Group B #11: iteration skips aliases
        INCOMPLETE = "INCOMPLETE"
        ASR_ERROR = "ASR_ERROR"
        ASR_GARBLED = "ASR_ERROR"  # a second name for the same member
        ROLE_SWAPPED = "ROLE_SWAPPED"
        NORMAL = "NORMAL"

    class SharedMetadata(BaseModel):  # Group B #8: one dict for every Session
        session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
        agent_id: str = "UNKNOWN"
        duration_sec: int | None = None
        turns: list[p.Turn] = Field(default_factory=list)
        metadata: dict[str, object] = Field(default_factory=lambda: _SHARED_DICT)

    class WeakEntropy(BaseModel):  # Group B #9: fresh-looking, sixteen values
        session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:1])
        agent_id: str = "UNKNOWN"
        duration_sec: int | None = None
        turns: list[p.Turn] = Field(default_factory=list)
        metadata: dict[str, object] = Field(default_factory=dict)

    class SmuggledScore(BaseModel):  # Group B #10: a class upstream does not have
        proposed_score: float = 0.0

    class HiddenField(BaseModel):  # round-4 boundary: the repr surface narrows
        id: str
        role: Literal["customer", "agent"]
        text: str
        flags: list[p.TurnFlag] = Field(default_factory=list)
        reliability: Literal["high", "low"] = "high"
        timestamp_start: int | None = Field(default=None, repr=False)
        timestamp_end: int | None = None

    class LenientFlag(str, enum.Enum):  # round-4 #21: garbage coerces to a member
        INCOMPLETE = "INCOMPLETE"
        ASR_ERROR = "ASR_ERROR"
        ROLE_SWAPPED = "ROLE_SWAPPED"
        NORMAL = "NORMAL"

        @classmethod
        def _missing_(cls, value):
            return cls.INCOMPLETE

    class ModuleRewritten(BaseModel):  # round-4 #20b: ownership filter laundered
        proposed_score: float = 0.0

    ModuleRewritten.__module__ = "somewhere.else"

    class PostInitZeroer(BaseModel):  # round-5 AT1: protocol hook, no bucket
        question_id: str
        rubric_id: int | None = None
        result: p.VerdictResult
        confidence: float
        score: float
        weight: float = 1.0
        evidence: list[p.EvidenceItem] = Field(default_factory=list)
        requires_human_review: bool = False
        review_reason: str | None = None
        checking_path: Literal["A", "B", "C"] = "A"

        def model_post_init(self, __context: object) -> None:
            self.score = 0.0

    class PostHocFlag(str, enum.Enum):  # round-5 AT2: assigned after the class
        INCOMPLETE = "INCOMPLETE"
        ASR_ERROR = "ASR_ERROR"
        ROLE_SWAPPED = "ROLE_SWAPPED"
        NORMAL = "NORMAL"

    def _coerce(value):
        return PostHocFlag.INCOMPLETE

    _coerce.__module__ = "enum"  # the forge: claiming to be machinery
    PostHocFlag._missing_ = _coerce

    class Freeze:  # round-5 AT3: plain mixin, registered nowhere
        def __setattr__(self, name, value):
            raise AttributeError("frozen")

    class MixinVerdict(Freeze, BaseModel):
        question_id: str
        rubric_id: int | None = None
        result: p.VerdictResult
        confidence: float
        score: float
        weight: float = 1.0
        evidence: list[p.EvidenceItem] = Field(default_factory=list)
        requires_human_review: bool = False
        review_reason: str | None = None
        checking_path: Literal["A", "B", "C"] = "A"

    class ValidatedDefault(BaseModel):  # round-5 AT5: default runs validators
        id: int
        category: p.RubricCategory
        name: str
        pass_criteria: str
        fail_criteria: str
        na_criteria: str | None = None
        is_weighted: bool = False
        weight: float = Field(default=1.0, validate_default=True)
        always_check: bool = True
        requires_domain_kb: bool = False
        trigger_keywords: list[str] = Field(default_factory=list)
        is_veto: bool = False

    # Baseline first. Without this the whole test passes vacuously against an
    # empty module — every mutation "fires" because everything is missing,
    # which is the tautology this test exists to have escaped.
    assert compare_to_snapshot(stand_in(), owned=owned) == [], (
        "the unmutated stand-in is already dirty, so nothing below proves anything"
    )

    for label, target, mutation in [
        ("deleted field", "CleanTurn", {"CleanTurn": MissingField}),
        ("changed default", "RubricItem", {"RubricItem": ChangedDefault}),
        ("widened annotation", "Turn", {"Turn": WidenedAnnotation}),
        ("relaxed requirement", "EvidenceItem", {"EvidenceItem": RelaxedRequirement}),
        ("changed wire value", "TurnFlag", {"TurnFlag": WrongWire}),
        ("constant factory", "Session", {"Session": ConstantFactory}),
        ("field alias", "CleanTurn", {"CleanTurn": AliasedField}),
        ("added constraint", "RubricItem", {"RubricItem": ConstrainedWeight}),
        ('extra="forbid"', "CleanTurn", {"CleanTurn": ForbiddingConfig}),
        ("field validator", "Verdict", {"Verdict": ZeroingValidator}),
        ("model validator", "Verdict", {"Verdict": EvidenceClearer}),
        ("enum base", "TurnFlag", {"TurnFlag": WrongBase}),
        ("enum reorder", "TurnFlag", {"TurnFlag": ReorderedFlag}),
        ("enum alias", "TurnFlag", {"TurnFlag": AliasedFlag}),
        ("shared-empty factory", "Session", {"Session": SharedMetadata}),
        ("weak-entropy factory", "Session", {"Session": WeakEntropy}),
        ("repr=False", "CleanTurn", {"CleanTurn": HiddenField}),
        ("enum _missing_ hook", "TurnFlag", {"TurnFlag": LenientFlag}),
        (
            "namespace re-export",
            "SpecificRubric",
            {"SpecificRubric": compiler_schemas.SpecificRubric},
        ),
        ("laundered __module__", "ModuleRewritten", {"ModuleRewritten": ModuleRewritten}),
        ("model_post_init hook", "Verdict", {"Verdict": PostInitZeroer}),
        ("post-hoc forged hook", "TurnFlag", {"TurnFlag": PostHocFlag}),
        ("plain mixin base", "Verdict", {"Verdict": MixinVerdict}),
        ("validate_default", "RubricItem", {"RubricItem": ValidatedDefault}),
    ]:
        problems = compare_to_snapshot(stand_in(**mutation), owned=owned)
        assert problems, f"the comparison did not catch: {label}"
        # And it is *this* mutation being caught, not ambient breakage.
        assert any(target in line for line in problems), (
            f"{label}: comparison complained, but not about {target}: {problems}"
        )

    # And one class *added*, not replaced: exactly the defect the old subset
    # comparison was blind to, because it only ever asked what the port lacked.
    problems = compare_to_snapshot(stand_in(SmuggledScore=SmuggledScore), owned=owned)
    assert any(
        "SmuggledScore" in line and "not in the upstream contract" in line
        for line in problems
    ), f"the comparison did not name the smuggled model: {problems}"

    # And a whole model removed.
    gone = types.ModuleType("gone")
    gone.__dict__.update({k: v for k, v in vars(p).items() if k != "Session"})
    assert any("Session" in line for line in compare_to_snapshot(gone, owned=owned)), (
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

    The M5 binding lives in test_m5_verdict_fields_never_enter_replay_hash.
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


def test_m5_verdict_fields_never_enter_replay_hash():
    """I5, bound to M5's port: the model-produced numbers stay out of the hash.

    `Verdict.score` and `Verdict.confidence` are model-produced (the Verdict
    docstring in `pipeline.py` says so), and M5's Contract says a proposed
    score cannot enter the replay-bearing payload. The test above exercises
    9020's module, so this one binds the clause to the artifact M5 shipped.
    Four parts, each guarding a way the previous one could pass vacuously:

    1. the port actually declares the model-produced fields — a rename must
       error here, not let the exclusion pass over an empty set;
    2. `_hashable()`'s output — the allowlist IS the contract surface —
       carries neither name as a key, at the top level or nested;
    3. real data: two records differing only in `AnchoredEvidence.score`,
       replay.py's own example of a model-proposed number riding along,
       hash identically;
    4. liveness: a stand-in namespace whose `_hashable` *does* carry the
       score hashes differently, so part 2 is enforced by difference and
       not by hope.
    """
    from argus.core.adjust import Precedent
    from argus.core.grounding import GroundedFinding, ProposedFinding
    from argus.core.replay import ReplayRecord, _hashable, record_for, replay_hash
    from argus.core.score import ScorableFact
    from argus.types.anchored import AnchoredEvidence, Span

    # 1. Port binding. The names are the fields the Verdict docstring marks
    # as model-produced; if upstream renames them, this fails loudly here.
    model_produced = {"score", "confidence"}
    assert model_produced <= set(p.Verdict.model_fields), (
        "Verdict no longer declares the model-produced fields the I5 clause "
        "names; re-read its docstring and update this set, do not delete it"
    )

    epoch = "c" * 40
    transcript = "[25s -> 30s]客服: 请问您贵姓？"
    quote = "请问您贵姓？"
    start = transcript.index(quote)

    def record(evidence_score: float) -> ReplayRecord:
        finding = GroundedFinding(
            finding=ProposedFinding(
                finding_id="F01",
                rubric_id=1,
                intents_node="process/greeting",
                violation="称谓语缺失",
                evidence=(
                    AnchoredEvidence(
                        turn_id="T01",
                        text=quote,
                        score=evidence_score,
                        supports=True,
                        span=Span(start=start, end=start + len(quote)),
                        quote=quote,
                        intents_sha=epoch,
                    ),
                ),
            ),
            epoch=epoch,
        )
        return record_for(
            intents_sha=epoch,
            rubric_version="v1",
            transcript=transcript,
            findings=(finding,),
            facts=(
                ScorableFact(finding_id="F01", rubric_id=1, outcome=p.VerdictResult.FAIL),
            ),
            precedents=(
                Precedent(
                    precedent_id="P-1",
                    prior_evaluation_id="prior-eval",
                    rubric_id=1,
                    ruled_outcome=p.VerdictResult.PASS,
                    intents_sha=epoch,
                ),
            ),
        )

    low, high = record(0.05), record(0.95)

    # Anti-vacuity: the inputs really did differ, on the exact field the
    # replay module's docstring names as a model-proposed number riding along.
    assert low.findings[0].finding.evidence[0].score == 0.05
    assert high.findings[0].finding.evidence[0].score == 0.95

    # 2. The recursive key sweep. Shown to reach the nested dicts, so the
    # empty intersection is a finding, not a sweep that collected nothing.
    collected: set[str] = set()

    def sweep(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                collected.add(key)
                sweep(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                sweep(item)

    sweep(_hashable(low))
    assert "evidence" in collected, "the sweep never reached a nested dict"
    assert not collected & model_produced, (
        f"model-produced keys reached the allowlist: {sorted(collected & model_produced)}"
    )

    # 3. Behavior, on real data: the proposed number does not move the hash.
    assert replay_hash(low) == replay_hash(high)

    # 4. Liveness — prove the hash mechanism consumes its allowlist, so the
    # day `score` is added to it, the hash moves and part 2 has teeth. A
    # vars() copy alone is not enough: the copied replay_hash's globals stay
    # bound to the real module, so the code object is rebound onto the
    # stand-in's namespace explicitly.
    from argus.core import replay as replay_module

    stand_in = types.ModuleType("replay_with_score")
    stand_in.__dict__.update(vars(replay_module))

    def _hashable_with_score(rec: ReplayRecord) -> dict:
        payload = _hashable(rec)
        payload["score"] = rec.findings[0].finding.evidence[0].score
        return payload

    stand_in._hashable = _hashable_with_score
    stand_in_hash = types.FunctionType(
        replay_hash.__code__, stand_in.__dict__, "replay_hash"
    )
    assert stand_in_hash(low) != replay_hash(low), (
        "adding score to the allowlist did not move the hash — part 2's "
        "exclusion is not enforced by the mechanism"
    )
    assert stand_in_hash(low) != stand_in_hash(high), (
        "the stand-in hash does not actually read the score it was given"
    )
