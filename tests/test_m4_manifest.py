"""M4 Acceptance Test: Manifest Population.

Test-first: write test RED, then implement manifest writing logic.
Never touches top_down. Only writes bottom_up, last_updated, last_updated_by, calibration_status.
"""

import json
import os
import tempfile
import copy
import pytest


SAMPLE_L2_MATCHED_ROUTING = {
    "channel": "matched",
    "intent_id": "certificate-renewal",
    "title": "证书延期",
    "description": "客户数字证书到期或过期，申请延期服务",
    "match_confidence": 0.87,
    "l1_name": "法人数字证书业务",
}

SAMPLE_L2_DEVIATION_ROUTING = {
    "channel": "deviation",
    "intent_id": "ukey-driver-failure",
    "title": "UKey驱动故障",
    "description": "客户UKey插入后无法识别，或驱动重装后仍无效",
    "deviation_score": 0.82,
    "best_match_intent_id": "certificate-unlock",
    "best_match_similarity": 0.31,
    "l1_name": "法人数字证书业务",
}

SAMPLE_CLUSTER_DATA = {
    "cluster_centroid": [0.12, -0.34, 0.78],
    "representative_requests": ["客户询问延期流程", "客户咨询续费费用"],
    "request_count": 342,
    "clustering_run_id": "run-2026-07-19T09-00-00Z",
}

SAMPLE_EXISTING_TOP_DOWN = {
    "manual": "证书延期操作手册.docx",
    "operator_count": 12,
    "goal_states": ["T_cert_renewed"],
    "pipeline_version": "doc2graph-v0.3",
    "processed_at": "2026-07-10T14:30:00Z",
}


