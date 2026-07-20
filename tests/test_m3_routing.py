"""M3 Acceptance Test: Dual-channel routing + deviation detection.

Test-first: write test RED, then implement the routing logic in scripts/routing.py.
"""

import json
import math
import os
import shutil
import tempfile

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _normalized_random(dim: int = 1024) -> list[float]:
    """Return a unit-norm random vector for mock embeddings."""
    v = np.random.randn(dim)
    return (v / np.linalg.norm(v)).tolist()


def _make_similar(vec: list[float], target_sim: float = 0.85) -> list[float]:
    """Return a unit vector whose cosine with *vec* is *target_sim*.

    Uses Gram-Schmidt to produce an orthogonal noise component so the
    requested similarity is exact (within float precision).
    """
    v = np.asarray(vec)
    dim = len(v)
    noise = np.random.randn(dim)
    # remove component parallel to v
    noise = noise - np.dot(noise, v) * v
    noise = noise / np.linalg.norm(noise)
    w = target_sim * v + math.sqrt(1.0 - target_sim ** 2) * noise
    return w.tolist()


# ---------------------------------------------------------------------------
# M3  tests
# ---------------------------------------------------------------------------

class TestExtractL2Descriptions:
    """Parsing intent_manifest.json files at the L2 level."""

    def test_extract_l2_descriptions(self):
        from scripts.routing import extract_l2_descriptions

        tmp = tempfile.mkdtemp()
        try:
            # L1
            l1 = os.path.join(tmp, "corp-digital-cert")
            os.makedirs(l1)
            with open(os.path.join(l1, "intent_manifest.json"), "w") as f:
                json.dump({"intent_id": "corp-digital-cert",
                           "description": "法人数字证书全生命周期服务"}, f)

            # L2 -- these are the ones we want
            l2_a = os.path.join(l1, "certificate-renewal")
            os.makedirs(l2_a)
            with open(os.path.join(l2_a, "intent_manifest.json"), "w") as f:
                json.dump({"intent_id": "certificate-renewal",
                           "description": "客户数字证书到期或过期，申请延期"}, f)

            l2_b = os.path.join(l1, "certificate-replacement")
            os.makedirs(l2_b)
            with open(os.path.join(l2_b, "intent_manifest.json"), "w") as f:
                json.dump({"intent_id": "certificate-replacement",
                           "description": "客户数字证书丢失或损坏，申请补办"}, f)

            # L3 -- should NOT be included
            l3 = os.path.join(l2_a, "fee-inquiry")
            os.makedirs(l3)
            with open(os.path.join(l3, "intent_manifest.json"), "w") as f:
                json.dump({"intent_id": "certificate-renewal.fee-inquiry",
                           "description": "客户询问延期费用标准",
                           "parent_intent_id": "certificate-renewal"}, f)

            descs = extract_l2_descriptions(tmp)
            assert len(descs) == 2, f"Expected 2 L2 descriptions, got {len(descs)}"
            ids = {d["intent_id"] for d in descs}
            assert "certificate-renewal" in ids
            assert "certificate-replacement" in ids
        finally:
            shutil.rmtree(tmp)

    def test_path_included(self):
        """Each L2 description dict must contain a *path* key."""
        from scripts.routing import extract_l2_descriptions

        tmp = tempfile.mkdtemp()
        try:
            l1 = os.path.join(tmp, "l1")
            os.makedirs(l1)
            with open(os.path.join(l1, "intent_manifest.json"), "w") as f:
                json.dump({"intent_id": "l1", "description": "x"}, f)
            l2 = os.path.join(l1, "l2")
            os.makedirs(l2)
            with open(os.path.join(l2, "intent_manifest.json"), "w") as f:
                json.dump({"intent_id": "l2", "description": "y"}, f)

            descs = extract_l2_descriptions(tmp)
            assert len(descs) == 1
            assert "path" in descs[0]
            assert "intent_manifest.json" in descs[0]["path"]
        finally:
            shutil.rmtree(tmp)

    def test_skips_root_manifest(self):
        """An intent_manifest.json at the root is not an L2."""
        from scripts.routing import extract_l2_descriptions

        tmp = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmp, "intent_manifest.json"), "w") as f:
                json.dump({"intent_id": "root", "description": "root"}, f)
            descs = extract_l2_descriptions(tmp)
            assert len(descs) == 0
        finally:
            shutil.rmtree(tmp)


