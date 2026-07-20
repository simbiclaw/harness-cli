"""Clustering and contrastive naming — M2.

Embedding via local Ollama (bge-m3). K-means via sklearn.
Claude does the naming; this module handles the deterministic math and prompt scaffolding.
"""

import json
import urllib.request
import numpy as np
from typing import Optional

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3"

GENERIC_NAMES = {"其他咨询", "综合问题", "其他", "其他业务", "综合", "其他服务", "一般咨询"}


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using local Ollama bge-m3."""
    vectors = []
    for text in texts:
        payload = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode()
        req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            vectors.append(result["embedding"])
    return vectors


def run_clustering(texts: list[str], k: Optional[int] = None) -> list[dict]:
    """Run k-means clustering on a list of Request texts.

    Args:
        texts: List of Request strings.
        k: Number of clusters. If None, auto-selected via silhouette (min 2).

    Returns:
        List of clusters, each with {centroid, members (indices into texts)}.
    """
    if k is None:
        k = max(2, min(len(texts) // 2, 5))  # heuristic for small batches

    vectors = embed(texts)
    X = np.array(vectors)

    from sklearn.cluster import KMeans
    # Retry with different random seeds if a cluster comes back empty
    for seed in [42, 7, 13, 0]:
        km = KMeans(n_clusters=k, random_state=seed, n_init=10)
        labels = km.fit_predict(X)
        if len(set(labels)) == k:  # all k clusters have at least one member
            break

    clusters = []
    for i in range(k):
        members = [j for j, lbl in enumerate(labels) if lbl == i]
        centroid = km.cluster_centers_[i].tolist()
        clusters.append({"centroid": centroid, "members": members})
    return clusters


def select_contrastive_samples(clusters: list[dict], target_idx: int, n: int = 3) -> list[dict]:
    """Select n contrastive member indices from the nearest neighboring cluster.

    Args:
        clusters: List of cluster dicts with centroid and members.
        target_idx: Index of the cluster being named.
        n: Number of contrastive samples to return.

    Returns:
        List of member indices (ints) from the nearest other cluster.
    """
    if len(clusters) < 2:
        return []

    target_centroid = np.array(clusters[target_idx]["centroid"])

    # Find nearest other cluster by centroid distance
    distances = []
    for i, c in enumerate(clusters):
        if i == target_idx:
            continue
        dist = np.linalg.norm(np.array(c["centroid"]) - target_centroid)
        distances.append((dist, i))
    distances.sort()
    nearest_idx = distances[0][1]

    members = clusters[nearest_idx]["members"]
    # Return at most n, or all if fewer
    sample = members[: min(n, len(members))]
    return sample


def build_naming_prompt(in_cluster_texts: list[str], contrastive_texts: list[str],
                        l1: str, l2: str) -> str:
    """Build a contrastive naming prompt for Claude.

    Args:
        in_cluster_texts: Request texts FROM the cluster (up to 5).
        contrastive_texts: Request texts from the nearest neighboring cluster (up to 5).
        l1: L1 business domain name.
        l2: L2 intent name (or "偏差通道-新发现" for deviation channel).
    """
    in_block = "\n".join(f"- {t}" for t in in_cluster_texts[:5])
    contrast_block = "\n".join(f"- {t}" for t in contrastive_texts[:5])

    return f"""你是客服意图分析助手。请根据以下一组客户 Request，生成该聚类的名称和描述。
目标是：用一个精确的名称和描述来刻画这组 Request，使其与对比组区分开来。

<同类 Request>  ← 来自该聚类的 Request (按与质心相似度排序)
{in_block}
</同类 Request>

<对比 Request>  ← 来自该 L1 下其他聚类的 Request (最接近本聚类但不属于它)
{contrast_block}
</对比 Request>

要求:
1. 用一句中文 (2-8 字) 命名 — 描述"客户想要什么"，而非"客户情绪如何"
2. 用两句话描述核心特征
3. 名称应区分于对比组 — 确保独特、有区分力
4. 这是"{l1}"业务线下的"{l2}"场景中的细分

输出格式:
<name> [名称] </name>
<description> [两句描述] </description>"""


def validate_cluster_name(name: str) -> bool:
    """Validate that a cluster name is not generic."""
    if not name or not name.strip():
        return False
    name = name.strip()
    if name in GENERIC_NAMES:
        return False
    if len(name) < 2:
        return False
    return True
