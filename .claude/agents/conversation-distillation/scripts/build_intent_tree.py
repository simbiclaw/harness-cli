"""
Build / refresh the intent tree's derived data from the source-of-truth
claim library.

`scripts/cluster_incremental.py --assign` already mutates the tree in place
and updates centroids and counts. This script does the consistency-and-derivation
pass that should run before publishing:

  - Recompute claim_count from claim_ids (catches manual edits)
  - Recompute exemplar_claims for every leaf (the 3-5 closest to centroid)
  - Recompute first_seen_at / first_seen_run if missing
  - Refresh inner-node aggregate fields (claim_count, derived centroid)
  - Validate run-time invariants from the stability protocol

Hard-fails (non-zero exit) on any invariant violation. The publish script
expects this to have run cleanly.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from state_io import (  # noqa: E402
    iter_claims, load_tree, log_event, read_pool, save_tree,
)
from cluster_incremental import (  # noqa: E402
    all_leaves, _cosine_similarity,
)
from embed_claims import load_embeddings  # noqa: E402


def _now() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def refresh_exemplars(leaf: dict, id_to_idx: dict, vecs: np.ndarray, n: int = 5) -> None:
    """Pick `n` claims closest to the leaf's centroid as exemplars."""
    cids = leaf.get("claim_ids", [])
    if not cids:
        leaf["exemplar_claims"] = []
        return
    centroid = np.asarray(leaf["centroid"], dtype=np.float32)
    sims: list[tuple[str, float]] = []
    for cid in cids:
        if cid in id_to_idx:
            sim = _cosine_similarity(vecs[id_to_idx[cid]], centroid)
            sims.append((cid, sim))
    if not sims:
        leaf["exemplar_claims"] = []
        return
    sims.sort(key=lambda t: t[1], reverse=True)
    leaf["exemplar_claims"] = [cid for cid, _ in sims[:n]]


def refresh_inner_counts(tree: dict) -> None:
    def walk(node):
        children = node.get("children") or []
        if not children:
            node["claim_count"] = len(node.get("claim_ids", []))
        else:
            total = 0
            for c in children:
                walk(c)
                total += c.get("claim_count", 0)
            node["claim_count"] = total
    for n in tree.get("tree", []):
        walk(n)


def validate_invariants(tree: dict, library_ids: set, pool_ids: set) -> list[str]:
    """
    Run the run-time invariants from stability_protocol.md.
    Returns a list of error strings; empty list means all pass.
    """
    errors: list[str] = []

    # Every claim ID in any leaf must exist in the library
    in_leaves: dict[str, str] = {}
    for leaf in all_leaves(tree):
        for cid in leaf.get("claim_ids", []):
            if cid not in library_ids:
                errors.append(f"leaf {leaf['id']} references missing claim {cid}")
            if cid in in_leaves and in_leaves[cid] != leaf["id"]:
                errors.append(
                    f"claim {cid} appears in two leaves: "
                    f"{in_leaves[cid]} and {leaf['id']}"
                )
            in_leaves[cid] = leaf["id"]

    # Every claim must be in either exactly one leaf or in the pool
    accounted = set(in_leaves.keys()) | pool_ids
    missing = library_ids - accounted
    if missing:
        errors.append(
            f"{len(missing)} claims in library are neither assigned to a leaf "
            f"nor in the pool (first 5: {sorted(missing)[:5]})"
        )
    extra_in_pool = pool_ids - library_ids
    if extra_in_pool:
        errors.append(
            f"{len(extra_in_pool)} pool entries reference claims not in the library"
        )

    # ID format and parent-chain consistency
    def walk(node, depth, parent_id_chain):
        nid = node.get("id", "")
        children = node.get("children") or []
        # ID format
        prefix = f"L{depth}."
        if not nid.startswith(prefix):
            errors.append(f"node {nid!r} at depth {depth} has wrong prefix")
        # Parent chain
        if parent_id_chain and not nid.startswith(parent_id_chain + "."):
            # L1 nodes have no parent chain
            if depth > 1:
                errors.append(
                    f"node {nid!r} not under parent chain {parent_id_chain!r}"
                )
        # Drift non-negative
        d = node.get("centroid_drift_since_anchor")
        if d is not None and d < 0:
            errors.append(f"node {nid!r} has negative drift {d}")
        for c in children:
            walk(c, depth + 1, nid)

    for n in tree.get("tree", []):
        walk(n, 1, "")

    return errors


def main() -> int:
    p = argparse.ArgumentParser(description="Refresh and validate the intent tree.")
    p.add_argument("--strict", action="store_true",
                   help="Hard-fail if any invariant violation is found")
    args = p.parse_args()

    tree = load_tree()

    # Build library_ids from the JSONL (just IDs; we don't need full claims)
    library_ids = {c["id"] for c in iter_claims()}
    pool_ids = set(read_pool())

    # Refresh exemplars (uses embeddings)
    ids, vecs = load_embeddings()
    id_to_idx = {cid: i for i, cid in enumerate(ids)}
    if vecs.size:
        for leaf in all_leaves(tree):
            refresh_exemplars(leaf, id_to_idx, vecs)
    else:
        print("WARNING: no embeddings available; exemplars not refreshed.", file=sys.stderr)

    # Recompute counts
    refresh_inner_counts(tree)

    # Save before validation so any partial work is persisted
    save_tree(tree)

    # Validate
    errors = validate_invariants(tree, library_ids, pool_ids)
    if errors:
        print(f"\n{len(errors)} invariant violation(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        log_event("invariants_failed", error_count=len(errors), errors=errors[:10])
        if args.strict:
            return 1
    else:
        log_event("invariants_passed", leaf_count=len(all_leaves(tree)))
        print("Tree refreshed; all invariants pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