class TestMatchedChannel:
    """Requests semantically close to an L2 description are routed
    to the 'matched' channel with similarity >= 0.60."""

    def test_matched_channel(self):
        from scripts.routing import route_request

        l2_descs = [
            {"intent_id": "cert-renewal",
             "description": "证书延期",
             "embedding": _normalized_random()},
            {"intent_id": "cert-replace",
             "description": "证书补办",
             "embedding": _normalized_random()},
            {"intent_id": "annual-report",
             "description": "企业年报",
             "embedding": _normalized_random()},
        ]

        # request very similar to cert-renewal
        req_emb = _make_similar(l2_descs[0]["embedding"], target_sim=0.75)
        result = route_request("call_001", req_emb, l2_descs)

        assert result["channel"] == "matched", f"Expected matched, got {result['channel']}"
        assert result["similarity_score"] >= 0.60, \
            f"Score {result['similarity_score']} < 0.60"
        assert result["matched_intent_id"] == "cert-renewal"
        assert result["audio_id"] == "call_001"

    def test_matched_channels_all_scores(self):
        """Matched results include scores for every L2."""
        from scripts.routing import route_request

        l2_descs = [
            {"intent_id": "a", "description": "a", "embedding": _normalized_random()},
            {"intent_id": "b", "description": "b", "embedding": _normalized_random()},
        ]
        req_emb = _make_similar(l2_descs[0]["embedding"], target_sim=0.80)
        result = route_request("c1", req_emb, l2_descs)

        assert "all_scores" in result
        assert len(result["all_scores"]) == 2
        score_map = {s["intent_id"]: s["similarity"] for s in result["all_scores"]}
        assert "a" in score_map
        assert "b" in score_map


class TestDeviationChannel:
    """Requests with no L2 description above threshold go to deviation."""

    def test_deviation_channel(self):
        from scripts.routing import route_request

        l2_descs = [
            {"intent_id": "cert-renewal",
             "description": "证书延期",
             "embedding": _normalized_random()},
            {"intent_id": "cert-replace",
             "description": "证书补办",
             "embedding": _normalized_random()},
        ]

        # completely unrelated random vector
        req_emb = _normalized_random()
        result = route_request("call_099", req_emb, l2_descs)

        assert result["channel"] == "deviation", \
            f"Expected deviation, got {result['channel']}"
        assert result["similarity_score"] < 0.60, \
            f"Score {result['similarity_score']} >= 0.60"
        assert result["matched_intent_id"] is None
        assert result["audio_id"] == "call_099"

    def test_deviation_on_empty_l2(self):
        """With zero L2 descriptions every request goes to deviation."""
        from scripts.routing import route_request

        req_emb = _normalized_random()
        result = route_request("c1", req_emb, [])
        assert result["channel"] == "deviation"
        assert result["matched_intent_id"] is None


class TestCollisionDetection:
    """Pairwise cosine > threshold freezes the newer anchor."""

    def test_collision_freezes_newer(self):
        from scripts.routing import detect_collisions

        base = _normalized_random()
        similar = _make_similar(base, target_sim=0.85)  # cosine ~0.85 > 0.7

        descriptions = [
            {"intent_id": "cert-renewal", "description": "证书到期延期",
             "embedding": base},
            {"intent_id": "cert-extend", "description": "证书延期办理",
             "embedding": similar},
        ]

        frozen = detect_collisions(descriptions, threshold=0.7)
        assert len(frozen) >= 1, "Expected at least one frozen anchor"
        # newer anchor (later in list) should be frozen
        assert frozen[0]["intent_id"] == "cert-extend", \
            f"Expected newer anchor cert-extend frozen, got {frozen[0]['intent_id']}"
        assert frozen[0]["collision_with"] == "cert-renewal"

    def test_no_collision(self):
        """Dissimilar descriptions produce no frozen anchors."""
        from scripts.routing import detect_collisions

        descriptions = [
            {"intent_id": "a", "description": "a",
             "embedding": _normalized_random()},
            {"intent_id": "b", "description": "b",
             "embedding": _normalized_random()},
        ]

        frozen = detect_collisions(descriptions, threshold=0.7)
        assert len(frozen) == 0

    def test_single_description_no_collision(self):
        """A single L2 can't collide with anything."""
        from scripts.routing import detect_collisions

        descriptions = [
            {"intent_id": "a", "description": "a",
             "embedding": _normalized_random()},
        ]
        frozen = detect_collisions(descriptions, threshold=0.7)
        assert len(frozen) == 0


