#!/usr/bin/env python3
"""Snapshot the upstream schema shape, for `tests/test_schemas.py` to compare against.

9021 M5. The first acceptance test hand-transcribed the expected field sets and
enum maps. Adversarial verification found the tables happened to be correct but
the approach unsound: a model omitted from *both* the port and the table is
undetectable, and the tables guarded field *names* only — so a changed default,
a widened annotation, or a relaxed requirement all passed green. One of those,
flipping `RubricItem.weight`'s default from 1.0 to 2.0, doubles every unweighted
row's contribution to the shipped score.

The fix is the same one M15 used for the rubric: stop transcribing. This script
imports the upstream module and records, per model, every field's requiredness,
realized default and annotation, plus declaration order and the full model set —
and every enum's complete name→value map. The test then compares mechanically,
so completeness is a property of the snapshot rather than of someone's diligence.

Regenerate when the upstream contract legitimately changes. A diff in the
snapshot is then a reviewable record of an on-disk format change, which is
Tier C, rather than a silent drift.

Usage:  python3 scripts/build_schema_snapshot.py [--upstream /home/user/sim]
"""

from __future__ import annotations

import argparse
import enum
import inspect
import json
import sys
from pathlib import Path

from pydantic import BaseModel
from pydantic_core import PydanticUndefined

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "tests" / "fixtures" / "upstream_schema_snapshot.json"

UPSTREAM_REPO = "simbiclaw/sim"
UPSTREAM_COMMIT = "0c2cccd"
UPSTREAM_PATH = "models/schemas.py"


def annotation_key(ann: object) -> str:
    """A stable string for an annotation, comparable across modules.

    `Literal["customer", "agent"]` and `str` must not compare equal — widening
    the first to the second drops the constraint M2's role-swap fix rests on.
    """
    text = str(ann)
    # Model references carry their defining module; strip it so the upstream
    # `models.schemas.CleanTurn` matches the port's `argus.types.pipeline.CleanTurn`.
    for prefix in ("models.schemas.", "argus.types.pipeline.", "<class '", "'>"):
        text = text.replace(prefix, "")
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
            return "<factory:uncallable>"
        # A factory producing a fresh value each call (uuid) is recorded by
        # type, not value, or the snapshot would never match twice.
        return f"<factory:{type(produced).__name__}>" if produced else repr(produced)
    if default is PydanticUndefined:
        return "<required>"
    if isinstance(default, enum.Enum):
        return f"{type(default).__name__}.{default.name}"
    return repr(default)


def snapshot_module(module) -> dict:
    models: dict[str, dict] = {}
    enums: dict[str, dict[str, str]] = {}

    for name, obj in vars(module).items():
        if not inspect.isclass(obj) or obj.__module__ != module.__name__:
            continue
        if issubclass(obj, BaseModel):
            models[name] = {
                "order": list(obj.model_fields),
                "fields": {
                    fname: {
                        "required": info.is_required(),
                        "default": default_key(info),
                        "annotation": annotation_key(info.annotation),
                    }
                    for fname, info in obj.model_fields.items()
                },
            }
        elif issubclass(obj, enum.Enum):
            enums[name] = {m.name: m.value for m in obj}

    return {"models": models, "enums": enums}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--upstream", type=Path, default=Path("/home/user/sim"))
    args = ap.parse_args()

    if not (args.upstream / UPSTREAM_PATH).exists():
        raise SystemExit(f"upstream schema not found at {args.upstream / UPSTREAM_PATH}")
    sys.path.insert(0, str(args.upstream))
    from models import schemas  # noqa: PLC0415

    doc = {
        "source": {
            "repo": UPSTREAM_REPO,
            "commit": UPSTREAM_COMMIT,
            "path": UPSTREAM_PATH,
        },
        "generated_by": "scripts/build_schema_snapshot.py",
        "note": (
            "Generated, not transcribed. A diff here is an on-disk format change "
            "(Tier C) and needs a steering entry, not a regenerate-and-move-on."
        ),
        **snapshot_module(schemas),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(REPO_ROOT)}: "
        f"{len(doc['models'])} models, {len(doc['enums'])} enums"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
