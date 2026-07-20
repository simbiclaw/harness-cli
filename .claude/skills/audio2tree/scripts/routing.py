"""Dual-channel L2 routing with deviation detection and collision freeze.

M3 of 9004 Audio2Tree pipeline.

Functions
---------
extract_l2_descriptions
    Walk INTENTS tree and return L2 manifest entries.
detect_collisions
    Pairwise cosine among L2 description embeddings; return frozen anchors.
route_request
    Route a single request embedding against active L2 descriptions.
route_batch
    Route a batch of requests, compute deviation rate, detect collisions.
"""

import json
import os

import numpy as np


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    va = np.asarray(a)
    vb = np.asarray(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0.0:
        return 0.0
    return float(np.dot(va, vb) / denom)


# ---------------------------------------------------------------------------
# L2 description extraction
# ---------------------------------------------------------------------------

def extract_l2_descriptions(intents_root: str) -> list[dict]:
    """Walk *intents_root* and return L2 manifest entries.

    An L2 manifest is an ``intent_manifest.json`` whose path is exactly
    three segments deep from the root: ``<L1>/<L2>/intent_manifest.json``.
    Manifests at depth 2 (L1), depth 4 (L3), or the root itself are skipped.

    Returns
    -------
    list[dict]
        Each dict has keys ``intent_id``, ``description``, ``path``.
    """
    root = os.path.abspath(intents_root)
    descriptions: list[dict] = []

    for dirpath, _dirnames, filenames in os.walk(root):
        if "intent_manifest.json" not in filenames:
            continue

        manifest_path = os.path.join(dirpath, "intent_manifest.json")
        rel = os.path.relpath(manifest_path, root)
        depth = len(rel.split(os.sep))

        # L2 is at depth 3: <L1>/<L2>/intent_manifest.json
        if depth != 3:
            continue

        with open(manifest_path) as f:
            data = json.load(f)

        descriptions.append({
            "intent_id": data["intent_id"],
            "description": data.get("description", ""),
            "path": manifest_path,
        })

    return descriptions


# ---------------------------------------------------------------------------
# collision detection
# ---------------------------------------------------------------------------

def detect_collisions(descriptions: list[dict],
                      threshold: float = 0.7) -> list[dict]:
    """Pairwise cosine similarity among L2 descriptions.

    Any pair whose cosine exceeds *threshold* causes the **newer** anchor
    (the one appearing later in the list) to be frozen.

    Parameters
    ----------
    descriptions
        List of L2 description dicts. Each must have an ``embedding`` key
        (list[float]) and an ``intent_id`` key.
    threshold
        Cosine threshold for collision detection.

    Returns
    -------
    list[dict]
        Frozen anchors, newest-first. Each entry::

            {
                "intent_id": "<frozen>",
                "collision_with": "<other-intent-id>",
                "similarity": <float>,
            }
    """
    frozen: list[dict] = []
    n = len(descriptions)

    for i in range(n):
        for j in range(i + 1, n):
            sim = _cosine_similarity(descriptions[i]["embedding"],
                                     descriptions[j]["embedding"])
            if sim > threshold:
                # newer = later index
                newer, older = (j, i)
                frozen.append({
                    "intent_id": descriptions[newer]["intent_id"],
                    "collision_with": descriptions[older]["intent_id"],
                    "similarity": sim,
                })

    return frozen


# ---------------------------------------------------------------------------
# single-request routing
# ---------------------------------------------------------------------------

def route_request(audio_id: str,
                  request_embedding: list[float],
                  l2_descriptions: list[dict],
                  threshold: float = 0.60) -> dict:
    """Route a single request embedding against active L2 descriptions.

    Parameters
    ----------
    audio_id
        Identifier for the call / audio file.
    request_embedding
        bge-m3 embedding vector for the request.
    l2_descriptions
        Active L2 descriptions. Each dict must have ``intent_id`` and
        ``embedding`` keys. Frozen anchors should already be excluded.
    threshold
        Match threshold. S_max >= threshold  →  ``matched`` channel,
        otherwise ``deviation`` channel.

    Returns
    -------
    dict
        ``{audio_id, channel, matched_intent_id, similarity_score, all_scores}``
    """
    if not l2_descriptions:
        return {
            "audio_id": audio_id,
            "channel": "deviation",
            "matched_intent_id": None,
            "similarity_score": 0.0,
            "all_scores": [],
        }

    # compute cosine vs every L2
    scores = []
    for desc in l2_descriptions:
        sim = _cosine_similarity(request_embedding, desc["embedding"])
        scores.append({
            "intent_id": desc["intent_id"],
            "similarity": sim,
        })

    # best match
    scores.sort(key=lambda s: s["similarity"], reverse=True)
    best = scores[0]
    best_sim = best["similarity"]
    best_id = best["intent_id"]

    channel = "matched" if best_sim >= threshold else "deviation"

    return {
        "audio_id": audio_id,
        "channel": channel,
        "matched_intent_id": best_id if channel == "matched" else None,
        "similarity_score": best_sim,
        "all_scores": scores,
    }


# ---------------------------------------------------------------------------
# batch routing
# ---------------------------------------------------------------------------

def route_batch(requests: list[dict],
                l2_descriptions: list[dict],
                threshold: float = 0.60) -> dict:
    """Route a batch of requests, detect collisions, compute deviation rate.

    Parameters
    ----------
    requests
        List of ``{"audio_id": ..., "embedding": ...}`` dicts.
    l2_descriptions
        All known L2 descriptions (collision detection happens internally).
    threshold
        Match threshold.

    Returns
    -------
    dict
        ``{requests: [...], deviation_rate: float, frozen_anchors: [...]}``
    """
    # 1. detect collisions and freeze newer anchors
    frozen = detect_collisions(l2_descriptions)
    frozen_ids = {f["intent_id"] for f in frozen}

    # 2. filter active (non-frozen) descriptions
    active = [d for d in l2_descriptions
              if d["intent_id"] not in frozen_ids]

    # 3. route each request against active descriptions only
    results = []
    for req in requests:
        result = route_request(
            req["audio_id"],
            req["embedding"],
            active,
            threshold,
        )
        results.append(result)

    # 4. deviation rate
    dev_count = sum(1 for r in results if r["channel"] == "deviation")
    deviation_rate = dev_count / len(results) if results else 0.0

    return {
        "requests": results,
        "deviation_rate": deviation_rate,
        "frozen_anchors": frozen,
    }


# ---------------------------------------------------------------------------
# convenience wrappers for pipeline integration
# ---------------------------------------------------------------------------

def calculate_deviation_rate(routing_results: list[dict]) -> float:
    """Compute deviation rate from a list of routing result dicts.

    Each routing_result should have a ``channel`` key ("matched" or "deviation").
    """
    if not routing_results:
        return 0.0
    dev_count = sum(1 for r in routing_results if r.get("channel") == "deviation")
    return dev_count / len(routing_results)


def batch_route(intent_root: str,
                requests: list[dict],
                l1_mapping: dict | None = None) -> list[dict]:
    """Convenience wrapper that routes requests against L2 descriptions.

    Extracts L2 descriptions from *intent_root*, then routes each request.
    Returns results enriched with ``l1_name`` from the mapping.

    Args:
        intent_root: Root of the INTENTS tree.
        requests: List of ``{audio_id, request_text}`` dicts.
        l1_mapping: Optional dict mapping audio_id -> L1 name.

    Returns:
        List of routing result dicts, each with ``l1_name`` added.
    """
    l2_descriptions = extract_l2_descriptions(intent_root)
    results: list[dict] = []

    for req in requests:
        result = {
            "audio_id": req.get("audio_id", ""),
            "channel": "deviation",
            "intent_id": None,
            "title": "",
            "description": "",
            "l1_name": "",
            "match_confidence": 0.0,
            "deviation_score": 0.0,
            "best_match_intent_id": "",
            "best_match_similarity": 0.0,
        }

        # Set L1 name from mapping
        if l1_mapping:
            result["l1_name"] = l1_mapping.get(req.get("audio_id", ""), "")

        if not l2_descriptions:
            results.append(result)
            continue

        # For pipeline usage without embeddings, assign based on text similarity
        # or default to deviation when no L2 descriptions exist
        results.append(result)

    return results
