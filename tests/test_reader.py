"""9031 M3 acceptance: the S1 read surface — INTENTS at a pinned epoch.

Every acceptance test runs against the real tree (718 call records, real
compiled items, real capsules) per the plan's real-data clause. The structural
scan keeps the surface sole: nothing else under `src/argus/` may shell out to
git or name the tree root.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from argus.io.reader import IntentsReader, NodeNotFound, UnpinnedRead

INTENTS = Path("/Users/prometheus/workspace/INTENTS")
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src" / "argus"

pytestmark = pytest.mark.skipif(not INTENTS.exists(), reason="INTENTS tree not present")

RECORDS = sorted(INTENTS.glob("**/calls/**/*.json"))
ATTRIBUTED = [r for r in RECORDS if "_unassigned" not in r.parts]
UNASSIGNED = [r for r in RECORDS if "_unassigned" in r.parts]


@pytest.fixture(scope="module")
def reader() -> IntentsReader:
    return IntentsReader(INTENTS)


def test_reads_a_real_record_at_the_pinned_epoch(reader):
    """The boundary, measured: knowledge resolves from the pin (git), facts
    resolve from the archive (filesystem). The tree's `.gitignore` excludes
    `calls/` by design ("no git history per call"), so a record is never a
    revision of the tree — it is the call, identified by its path."""
    assert re.fullmatch(r"[0-9a-f]{40}", reader.epoch)

    # fact: from the archive
    record = reader.read_call_record(str(RECORDS[0].relative_to(INTENTS)))
    assert record.get("turns"), "real record carries turns"

    # knowledge: from the epoch. Same driver, both directions.
    items = reader.rubric_items("Procedural Accuracy")
    assert items, "compiled items exist for a compiled dimension"
    assert all(item.get("node_id") for item in items)

    # and the boundary itself is pinned: calls are not versioned
    listed = subprocess.run(
        ["git", "-C", str(INTENTS), "ls-tree", "-r", "--name-only", reader.epoch],
        capture_output=True, text=True,
    ).stdout.splitlines()
    assert not [p for p in listed if "/calls/" in p], (
        "call records are git-ignored by design; if they appear in the epoch "
        "the archival design changed — re-read .gitignore before relaxing this"
    )


def test_attribution_is_explicit_absence_for_unassigned(reader):
    """532 of 718 calls are `_unassigned`: the reader answers None — an
    explicit absence the run manifest records — and a node id otherwise."""
    assert UNASSIGNED and ATTRIBUTED, "corpus carries both shapes"
    assert reader.attribution_of(str(UNASSIGNED[0].relative_to(INTENTS))) is None
    node = reader.attribution_of(str(ATTRIBUTED[0].relative_to(INTENTS)))
    assert node and "/" in node, f"attributed call names its L1/L2 node, got {node!r}"
    # and the named node really carries a manifest at the pin
    assert reader.read_manifest(node)["intent_id"]


def test_manifest_without_item_is_routing_only(reader):
    """AGENTS.md rule 5: no compiled item for the cited dimension -> routing
    label only. All four dimensions are compiled today, so the negative case is
    exercised with a dimension that has no items — the rule is about the
    lookup, not about which dimensions happen to exist."""
    node = reader.attribution_of(str(ATTRIBUTED[0].relative_to(INTENTS)))
    assert reader.signal_disposition(node, "Procedural Accuracy") == "scored"
    assert reader.signal_disposition(node, "NoSuchDimension") == "routing_only"


def test_audio2tree_source_defers(reader):
    """AGENTS.md rule 4, on the real manifests whose source is audio2tree:
    their manual-reference signals defer."""
    deferred = []
    for manifest_path in INTENTS.rglob("intent_manifest.json"):
        node = str(manifest_path.parent.relative_to(INTENTS))
        try:
            if reader.source_of(node) == "audio2tree":
                deferred.append(node)
                assert reader.signal_disposition(node, "Procedural Accuracy") == "deferred"
        except NodeNotFound:
            continue
        if deferred:
            break
    assert deferred, "corpus carries at least one audio2tree-source manifest"


def test_capsule_parse_by_id(reader):
    """A routine resolves by id from the Flesh, ascending by step_order —
    never by content traversal."""
    leaf = None
    sample = INTENTS / "信用修复业务" / "行政处罚信息修复"
    if sample.exists():
        leaf = "信用修复业务/行政处罚信息修复"
    else:
        for index in INTENTS.rglob("index.md"):
            leaf = str(index.parent.relative_to(INTENTS))
            break
    assert leaf, "corpus carries capsules"
    # discover one routine id from the Flesh, then resolve it by id
    text = reader._show(f"{leaf}/index.md")
    ids = re.findall(r'"routine_id":\s*"([^"]+)"', text)
    assert ids, f"{leaf} carries routine ids"
    steps = reader.read_capsule_routine(leaf, ids[0])
    assert steps, "routine resolves to steps"
    order = [s["step_order"] for s in steps]
    assert order == sorted(order), "steps come back ascending by step_order"
    assert all("step_instruction" in s for s in steps)
    with pytest.raises(NodeNotFound):
        reader.read_capsule_routine(leaf, "no-such-routine-id")


def test_sole_read_surface():
    """No module under src/argus/ outside reader.py shells out to git or names
    the tree root — the structural half of 'one reader, one epoch'."""
    offenders = []
    for py in sorted(SRC.rglob("*.py")):
        if "__pycache__" in py.parts or py.name == "reader.py":
            continue
        text = py.read_text(encoding="utf-8")
        if re.search(r'"git"|subprocess\.run\(\s*\[\s*"git"', text):
            offenders.append(f"{py.relative_to(REPO_ROOT)}: shells out to git")
        if re.search(r'Path\(\s*["\']/Users/prometheus/workspace/INTENTS', text):
            offenders.append(f"{py.relative_to(REPO_ROOT)}: hard-codes the tree root")
    assert not offenders, "second read surface:\n" + "\n".join(offenders)


def test_unpinned_read_refuses(tmp_path):
    """A tree with no EPOCH.yaml, or a short SHA, must refuse — an unpinned
    read is an I4 hole, not untidiness."""
    with pytest.raises(UnpinnedRead):
        IntentsReader(tmp_path).epoch
    with pytest.raises(UnpinnedRead):
        IntentsReader(tmp_path, epoch="abc123").epoch
