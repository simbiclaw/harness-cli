# tests/test_io_import.py
"""9024 M7 — the port: B's proposal half lives in `io/`, behaviour-identical.

The contract is M7's data-flow table, not a module list: seven modules move
re-namespaced (`llm_client`, `nli`, `prompts`, `fact_checker` path A only,
`atomizer`, `question_generator`, `qa_agent` rewired), the arguments they used
to take from dropped modules are supplied — `Session` from the call record
(`argus.io.call_record`), `SessionKBContext` from a test-owned stub (the
baseline's rubric items as data) until 9025's Provider lands — and the orchestrator's ingest stages are gone. What must be true:
the port produces the **same output as 9023 M4's baseline on the same
transcript** (captured from simbi into `tests/fixtures/io_import_baseline.json`
with the same fakes), and nothing in `io/` re-decides a producer's.

The fakes (`tests/fakes.py`) mirror simbi's reply-for-reply, so both sides of
the comparison are fed identical answers.

The interface the tests pin, per the data-flow table and the 2026-09-15 Q29
ruling (roles must be established or the call is not processed):

    session    = call_record.build_session(record)   # declines if roles absent
    kb_context = <test-owned stub: the baseline's rubric items as data>
    report     = qa_agent.run_session(session, kb_context=..., llm_client=..., nli_model=..., nli=...)
"""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GOLDEN = REPO / "tests" / "fixtures" / "io_import_baseline.json"
RECORD = REPO / "tests" / "fixtures" / "call_record_baseline.json"

PORTED_MODULES = (
    "argus.io.llm_client",
    "argus.io.nli",
    "argus.io.prompts",
    "argus.io.fact_checker",
    "argus.io.atomizer",
    "argus.io.question_generator",
    "argus.io.qa_agent",
)


def test_the_seven_ported_modules_live_in_io():
    """The import list is the port's existence claim."""
    for name in PORTED_MODULES:
        importlib.import_module(name)


# --- The structural check: the act, not the word ---------------------------
#
# The first version of this test scanned the seven ported modules for tokens
# (`rglob`, `role_swap`, `bottom_up`, …). It was defeated by a live
# knowledge-tree traversal and a transcript re-derivation inside
# `io/qa_agent.py` — `Path("INTENTS").glob("**/*.yaml")` plus a regex
# extraction into `session.metadata` — with all eight acceptance tests green.
# Three separate reasons it failed, all of them the same mistake:
#
#   vocabulary  the ban is "no tree traversal"; the check matched `rglob`, and
#               `glob` walks the same tree.
#   prose/code  a token scan cannot tell a call from a comment. The bypasser's
#               first attempt was blocked because a *comment* said `rglob` — a
#               false positive of the very same root cause.
#   scope       it covered the seven ported modules; `io/call_record.py`, whose
#               whole job is reading producer data, was not among them.
#
# So the check is over all of `io/`, and it reads the parsed syntax tree, where
# a comment is not a call and a method is named by what it does. Following
# `tests/test_no_write_path.py`'s idiom: a deterministic checker, red samples
# proving it fires on the act, green samples proving it does not fire on the
# word, then the live tree.
#
# What it deliberately does NOT do: it does not ban scanning text. The ported
# code scans text legitimately and must keep doing so — `_filter_na_rubrics`
# tests `kw in transcript_text`, `question_generator` tests
# `kw in t.text`, both ported verbatim from B and both shaping the M4 baseline.
# What is banned is the *instrument for re-deriving structure*: a regex over
# text. Residual hole, stated rather than hidden: a role decided from a
# substring scan into a differently-named variable would not be seen here; the
# write ban below catches it only if the role is written to a role-named field.

# Calls that walk a directory tree, whatever the receiver is called. The ban is
# on traversal, not on one spelling of it.
TRAVERSAL = {"glob", "iglob", "rglob", "iterdir", "walk", "scandir", "listdir"}

# The re-family. Everything except the whole-token validators extracts
# something out of a text; `match`/`fullmatch` against an anchored pattern asks
# only "is this entire string one X", which is the shape calibration_io.py uses
# to validate the ledger's identifiers (epoch SHA, manifest file name,
# `cookbook.<slug>.yaml`, a severity ref, a bare item id) — none of which is
# turn text. See `test_the_live_io_tree_is_clean` for the residual.
REGEX_METHODS = {
    "compile", "search", "match", "fullmatch", "findall", "finditer",
    "sub", "subn", "split",
}
VALIDATORS = {"match", "fullmatch"}