class TestRoutingOutputSchema:
    """Every routed request dict must carry the expected fields."""

    def test_matched_schema(self):
        from scripts.routing import route_request

        l2_descs = [
            {"intent_id": "x", "description": "x",
             "embedding": _normalized_random()},
        ]
        req_emb = _make_similar(l2_descs[0]["embedding"], target_sim=0.80)
        result = route_request("c1", req_emb, l2_descs)

        assert "audio_id" in result
        assert "channel" in result
        assert "matched_intent_id" in result
        assert "similarity_score" in result
        assert "all_scores" in result
        assert result["channel"] in ("matched", "deviation")
        assert isinstance(result["similarity_score"], float)

    def test_deviation_schema(self):
        from scripts.routing import route_request

        result = route_request("c2", _normalized_random(), [])
        assert "audio_id" in result
        assert result["channel"] == "deviation"
        assert result["matched_intent_id"] is None
        assert isinstance(result["similarity_score"], float)
        assert "all_scores" in result


class TestRouteBatch:
    """Batch routing aggregates individual decisions and computes deviation rate."""

    def test_route_batch_all_matched(self):
        from scripts.routing import route_batch

        base = _normalized_random()
        l2_descs = [
            {"intent_id": "cert-renewal", "description": "证书延期",
             "embedding": base},
        ]
        requests = [
            {"audio_id": "c1", "embedding": _make_similar(base, 0.75)},
            {"audio_id": "c2", "embedding": _make_similar(base, 0.80)},
        ]

        result = route_batch(requests, l2_descs)
        assert len(result["requests"]) == 2
        for r in result["requests"]:
            assert r["channel"] == "matched"
        assert result["deviation_rate"] == 0.0

    def test_route_batch_with_deviation(self):
        from scripts.routing import route_batch

        base = _normalized_random()
        l2_descs = [
            {"intent_id": "cert-renewal", "description": "证书延期",
             "embedding": base},
        ]
        requests = [
            {"audio_id": "c1", "embedding": _make_similar(base, 0.75)},
            {"audio_id": "c2", "embedding": _normalized_random()},  # deviation
            {"audio_id": "c3", "embedding": _normalized_random()},  # deviation
        ]

        result = route_batch(requests, l2_descs)
        assert len(result["requests"]) == 3
        assert result["requests"][0]["channel"] == "matched"
        assert result["requests"][1]["channel"] == "deviation"
        assert result["requests"][2]["channel"] == "deviation"
        assert result["deviation_rate"] == pytest.approx(2.0 / 3.0)

    def test_route_batch_includes_frozen_anchors(self):
        """Batch route result must include frozen_anchors."""
        from scripts.routing import route_batch

        base = _normalized_random()
        similar = _make_similar(base, 0.85)
        l2_descs = [
            {"intent_id": "a", "description": "a", "embedding": base},
            {"intent_id": "b", "description": "b", "embedding": similar},
        ]
        requests = [
            {"audio_id": "c1", "embedding": _normalized_random()},
        ]

        result = route_batch(requests, l2_descs)
        assert "frozen_anchors" in result
        assert len(result["frozen_anchors"]) >= 1

    def test_route_batch_empty_requests(self):
        """Empty request list returns empty results and 0.0 rate."""
        from scripts.routing import route_batch

        result = route_batch([], [])
        assert result["requests"] == []
        assert result["deviation_rate"] == 0.0
        assert "frozen_anchors" in result
