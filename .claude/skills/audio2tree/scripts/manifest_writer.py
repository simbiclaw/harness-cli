"""Manifest writer — M4.

Populates intent_manifest.json bottom_up sections.
NEVER touches top_down.

JSON shapes match docs/references/audio2tree-pipeline-design.md section 5 exactly.
"""

import json
import os
from datetime import datetime, timezone


RUN_ID = "audio2tree-run-{}".format(datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"))


def read_manifest(path: str) -> dict | None:
    """Read an existing manifest from disk.

    Args:
        path: Path to intent_manifest.json.

    Returns:
        Parsed dict, or None if file does not exist.
    """
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def merge_manifest(existing: dict, bottom_up_data: dict) -> dict:
    """Merge bottom_up data into an existing manifest.

    Only modifies: bottom_up, last_updated, last_updated_by, calibration_status.
    Never touches: top_down, intent_id, title, description, source.

    Args:
        existing: The existing manifest dict (will not be mutated).
        bottom_up_data: New bottom_up section data.

    Returns:
        A new merged manifest dict.
    """
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    merged = dict(existing)
    merged["bottom_up"] = bottom_up_data
    merged["last_updated"] = now
    merged["last_updated_by"] = "audio_to_tree"

    # Set calibration_status based on channel
    channel = bottom_up_data.get("channel", "")
    if channel == "deviation":
        merged["calibration_status"] = "needs_manual"
    else:
        merged["calibration_status"] = "calibrated"

    return merged


def write_l2_manifest(
    intent_root: str,
    l2_path: str,
    routing_result: dict,
    cluster_data: dict,
    existing_manifest: dict | None,
) -> str:
    """Write or update an L2 intent_manifest.json.

    Args:
        intent_root: Root of the INTENTS tree (used for run_id generation).
        l2_path: Path to the L2 directory (where intent_manifest.json will be written).
        routing_result: Dict with routing information (channel, intent_id, title,
                        description, match_confidence, etc.).
        cluster_data: Dict with clustering information (cluster_centroid,
                      representative_requests, request_count, clustering_run_id).
        existing_manifest: Existing manifest dict, or None.

    Returns:
        Path to the written manifest file.
    """
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    channel = routing_result.get("channel", "matched")
    manifest_path = os.path.join(l2_path, "intent_manifest.json")

    # Build the bottom_up section
    if channel == "deviation":
        bottom_up = {
            "channel": "deviation",
            "deviation_score": routing_result.get("deviation_score", 0.0),
            "best_match_intent_id": routing_result.get("best_match_intent_id", ""),
            "best_match_similarity": routing_result.get("best_match_similarity", 0.0),
            "request_count": cluster_data.get("request_count", 0),
            "status": "pending_review",
            "discovered_at": now,
        }
    else:
        bottom_up = {
            "channel": "matched",
            "match_confidence": routing_result.get("match_confidence", 0.0),
            "request_count": cluster_data.get("request_count", 0),
            "cluster_centroid": cluster_data.get("cluster_centroid", []),
            "representative_requests": cluster_data.get("representative_requests", []),
            "clustering_run_id": cluster_data.get("clustering_run_id", RUN_ID),
            "last_clustered_at": now,
        }

    # Determine source and top_down
    has_existing_top_down = (
        existing_manifest is not None
        and existing_manifest.get("top_down")
        and existing_manifest["top_down"] != {}
    )

    top_down = {}
    source = "audio2tree"
    calibration_status = "needs_manual" if channel == "deviation" else "calibrated"
    calibration_detail = None

    if existing_manifest is not None:
        if has_existing_top_down:
            top_down = existing_manifest.get("top_down", {})
            source = "both"
        else:
            top_down = {}
            source = "audio2tree"

    # Build the manifest
    manifest = {
        "intent_id": routing_result.get("intent_id", ""),
        "title": routing_result.get("title", ""),
        "description": routing_result.get("description", ""),
        "source": source,
        "top_down": top_down,
        "bottom_up": bottom_up,
        "calibration_status": calibration_status,
        "last_updated": now,
        "last_updated_by": "audio_to_tree",
    }

    # Add calibration_detail for deviation
    if channel == "deviation":
        best_match = routing_result.get("best_match_intent_id", "无匹配")
        best_sim = routing_result.get("best_match_similarity", 0.0)
        count = cluster_data.get("request_count", 0)
        manifest["calibration_detail"] = (
            f"{count}通通话。与最近手册'{best_match}'余弦距离{best_sim:.2f}。无对应操作手册。"
        )

    # If we have an existing manifest with top_down, merge rather than replace
    if existing_manifest is not None and has_existing_top_down:
        manifest = merge_manifest(existing_manifest, bottom_up)
        # Ensure source is 'both' when top_down exists
        if manifest["top_down"] and manifest["top_down"] != {}:
            manifest["source"] = "both"

    os.makedirs(l2_path, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return manifest_path


def populate_manifests(
    intent_root: str,
    routing_results: list[dict],
    cluster_results: list[dict],
) -> dict:
    """Batch-populate manifests for all L2 nodes produced by routing + clustering.

    Args:
        intent_root: Root of the INTENTS tree.
        routing_results: List of routing result dicts, one per L2.
        cluster_results: List of cluster result dicts, parallel to routing_results.

    Returns:
        Dict mapping L2 path to the written manifest path.
    """
    written = {}

    for i, (routing, cluster) in enumerate(zip(routing_results, cluster_results)):
        l1_name = routing.get("l1_name", "")
        l2_id = routing.get("intent_id") or f"dev-cluster-{i}"
        l2_title = routing.get("title") or l2_id
        l2_dir = os.path.join(intent_root, l1_name, l2_title)

        existing_path = os.path.join(l2_dir, "intent_manifest.json")
        existing = read_manifest(existing_path)

        manifest_path = write_l2_manifest(
            intent_root=intent_root,
            l2_path=l2_dir,
            routing_result=routing,
            cluster_data=cluster,
            existing_manifest=existing,
        )
        written[l2_dir] = manifest_path

    return written
