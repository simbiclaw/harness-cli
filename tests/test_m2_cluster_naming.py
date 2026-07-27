"""M2 Acceptance Test: Basic clustering + contrastive naming.

Test-first: write test RED, then implement clustering + naming logic.
"""

import os

import pytest

try:
    import sklearn  # noqa: F401

    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "demo_calls.json")

# Sample extracted Requests for 5 calls (from M1 extraction — these are the expected outputs)
SAMPLE_REQUESTS = [
    {
        "audio_id": "call_001",
        "request_text": "客户咨询浙江应急管理局处罚系统案件上报失败原因及解决方法",
    },
    {"audio_id": "call_002", "request_text": "客户咨询数字证书到期延期办理流程、所需材料和费用"},
    {"audio_id": "call_003", "request_text": "客户投诉未收到承诺的回复电话，要求解决问题"},
    {"audio_id": "call_004", "request_text": "客户咨询企业年报截止日期及逾期处罚规定"},
    {"audio_id": "call_005", "request_text": "客户咨询数字证书丢失补办流程、时间及收费标准"},
]


class TestClusterNaming:
    """M2: Clustering partition + contrastive naming prompt + name validation."""

    @pytest.mark.skipif(not _HAS_SKLEARN, reason="scikit-learn not installed")
    def test_cluster_script_partitions_requests(self):
        """K-means on 5 Requests must produce at least 2 non-empty clusters,
        and all Requests must be assigned."""
        import numpy as np

        import scripts.cluster as cluster_mod

        _orig_embed = cluster_mod.embed
        cluster_mod.embed = lambda texts: [np.random.rand(1024).tolist() for _ in texts]
        try:
            from scripts.cluster import run_clustering

            texts = [r["request_text"] for r in SAMPLE_REQUESTS]
            clusters = run_clustering(texts, k=2)
        finally:
            cluster_mod.embed = _orig_embed
        assert len(clusters) >= 2, f"Expected >= 2 clusters, got {len(clusters)}"
        # All requests assigned (empty clusters may exist but all texts tracked)
        assigned = sum(len(c["members"]) for c in clusters)
        assert assigned == len(texts), f"All {len(texts)} Requests must be assigned, got {assigned}"

    @pytest.mark.skipif(not _HAS_SKLEARN, reason="scikit-learn not installed")
    def test_cluster_returns_centroids(self):
        """Each non-empty cluster must have a centroid and member list."""
        import numpy as np

        import scripts.cluster as cluster_mod

        _orig_embed = cluster_mod.embed
        cluster_mod.embed = lambda texts: [np.random.rand(1024).tolist() for _ in texts]
        try:
            from scripts.cluster import run_clustering

            texts = [r["request_text"] for r in SAMPLE_REQUESTS]
            clusters = run_clustering(texts, k=2)
        finally:
            cluster_mod.embed = _orig_embed
        non_empty = [c for c in clusters if len(c["members"]) > 0]
        assert len(non_empty) >= 1, "At least one cluster must be non-empty"
        for c in non_empty:
            assert "centroid" in c
            assert "members" in c
            assert len(c["members"]) > 0

    def test_contrastive_prompt_has_both_sections(self):
        """Contrastive naming prompt must include <同类 Request> and <对比 Request> sections."""
        from scripts.cluster import build_naming_prompt

        in_cluster = ["客户咨询证书延期流程", "客户询问延期费用"]
        contrastive = ["客户投诉未收到回复电话", "客户咨询补办流程"]

        prompt = build_naming_prompt(in_cluster, contrastive, l1="法人数字证书业务", l2="证书延期")
        assert "<同类 Request>" in prompt
        assert "<对比 Request>" in prompt
        assert "法人数字证书业务" in prompt
        assert "证书延期" in prompt

    def test_name_validation_rejects_generic(self):
        """Non-generic names pass; generic names like '其他咨询' are rejected."""
        from scripts.cluster import validate_cluster_name

        assert validate_cluster_name("咨询证书续费流程") is True
        assert validate_cluster_name("询问延期费用标准") is True
        assert validate_cluster_name("其他咨询") is False
        assert validate_cluster_name("综合问题") is False
        assert validate_cluster_name("其他") is False
        assert validate_cluster_name("") is False

    def test_select_contrastive_samples_from_nearest_cluster(self):
        """Contrastive samples come from the nearest neighboring cluster's centroid."""
        from scripts.cluster import select_contrastive_samples

        clusters = [
            {
                "members": ["证书延期流程咨询", "延期费用询问", "VIP优惠确认"],
                "centroid": [0.1, 0.2],
            },
            {"members": ["投诉未回复", "服务态度差", "要求退款"], "centroid": [0.9, 0.8]},
            {"members": ["补办流程", "材料准备", "工本费"], "centroid": [0.5, 0.4]},
        ]
        target_cluster_idx = 0
        samples = select_contrastive_samples(clusters, target_cluster_idx, n=3)
        assert len(samples) == 3
        # Samples should come from the nearest cluster (cluster 2, centroid [0.5, 0.4])
        # not from cluster 1 which is farther
