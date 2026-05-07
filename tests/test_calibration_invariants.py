"""M4 structural tests: calibration invariants from PRODUCT_SENSE.md Cross-product.

These tests define the contract the calibration module must satisfy.
They run against stub implementations; when real implementations exist,
replace the stubs with the real modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Stub types — replace with real types when they exist in src/argus/
# ---------------------------------------------------------------------------


@dataclass
class IntentNode:
    id: str
    label: str
    parent_id: str | None = None
    claims: list[str] = field(default_factory=list)


@dataclass
class IntentTree:
    root: IntentNode
    nodes: dict[str, IntentNode] = field(default_factory=dict)


@dataclass
class ComputeNode:
    id: str
    label: str
    procedure: str


@dataclass
class ComputeGraph:
    nodes: dict[str, ComputeNode] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class CalibratedGraph:
    """Result of calibration. When intent and compute disagree, intent wins."""

    nodes: dict[str, Any] = field(default_factory=dict)
    conflicts_resolved: list[str] = field(default_factory=list)
    intent_prevailed: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stub calibrate — replace with real calibrate when it exists
# ---------------------------------------------------------------------------


def calibrate(intent_tree: IntentTree, compute_graph: ComputeGraph) -> CalibratedGraph:
    """Stub: bottom-up authority — intent wins when there's a conflict."""
    conflicts = []
    intent_wins = []

    for node_id, i_node in intent_tree.nodes.items():
        if node_id in compute_graph.nodes:
            c_node = compute_graph.nodes[node_id]
            if i_node.label != c_node.label:
                conflicts.append(node_id)
                intent_wins.append(node_id)

    return CalibratedGraph(
        nodes={nid: {"label": n.label} for nid, n in intent_tree.nodes.items()},
        conflicts_resolved=conflicts,
        intent_prevailed=intent_wins,
    )


# ---------------------------------------------------------------------------
# Stub conversation distillation
# ---------------------------------------------------------------------------


def distill_conversation(transcript: list[dict[str, str]]) -> IntentTree:
    """Stub: extract intent tree from transcript turns."""
    root = IntentNode(id="root", label="root")
    tree = IntentTree(root=root, nodes={"root": root})

    for i, turn in enumerate(transcript):
        node_id = f"intent-{i}"
        node = IntentNode(
            id=node_id,
            label=f"intent from turn {i}: {turn.get('text', '')[:40]}",
            parent_id="root",
            claims=[turn.get("text", "")],
        )
        tree.nodes[node_id] = node

    return tree


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_bottom_up_authority():
    """Intent tree wins when it conflicts with compute graph."""
    intent = IntentTree(
        root=IntentNode(id="root", label="root"),
        nodes={
            "root": IntentNode(id="root", label="root"),
            "n1": IntentNode(
                id="n1",
                label="annual report due March 31",  # bottom-up truth
                parent_id="root",
                claims=["customer asked about March 31 deadline"],
            ),
        },
    )
    compute = ComputeGraph(
        nodes={
            "n1": ComputeNode(
                id="n1",
                label="annual report due April 15",  # stale docs
                procedure="file-annual-report",
            ),
        },
    )

    result = calibrate(intent, compute)

    assert "n1" in result.conflicts_resolved
    assert "n1" in result.intent_prevailed
    assert result.nodes["n1"]["label"] == "annual report due March 31"


def test_intent_tree_stability():
    """Running distillation twice on the same input preserves intent-node IDs."""
    transcript = [
        {"speaker": "agent", "text": "How can I help with your annual report?"},
        {"speaker": "caller", "text": "I need to file before the deadline."},
        {"speaker": "agent", "text": "The deadline is March 31st."},
    ]

    tree1 = distill_conversation(transcript)
    tree2 = distill_conversation(transcript)

    ids1 = set(tree1.nodes.keys())
    ids2 = set(tree2.nodes.keys())

    assert ids1 == ids2, f"IDs differ between runs: {ids1} vs {ids2}"

    # Run on input + 10% new claims, assert >= 90% prior-ID preservation
    extended = [
        *transcript,
        {"speaker": "caller", "text": "Also, what about e-seals?"},
    ]
    tree3 = distill_conversation(extended)
    ids3 = set(tree3.nodes.keys())
    preserved = ids1 & ids3
    preservation_ratio = len(preserved) / len(ids1) if ids1 else 1.0
    assert preservation_ratio >= 0.9, (
        f"Only {preservation_ratio:.0%} IDs preserved, expected >= 90%"
    )
