"""
Publish the intent tree as an IIntentTreeSource artifact.

Reads `state/intent_tree.json` (assumed valid; run build_intent_tree.py
--strict first), wraps it with publish_metadata, computes the canonical
content hash, links to the previous publish via parent_hash, and writes
to a versioned file under `published/`.

Each publish is immutable — they accumulate. Downstream consumers select
the latest by reading `published/latest.json` (a symlink) or by listing
`published/intent_tree_v*.json` and picking the highest version.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from state_io import (  # noqa: E402
    canonical_tree_hash, claim_count, load_config, load_tree, log_event,
    read_pool, state_dir,
)
from cluster_incremental import all_leaves  # noqa: E402


def published_dir() -> Path:
    """Where versioned publishes go."""
    env = os.environ.get("CD_PUBLISHED_DIR")
    if env:
        return Path(env).resolve()
    return state_dir().parent / "published"


def latest_version_and_hash() -> tuple[int, str | None]:
    """Find the highest existing version and its hash, or (0, None) if first publish."""
    pd = published_dir()
    if not pd.exists():
        return 0, None
    versions = []
    for f in pd.glob("intent_tree_v*.json"):
        # Extract numeric version
        stem = f.stem  # intent_tree_v7
        try:
            n = int(stem.split("_v")[-1])
            versions.append((n, f))
        except ValueError:
            continue
    if not versions:
        return 0, None
    versions.sort()
    latest_n, latest_path = versions[-1]
    with open(latest_path, "r") as f:
        doc = json.load(f)
    h = doc.get("publish_metadata", {}).get("tree_hash")
    return latest_n, h


def main() -> int:
    p = argparse.ArgumentParser(description="Publish IIntentTreeSource artifact.")
    p.add_argument("--output", "-o", type=Path, default=None,
                   help="Output file path (default: published/intent_tree_v<N+1>.json)")
    p.add_argument("--allow-empty", action="store_true",
                   help="Allow publishing a tree with zero leaves (otherwise refused)")
    args = p.parse_args()

    tree = load_tree()
    leaves = all_leaves(tree)
    if not leaves and not args.allow_empty:
        print(
            "Refusing to publish an empty tree. Run extraction → embed → assign "
            "→ discover first, or pass --allow-empty.",
            file=sys.stderr,
        )
        return 1

    cfg = load_config()
    parent_version, parent_hash = latest_version_and_hash()
    new_version = parent_version + 1

    # Compute canonical hash
    tree_hash = canonical_tree_hash(tree)

    # Build stats
    n_library = claim_count()
    n_assigned = sum(len(leaf.get("claim_ids", [])) for leaf in leaves)
    n_pool = len(read_pool())

    l1_count = len(tree.get("tree", []))
    l2_count = sum(
        len(l1.get("children", [])) for l1 in tree.get("tree", [])
        if isinstance(l1.get("children"), list)
    )
    l3_count = 0
    for l1 in tree.get("tree", []):
        for l2 in l1.get("children") or []:
            l3_count += len(l2.get("children") or [])

    # Surface human review flags from current state
    flags = []
    for leaf in leaves:
        d = leaf.get("centroid_drift_since_anchor", 0.0)
        if d >= cfg["drift_threshold_block"]:
            flags.append({"kind": "centroid_drift_block", "leaf_id": leaf["id"], "drift": round(d, 4)})
        elif d >= cfg["drift_threshold_warn"]:
            flags.append({"kind": "centroid_drift_warning", "leaf_id": leaf["id"], "drift": round(d, 4)})
        if 0 < leaf.get("claim_count", 0) < cfg["retention_floor"] and not leaf.get("retention_pinned"):
            flags.append({"kind": "tiny_leaf", "leaf_id": leaf["id"], "claim_count": leaf["claim_count"]})

    document = {
        "schema_version": "1.0",
        "publish_metadata": {
            "version": new_version,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tree_hash": tree_hash,
            "parent_hash": parent_hash,
            "parent_version": parent_version if parent_version > 0 else None,
            "extractor_version": "conversation-distillation@1.0",
            "embedding_model": cfg["embedding_model"],
        },
        "stats": {
            "total_claims_in_library": n_library,
            "claims_assigned": n_assigned,
            "claims_in_unassigned_pool": n_pool,
            "level_1_count": l1_count,
            "level_2_count": l2_count,
            "level_3_count": l3_count,
            "human_review_flags": flags,
        },
        "tree": tree.get("tree", []),
    }

    # Determine output path
    if args.output is None:
        pd = published_dir()
        pd.mkdir(parents=True, exist_ok=True)
        output_path = pd / f"intent_tree_v{new_version}.json"
    else:
        output_path = args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(document, f, indent=2, ensure_ascii=False, allow_nan=False)

    # Update latest.json (a copy, not symlink — works on more filesystems)
    latest_path = output_path.parent / "latest.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(document, f, indent=2, ensure_ascii=False, allow_nan=False)

    log_event(
        "tree_published",
        version=new_version, hash=tree_hash, parent_hash=parent_hash,
        path=str(output_path),
        leaves=len(leaves), claims=n_library, pool=n_pool,
        flags=len(flags),
    )

    print(f"Published version {new_version} to {output_path}")
    print(f"  tree_hash:   {tree_hash}")
    print(f"  parent_hash: {parent_hash or '(initial publish)'}")
    print(f"  leaves: {len(leaves)}, claims: {n_library}, pool: {n_pool}, flags: {len(flags)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
