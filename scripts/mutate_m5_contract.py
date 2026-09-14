#!/usr/bin/env python3
"""Apply each known M5 defect, one at a time, and watch the suite catch it.

The 21 defects are what three rounds of adversarial verification plus two
further passes found in M5's acceptance floor. The numbering and grouping
cross-reference HANDOFF-2026-09-14.md: Group A (#1-7) is what the round-4
builder records, Group B (#8-11) is what the local round added, R1 marks the
round-1 classes that started the generated oracle, and #20/#21 are what
round-4's verification found in the namespace and behaviour surfaces. Each
defect is applied as a textual mutation to `src/argus/types/pipeline.py` —
except #7, which hand-edits the fixture the way a lazy re-baseline would —
then the suite runs and the tree is restored. Restore happens in a `finally`:
the port file is untouchable territory, and a crashed sweep must not leave a
mutated tree.

Methodology, hardening the pyc taint that corrupted round-4's first verdict:
two same-size mutations landing inside one clock second share the (mtime,
size) pair CPython's bytecode validator checks, so a suite run can silently
import the PREVIOUS attempt's compiled port and grade a file that is no
longer on disk. Every attempt therefore clears `__pycache__` under `src/argus`
and `tests` first, and runs pytest with bytecode writing disabled.

Any row that comes out green is a survivor — it means the acceptance floor
does not actually catch that defect, and the repair is incomplete.

Run with the venv interpreter (it has pydantic):

    PYTHONPATH=src .venv/bin/python scripts/mutate_m5_contract.py

Exit status: 0 if every row is red, 1 if any survivor.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PORT = REPO_ROOT / "src" / "argus" / "types" / "pipeline.py"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "upstream_schema_snapshot.json"
SUITE = "tests/test_schemas.py"


@dataclass
class Mutation:
    ref: str  # cross-reference into the handoff's grouping
    description: str
    edits: list[tuple[str, str]] = field(default_factory=list)
    fixture: bool = False  # hand-edit the fixture instead of the port


MUTATIONS: list[Mutation] = [
    Mutation(
        "A#1",
        'field alias added (RubricItem.weight alias="w")',
        edits=[
            (
                "    is_weighted: bool = False\n    weight: float = 1.0\n",
                '    is_weighted: bool = False\n    weight: float = Field(default=1.0, alias="w")\n',
            )
        ],
    ),
    Mutation(
        "A#2",
        "FieldInfo constraint added (weight ge=0.0)",
        edits=[
            (
                "    is_weighted: bool = False\n    weight: float = 1.0\n",
                "    is_weighted: bool = False\n    weight: float = Field(default=1.0, ge=0.0)\n",
            )
        ],
    ),
    Mutation(
        "A#3a",
        'model_config extra="forbid" (CleanTurn)',
        edits=[
            (
                "class CleanTurn(BaseModel):\n    id: str",
                'class CleanTurn(BaseModel):\n    model_config = {"extra": "forbid"}\n\n    id: str',
            )
        ],
    ),
    Mutation(
        "A#3b",
        "model_config frozen=True (CleanTranscript)",
        edits=[
            (
                "class CleanTranscript(BaseModel):\n    session_id: str",
                'class CleanTranscript(BaseModel):\n    model_config = {"frozen": True}\n\n    session_id: str',
            )
        ],
    ),
    Mutation(
        "A#3c",
        "model_config str_to_lower=True (CleanTurn)",
        edits=[
            (
                "class CleanTurn(BaseModel):\n    id: str",
                'class CleanTurn(BaseModel):\n    model_config = {"str_to_lower": True}\n\n    id: str',
            )
        ],
    ),
    Mutation(
        "A#3d",
        "model_config str_strip_whitespace=True (CleanTurn)",
        edits=[
            (
                "class CleanTurn(BaseModel):\n    id: str",
                'class CleanTurn(BaseModel):\n    model_config = {"str_strip_whitespace": True}\n\n    id: str',
            )
        ],
    ),
    Mutation(
        "A#4a",
        "@field_validator zeroes Verdict.score",
        edits=[
            (
                "from pydantic import BaseModel, Field\n",
                "from pydantic import BaseModel, Field, field_validator\n",
            ),
            (
                '    checking_path: Literal["A", "B", "C"] = "A"\n',
                '    checking_path: Literal["A", "B", "C"] = "A"\n'
                "\n"
                '    @field_validator("score")\n'
                "    @classmethod\n"
                "    def _zero_score(cls, v: float) -> float:\n"
                "        return 0.0\n",
            ),
        ],
    ),
    Mutation(
        "A#4b",
        "@model_validator clears Verdict.evidence",
        edits=[
            (
                "from pydantic import BaseModel, Field\n",
                "from pydantic import BaseModel, Field, model_validator\n",
            ),
            (
                '    checking_path: Literal["A", "B", "C"] = "A"\n',
                '    checking_path: Literal["A", "B", "C"] = "A"\n'
                "\n"
                '    @model_validator(mode="after")\n'
                "    def _clear_evidence(self):\n"
                "        self.evidence = []\n"
                "        return self\n",
            ),
        ],
    ),
    Mutation(
        "A#5",
        "enum base (str, Enum) -> (Enum) (TurnFlag)",
        edits=[("class TurnFlag(str, Enum):", "class TurnFlag(Enum):")],
    ),
    Mutation(
        "A#6",
        "enum members reordered (NORMAL first in TurnFlag)",
        edits=[
            (
                'class TurnFlag(str, Enum):\n    INCOMPLETE = "INCOMPLETE"\n    ASR_ERROR = "ASR_ERROR"\n    ROLE_SWAPPED = "ROLE_SWAPPED"\n    NORMAL = "NORMAL"\n',
                'class TurnFlag(str, Enum):\n    NORMAL = "NORMAL"\n    INCOMPLETE = "INCOMPLETE"\n    ASR_ERROR = "ASR_ERROR"\n    ROLE_SWAPPED = "ROLE_SWAPPED"\n',
            )
        ],
    ),
    Mutation(
        "A#7",
        "provenance: fixture fact hand-edited, digest stale",
        fixture=True,
    ),
    Mutation(
        "B#8",
        "shared-empty default_factory (Session.metadata)",
        edits=[
            (
                "from pydantic import BaseModel, Field\n",
                "from pydantic import BaseModel, Field\n\n"
                "_SHARED_METADATA: dict = {}  # every instance gets this one object\n",
            ),
            (
                "    metadata: dict[str, Any] = Field(default_factory=dict)\n",
                "    metadata: dict[str, Any] = Field(default_factory=lambda: _SHARED_METADATA)\n",
            ),
        ],
    ),
    Mutation(
        "B#9",
        "weak-entropy factory (session_id uuid4()[:1])",
        edits=[("str(uuid.uuid4())[:8]", "str(uuid.uuid4())[:1]")],
    ),
    Mutation(
        "B#10",
        "smuggled extra model (SmuggledScore.proposed_score)",
        edits=[
            (
                "    summary: str\n    improvement_suggestions: list[str]\n",
                "    summary: str\n    improvement_suggestions: list[str]\n"
                "\n\n"
                "class SmuggledScore(BaseModel):\n"
                "    proposed_score: float = 0.0\n",
            )
        ],
    ),
    Mutation(
        "B#11",
        "enum alias added (TurnFlag.ASR_GARBLED)",
        edits=[
            (
                '    ASR_ERROR = "ASR_ERROR"\n    ROLE_SWAPPED',
                '    ASR_ERROR = "ASR_ERROR"\n    ASR_GARBLED = "ASR_ERROR"\n    ROLE_SWAPPED',
            )
        ],
    ),
    Mutation(
        "R1",
        "deleted field (CleanTurn.timestamp_end)",
        edits=[
            (
                "    timestamp_start: int | None = None\n    timestamp_end: int | None = None\n",
                "    timestamp_start: int | None = None\n",
            )
        ],
    ),
    Mutation(
        "R1",
        "changed default (RubricItem.weight 1.0 -> 2.0)",
        edits=[
            (
                "    is_weighted: bool = False\n    weight: float = 1.0\n",
                "    is_weighted: bool = False\n    weight: float = 2.0\n",
            )
        ],
    ),
    Mutation(
        "R1",
        "widened annotation (Turn.role Literal -> str)",
        edits=[
            (
                '    id: str\n    role: Literal["customer", "agent"]\n    text: str  # verbatim',
                "    id: str\n    role: str\n    text: str  # verbatim",
            )
        ],
    ),
    Mutation(
        "R1",
        "relaxed requirement (Atom.source_turn_ids optional)",
        edits=[
            (
                "    source_turn_ids: list[str]  # required upstream: this is the atom's anchor\n",
                "    source_turn_ids: list[str] = []\n",
            )
        ],
    ),
    Mutation(
        "#20",
        "namespace re-export (compiler_schemas.SpecificRubric)",
        edits=[
            (
                "    summary: str\n    improvement_suggestions: list[str]\n",
                "    summary: str\n    improvement_suggestions: list[str]\n"
                "\n\n"
                "from argus.types.compiler_schemas import SpecificRubric  # noqa: E402\n",
            )
        ],
    ),
    Mutation(
        "#21",
        "enum behaviour hook (_missing_ coerces garbage to INCOMPLETE)",
        edits=[
            (
                'class TurnFlag(str, Enum):\n    INCOMPLETE = "INCOMPLETE"\n    ASR_ERROR = "ASR_ERROR"\n    ROLE_SWAPPED = "ROLE_SWAPPED"\n    NORMAL = "NORMAL"\n',
                'class TurnFlag(str, Enum):\n    INCOMPLETE = "INCOMPLETE"\n    ASR_ERROR = "ASR_ERROR"\n    ROLE_SWAPPED = "ROLE_SWAPPED"\n    NORMAL = "NORMAL"\n'
                "\n"
                "    @classmethod\n"
                "    def _missing_(cls, value):\n"
                "        return cls.INCOMPLETE\n",
            )
        ],
    ),
]


def apply_fixture_mutation() -> None:
    """A#7: change a fact the way a hand-edit would — digest left stale.

    The score-doubling default, laundered through the fixture: RubricItem
    weight 1.0 -> 2.0 in the JSON, with the digest recomputed by nobody. The
    file is rewritten in the builder's canonical byte form so this is exactly
    "edited one value", not "reformatted the document".
    """
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    doc["models"]["RubricItem"]["fields"]["weight"]["default"] = "'2.0'"
    FIXTURE.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def clear_pycache() -> None:
    """Kill every cached bytecode the suite could stale-import.

    CPython validates a .pyc against its source by (mtime, size). Two
    same-size mutations written inside one clock second therefore validate
    against a .pyc compiled from the PREVIOUS attempt, and the suite grades a
    port that is no longer on disk — the taint that corrupted round-4's first
    verdict. Clear the caches before every attempt and forbid new ones (-B and
    PYTHONDONTWRITEBYTECODE, belt and suspenders) for the duration.
    """
    for base in (REPO_ROOT / "src" / "argus", REPO_ROOT / "tests"):
        for cache in base.rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)


def run_suite() -> tuple[bool, str]:
    """The suite under the current tree. Green means a survivor; the output
    travels with the verdict so a survivor can be investigated, not guessed at."""
    env = {**os.environ, "PYTHONPATH": "src", "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", SUITE, "-q"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode == 0, done.stdout + done.stderr


def main() -> int:
    port_original = PORT.read_text(encoding="utf-8")
    fixture_original = FIXTURE.read_bytes()
    rows: list[tuple[Mutation, bool, str]] = []

    print(f"{'defect':<7} {'mutation':<52} result")
    print(f"{'-' * 7} {'-' * 52} {'-' * 6}")
    try:
        for mutation in MUTATIONS:
            try:
                if mutation.fixture:
                    apply_fixture_mutation()
                else:
                    text = port_original
                    for anchor, replacement in mutation.edits:
                        if anchor not in text:
                            raise SystemExit(
                                f"mutation {mutation.ref}: anchor not found in "
                                f"{PORT.relative_to(REPO_ROOT)}: {anchor!r}"
                            )
                        text = text.replace(anchor, replacement, 1)
                    PORT.write_text(text, encoding="utf-8")
                clear_pycache()
                green, output = run_suite()
            finally:
                PORT.write_text(port_original, encoding="utf-8")
                FIXTURE.write_bytes(fixture_original)
            rows.append((mutation, green, output))
            verdict = "GREEN  <-- SURVIVOR" if green else "red"
            print(f"{mutation.ref:<7} {mutation.description:<52} {verdict}")
            if green:
                print(output[-2000:])
    finally:
        PORT.write_text(port_original, encoding="utf-8")
        FIXTURE.write_bytes(fixture_original)

    assert PORT.read_text(encoding="utf-8") == port_original, (
        "the port file was not restored — do not commit anything"
    )
    assert FIXTURE.read_bytes() == fixture_original, (
        "the fixture was not restored — do not commit anything"
    )

    survivors = [m for m, green, _ in rows if green]
    print()
    if survivors:
        print(f"{len(survivors)} SURVIVOR(S) of {len(rows)} — the floor missed:")
        for m in survivors:
            print(f"  {m.ref} {m.description}")
        return 1
    print(
        f"all {len(rows)} mutations red — every known defect is caught "
        f"by {SUITE}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
