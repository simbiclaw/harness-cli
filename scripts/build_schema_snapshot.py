#!/usr/bin/env python3
"""Snapshot the upstream schema shape, for `tests/test_schemas.py` to compare against.

9021 M5. The first acceptance test hand-transcribed the expected field sets and
enum maps. Adversarial verification found the tables happened to be correct but
the approach unsound: a model omitted from *both* the port and the table is
undetectable, and the tables guarded field *names* only — so a changed default,
a widened annotation, or a relaxed requirement all passed green. One of those,
flipping `RubricItem.weight`'s default from 1.0 to 2.0, doubles every weighted
row's contribution to the shipped score (`simbiclaw/sim@0c2cccd
core/aggregator.py:55` multiplies `v.score * v.weight`).

The fix is the same one M15 used for the rubric: stop transcribing. This script
imports the upstream module and records, per model, every field's requiredness,
realized default, annotation, aliases and constraints, the model's `model_config`
and its validators/serializers, plus declaration order and the full model set —
and every enum's base classes and complete ordered member list. The test then
regenerates the same facts from the port and diffs, so completeness is a
property of the snapshot rather than of someone's diligence, and *every* fact
recorded here is compared without anyone writing an assertion per fact.

Six things this file learned in rounds four and five:

- **What the check cannot see belongs in the key.** Requiredness, default and
  annotation were the only three facts recorded, so fourteen mutations that
  change the on-disk contract without touching those three survived: an alias,
  a `ge=` constraint, `extra="forbid"`, `frozen=True`, `str_to_lower=True`, a
  score-zeroing `@field_validator`, an evidence-clearing `@model_validator`, a
  non-`str` enum base, a reordered enum. All nine facts were readable from the
  objects this script already held.
- **Provenance has to be verified, not stamped.** `UPSTREAM_COMMIT` used to be
  a literal nothing checked, and the test never read `source` at all — so
  `--upstream <any directory with a models/schemas.py>` produced a fixture
  stamped `0c2cccd`, and "completeness is a property of the snapshot" reduced
  to "completeness is a property of whatever directory the last person passed".
  The builder now asks git for the SHA, refuses to write unless the file it
  imported is byte-identical to that path at that commit, and records what it
  verified. The document carries a digest so a later hand-edit of the fixture
  is a test failure rather than a silent re-baseline.
- **Value-equality cannot see shared mutability.** An empty result used to
  encode as `[]` whether the factory handed every caller the same object or a
  new one, so `default_factory=lambda: _SHARED_LIST` and `default_factory=list`
  were the same string — and two `Session()` instances then shared one
  `metadata` dict. Empty mutable results are now classified by identity: the
  factory is called twice more, and any two results being the same object is
  recorded as `shared-empty`. Literal mutables (`= []`, upstream's spelling)
  are `fresh-empty` by construction — pydantic deep-copies them per instance —
  which is what keeps the two spellings equal.
- **"Changes every call" is not entropy.** Three draws classified
  `uuid4()[:1]` — sixteen distinct values over two thousand calls — as
  `fresh`. The sampler now draws twenty-four times and names three tiers:
  `constant`, `weak`, `fresh`. It is a statistical proxy with a documented
  floor (see `default_key`), not a guarantee.
- **Aliases are members too.** Iterating an enum class skips aliased names;
  `__members__` keeps them, in declaration order, aliases adjacent to their
  canonical member.
- **A filter is an attack surface.** `model_post_init` registers in no
  decorator bucket; a plain mixin overriding `__setattr__` appears in no
  recorded fact; and a behaviour hook assigned after the class with a forged
  `__module__` passes a defining-module filter by claiming to be machinery.
  So the class-level facts went raw: every callable on every contract class,
  by name and defining module, and every MRO base. A name cannot be forged
  away — it is recorded under whatever module it claims, and the claiming is
  itself the diff. Upstream and the port run the same interpreter, so the
  machinery entries are identical on both sides and cancel in the diff;
  filtering them out bought nothing and cost the truth.

Regenerate when the upstream contract legitimately changes. A diff in the
snapshot is then a reviewable record of an on-disk format change, which is
Tier C, rather than a silent drift.

Usage:  python3 scripts/build_schema_snapshot.py [--upstream /home/user/sim]
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import enum
import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel
from pydantic_core import PydanticUndefined

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "tests" / "fixtures" / "upstream_schema_snapshot.json"

UPSTREAM_REPO = "simbiclaw/sim"
UPSTREAM_COMMIT = "0c2cccd178a5696c59ffa90dca129511af5ae5c0"
UPSTREAM_PATH = "models/schemas.py"

# The seven decorator buckets pydantic records per model. Read off the dataclass
# rather than listed here, so a pydantic upgrade that adds an eighth bucket is
# picked up instead of silently unwatched.
DECORATOR_BUCKETS = tuple(
    f.name for f in dataclasses.fields(BaseModel.__pydantic_decorators__)
)


def annotation_key(ann: object) -> str:
    """A canonical string for an annotation, comparable across the two modules.

    Upstream writes `typing.List[X]` and `Optional[X]`; the port writes
    `list[X]` and `X | None`. Those are the same type and must compare equal.
    `Literal["customer", "agent"]` and `str` are NOT the same type and must not
    — widening that one drops the constraint M2's role-swap fix rests on.

    Both sides of the comparison run through this one function, so the port's
    facts and upstream's facts are directly diffable.
    """
    text = str(ann)
    for before, after in (
        ("typing.List[", "list["),
        ("typing.Dict[", "dict["),
        ("typing.Set[", "set["),
        ("typing.Tuple[", "tuple["),
        # Model references carry their defining module; strip it so the upstream
        # `models.schemas.CleanTurn` matches `argus.types.pipeline.CleanTurn`.
        ("models.schemas.", ""),
        ("argus.types.pipeline.", ""),
        ("<class '", ""),
        ("'>", ""),
    ):
        text = text.replace(before, after)
    if text.startswith("typing.Optional[") and text.endswith("]"):
        text = text[len("typing.Optional[") : -1] + " | None"
    return text


def default_key(info: object) -> str:
    """A stable string for a field's default, with factories realized.

    `default_factory=list` and `default_factory=dict` are recorded by the value
    they produce, so the `= []` to `default_factory` rewrite compares equal
    while a changed literal default does not.
    """
    default = getattr(info, "default", PydanticUndefined)
    factory = getattr(info, "default_factory", None)
    if factory is not None:
        try:
            produced = factory()
        except TypeError:
            # A one-argument factory takes the already-validated data and cannot
            # be called here. Recording every such factory as one opaque string
            # made any two of them compare equal; the code object's constants and
            # names are the cheapest fact that actually distinguishes them.
            # Unreachable on the 0c2cccd contract — upstream has exactly one
            # factory and it takes no arguments — so this is a floor, not a
            # feature: if upstream ever grows one, the oracle already sees it.
            code = getattr(factory, "__code__", None)
            body = repr((code.co_consts, code.co_names)) if code else repr(factory)
            return f"<factory:validated-data:{body}>"
        if type(produced) in (list, dict, set):
            # An empty mutable container is where value-equality goes blind:
            # `[] == []` whether the factory hands every caller the same
            # object or a new one, and two `Session()` instances sharing one
            # `metadata` dict is the defect. Identity sees what equality
            # cannot, so the factory is called twice more and any two results
            # being the same object is recorded. Mutable only — tuple,
            # frozenset and str are excluded on purpose: CPython legally
            # interns immutable empties (`lambda: ()` returns one shared
            # tuple), and sharing an immutable is harmless, so those keep the
            # value path below.
            second, third = factory(), factory()
            shared = produced is second or second is third or produced is third
            kind = "shared-empty" if shared else "fresh-empty"
            return f"<factory:{type(produced).__name__}:{kind}>"
        if not produced:
            # An empty immutable container is its own value, so `= ()` and
            # `default_factory=tuple` compare equal, as they should.
            return repr(produced)
        # A factory producing a value cannot be snapshotted by value — a uuid
        # would never match twice. Recording it by type alone was a blind spot:
        # `lambda: "FIXED"` and `lambda: uuid4().hex[:8]` were the same string,
        # so a port that gave every Session one shared id passed green, and
        # `session_id` is what QAReport and the replay record key on. Freshness
        # is the property the type cannot carry, so it goes in the key. Say
        # plainly what this check is: a statistical proxy with a documented
        # floor, not an entropy guarantee. Twenty-four draws, all distinct,
        # collide with p ~= 7e-8 over a 16**8 space and with certainty over a
        # sixteen-value alphabet — which is the discrimination the contract
        # needs: upstream's session_id is uuid4 hex, and the mutation worth
        # catching is a low-entropy substitute (`uuid4()[:1]` spans sixteen
        # distinct values and keyed `fresh` under the old three-draw sampler).
        # What this cannot see: a factory that is fresh for its first N calls
        # and constant afterwards still keys `fresh`; no draw count fixes that.
        draws = {repr(produced)} | {repr(factory()) for _ in range(23)}
        if len(draws) == 1:
            kind = "constant"
        elif len(draws) == 24:
            kind = "fresh"
        else:
            kind = "weak"
        return f"<factory:{type(produced).__name__}:{kind}>"
    if default is PydanticUndefined:
        return "<required>"
    if isinstance(default, enum.Enum):
        return f"{type(default).__name__}.{default.name}"
    if type(default) in (list, dict, set) and not default:
        # Upstream writes literal mutable defaults (`turns: List[Turn] = []`)
        # and the port rewrites them as `default_factory=list`; pydantic
        # deep-copies literal mutables per instance (verified: two instances
        # of `x: list = []` hold distinct objects), so both spellings are the
        # same fact — fresh per instance by construction — and share one key.
        return f"<factory:{type(default).__name__}:fresh-empty>"
    return repr(default)


def field_facts(info: object) -> dict:
    """Everything about one field that the on-disk contract depends on.

    The first three were the whole oracle and let eight mutations through.
    The rest are the ones that change what the model accepts or emits without
    changing requiredness, default or annotation:

    - aliases decide the *key* on the wire. `alias="w"` makes
      `model_validate({"weight": 2.0})` silently keep the default, and
      `serialization_alias="aid"` makes `model_dump_json(by_alias=True)` emit a
      key nothing downstream reads. Both are on-disk format changes (Tier C).
    - `constraints` is `FieldInfo.metadata` — `ge=0.0`, `max_length=3`. Upstream
      has none; one added here rejects payloads upstream accepts, which is the
      break the first attempt at this port was rejected for.
    - `frozen` / `exclude` / `repr` change assignability and what `model_dump`
      and the repr surface emit.
    - `validate_default` runs validators even on the default — a default that
      never went through them is a different fact. `kw_only` / `discriminator`
      / `title` are the same class of constructor-surface flag: outside this
      record they are unwatched, and the fifth round of this oracle was spent
      learning not to leave FieldInfo attributes outside it.
    """
    return {
        "required": info.is_required(),
        "default": default_key(info),
        "annotation": annotation_key(info.annotation),
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


def _defined_module(value: object) -> str | None:
    """The module a callable was defined in, unwrapped from its descriptor."""
    if isinstance(value, property):
        value = value.fget
    elif isinstance(value, (classmethod, staticmethod)):
        value = value.__func__
    return getattr(value, "__module__", None)


def callables_of(cls: type) -> dict[str, str | None]:
    """Every callable on the class, by name and defining module — raw.

    The class's own dict, unfiltered: contract-defined hooks, enum- and
    pydantic-injected machinery, builtin slots, all of it. Recorded raw
    because a defining-module filter is itself an attack surface: a hook
    assigned after the class whose `__module__` is forged to `enum` passes a
    filtered record as machinery, but a name cannot be forged away — it is
    recorded with whatever module it claims, and the claiming is visible.
    Upstream and the port run the same interpreter, so the machinery entries
    are identical on both sides and cancel in the diff; only contract-level
    differences survive.

    The predicate is `callable(...) or isinstance(..., (classmethod,
    staticmethod, property))` because the descriptor forms are not callable
    objects: a classmethod never is, a property never is, and a staticmethod
    only became one in 3.10 — a bare `callable()` check silently drops an
    in-body `@classmethod def _missing_`, which is precisely the hook this
    fact exists to see.
    """
    return {
        name: _defined_module(value)
        for name, value in vars(cls).items()
        if callable(value) or isinstance(value, (classmethod, staticmethod, property))
    }


def model_facts(model: type[BaseModel]) -> dict:
    """One model's fields plus the whole-model surfaces that were unwatched.

    `config` is the full `model_config`. Upstream sets none, so it is `{}`
    everywhere; `extra="forbid"` rejects the forward-compatible keys M6 adds,
    `frozen=True` makes assignment raise where upstream allows it, and
    `str_to_lower=True` / `str_strip_whitespace=True` rewrite `CleanTurn.text`,
    destroying the verbatim text the I2 character span is measured against
    (`src/argus/types/pipeline.py:62`).

    `decorators` is the name of every validator and serializer pydantic knows
    about. A `@field_validator("score")` returning 0.0 zeroes every shipped
    score and a `@model_validator` clearing `evidence` strips every anchor —
    neither touches a field's declared shape, so nothing else here sees them.
    Names and targets only: comparing function bodies would fail on a rename.

    `bases` is every MRO base name: the decorator buckets see only what
    pydantic registers, so a plain mixin overriding `__setattr__` — same
    observable effect as `frozen`, no registration anywhere — was invisible
    until its name showed up here.

    `callables` is every callable on the class, raw (`callables_of`): the
    decorator buckets also miss the protocol hooks pydantic calls by name —
    a `model_post_init` that zeroes `score` registers nowhere and touches no
    declared field.
    """
    decorators: dict[str, object] = {}
    for bucket in DECORATOR_BUCKETS:
        found = getattr(model.__pydantic_decorators__, bucket)
        decorators[bucket] = sorted(found)
    return {
        "bases": [c.__name__ for c in model.__mro__[1:]],
        "callables": callables_of(model),
        "order": list(model.model_fields),
        "config": {k: repr(v) for k, v in sorted(model.model_config.items())},
        "decorators": decorators,
        "fields": {name: field_facts(info) for name, info in model.model_fields.items()},
    }


def enum_facts(member_type: type[enum.Enum]) -> dict:
    """An enum's members *in order*, what it inherits from, and what it defines.

    `bases` catches `class TurnFlag(Enum)` written where upstream has
    `class TurnFlag(str, Enum)`: same names, same values, but
    `TurnFlag.NORMAL == "NORMAL"` flips to False and every string comparison in
    the pipeline quietly stops matching.

    `members` is a list, not a mapping, because declaration order is observable:
    `list(VerdictResult)[0]` is what a caller reaching for a fallback gets, and
    a mapping compared as a mapping cannot see PASS and FAIL swap places. Read
    through `__members__`, not iteration — iteration skips aliased members, so
    a member added under a second name was invisible; `__members__` keeps it,
    adjacent to its canonical member, in declaration order.

    `callables` is every callable on the class, raw (`callables_of`). Bases
    and members do not see behaviour: a `_missing_` added to TurnFlag makes
    `TurnFlag("garbage")` coerce to INCOMPLETE where upstream raises
    ValueError, and no wire value changes. This record used to filter the
    class dict to callables the contract module defined — which is exactly
    the hole a forged `__module__` walks through, so the filter is gone and
    the machinery rides along, cancelling in the diff.
    """
    return {
        "bases": [c.__name__ for c in member_type.__mro__[1:]],
        "members": [[name, m.value] for name, m in member_type.__members__.items()],
        "callables": callables_of(member_type),
    }


def snapshot_module(module: object, owned: set[str] | None = None) -> dict:
    """The contract as this module declares it.

    `owned` is the set of defining module names a class must belong to to count
    as part of the contract; it defaults to `module` itself. The comparison runs
    this same function over the port, and the mutation battery runs it over
    stand-in modules whose replacement classes are defined in the test module —
    without the filter, the imported `BaseModel` and `Enum` names would be
    snapshotted as contract members of every namespace.
    """
    owned = owned or {getattr(module, "__name__", "")}
    models: dict[str, dict] = {}
    enums: dict[str, dict] = {}

    for name, obj in vars(module).items():
        if not inspect.isclass(obj) or obj.__module__ not in owned:
            continue
        if issubclass(obj, BaseModel):
            models[name] = model_facts(obj)
        elif issubclass(obj, enum.Enum):
            enums[name] = enum_facts(obj)

    return {"models": models, "enums": enums}


def canonical(doc: dict) -> str:
    """The byte form both the file and the digest are computed from."""
    return json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True)


def digest_of(doc: dict) -> str:
    """A digest over every fact but the digest itself.

    This is what makes a hand-edit of the fixture a test failure. Renaming a
    model in the port *and* in the snapshot keeps the counts and the comparison
    green — that mutation survived the third pass — but it cannot keep this
    digest, because the person doing it is editing JSON, not running the builder.
    And the builder cannot be run to launder it: `verified_source` below refuses
    any directory that is not the pinned upstream commit.

    Plainly, its limit: sha256 over data anyone can recompute anchors this
    against *laziness* — the hand-edit, the stale re-baseline — not against
    *forgery*. An adversary who edits the facts and re-derives the digest
    defeats it; that is why the write path is gated by `verified_source`, and
    why the constants the test checks the document against are held in
    tests/test_schemas.py, not imported from here.
    """
    body = {k: v for k, v in doc.items() if k != "digest"}
    return "sha256:" + hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise SystemExit(
            f"provenance check failed: `git {' '.join(args)}` in {repo} exited "
            f"{done.returncode}: {done.stderr.strip() or done.stdout.strip()}"
        )
    return done.stdout


def verified_source(upstream: Path) -> dict:
    """Identify the upstream tree with git, or refuse to write.

    The old builder stamped `UPSTREAM_COMMIT` on whatever it was pointed at, and
    no test read it back. The regenerate-to-fit attack was therefore free: break
    the port, point `--upstream` at a directory whose `models/schemas.py`
    re-exports the port, regenerate, green — with the fixture still claiming
    `commit: 0c2cccd`.

    Three facts are checked, in the order a doubt would arise: the directory is
    a git repo at the pinned commit; the schema file on disk is byte-identical
    to that path at that commit (so an edited working copy cannot be imported
    and recorded as if it were the commit's); and the bytes are hashed into the
    document so the test can pin them to a constant it holds independently.

    Deliberately narrow: repo-wide dirtiness is not checked, only this one
    file's. An unrelated untracked file in the upstream checkout is not a reason
    to refuse, and widening it would make the builder unrunnable for an honest
    operator with a scratch file in that tree.
    """
    head = _git(upstream, "rev-parse", "HEAD").strip()
    if head != UPSTREAM_COMMIT:
        raise SystemExit(
            f"{upstream} is at {head}, not the pinned upstream {UPSTREAM_COMMIT}. "
            "Refusing to write a snapshot stamped with a commit it was not built "
            "from. Check out the pinned commit, or change UPSTREAM_COMMIT here and "
            "in tests/test_schemas.py — which is an on-disk contract change and "
            "Tier C, so it needs a steering entry."
        )

    on_disk = (upstream / UPSTREAM_PATH).read_bytes()
    committed = subprocess.run(
        ["git", "-C", str(upstream), "show", f"{UPSTREAM_COMMIT}:{UPSTREAM_PATH}"],
        capture_output=True,
        check=False,
    )
    if committed.returncode != 0:
        raise SystemExit(f"{UPSTREAM_PATH} is not present at {UPSTREAM_COMMIT} in {upstream}")
    if on_disk != committed.stdout:
        raise SystemExit(
            f"{upstream / UPSTREAM_PATH} differs from {UPSTREAM_COMMIT}:{UPSTREAM_PATH}. "
            "The module this script would import is not the module the snapshot "
            "would claim to describe. Stash or revert, then re-run."
        )

    return {
        "repo": UPSTREAM_REPO,
        "commit": head,
        "path": UPSTREAM_PATH,
        "sha256": hashlib.sha256(on_disk).hexdigest(),
    }


def declared_classes(source: bytes) -> list[str]:
    """Top-level class names as the upstream *text* declares them, in order.

    The completeness claim used to be two integers written by hand in the test
    (`== 16`, `== 10`). Renaming a model in the port and in the snapshot kept
    both counts and stayed green. This reads the names out of the source with a
    second, independent mechanism — the parser rather than the import — so the
    test can assert that the set of snapshotted classes *is* the set upstream
    declares, and nobody maintains a number.
    """
    tree = ast.parse(source)
    return [node.name for node in tree.body if isinstance(node, ast.ClassDef)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--upstream", type=Path, default=Path("/home/user/sim"))
    args = ap.parse_args()

    if not (args.upstream / UPSTREAM_PATH).exists():
        raise SystemExit(f"upstream schema not found at {args.upstream / UPSTREAM_PATH}")
    source = verified_source(args.upstream)

    sys.path.insert(0, str(args.upstream))
    from models import schemas  # noqa: PLC0415

    doc = {
        "source": source,
        "generated_by": "scripts/build_schema_snapshot.py",
        "note": (
            "Generated, not transcribed, from a git-verified upstream checkout. "
            "A diff here is an on-disk format change (Tier C) and needs a steering "
            "entry, not a regenerate-and-move-on. Hand-editing this file breaks "
            "`digest` and fails tests/test_schemas.py."
        ),
        "declared_classes": declared_classes((args.upstream / UPSTREAM_PATH).read_bytes()),
        **snapshot_module(schemas),
    }
    doc["digest"] = digest_of(doc)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(canonical(doc) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(REPO_ROOT)} from {source['commit'][:7]}: "
        f"{len(doc['models'])} models, {len(doc['enums'])} enums"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
