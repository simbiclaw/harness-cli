"""S1 fixture — no write path from `src/argus/` into `INTENTS/` (D15).

Specified by 9002 at M0 and M7 and never written; landed here under 9021 M13.
Until now D15 was prose, and the only thing keeping it true was that the code
which would violate it did not exist yet. That is not enforcement — it is an
accident that expires the moment someone writes the obvious convenience.

The rule D15 states: Argus is a consumer. Corrections do not re-enter the tree
by Argus reaching back into its own referent; they arrive as upstream
write-time epoch commits (ADR-0003). A consumer that can rewrite what it is
measured against has no fixed referent, and I4's pinned-epoch reproducibility
becomes unfalsifiable.

Note for M16: producing compiled `_rubric/` nodes is *emitting to a staging
path*. The moment a milestone writes them into the tree directly, this fixture
fires — which is the intended behaviour, not a false positive.

Structured like `tests/test_i8_provenance_separation.py`: a deterministic
checker, red and green samples proving the checker fires, then a scan of the
live tree.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src" / "argus"

# A referent is "INTENTS-ish" if the expression mentions the tree by name, by
# a conventional variable, or by one of its landmark files.
INTENTS_TOKENS = {
    "INTENTS",
    "intents",
    "intents_root",
    "intents_path",
    "intents_dir",
    "intents_node",
    "node_path",
    "epoch_path",
}
INTENTS_LITERAL_MARKERS = ("INTENTS", "_rubric", "EPOCH.yaml", "_meta/")

# Methods that mutate the filesystem at the receiver's path.
MUTATING_METHODS = {
    "write_text",
    "write_bytes",
    "touch",
    "unlink",
    "mkdir",
    "rmdir",
    "rename",
    "replace",
    "symlink_to",
    "hardlink_to",
    "chmod",
}
# Module-level functions that mutate a path given as an argument.
MUTATING_FUNCS = {
    "remove",
    "unlink",
    "rename",
    "replace",
    "rmtree",
    "copy",
    "copy2",
    "copyfile",
    "copytree",
    "move",
    "mkdir",
    "makedirs",
}
WRITE_MODES = set("wax+")


def _mentions_intents(node: ast.AST) -> bool:
    """True when any identifier or string under `node` names the INTENTS tree."""
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and n.id in INTENTS_TOKENS:
            return True
        if isinstance(n, ast.Attribute) and n.attr in INTENTS_TOKENS:
            return True
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if any(m in n.value for m in INTENTS_LITERAL_MARKERS):
                return True
    return False


def _is_write_mode(node: ast.Call) -> bool:
    """True when an open()-style call requests a writable mode."""
    mode = None
    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
        mode = node.args[1].value
    for kw in node.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            mode = kw.value.value
    if not isinstance(mode, str):
        return False
    return bool(set(mode) & WRITE_MODES)


def write_path_violations(code: str) -> list[str]:
    """Return D15 violations in a code sample: a write aimed at the INTENTS tree.

    Three forms are caught: `open(<intents>, "w")`, a mutating `Path` method on
    an INTENTS receiver, and a mutating `os`/`shutil` function handed an
    INTENTS argument.
    """
    violations: list[str] = []

    for node in ast.walk(ast.parse(code)):
        if not isinstance(node, ast.Call):
            continue

        fname = ""
        if isinstance(node.func, ast.Attribute):
            fname = node.func.attr
        elif isinstance(node.func, ast.Name):
            fname = node.func.id

        # open(path, "w") / Path.open("w")
        if fname == "open" and _is_write_mode(node):
            receiver = node.func.value if isinstance(node.func, ast.Attribute) else None
            if _mentions_intents(node) or (receiver and _mentions_intents(receiver)):
                violations.append(f"line {node.lineno}: open(..., write) on INTENTS")
            continue

        # p.write_text(...) where p names the tree
        if fname in MUTATING_METHODS and isinstance(node.func, ast.Attribute):
            if _mentions_intents(node.func.value):
                violations.append(f"line {node.lineno}: {fname}() on INTENTS")
            continue

        # os.remove(intents_path) / shutil.copy(src, "INTENTS/...")
        if fname in MUTATING_FUNCS:
            if any(_mentions_intents(a) for a in node.args) or any(
                _mentions_intents(kw.value) for kw in node.keywords
            ):
                violations.append(f"line {node.lineno}: {fname}(INTENTS)")

    return violations


# --- Red samples: each must be caught --------------------------------------

RED_OPEN_WRITE = """
def correct(intents_root, node_id, text):
    with open(intents_root / node_id, "w") as fh:
        fh.write(text)
"""

RED_WRITE_TEXT = """
def correct(intents_path, text):
    intents_path.write_text(text, encoding="utf-8")
"""

RED_LITERAL_PATH = """
from pathlib import Path

def correct(text):
    Path("INTENTS/_rubric/rules_criteria/item-18.yaml").write_text(text)
"""

RED_SHUTIL = """
import shutil

def publish(staged):
    shutil.copy(staged, "INTENTS/_rubric/rules_criteria/item-18.yaml")
"""

RED_UNLINK = """
def retract(intents_node):
    intents_node.unlink()
"""

# --- Green samples: reading is the whole point -----------------------------

GREEN_READ = """
def load(intents_root, node_id):
    with open(intents_root / node_id) as fh:
        return fh.read()
"""

GREEN_READ_TEXT = """
import yaml

def load(intents_path):
    return yaml.safe_load(intents_path.read_text())
"""

GREEN_WRITE_ELSEWHERE = """
def emit(staging_dir, node_id, text):
    (staging_dir / node_id).write_text(text, encoding="utf-8")
"""


def test_red_samples_are_caught():
    """The checker fires on every shape of write into the tree."""
    for name, sample in [
        ("open-write", RED_OPEN_WRITE),
        ("write_text", RED_WRITE_TEXT),
        ("literal path", RED_LITERAL_PATH),
        ("shutil.copy", RED_SHUTIL),
        ("unlink", RED_UNLINK),
    ]:
        assert write_path_violations(sample), f"checker missed a write path: {name}"


def test_green_samples_are_clean():
    """Reading INTENTS, and writing anywhere else, are both allowed."""
    for name, sample in [
        ("read", GREEN_READ),
        ("read_text", GREEN_READ_TEXT),
        ("write elsewhere", GREEN_WRITE_ELSEWHERE),
    ]:
        assert not write_path_violations(sample), f"false positive on: {name}"


def test_no_write_path_in_src_argus():
    """D15 on the live tree: nothing under src/argus/ writes into INTENTS.

    This is the assertion 9002 specified twice and never landed. It is
    currently satisfied, and from here it stays satisfied by force rather than
    by the absence of the code that would break it.
    """
    assert SRC.exists(), f"source tree missing at {SRC}"
    failures: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        for v in write_path_violations(path.read_text(encoding="utf-8")):
            failures.append(f"{path.relative_to(REPO_ROOT)}: {v}")
    assert not failures, "D15 write path into INTENTS:\n  " + "\n  ".join(failures)
