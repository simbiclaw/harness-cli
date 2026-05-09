"""
Incremental clustering with stability constraints.

This is where the stability protocol from references/stability_protocol.md
is enforced programmatically. Three subcommands:

  --assign     Assign new (just-embedded) claims to existing leaves or pool
  --discover   Run k-means on the unassigned pool to propose new leaves
               (NOTE: cluster *naming* is left to the subagent's reasoning;
                this script writes proposals to a file the subagent reads)
  --audit      Surface drift, merge candidates, tiny-leaf flags
  --pool-status How big is the pool now?
  --re-anchor <leaf_id>   (gated; logs explicitly)
  --merge <leaf_a> <leaf_b> --new-id <slug>   (gated)
  --absorb <leaf> <parent_or_sibling>          (gated)

Cluster naming is the LLM-judgment part. This script does not call an LLM;
it writes proposals to state/discovery_proposals.json which the subagent
reads, names, and then re-runs the script with `--apply-proposals`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from state_io import (  # noqa: E402
    iter_claims, load_config, load_tree, log_event, read_pool, replace_pool,
    save_tree, state_dir, state_snapshot, append_to_pool,
)
from embed_claims import load_embeddings  # noqa: E402


PROPOSALS_PATH = lambda: state_dir() / "discovery_proposals.json"  # noqa: E731


# ---------------------------------------------------------------------------
# Tree walk helpers
# ---------------------------------------------------------------------------


def all_leaves(tree: dict) -> list[dict]:
    """Walk the tree and return all leaf nodes (no children)."""
    out: list[dict] = []
    def walk(node: dict):
        children = node.get("children") or []
        if not children:
            out.append(node)
        else:
            for c in children:
                walk(c)
    for n in tree.get("tree", []):
        walk(n)
    return out


def all_l2_centroid_carriers(tree: dict) -> list[dict]:
    """All L2 nodes (proposed parents for new L3 leaves)."""
    out: list[dict] = []
    for l1 in tree.get("tree", []):
        for l2 in l1.get("children", []) or []:
            out.append(l2)
    return out


def all_l1_centroid_carriers(tree: dict) -> list[dict]:
    return list(tree.get("tree", []))


def aggregate_centroid(node: dict) -> np.ndarray | None:
    """
    Compute a node's centroid from its descendants. For inner nodes, this
    is the mean of children's centroids; for leaves, it's the stored centroid.
    Returns None if no descendants have centroids yet.
    """
    if "centroid" in node and node.get("centroid"):
        return np.asarray(node["centroid"], dtype=np.float32)
    children = node.get("children") or []
    if not children:
        return None
    child_cs = [aggregate_centroid(c) for c in children]
    child_cs = [c for c in child_cs if c is not None]
    if not child_cs:
        return None
    stacked = np.vstack(child_cs)
    return stacked.mean(axis=0)


def find_node(tree: dict, node_id: str) -> dict | None:
    def walk(node):
        if node.get("id") == node_id:
            return node
        for c in node.get("children") or []:
            r = walk(c)
            if r is not None:
                return r
        return None
    for n in tree.get("tree", []):
        r = walk(n)
        if r is not None:
            return r
    return None


def find_parent(tree: dict, node_id: str) -> dict | None:
    """Return the parent node of `node_id`, or None for L1 nodes."""
    def walk(parent, node):
        if node.get("id") == node_id:
            return parent
        for c in node.get("children") or []:
            r = walk(node, c)
            if r is not None:
                return r
        return None
    for n in tree.get("tree", []):
        if n.get("id") == node_id:
            return None  # L1 has no parent in the tree (root)
        r = walk(n, n)
        if r is not None:
            return r
    return None


# ---------------------------------------------------------------------------
# Centroid I/O for leaves
# ---------------------------------------------------------------------------


def update_leaf_centroid(leaf: dict, new_emb: np.ndarray) -> None:
    """Add a new claim embedding to a leaf, updating centroid as running mean."""
    n = len(leaf.get("claim_ids", []))
    if "centroid" in leaf and leaf.get("centroid"):
        old = np.asarray(leaf["centroid"], dtype=np.float32)
        new_centroid = (old * n + new_emb) / (n + 1)
    else:
        new_centroid = new_emb.copy()
    # Re-normalize (centroid of L2-normalized vectors isn't unit-length)
    norm = np.linalg.norm(new_centroid)
    if norm > 0:
        new_centroid = new_centroid / norm
    leaf["centroid"] = new_centroid.tolist()
    if "anchor_centroid" not in leaf:
        leaf["anchor_centroid"] = leaf["centroid"]
    leaf["centroid_drift_since_anchor"] = float(_cosine_distance(
        np.asarray(leaf["anchor_centroid"], dtype=np.float32),
        new_centroid,
    ))


def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    sim = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))
    return max(0.0, min(2.0, 1.0 - sim))


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


# ---------------------------------------------------------------------------
# --assign
# ---------------------------------------------------------------------------


def cmd_assign(args: argparse.Namespace) -> int:
    cfg = load_config()
    tree = load_tree()

    ids, vecs = load_embeddings()
    if not ids:
        print("No embeddings found. Run embed_claims.py first.")
        return 0
    id_to_idx = {cid: i for i, cid in enumerate(ids)}

    # Already-assigned claims live in leaves' claim_ids; pool already has its IDs.
    assigned = set()
    for leaf in all_leaves(tree):
        for cid in leaf.get("claim_ids", []):
            assigned.add(cid)
    pool = set(read_pool())

    candidates = [cid for cid in ids if cid not in assigned and cid not in pool]
    if not candidates:
        print("Nothing new to assign.")
        return 0

    leaves = all_leaves(tree)
    leaf_centroids: list[tuple[dict, np.ndarray]] = []
    for leaf in leaves:
        if not leaf.get("centroid"):
            continue
        if leaf.get("centroid_drift_since_anchor", 0.0) >= cfg["drift_threshold_block"]:
            continue  # frozen leaf
        leaf_centroids.append((leaf, np.asarray(leaf["centroid"], dtype=np.float32)))

    n_assigned = 0
    n_pooled = 0
    new_pool_ids: list[str] = []

    with state_snapshot():
        for cid in candidates:
            emb = vecs[id_to_idx[cid]]
            best_leaf = None
            best_sim = -1.0
            for leaf, c in leaf_centroids:
                sim = _cosine_similarity(emb, c)
                if sim > best_sim:
                    best_sim = sim
                    best_leaf = leaf

            if best_leaf is not None and best_sim >= cfg["assignment_threshold"]:
                best_leaf.setdefault("claim_ids", []).append(cid)
                update_leaf_centroid(best_leaf, emb)
                best_leaf["claim_count"] = len(best_leaf["claim_ids"])
                n_assigned += 1
                log_event(
                    "claim_assigned",
                    claim_id=cid, leaf_id=best_leaf["id"], similarity=round(best_sim, 4),
                )
            else:
                new_pool_ids.append(cid)
                n_pooled += 1

        if new_pool_ids:
            append_to_pool(new_pool_ids)

        # Update L2/L1 claim counts as sums of descendants
        _refresh_inner_counts(tree)
        save_tree(tree)

    print(f"Assigned: {n_assigned}, pooled: {n_pooled}, pool size now: {len(read_pool())}")
    return 0


def _refresh_inner_counts(tree: dict) -> None:
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


# ---------------------------------------------------------------------------
# --pool-status
# ---------------------------------------------------------------------------


def cmd_pool_status(args: argparse.Namespace) -> int:
    cfg = load_config()
    pool_ids = read_pool()
    threshold = cfg["discovery_pool_size"]
    print(f"Pool size: {len(pool_ids)} / {threshold} (discovery threshold)")
    if len(pool_ids) >= threshold:
        print("→ Discovery is RECOMMENDED. Run with --discover.")
    return 0


# ---------------------------------------------------------------------------
# --discover
# ---------------------------------------------------------------------------


def cmd_discover(args: argparse.Namespace) -> int:
    cfg = load_config()
    tree = load_tree()
    pool_ids = read_pool()

    if not pool_ids:
        print("Pool is empty.")
        return 0

    if len(pool_ids) < cfg["discovery_pool_size"] and not args.force:
        print(
            f"Pool size {len(pool_ids)} < discovery_pool_size {cfg['discovery_pool_size']}. "
            "Use --force to discover anyway."
        )
        return 0

    ids, vecs = load_embeddings()
    id_to_idx = {cid: i for i, cid in enumerate(ids)}

    # Get the embeddings for pool claims
    pool_vecs = []
    pool_kept_ids = []
    for cid in pool_ids:
        if cid in id_to_idx:
            pool_vecs.append(vecs[id_to_idx[cid]])
            pool_kept_ids.append(cid)
    if not pool_vecs:
        print("No embeddings for pool claims; run embed_claims.py first.")
        return 1
    pool_matrix = np.vstack(pool_vecs)

    # Choose k via elbow-ish heuristic
    k_max = min(15, max(2, len(pool_kept_ids) // 5))
    k = _pick_k(pool_matrix, k_min=2, k_max=k_max)
    print(f"Running k-means with k={k} on {len(pool_kept_ids)} pool claims...")

    labels, centroids = _kmeans(pool_matrix, k=k, seeds=10, max_iter=100)

    # Build proposals: one per cluster of size ≥ min_cluster_size
    min_size = cfg["discovery_min_cluster_size"]
    proposals: list[dict] = []
    pool_remaining: list[str] = []

    # Look up claim text by ID (cheap pass through the library)
    text_lookup = _build_claim_text_lookup(set(pool_kept_ids))

    for cluster_idx in range(k):
        member_ids = [pool_kept_ids[i] for i, lbl in enumerate(labels) if lbl == cluster_idx]
        if len(member_ids) < min_size:
            pool_remaining.extend(member_ids)
            continue

        # Pick exemplars: claims closest to the cluster's centroid
        member_vecs = np.vstack([pool_matrix[i] for i, lbl in enumerate(labels) if lbl == cluster_idx])
        sims = member_vecs @ centroids[cluster_idx]
        # Top 5 by similarity
        order = np.argsort(-sims)[:5]
        exemplar_ids = [member_ids[i] for i in order]
        exemplar_texts = [text_lookup.get(cid, "") for cid in exemplar_ids]

        # Suggest parent by similarity to existing L2 (then L1) centroids
        parent_id, parent_sim = _propose_parent(tree, centroids[cluster_idx], cfg)

        proposals.append({
            "proposal_id": f"prop_{cluster_idx:03d}_{int(time.time())}",
            "member_count": len(member_ids),
            "member_ids": member_ids,
            "exemplar_ids": exemplar_ids,
            "exemplar_texts": exemplar_texts,
            "centroid": centroids[cluster_idx].tolist(),
            "proposed_parent_id": parent_id,
            "parent_similarity": round(parent_sim, 4),
            "parent_fits_threshold": parent_sim >= cfg["parent_fit_threshold"],
            "needs_human_review_for_new_l1": parent_id is None,
            # The subagent fills these in
            "title": None,
            "summary": None,
            "approved_parent_id": None,
        })

    PROPOSALS_PATH().parent.mkdir(parents=True, exist_ok=True)
    with open(PROPOSALS_PATH(), "w") as f:
        json.dump({"generated_at": _now(), "proposals": proposals}, f, indent=2)

    # Update the pool: keep small-cluster members
    replace_pool(pool_remaining)

    print(f"Wrote {len(proposals)} discovery proposals to {PROPOSALS_PATH()}")
    print(f"Pool reduced to {len(pool_remaining)} (small-cluster members retained).")
    print("\nNext step: subagent reads the proposals file, names each cluster,")
    print("approves a parent, then runs `--apply-proposals` to commit them.")

    log_event("discovery_run", proposals=len(proposals), pool_after=len(pool_remaining))
    return 0


def _pick_k(matrix: np.ndarray, k_min: int = 2, k_max: int = 15) -> int:
    """Elbow heuristic on inertia curve. Falls back to k_min if the curve is flat."""
    if matrix.shape[0] <= k_min:
        return min(matrix.shape[0], k_max)
    inertias = []
    ks = list(range(k_min, min(k_max, matrix.shape[0]) + 1))
    for k in ks:
        _, centroids = _kmeans(matrix, k=k, seeds=3, max_iter=50)
        # Inertia: sum of squared distances to nearest centroid
        # (cheap recompute since we have centroids)
        sims = matrix @ centroids.T  # (N, k)
        nearest = sims.max(axis=1)
        inertia = float(np.sum(2.0 - 2.0 * nearest))  # 2 - 2cos = sq euclidean for unit vectors
        inertias.append(inertia)
    if len(inertias) <= 2:
        return ks[0]
    # Find the elbow as the k where the second derivative is most negative
    # (a knee in the inertia curve).
    diffs = np.diff(inertias)
    second = np.diff(diffs)
    if len(second) == 0:
        return ks[0]
    elbow_idx = int(np.argmin(second)) + 1  # +1 for the index offset
    return ks[elbow_idx]


def _kmeans(X: np.ndarray, k: int, seeds: int = 10, max_iter: int = 100):
    """
    Cosine-style k-means on L2-normalized vectors. Returns (labels, centroids).
    Centroids are returned L2-normalized.
    """
    rng = np.random.default_rng(0)
    best_labels = None
    best_centroids = None
    best_inertia = float("inf")
    n = X.shape[0]
    for _ in range(seeds):
        # k-means++ init
        first = int(rng.integers(0, n))
        centroids = [X[first]]
        for _ in range(k - 1):
            sims = X @ np.vstack(centroids).T
            nearest = sims.max(axis=1)
            dists = np.maximum(0.0, 2.0 - 2.0 * nearest)
            probs = dists / (dists.sum() + 1e-12)
            idx = int(rng.choice(n, p=probs))
            centroids.append(X[idx])
        centroids = np.vstack(centroids)

        for _ in range(max_iter):
            sims = X @ centroids.T
            labels = np.argmax(sims, axis=1)
            new_centroids = np.zeros_like(centroids)
            for c in range(k):
                mask = labels == c
                if not mask.any():
                    new_centroids[c] = centroids[c]
                else:
                    mean = X[mask].mean(axis=0)
                    norm = np.linalg.norm(mean)
                    new_centroids[c] = mean / (norm + 1e-12)
            shift = float(np.linalg.norm(new_centroids - centroids))
            centroids = new_centroids
            if shift < 1e-6:
                break

        sims = X @ centroids.T
        inertia = float(np.sum(2.0 - 2.0 * sims.max(axis=1)))
        if inertia < best_inertia:
            best_inertia = inertia
            best_labels = labels.copy()
            best_centroids = centroids.copy()

    return best_labels, best_centroids


def _propose_parent(tree: dict, centroid: np.ndarray, cfg: dict) -> tuple[str | None, float]:
    """
    Find the existing L2 (or, if no L2 fits, L1) closest to `centroid`.
    Returns (id, similarity) or (None, 0.0) if nothing fits the threshold.
    """
    candidates: list[tuple[dict, np.ndarray]] = []
    for l2 in all_l2_centroid_carriers(tree):
        c = aggregate_centroid(l2)
        if c is not None:
            candidates.append((l2, c))
    best_sim = -1.0
    best_node: dict | None = None
    for node, c in candidates:
        sim = _cosine_similarity(centroid, c)
        if sim > best_sim:
            best_sim = sim
            best_node = node
    if best_node is not None and best_sim >= cfg["parent_fit_threshold"]:
        return best_node["id"], best_sim

    # Fall back to L1
    candidates = []
    for l1 in all_l1_centroid_carriers(tree):
        c = aggregate_centroid(l1)
        if c is not None:
            candidates.append((l1, c))
    best_sim = -1.0
    best_node = None
    for node, c in candidates:
        sim = _cosine_similarity(centroid, c)
        if sim > best_sim:
            best_sim = sim
            best_node = node
    if best_node is not None and best_sim >= cfg["parent_fit_threshold"]:
        return best_node["id"], best_sim

    return None, 0.0


def _build_claim_text_lookup(ids_of_interest: set) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in iter_claims():
        if c["id"] in ids_of_interest:
            out[c["id"]] = c.get("proposition", "")
        if len(out) == len(ids_of_interest):
            break
    return out


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# --apply-proposals
# ---------------------------------------------------------------------------


def cmd_apply_proposals(args: argparse.Namespace) -> int:
    """
    Read state/discovery_proposals.json, after the subagent has filled in
    `title`, `summary`, and `approved_parent_id` for each proposal.
    Apply: create new leaves under the named parents, move pool claims into them,
    drop the proposals file.
    """
    p = PROPOSALS_PATH()
    if not p.exists():
        print(f"No proposals at {p}. Run --discover first.")
        return 1

    with open(p, "r") as f:
        doc = json.load(f)

    proposals = doc["proposals"]
    incomplete = [pr for pr in proposals if not pr.get("title") or not pr.get("approved_parent_id")]
    if incomplete:
        print(
            f"{len(incomplete)} proposals are incomplete (missing title or approved_parent_id). "
            "Subagent must fill these in before applying."
        )
        for pr in incomplete[:5]:
            print(f"  - {pr['proposal_id']}: title={pr.get('title')!r}, parent={pr.get('approved_parent_id')!r}")
        return 1

    tree = load_tree()
    n_applied = 0
    new_leaf_ids: list[str] = []

    with state_snapshot():
        for pr in proposals:
            parent_id = pr["approved_parent_id"]
            if parent_id == "__new_l1__":
                # Subagent escalated; refuse to auto-create. The user's --audit
                # workflow handles new L1 creation.
                log_event("proposed_new_l1_skipped", proposal_id=pr["proposal_id"])
                continue
            parent = find_node(tree, parent_id)
            if parent is None:
                print(f"  WARNING: proposal {pr['proposal_id']} parent {parent_id!r} not found; skipping")
                continue

            slug = _slug_from_title(pr["title"])
            new_id = f"{parent_id}.{slug}"
            # Avoid collisions
            existing_ids = {c.get("id") for c in (parent.get("children") or [])}
            if new_id in existing_ids:
                # Append a short hash suffix
                h = _short_hash(slug)
                new_id = f"{parent_id}.{slug}-{h}"

            level = _level_of(parent_id) + 1
            if level > 3:
                print(f"  WARNING: proposal {pr['proposal_id']} would create L{level} node (>3); skipping")
                continue

            new_leaf = {
                "id": new_id,
                "level": level,
                "title": pr["title"],
                "summary": pr.get("summary", ""),
                "first_seen_run": doc.get("run_id", _now()),
                "first_seen_at": _now(),
                "claim_ids": list(pr["member_ids"]),
                "claim_count": len(pr["member_ids"]),
                "centroid": pr["centroid"],
                "anchor_centroid": pr["centroid"],
                "centroid_drift_since_anchor": 0.0,
                "exemplar_claims": pr["exemplar_ids"],
            }
            parent.setdefault("children", []).append(new_leaf)
            new_leaf_ids.append(new_id)
            n_applied += 1
            log_event(
                "cluster_discovered",
                leaf_id=new_id, parent_id=parent_id,
                claim_count=new_leaf["claim_count"],
                title=new_leaf["title"],
            )

        _refresh_inner_counts(tree)
        save_tree(tree)

    # Drop the proposals file
    p.unlink()
    print(f"Applied {n_applied} proposals; created leaves: {new_leaf_ids}")
    return 0


def _slug_from_title(title: str) -> str:
    s = title.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:60] or "unnamed"


def _short_hash(s: str) -> str:
    import hashlib as _h
    return _h.sha256(s.encode("utf-8")).hexdigest()[:6]


def _level_of(node_id: str) -> int:
    """Recover level from id prefix."""
    if node_id.startswith("L1."):
        return 1
    if node_id.startswith("L2."):
        return 2
    if node_id.startswith("L3."):
        return 3
    # Fallback: count dots after the L<n> prefix
    m = re.match(r"L(\d+)\.", node_id)
    if m:
        return int(m.group(1))
    return 1


# ---------------------------------------------------------------------------
# --audit
# ---------------------------------------------------------------------------


def cmd_audit(args: argparse.Namespace) -> int:
    cfg = load_config()
    tree = load_tree()
    leaves = all_leaves(tree)

    print(f"Audit over {len(leaves)} leaves\n")

    # Drift
    drift_warn = []
    drift_block = []
    for leaf in leaves:
        d = leaf.get("centroid_drift_since_anchor", 0.0)
        if d >= cfg["drift_threshold_block"]:
            drift_block.append((leaf, d))
        elif d >= cfg["drift_threshold_warn"]:
            drift_warn.append((leaf, d))

    if drift_block:
        print(f"BLOCKED leaves (drift ≥ {cfg['drift_threshold_block']}):")
        for leaf, d in drift_block:
            print(f"  [{leaf['id']}] drift={d:.3f}, claims={leaf.get('claim_count', 0)}")
        print(f"  → Run with `--re-anchor <leaf_id>` to refresh the anchor.\n")

    if drift_warn:
        print(f"WARNING leaves (drift ≥ {cfg['drift_threshold_warn']}):")
        for leaf, d in drift_warn:
            print(f"  [{leaf['id']}] drift={d:.3f}, claims={leaf.get('claim_count', 0)}")
        print()

    # Merge candidates
    pairs = []
    for i, a in enumerate(leaves):
        ca = aggregate_centroid(a)
        if ca is None:
            continue
        for b in leaves[i + 1:]:
            cb = aggregate_centroid(b)
            if cb is None:
                continue
            sim = _cosine_similarity(ca, cb)
            if sim >= cfg["merge_candidate_threshold"]:
                pairs.append((a, b, sim))
    if pairs:
        print(f"MERGE CANDIDATES (similarity ≥ {cfg['merge_candidate_threshold']}):")
        for a, b, sim in pairs:
            print(f"  {a['id']} ↔ {b['id']}  sim={sim:.4f}")
        print(f"  → Decide manually; use `--merge <a> <b> --new-id <slug>` to act.\n")

    # Tiny leaves
    tiny = [leaf for leaf in leaves if leaf.get("claim_count", 0) < cfg["retention_floor"]
            and not leaf.get("retention_pinned")]
    if tiny:
        print(f"TINY leaves (claim_count < {cfg['retention_floor']}):")
        for leaf in tiny:
            print(f"  [{leaf['id']}] claims={leaf.get('claim_count', 0)}")
        print(f"  → Consider `--absorb <leaf> <parent_or_sibling>` or pin retention.\n")

    if not (drift_block or drift_warn or pairs or tiny):
        print("All clean. No flags raised.")

    return 0


# ---------------------------------------------------------------------------
# Surgical operations: --re-anchor, --merge, --absorb
# These mutate the tree non-additively, so each is gated by a confirmation
# flag and logged with the human-decided rationale (passed via --reason).
# ---------------------------------------------------------------------------


def cmd_re_anchor(args: argparse.Namespace) -> int:
    if not args.confirm:
        print("Re-anchoring is destructive. Pass --confirm to proceed.")
        return 1
    tree = load_tree()
    leaf = find_node(tree, args.leaf_id)
    if leaf is None:
        print(f"Leaf {args.leaf_id!r} not found.")
        return 1
    with state_snapshot():
        old_drift = leaf.get("centroid_drift_since_anchor", 0.0)
        leaf["anchor_centroid"] = leaf["centroid"]
        leaf["centroid_drift_since_anchor"] = 0.0
        save_tree(tree)
    log_event(
        "node_re_anchored",
        leaf_id=args.leaf_id, old_drift=round(old_drift, 4),
        reason=args.reason or "(none provided)",
    )
    print(f"Re-anchored {args.leaf_id} (was drift={old_drift:.4f}).")
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    if not args.confirm:
        print("Merge is destructive. Pass --confirm to proceed.")
        return 1
    tree = load_tree()
    a = find_node(tree, args.leaf_a)
    b = find_node(tree, args.leaf_b)
    if a is None or b is None:
        print(f"Both leaves must exist; got a={a is not None}, b={b is not None}.")
        return 1
    parent_a = find_parent(tree, args.leaf_a)
    parent_b = find_parent(tree, args.leaf_b)
    if parent_a is None or parent_b is None:
        print("Cannot merge L1 nodes through this command; manual edit required.")
        return 1
    if parent_a is not parent_b:
        print(
            "Refusing to merge across different parents; would change tree topology. "
            "Either reparent first or perform the merge manually with explicit reasoning."
        )
        return 1
    with state_snapshot():
        merged_ids = list(a.get("claim_ids", [])) + list(b.get("claim_ids", []))
        # Weighted-mean centroid
        ca = np.asarray(a["centroid"], dtype=np.float32) * a.get("claim_count", 1)
        cb = np.asarray(b["centroid"], dtype=np.float32) * b.get("claim_count", 1)
        n = a.get("claim_count", 1) + b.get("claim_count", 1)
        new_centroid = (ca + cb) / max(n, 1)
        norm = np.linalg.norm(new_centroid)
        if norm > 0:
            new_centroid = new_centroid / norm

        new_id = f"{parent_a['id']}.{args.new_id}"
        new_leaf = {
            "id": new_id,
            "level": _level_of(parent_a["id"]) + 1,
            "title": args.title or f"{a.get('title', '')} + {b.get('title', '')}",
            "summary": args.summary or "Merged from prior leaves; review summary.",
            "claim_ids": merged_ids,
            "claim_count": len(merged_ids),
            "centroid": new_centroid.tolist(),
            "anchor_centroid": new_centroid.tolist(),
            "centroid_drift_since_anchor": 0.0,
            "first_seen_at": _now(),
            "merged_from": [args.leaf_a, args.leaf_b],
        }

        parent_a["children"] = [c for c in parent_a["children"]
                                if c["id"] not in (args.leaf_a, args.leaf_b)]
        parent_a["children"].append(new_leaf)

        # Mark the old leaves as merged in the audit trail (we don't keep them
        # in the tree, but consumers following the old ids can find this in
        # audit_log.jsonl)
        log_event("nodes_merged", source_ids=[args.leaf_a, args.leaf_b],
                  new_id=new_id, claim_count=len(merged_ids),
                  reason=args.reason or "(none provided)")
        _refresh_inner_counts(tree)
        save_tree(tree)
    print(f"Merged {args.leaf_a} + {args.leaf_b} → {new_id}")
    return 0


def cmd_absorb(args: argparse.Namespace) -> int:
    if not args.confirm:
        print("Absorb is destructive. Pass --confirm to proceed.")
        return 1
    tree = load_tree()
    src = find_node(tree, args.leaf_id)
    dst = find_node(tree, args.dst_id)
    if src is None or dst is None:
        print("Both source and destination must exist.")
        return 1
    if dst.get("children"):
        print("Destination must be a leaf (or capable of holding claims directly).")
        return 1
    src_parent = find_parent(tree, args.leaf_id)
    if src_parent is None:
        print("Cannot absorb an L1 node.")
        return 1
    with state_snapshot():
        dst.setdefault("claim_ids", []).extend(src.get("claim_ids", []))
        dst["claim_count"] = len(dst["claim_ids"])
        # Recompute dst centroid as weighted mean (we don't have per-claim
        # embeddings here without loading them; use claim-count weighting)
        # — full re-embed would be more accurate but is a separate step.
        n_src = src.get("claim_count", 1)
        n_dst_old = max(1, dst.get("claim_count", 1) - n_src)
        cs = np.asarray(src["centroid"], dtype=np.float32) * n_src
        cd = np.asarray(dst["centroid"], dtype=np.float32) * n_dst_old
        new = (cs + cd) / (n_src + n_dst_old)
        norm = np.linalg.norm(new)
        if norm > 0:
            new = new / norm
        dst["centroid"] = new.tolist()
        # Re-anchor since the leaf's contents changed materially
        dst["anchor_centroid"] = dst["centroid"]
        dst["centroid_drift_since_anchor"] = 0.0
        # Remove src
        src_parent["children"] = [c for c in src_parent["children"] if c["id"] != args.leaf_id]
        log_event("node_absorbed", source_id=args.leaf_id, destination_id=args.dst_id,
                  claim_count=n_src, reason=args.reason or "(none provided)")
        _refresh_inner_counts(tree)
        save_tree(tree)
    print(f"Absorbed {args.leaf_id} into {args.dst_id}.")
    return 0


# ---------------------------------------------------------------------------
# CLI dispatch
# ---------------------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser(description="Incremental clustering with stability constraints.")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("--assign".lstrip("-"), help="Assign new claims to leaves or pool")
    sub.add_parser("--pool-status".lstrip("-"), help="Report pool size")
    sp_disc = sub.add_parser("--discover".lstrip("-"), help="Discover new clusters from the pool")
    sp_disc.add_argument("--force", action="store_true",
                         help="Run discovery even if pool is below threshold")
    sub.add_parser("--apply-proposals".lstrip("-"),
                   help="After subagent fills in titles, commit proposals to tree")
    sub.add_parser("--audit".lstrip("-"), help="Surface drift, merge candidates, tiny-leaf flags")

    sp_ra = sub.add_parser("--re-anchor".lstrip("-"), help="Re-anchor a leaf (gated)")
    sp_ra.add_argument("leaf_id")
    sp_ra.add_argument("--confirm", action="store_true")
    sp_ra.add_argument("--reason", default=None)

    sp_m = sub.add_parser("--merge".lstrip("-"), help="Merge two leaves under same parent (gated)")
    sp_m.add_argument("leaf_a"); sp_m.add_argument("leaf_b")
    sp_m.add_argument("--new-id", required=True)
    sp_m.add_argument("--title", default=None)
    sp_m.add_argument("--summary", default=None)
    sp_m.add_argument("--confirm", action="store_true")
    sp_m.add_argument("--reason", default=None)

    sp_a = sub.add_parser("--absorb".lstrip("-"), help="Move one leaf's claims into another (gated)")
    sp_a.add_argument("leaf_id"); sp_a.add_argument("dst_id")
    sp_a.add_argument("--confirm", action="store_true")
    sp_a.add_argument("--reason", default=None)

    args = p.parse_args()
    cmd = args.command
    if cmd == "assign":
        return cmd_assign(args)
    if cmd == "pool-status":
        return cmd_pool_status(args)
    if cmd == "discover":
        return cmd_discover(args)
    if cmd == "apply-proposals":
        return cmd_apply_proposals(args)
    if cmd == "audit":
        return cmd_audit(args)
    if cmd == "re-anchor":
        return cmd_re_anchor(args)
    if cmd == "merge":
        return cmd_merge(args)
    if cmd == "absorb":
        return cmd_absorb(args)
    print(f"Unknown command: {cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
