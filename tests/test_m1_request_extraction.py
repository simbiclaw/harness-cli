"""M1 Acceptance Test: Batch Request extraction from call transcripts.

Test-first: write test RED, then implement the extraction logic.
"""

import json
import os
import pytest

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "demo_calls.json")


def load_fixture():
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def extract_customer_turns(turns):
    """Extract only customer turns from a turn list."""
    return [t for t in turns if t["speaker"] == "customer"]


class TestRequestExtraction:
    """M1: Feed 5 fixture transcripts into extraction, assert valid Requests."""

    def test_fixture_has_5_calls(self):
        """Prerequisite: fixture must contain exactly 5 calls."""
        calls = load_fixture()
        assert len(calls) == 5, f"Expected 5 calls, got {len(calls)}"

    def test_every_call_has_both_speakers(self):
        """Prerequisite: each call must have both agent and customer turns."""
        calls = load_fixture()
        for call in calls:
            speakers = {t["speaker"] for t in call["turns"]}
            assert "agent" in speakers, f"{call['audio_id']}: missing agent turns"
            assert "customer" in speakers, f"{call['audio_id']}: missing customer turns"

    def test_build_extraction_prompt_includes_all_customer_turns(self):
        """The extraction prompt must include every customer turn."""
        calls = load_fixture()
        for call in calls:
            customer_turns = extract_customer_turns(call["turns"])
            customer_text = "\n".join(t["text"] for t in customer_turns)
            # Prompt must contain all customer text
            assert len(customer_text) > 20, f"{call['audio_id']}: customer text too short for meaningful extraction"

    def test_parse_request_must_be_one_chinese_sentence(self):
        """Response parser: Request must be one Chinese sentence, 8-80 chars,
        not contain agent dialogue markers like '坐席' or 'agent'."""
        from scripts.request_extractor import parse_request_response

        # Valid response
        valid, req = parse_request_response("客户咨询数字证书延期流程和费用", "call_001")
        assert valid is True
        assert 8 <= len(req["request_text"]) <= 80
        assert "坐席" not in req["request_text"]
        assert req["audio_id"] == "call_001"

    def test_parse_rejects_agent_dialogue(self):
        """Response containing agent markers must be rejected."""
        from scripts.request_extractor import parse_request_response

        valid, req = parse_request_response("坐席询问了客户证书到期时间，客户回答今天", "call_001")
        assert valid is False

    def test_parse_rejects_too_short(self):
        """Response under 8 chars rejected."""
        from scripts.request_extractor import parse_request_response

        valid, req = parse_request_response("延期", "call_001")
        assert valid is False

    def test_parse_rejects_too_long(self):
        """Response over 80 chars rejected."""
        from scripts.request_extractor import parse_request_response

        long_text = "客户咨询数字证书延期流程和费用问题，同时询问了VIP优惠政策，还问了补办流程和所需材料，以及年报截止日期" * 2
        valid, req = parse_request_response(long_text, "call_001")
        assert valid is False

    def test_parse_rejects_uncertain(self):
        """UNCLEAR marker must be rejected but preserved."""
        from scripts.request_extractor import parse_request_response

        valid, req = parse_request_response("UNCLEAR", "call_001")
        assert valid is False
        assert req["request_text"] is None
        assert req["confidence"] == 0.0