# The fields a producer owns. `io/` reads them (call_record maps them onto
# `Turn.role`) and never writes them: role establishment is the ruling's
# precondition, so a module that writes one has taken the producer's decision.
ROLE_FIELDS = {"speaker_role", "speaker_role_source"}


def _callee_name(call: ast.Call) -> str:
    """The name a call goes by, for `m.f()` and `f()` alike."""
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    if isinstance(call.func, ast.Name):
        return call.func.id
    return ""


def _regex_bindings(tree: ast.AST) -> tuple[set[str], set[str], set[str]]:
    """The names in this module that reach `re` or a pattern built from it.

    Aliases are resolved rather than guessed: `import re as _r` binds `_r`,
    `from re import findall` binds `findall`, and a name assigned the result of
    a `compile()` call is a pattern whatever it is called. A check that matches
    the spelling `re.` is the same defect as one that matches `rglob`.
    """
    module_names = {"re"}
    function_names: set[str] = set()
    pattern_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "re":
                    module_names.add(alias.asname or "re")
        elif isinstance(node, ast.ImportFrom) and node.module == "re":
            for alias in node.names:
                function_names.add(alias.asname or alias.name)
        elif (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and _callee_name(node.value) == "compile"
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    pattern_names.add(target.id)
    return module_names, function_names, pattern_names


def _pattern_argument(call: ast.Call) -> ast.expr | None:
    """The pattern handed to `compile(...)`, positional or by keyword."""
    if call.args:
        return call.args[0]
    for keyword in call.keywords:
        if keyword.arg == "pattern":
            return keyword.value
    return None


def _role_writes(tree: ast.AST) -> list[str]:
    """Stores into a role field — the producer's decision, taken in `io/`."""
    writes: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, ast.Store)
            and node.attr in ROLE_FIELDS
        ):
            writes.append(f"line {node.lineno}: assigns {node.attr}")
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.ctx, ast.Store)
            and isinstance(node.slice, ast.Constant)
            and node.slice.value in ROLE_FIELDS
        ):
            writes.append(f"line {node.lineno}: assigns [{node.slice.value!r}]")
        elif (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Store)
            and node.id in ROLE_FIELDS
        ):
            writes.append(f"line {node.lineno}: assigns {node.id}")
    return writes


def producer_logic_violations(code: str) -> list[str]:
    """Return the producer decisions `code` takes, as `line N: what` strings.

    Three acts: walking a tree, extracting structure from text with a regex,
    and writing a speaker role. Comments and docstrings are not calls, so
    naming a banned act in prose is not a violation — the false positive and
    the false negative had the same root cause.
    """
    tree = ast.parse(code)
    module_names, function_names, pattern_names = _regex_bindings(tree)
    re_receivers = module_names | pattern_names
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _callee_name(node)
        func = node.func

        if name in TRAVERSAL:
            violations.append(
                f"line {node.lineno}: {name}() walks a tree — the knowledge "
                "tree has one read surface (M13's Provider), not this"
            )
            continue

        on_regex = (
            isinstance(func, ast.Attribute)
            and (
                (isinstance(func.value, ast.Name) and func.value.id in re_receivers)
                or (
                    isinstance(func.value, ast.Call)
                    and _callee_name(func.value) == "compile"
                )
            )
        ) or (isinstance(func, ast.Name) and func.id in function_names)

        if name in REGEX_METHODS and on_regex:
            if name == "compile":
                pattern = _pattern_argument(node)
                if not (
                    isinstance(pattern, ast.Constant)
                    and isinstance(pattern.value, str)
                    and pattern.value.startswith("^")
                    and pattern.value.endswith("$")
                ):
                    violations.append(
                        f"line {node.lineno}: compile() pattern is not an "
                        "anchored ^…$ whole-token validator"
                    )
            elif name not in VALIDATORS:
                violations.append(
                    f"line {node.lineno}: {name}() extracts from text — "
                    "re-deriving structure from a transcript is the producer's"
                )

    for write in _role_writes(tree):
        violations.append(f"{write} a speaker role — establishment is a producer")

    return violations


