#!/usr/bin/env python3
"""Audio2Tree pipeline — M1-M4 integrated.

Usage:
    python .claude/skills/audio2tree/scripts/audio2tree_pipeline.py --run-all \\
        --input-dir <path_to_structural_json> \\
        --output-intents <path_to_INTENTS_root>

Wires:
    S0: Load .structural.json files (or fixture JSON)
    S1: Request extraction via request_extractor
    S2: Embedding + clustering via cluster
    S3: Dual-channel routing via routing
    S4: Manifest population via manifest_writer

Phase A: Skill Prototype. Claude does extraction and naming.
Python handles math (embedding, k-means, cosine, JSON writing).
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure scripts/ is importable
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR.parent))


def load_demo_calls(fixture_path: str) -> list[dict]:
    """Load demo call fixture JSON."""
    with open(fixture_path) as f:
        return json.load(f)


def load_demo_transcripts(demo_dir: str) -> list[dict]:
    """Load demo transcripts from .txt files and convert to turn format.

    Parses 坐席:/客户: labeled dialogue into turn dicts.
    """
    calls = []
    for i in range(1, 6):
        txt_path = os.path.join(demo_dir, f"call_00{i}.txt")
        if not os.path.exists(txt_path):
            continue

        with open(txt_path) as f:
            lines = f.readlines()

        turns = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("坐席:"):
                text = line[len("坐席:"):].strip()
                turns.append({"speaker": "agent", "text": text})
            elif line.startswith("客户:"):
                text = line[len("客户:"):].strip()
                turns.append({"speaker": "customer", "text": text})

        calls.append({
            "audio_id": f"call_00{i}",
            "turns": turns,
        })

    return calls


def extract_requests(calls: list[dict]) -> list[dict]:
    """Extract Requests from calls by building extraction prompts.

    Phase A: This builds the prompt for Claude.
    For automated tests, we use pre-validated expected Requests.

    Returns:
        List of Request dicts with {audio_id, prompt, customer_turns}.
    """
    from request_extractor import build_extraction_prompt

    requests = []
    for call in calls:
        customer_turns = [t for t in call["turns"] if t["speaker"] == "customer"]
        if not customer_turns:
            continue

        prompt = build_extraction_prompt(customer_turns)

        requests.append({
            "audio_id": call["audio_id"],
            "prompt": prompt,
            "customer_turns": len(customer_turns),
        })

    return requests


def run_s1_s2_s3_s4(
    intent_root: str,
    requests: list[dict],
    expected_requests: Optional[list[dict]] = None,
    l1_mapping: Optional[dict] = None,
    skip_claude: bool = True,
    default_l1: str = "",
) -> dict:
    """Run S1-S4 stages in sequence.

    Args:
        intent_root: Root of the INTENTS tree for manifest output.
        requests: List of Request metadata from extract_requests().
        expected_requests: Pre-extracted Request texts (for automated tests).
        l1_mapping: Optional dict audio_id -> L1 name.
        skip_claude: If True, use expected_requests instead of calling Claude.
        default_l1: Default L1 name when mapping not found.

    Returns:
        Dict with pipeline results.
    """
    from cluster import run_clustering, select_contrastive_samples
    from routing import batch_route, calculate_deviation_rate
    from manifest_writer import populate_manifests

    # S1: Extract Request texts
    request_texts = []
    if skip_claude and expected_requests:
        request_texts = [r["request_text"] for r in expected_requests]
    else:
        request_texts = [r.get("request_text", "") for r in requests]

    if not request_texts:
        return {"error": "No request texts available", "manifests": {}, "deviation_rate": 0.0}

    # S2: Embedding + clustering
    clusters = run_clustering(request_texts)

    # Build cluster results for manifest writer
    cluster_results = []
    routing_results = []

    for i, cluster in enumerate(clusters):
        member_indices = cluster["members"]
        if not member_indices:
            cluster_results.append({"request_count": 0, "clustering_run_id": ""})
            routing_results.append({"channel": "deviation", "intent_id": f"empty-cluster-{i}"})
            continue

        member_texts = [request_texts[j] for j in member_indices]

        cluster_data = {
            "cluster_centroid": cluster["centroid"],
            "representative_requests": member_texts[:5],
            "request_count": len(member_indices),
            "clustering_run_id": f"run-{i}",
        }

        # S3: Route the cluster representative through L1/L2
        rep_text = member_texts[0] if member_texts else ""
        routing = batch_route(
            intent_root,
            [{"audio_id": f"cluster-{i}", "request_text": rep_text}],
            l1_mapping
        )
        if routing:
            result = routing[0]
            if not result.get("l1_name") and default_l1:
                result["l1_name"] = default_l1
            # Deviation channel: fill fallback intent_id and title
            if result.get("channel") == "deviation" and not result.get("intent_id"):
                result["intent_id"] = f"dev-cluster-{i}"
                result["title"] = f"偏差聚类-{i}"
                result["description"] = f"自动发现的偏差聚类 #{i}"
            routing_results.append(result)
        else:
            routing_results.append({
                "channel": "deviation",
                "intent_id": f"dev-cluster-{i}",
                "title": f"偏差聚类-{i}",
                "description": f"自动发现的偏差聚类 #{i}",
                "l1_name": default_l1,
                "deviation_score": 0.0,
                "best_match_intent_id": "",
                "best_match_similarity": 0.0,
            })

        cluster_results.append(cluster_data)

    # S4: Manifest population
    manifests = populate_manifests(intent_root, routing_results, cluster_results)

    # Report deviation rate
    deviation_rate = calculate_deviation_rate(routing_results)

    return {
        "manifests": manifests,
        "deviation_rate": deviation_rate,
        "cluster_count": len(clusters),
        "routing_count": len(routing_results),
    }


def run_all(
    intent_root: str,
    input_dir: str,
    fixture_path: Optional[str] = None,
    l1_mapping: Optional[dict] = None,
    default_l1: str = "",
) -> dict:
    """Run the full pipeline S0-S4.

    Args:
        intent_root: INTENTS root for manifest output.
        input_dir: Directory containing input files.
        fixture_path: Optional path to fixture JSON with call data.
        l1_mapping: Optional mapping of audio_id to L1 name.
        default_l1: Default L1 business domain name.

    Returns:
        Pipeline results dict.
    """
    calls = []
    if fixture_path and os.path.exists(fixture_path):
        calls = load_demo_calls(fixture_path)
    elif input_dir and os.path.isdir(input_dir):
        calls = load_demo_transcripts(input_dir)

    if not calls:
        return {"error": "No input data found"}

    expected_requests = build_test_requests(calls)
    requests = extract_requests(calls)

    results = run_s1_s2_s3_s4(
        intent_root=intent_root,
        requests=requests,
        expected_requests=expected_requests,
        l1_mapping=l1_mapping,
        skip_claude=True,
        default_l1=default_l1,
    )

    return results


def build_test_requests(calls: list[dict]) -> list[dict]:
    """Build expected Request texts from calls using known outputs."""
    known = {
        "call_001": "客户咨询浙江应急管理局处罚系统案件上报失败原因及解决方法",
        "call_002": "客户咨询数字证书到期延期办理流程、所需材料和费用",
        "call_003": "客户投诉未收到承诺的回复电话，要求解决问题",
        "call_004": "客户咨询企业受益所有人备案登记流程及操作步骤",
        "call_005": "客户咨询CA锁与平台注册信息未绑定的处理方法",
    }

    requests = []
    for call in calls:
        audio_id = call["audio_id"]
        request_text = known.get(audio_id, "")
        if request_text:
            requests.append({"audio_id": audio_id, "request_text": request_text})

    return requests


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Audio2Tree Pipeline (M1-M4)")
    parser.add_argument("--run-all", action="store_true", help="Run full pipeline S0-S4")
    parser.add_argument("--input-dir", default="INTENTS/_demo",
                        help="Directory with demo transcript .txt files")
    parser.add_argument("--output-intents", default="INTENTS",
                        help="INTENTS root directory for manifest output")
    parser.add_argument("--fixture", default="tests/fixtures/demo_calls.json",
                        help="Path to fixture JSON with call data")
    parser.add_argument("--l1", default="法人数字证书业务",
                        help="L1 business domain name for routing")

    args = parser.parse_args()

    if args.run_all:
        l1_mapping = {}
        for i in range(1, 6):
            l1_mapping[f"call_00{i}"] = args.l1

        results = run_all(
            intent_root=args.output_intents,
            input_dir=args.input_dir,
            fixture_path=args.fixture,
            l1_mapping=l1_mapping,
            default_l1=args.l1,
        )

        if "error" in results:
            print(f"Pipeline error: {results['error']}")
            sys.exit(1)

        print(f"Pipeline complete.")
        print(f"  Clusters formed: {results.get('cluster_count', 0)}")
        print(f"  Routes assigned: {results.get('routing_count', 0)}")
        print(f"  Manifests written: {len(results.get('manifests', {}))}")
        print(f"  Deviation rate: {results.get('deviation_rate', 0.0):.2%}")

        for l2_path in results.get("manifests", {}):
            print(f"  Manifest: {l2_path}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