class TestManifestWriter:
    """M4: Manifest population - unit tests."""

    def test_create_l2_matched_manifest(self):
        """Given routing results for matched L2, create intent_manifest.json."""
        from scripts.manifest_writer import write_l2_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            l2_path = os.path.join(tmpdir, "证书延期")
            os.makedirs(l2_path)

            manifest_path = write_l2_manifest(
                intent_root=tmpdir,
                l2_path=l2_path,
                routing_result=SAMPLE_L2_MATCHED_ROUTING,
                cluster_data=SAMPLE_CLUSTER_DATA,
                existing_manifest=None,
            )

            assert os.path.exists(manifest_path)
            with open(manifest_path) as f:
                manifest = json.load(f)

            # Assert bottom_up populated
            assert manifest["bottom_up"]["channel"] == "matched"
            assert manifest["bottom_up"]["match_confidence"] == 0.87
            assert manifest["bottom_up"]["request_count"] == 342
            assert manifest["bottom_up"]["cluster_centroid"] == [0.12, -0.34, 0.78]
            assert "客户询问延期流程" in manifest["bottom_up"]["representative_requests"]
            assert manifest["bottom_up"]["clustering_run_id"] == "run-2026-07-19T09-00-00Z"
            assert "last_clustered_at" in manifest["bottom_up"]

            # Assert top_down is untouched (or empty if none provided)
            assert manifest["top_down"] == {}

            # Assert source is 'audio2tree' when no existing top_down
            assert manifest["source"] == "audio2tree"

    def test_create_l2_matched_manifest_with_top_down_preserved(self):
        """When existing top_down present, source becomes 'both' and top_down preserved."""
        from scripts.manifest_writer import write_l2_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            l2_path = os.path.join(tmpdir, "证书延期")
            os.makedirs(l2_path)

            existing = {
                "intent_id": "certificate-renewal",
                "title": "证书延期",
                "description": "...",
                "source": "doc2graph",
                "top_down": SAMPLE_EXISTING_TOP_DOWN,
                "bottom_up": {"channel": None, "request_count": 0},
                "calibration_status": "uncalibrated",
            }

            manifest_path = write_l2_manifest(
                intent_root=tmpdir,
                l2_path=l2_path,
                routing_result=SAMPLE_L2_MATCHED_ROUTING,
                cluster_data=SAMPLE_CLUSTER_DATA,
                existing_manifest=existing,
            )

            with open(manifest_path) as f:
                manifest = json.load(f)

            # Assert bottom_up populated
            assert manifest["bottom_up"]["channel"] == "matched"
            assert manifest["bottom_up"]["request_count"] == 342

            # Assert top_down preserved exactly
            assert manifest["top_down"] == SAMPLE_EXISTING_TOP_DOWN

            # Assert source is 'both' when existing top_down present
            assert manifest["source"] == "both"

    def test_create_l2_deviation_manifest(self):
        """Given deviation routing results, create intent_manifest.json."""
        from scripts.manifest_writer import write_l2_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            l2_path = os.path.join(tmpdir, "UKey驱动故障")
            os.makedirs(l2_path)

            deviation_cluster = {
                "request_count": 127,
                "clustering_run_id": "run-2026-07-19T09-00-00Z",
            }

            manifest_path = write_l2_manifest(
                intent_root=tmpdir,
                l2_path=l2_path,
                routing_result=SAMPLE_L2_DEVIATION_ROUTING,
                cluster_data=deviation_cluster,
                existing_manifest=None,
            )

            with open(manifest_path) as f:
                manifest = json.load(f)

            # Assert bottom_up is deviation channel
            assert manifest["bottom_up"]["channel"] == "deviation"
            assert manifest["bottom_up"]["status"] == "pending_review"
            assert manifest["bottom_up"]["request_count"] == 127
            assert manifest["bottom_up"]["deviation_score"] == 0.82
            assert manifest["bottom_up"]["best_match_intent_id"] == "certificate-unlock"
            assert manifest["bottom_up"]["best_match_similarity"] == 0.31
            assert "discovered_at" in manifest["bottom_up"]

            # Assert source is 'audio2tree' and top_down is empty object
            assert manifest["source"] == "audio2tree"
            assert manifest["top_down"] == {}

            # Assert calibration fields
            assert manifest["calibration_status"] == "needs_manual"
            assert "calibration_detail" in manifest

    def test_manifest_never_touches_top_down(self):
        """Create manifest with existing top_down data, run manifest_writer, assert original top_down preserved."""
        from scripts.manifest_writer import write_l2_manifest, merge_manifest

        # Simulate an existing manifest with top_down
        existing = {
            "intent_id": "certificate-renewal",
            "title": "证书延期",
            "description": "客户数字证书到期或过期，申请延期服务",
            "source": "doc2graph",
            "top_down": dict(SAMPLE_EXISTING_TOP_DOWN),
            "bottom_up": {"channel": None, "request_count": 0},
            "calibration_status": "uncalibrated",
        }

        # New bottom_up data
        bottom_up_data = {
            "channel": "matched",
            "match_confidence": 0.87,
            "request_count": 342,
            "cluster_centroid": [0.12, -0.34, 0.78],
            "representative_requests": ["客户询问延期流程"],
            "clustering_run_id": "run-2026-07-19T09-00-00Z",
            "last_clustered_at": "2026-07-19T09:15:22Z",
        }

        merged = merge_manifest(existing, bottom_up_data)

        # Original top_down fields preserved exactly
        assert merged["top_down"] == SAMPLE_EXISTING_TOP_DOWN
        assert merged["top_down"]["manual"] == "证书延期操作手册.docx"
        assert merged["top_down"]["operator_count"] == 12

        # Only bottom_up, last_updated, last_updated_by, calibration_status modified
        assert merged["bottom_up"]["channel"] == "matched"
        assert merged["bottom_up"]["request_count"] == 342
        assert merged["last_updated_by"] == "audio_to_tree"
        assert "last_updated" in merged
        assert merged["calibration_status"] == "calibrated"

        # intent_id, title, description unchanged
        assert merged["intent_id"] == "certificate-renewal"
        assert merged["title"] == "证书延期"
        assert merged["description"] is not None

    def test_manifest_writer_merge_existing(self):
        """Given existing manifest, update only bottom_up fields."""
        from scripts.manifest_writer import merge_manifest

        existing = {
            "intent_id": "certificate-renewal",
            "title": "证书延期",
            "description": "Existing description",
            "source": "doc2graph",
            "top_down": {"manual": "existing.docx"},
            "bottom_up": {"channel": None, "request_count": 0},
            "calibration_status": "uncalibrated",
        }

        bottom_up_data = {
            "channel": "matched",
            "match_confidence": 0.91,
            "request_count": 400,
            "cluster_centroid": [0.2, -0.3, 0.8],
            "representative_requests": ["客户咨询费用"],
            "clustering_run_id": "run-2026-07-20T09-00-00Z",
            "last_clustered_at": "2026-07-20T09:15:22Z",
        }

        merged = merge_manifest(existing, bottom_up_data)

        # Assert intent_id, title, description, source, top_down preserved
        assert merged["intent_id"] == "certificate-renewal"
        assert merged["title"] == "证书延期"
        assert merged["description"] == "Existing description"
        assert merged["source"] == "doc2graph"
        assert merged["top_down"] == {"manual": "existing.docx"}

        # Assert bottom_up updated
        assert merged["bottom_up"]["channel"] == "matched"
        assert merged["bottom_up"]["match_confidence"] == 0.91
        assert merged["bottom_up"]["request_count"] == 400

    def test_l2_manifest_has_required_fields(self):
        """All produced manifests must have: intent_id, title, description, source.
        Each bottom_up must have: channel, request_count.
        Must have last_updated_by == 'audio_to_tree'."""
        from scripts.manifest_writer import write_l2_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create matched manifest
            l2_path_m = os.path.join(tmpdir, "证书延期")
            os.makedirs(l2_path_m)
            write_l2_manifest(tmpdir, l2_path_m, SAMPLE_L2_MATCHED_ROUTING, SAMPLE_CLUSTER_DATA, None)

            with open(os.path.join(l2_path_m, "intent_manifest.json")) as f:
                matched = json.load(f)

            # Required top-level fields
            assert "intent_id" in matched
            assert "title" in matched
            assert "description" in matched
            assert "source" in matched
            assert "last_updated" in matched
            assert matched["last_updated_by"] == "audio_to_tree"

            # Required bottom_up fields
            assert "channel" in matched["bottom_up"]
            assert "request_count" in matched["bottom_up"]

            # Create deviation manifest
            l2_path_d = os.path.join(tmpdir, "UKey驱动故障")
            os.makedirs(l2_path_d)
            dev_cluster = {"request_count": 50, "clustering_run_id": "run-1"}
            write_l2_manifest(tmpdir, l2_path_d, SAMPLE_L2_DEVIATION_ROUTING, dev_cluster, None)

            with open(os.path.join(l2_path_d, "intent_manifest.json")) as f:
                dev = json.load(f)

            assert "intent_id" in dev
            assert "title" in dev
            assert "description" in dev
            assert "source" in dev
            assert "channel" in dev["bottom_up"]
            assert "request_count" in dev["bottom_up"]
            assert dev["last_updated_by"] == "audio_to_tree"