# --- Red samples: each is an act, and each must be caught ------------------

RED_LIVE_TRAVERSAL = """
from pathlib import Path
import re

def enrich(session):
    for node in Path("INTENTS").glob("**/*.yaml"):
        text = node.read_text()
    session.metadata["phone"] = re.findall(r"1[3-9]\\\\d{9}", "".join(t.text for t in session.turns))
"""

RED_MODULE_GLOB = """
import glob

def nodes():
    return glob.glob("INTENTS/_rubric/*.yaml")
"""

RED_INNOCUOUS_RECEIVER = """
def walk(base):
    return list(base.rglob("*.json"))
"""

RED_OS_WALK = """
import os

def find(root):
    for dirpath, _, names in os.walk(root):
        yield dirpath, names
"""

RED_ITERDIR = """
def names(turns_dir):
    return [p.name for p in turns_dir.iterdir()]
"""

RED_FROM_RE = """
from re import findall

def phones(turns):
    return [findall(r"1[3-9]\\\\d{9}", t.text) for t in turns]
"""

RED_ALIASED_RE = """
import re as _r

def hits(turns):
    return [t for t in turns if _r.search(r"\\\\d{11}", t.text)]
"""

RED_COMPILED_THEN_SEARCH = """
import re

PHONE = re.compile(r"1[3-9]\\\\d{9}")

def hits(turns):
    return [t for t in turns if PHONE.search(t.text)]
"""

RED_INLINE_SEARCH = """
import re

def hits(turns):
    return [t for t in turns if re.compile(r"1[3-9]\\\\d{9}").search(t.text)]
"""

RED_ROLE_WRITE = """
def attribute(record):
    record["speakers"][0]["speaker_role"] = "agent"
    record["speakers"][0]["speaker_role_source"] = "keyword-match"
"""

# --- Green samples: the word is not the act -------------------------------

GREEN_COMMENT_ONLY = """
def build(record):
    # deliberately no rglob here, and no glob either; the tree is M13's
    # and re.findall over a transcript is the producer's job
    return record["turns"]
"""

GREEN_DOCSTRING_ONLY = '''
def build(record):
    """Reads the record. Does not rglob, glob, or iterdir anything."""
    return record["turns"]
'''

GREEN_KEYWORD_SCAN = """
def filter_na(rubrics, transcript_text, turns):
    applicable = [
        r for r in rubrics
        if any(kw in transcript_text for kw in r.trigger_keywords)
    ]
    relevant = [t for t in turns if any(kw in t.text for kw in rubrics[0].trigger_keywords)]
    return applicable, relevant
"""

GREEN_ANCHORED_VALIDATOR = """
import re
from pathlib import Path

_EPOCH_RE = re.compile(r"^\\\\d{4}-\\\\d{2}-\\\\d{2}-[0-9a-f]{40}$")

def load(path: Path, epoch_id: str):
    file_match = "calibration-manifest.%s.yaml" % epoch_id
    if not _EPOCH_RE.match(epoch_id):
        raise ValueError(file_match)
    return epoch_id
"""

GREEN_STRING_METHODS = """
def parts(path, text):
    stem = path.name.split(".")[0]
    return stem, text.split("客户")


def cid(criterion_id):
    return criterion_id.startswith("C")
"""

GREEN_ROLE_READ = """
def build(record):
    roles = {s["id"]: s["speaker_role"] for s in record["speakers"]}
    return [{"id": t["id"], "role": roles[t["speaker"]]} for t in record["turns"]]
"""


def test_red_samples_are_caught():
    """The checker fires on every shape of the act, however it is spelled."""
    for name, sample in [
        ("live traversal + regex into metadata", RED_LIVE_TRAVERSAL),
        ("glob module", RED_MODULE_GLOB),
        ("innocuous receiver name", RED_INNOCUOUS_RECEIVER),
        ("os.walk", RED_OS_WALK),
        ("iterdir", RED_ITERDIR),
        ("from re import findall", RED_FROM_RE),
        ("import re as _r", RED_ALIASED_RE),
        ("compiled pattern then .search", RED_COMPILED_THEN_SEARCH),
        ("inline compile(...).search", RED_INLINE_SEARCH),
        ("write to a role field", RED_ROLE_WRITE),
    ]:
        assert producer_logic_violations(sample), f"checker missed the act: {name}"


def test_green_samples_are_clean():
    """The word is not the act: prose, and the port's own text handling, pass."""
    for name, sample in [
        ("a comment naming the banned calls", GREEN_COMMENT_ONLY),
        ("a docstring naming them", GREEN_DOCSTRING_ONLY),
        ("keyword scan over the transcript (ported, must survive)", GREEN_KEYWORD_SCAN),
        ("anchored validator over ledger identifiers", GREEN_ANCHORED_VALIDATOR),
        ("str.split / startswith on non-regex receivers", GREEN_STRING_METHODS),
        ("reading a speaker role", GREEN_ROLE_READ),
    ]:
        found = producer_logic_violations(sample)
        assert not found, f"false positive on {name}: {found}"


def test_the_check_covers_the_module_whose_job_is_reading_producer_data():
    """The scope half of the defect: `call_record.py` is in the scan.

    The old check walked `PORTED_MODULES`, so the one module whose whole job is
    reading the producer's record — exactly where a re-derivation would be
    introduced — was the one module never scanned.
    """
    io_dir = REPO / "src" / "argus" / "io"
    scanned = {path.name for path in io_dir.glob("*.py")}
    assert "call_record.py" in scanned
    for name in PORTED_MODULES:
        assert name.split("io.", 1)[1] + ".py" in scanned


def test_no_producer_logic_in_io():
    """No module in `io/` re-decides what a producer decides.

    M7's prohibitions, structural: no knowledge-tree traversal (M13's Provider
    is the sole read surface), no ASR-text parsing of call records (the
    producer's `calls/*.json` already carries the structure), no role
    establishment (Q29 makes it an input precondition). Scanned over **all** of
    `io/`, not the seven ported modules — the property is worded "no module
    inside `io/`", and the narrowness was the third way the old check was
    bypassed.

    What this does not cover structurally: role inference from transcript text
    and call-level intent assignment have no syntactic signature here (the
    port's absorbed `_infer_intent` is the consumer's own within-call proposal
    step, permitted by the data-flow table), so for those two the evidence is
    the port's shape, not this assertion.
    """
    io_dir = REPO / "src" / "argus" / "io"
    for name in PORTED_MODULES:
        filename = name.split("io.", 1)[1] + ".py"
        assert (io_dir / filename).exists(), f"missing ported module: io/{filename}"

    failures: list[str] = []
    for path in sorted(io_dir.glob("*.py")):
        code = path.read_text(encoding="utf-8")
        for violation in producer_logic_violations(code):
            failures.append(f"io/{path.name}: {violation}")
    assert not failures, "producer logic in io/:\n  " + "\n  ".join(failures)


def test_pipeline_runs_from_io_matches_the_m4_baseline():
    """The port is behaviour-identical: same input, same output as M4's baseline.

    The input is the synthetic call record encoding `TRANSCRIPT_NORMAL` (the
    golden's own input), with speaker roles established. The kb context is the
    stub the sequencing note allows until 9025 lands. Every field of the
    report is compared — the port does not get to differ quietly.
    """
    from tests.fakes import FakeLLM, FakeNLI

    from argus.io import call_record, qa_agent
    from argus.types.pipeline import RubricItem, SessionKBContext

    record = json.loads(RECORD.read_text(encoding="utf-8"))
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["report"]
    items_data = json.loads(
        (REPO / "tests" / "fixtures" / "rubric_items_baseline.json").read_text(encoding="utf-8")
    )["items"]

    # The kb stub the sequencing note allows: the 25-item rubric the baseline
    # was captured with, as data, until 9026's compiled nodes and 9025's
    # Provider replace this fixture with the real referent.
    # low_coverage_warning=True is the faithful value: the baseline context was
    # produced on an empty KB, and B's retriever warns at that coverage.
    items = [RubricItem.model_validate(i) for i in items_data]
    kb_context = SessionKBContext(
        all_rubric_items=items, applicable_rubrics=items,
        low_coverage_warning=True,
    )

    session = call_record.build_session(record)
    report = qa_agent.run_session(
        session,
        kb_context=kb_context,
        llm_client=FakeLLM(),
        nli_model="cross-encoder/nli-deberta-v3-large",
        nli=FakeNLI(),
    )

    assert report.model_dump() == golden
