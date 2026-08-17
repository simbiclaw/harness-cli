"""Acceptance tests for the local-model B-E refinement script (9003 M8).

RED phase: these tests fail until `scripts/befine.py` exists in the
rubric-compiler skill (import/exec error = the documented RED state).

Contract: B-E refinement is executed by the LOCAL model endpoint
(docs/references/ds4-flash-GUIDE.md — LiteLLM at 192.168.3.55:4000,
model deepseek-v4-flash, OpenAI-compatible chat completions), env-overridable
(LOCAL_MODEL_URL / LOCAL_MODEL_NAME / LOCAL_MODEL_API_KEY — the LOCAL id is deepseek-v4-flash-local; deepseek-v4-flash is NOT in the proxy's /v1/models list). HALT semantics:
an unreachable endpoint or malformed response exits 2 with a clear error and
leaves the node UNCHANGED — no fallback to the session model. Refined
signals replace every checkable-False fallback signal; decisions record the
model identity. Tests use a mock local HTTP server (hermetic, no LAN).
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import ClassVar

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "rubric-compiler"
BEFINE = SKILL_DIR / "scripts" / "befine.py"
RUNNER = SKILL_DIR / "scripts" / "run_compile.py"
PILOT = REPO_ROOT / "docs" / "exec-plans" / "active" / "9003-pilot-item18"


CANNED_REFINEMENT = {
    "fail": [
        {
            "id": "18-F1",
            "severity": "major",
            "description": "解释跳过关键步骤——坐席从问题陈述直接跳到解决方案，中间未出现诊断步骤",
            "decomposed_from": "fail_standard: 思路混乱、发散或完全无方向",
            "gate_checkable_test": {
                "proposer_can_find_span": "定位坐席解释话轮",
                "gate_can_verify": "检查 explanation_span 中 (诊断|原因|方案) 环节",
            },
            "checkable": True,
            "audit_result": "pass",
        }
    ],
    "excellence": [
        {
            "id": "18-E1",
            "severity": "minor",
            "description": "客户困惑后坐席改变了指导策略——从快速概述切换为逐步拆解",
            "decomposed_from": "pass_standard: 适时调整自己的说话方式、指导方法",
            "gate_checkable_test": {
                "proposer_can_find_span": "定位客户困惑时间戳",
                "gate_can_verify": "对比前后话轮 (word_count, technical_term_count)",
            },
            "checkable": False,
            "audit_result": "model_only",
        }
    ],
}


class MockLocalModel(BaseHTTPRequestHandler):
    """Canned OpenAI-compatible chat completions endpoint."""

    payload: ClassVar[str] = json.dumps(CANNED_REFINEMENT, ensure_ascii=False)
    payloads: ClassVar[list] = []  # queue; popped per request before payload
    status: ClassVar[int] = 200
    malformed: ClassVar[bool] = False
    received: ClassVar[dict] = {}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        MockLocalModel.received = body
        if MockLocalModel.payloads:
            content = MockLocalModel.payloads.pop(0)
        else:
            content = "not-json{{{" if MockLocalModel.malformed else MockLocalModel.payload
        response = {
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "model": "deepseek-v4-flash",
        }
        data = json.dumps(response, ensure_ascii=False).encode()
        self.send_response(MockLocalModel.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture()
def mock_model():
    MockLocalModel.malformed = False  # reset test-order pollution
    MockLocalModel.payloads = []  # reset retry queue
    server = HTTPServer(("127.0.0.1", 0), MockLocalModel)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _run_loop(out: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "loop",
            "--inputs",
            str(PILOT),
            "--out",
            str(out),
            "--no-epoch-commit",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
    )


def _befine(out: Path, url: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = {
        "LOCAL_MODEL_URL": url,
        "LOCAL_MODEL_NAME": "deepseek-v4-flash-local",
        "LOCAL_MODEL_API_KEY": "sk-test",
    }
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(BEFINE), "--out", str(out)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )


class TestBefineLocalModel:
    def test_replaces_fallbacks_via_local_model(self, tmp_path: Path, mock_model: str) -> None:
        _run_loop(tmp_path / "out")
        r = _befine(tmp_path / "out", mock_model)
        assert r.returncode == 0, r.stdout + r.stderr
        node = json.loads((tmp_path / "out" / "nodes" / "item-18.json").read_text())
        ids = {s["id"] for lane in ("fail", "excellence") for s in node["signals"][lane]}
        assert "18-F1" in ids and "18-E1" in ids, "refined signals must land in the node"
        assert not any(
            "unmatched standard" in s["description"]
            for lane in ("fail", "excellence")
            for s in node["signals"][lane]
        ), "fallbacks must be replaced"
        # the request must target the OpenAI chat endpoint with deterministic knobs
        req = MockLocalModel.received
        assert req["model"] == "deepseek-v4-flash-local", (
            "must call the LOCAL deployment id (privacy: LAN only)"
        )
        assert req.get("temperature") == 0, "B-E must run greedy for reproducibility"

    def test_default_model_is_the_local_deployment(self, tmp_path: Path, mock_model: str) -> None:
        """Without LOCAL_MODEL_NAME, the default must be deepseek-v4-flash-local
        (the LAN deployment) — never an ambiguous/cloud-routed id (privacy)."""
        _run_loop(tmp_path / "out")
        env = {"LOCAL_MODEL_URL": mock_model, "LOCAL_MODEL_API_KEY": "sk-test"}
        r = subprocess.run(
            [sys.executable, str(BEFINE), "--out", str(tmp_path / "out")],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env=env,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert MockLocalModel.received["model"] == "deepseek-v4-flash-local", (
            f"default must be the LOCAL deployment id, got {MockLocalModel.received['model']}"
        )

    def test_halts_when_endpoint_unreachable(self, tmp_path: Path) -> None:
        _run_loop(tmp_path / "out")
        before = (tmp_path / "out" / "nodes" / "item-18.json").read_text()
        r = _befine(tmp_path / "out", "http://127.0.0.1:1")  # closed port
        assert r.returncode == 2, f"must halt, got {r.returncode}"
        assert (
            "LOCAL_MODEL" in (r.stdout + r.stderr).upper()
            or "unreachable" in (r.stdout + r.stderr).lower()
        )
        after = (tmp_path / "out" / "nodes" / "item-18.json").read_text()
        assert before == after, "node must be UNCHANGED on halt (no fallback)"

    def test_halts_on_malformed_response(self, tmp_path: Path, mock_model: str) -> None:
        _run_loop(tmp_path / "out")
        MockLocalModel.malformed = True
        r = _befine(tmp_path / "out", mock_model)
        assert r.returncode == 2, f"malformed response must halt, got {r.returncode}"

    def test_parses_fenced_json(self, tmp_path: Path, mock_model: str) -> None:
        """Models commonly wrap JSON in markdown fences — the script must strip
        ```json fences before parsing (live finding: ds4-flash may fence)."""
        _run_loop(tmp_path / "out")
        MockLocalModel.payload = (
            "```json\n" + json.dumps(CANNED_REFINEMENT, ensure_ascii=False) + "\n```"
        )
        r = _befine(tmp_path / "out", mock_model)
        assert r.returncode == 0, r.stdout + r.stderr
        node = json.loads((tmp_path / "out" / "nodes" / "item-18.json").read_text())
        ids = {s["id"] for lane in ("fail", "excellence") for s in node["signals"][lane]}
        assert "18-F1" in ids, "fenced JSON must still be parsed"

    def test_repairs_missing_field_then_succeeds(self, tmp_path: Path, mock_model: str) -> None:
        """GAN repair round: a response missing a required field is rejected and
        re-requested with the error fed back; the second attempt succeeds."""
        _run_loop(tmp_path / "out")
        bad = json.loads(json.dumps(CANNED_REFINEMENT))
        del bad["fail"][0]["decomposed_from"]  # missing required field
        MockLocalModel.payloads = [json.dumps(bad, ensure_ascii=False)]
        r = _befine(tmp_path / "out", mock_model)
        assert r.returncode == 0, r.stdout + r.stderr
        node = json.loads((tmp_path / "out" / "nodes" / "item-18.json").read_text())
        ids = {s["id"] for lane in ("fail", "excellence") for s in node["signals"][lane]}
        assert "18-F1" in ids, "repair round must land the refined signals"
        decisions = [
            json.loads(line)
            for line in (tmp_path / "out" / "compile-decisions.jsonl").read_text().splitlines()
            if line.strip()
        ]
        repairs = [d for d in decisions if d.get("step") == "b-e-repair"]
        assert repairs, "the repair round must be recorded in decisions"

    def test_retries_empty_response_then_succeeds(self, tmp_path: Path, mock_model: str) -> None:
        """An EMPTY content (transient server behavior) is repairable — one retry
        succeeds; non-empty garbage still halts immediately (existing test)."""
        _run_loop(tmp_path / "out")
        MockLocalModel.payloads = ["", json.dumps(CANNED_REFINEMENT, ensure_ascii=False)]
        r = _befine(tmp_path / "out", mock_model)
        assert r.returncode == 0, r.stdout + r.stderr
        node = json.loads((tmp_path / "out" / "nodes" / "item-18.json").read_text())
        ids = {s["id"] for lane in ("fail", "excellence") for s in node["signals"][lane]}
        assert "18-F1" in ids, "retry after empty response must land the signals"
        decisions = [
            json.loads(line)
            for line in (tmp_path / "out" / "compile-decisions.jsonl").read_text().splitlines()
            if line.strip()
        ]
        assert any(d.get("step") == "b-e-repair" for d in decisions), (
            "empty-response retry must be recorded"
        )

    def test_repairs_auth1_finding_then_succeeds(self, tmp_path: Path, mock_model: str) -> None:
        """GAN Evaluator→Generator feedback: a refined signal carrying an
        evaluative adjective (AUTH-1) is fed back to the model for repair."""
        _run_loop(tmp_path / "out")
        bad = json.loads(json.dumps(CANNED_REFINEMENT))
        bad["excellence"][0]["description"] = "agent is proactive and flexible in adapting guidance"
        MockLocalModel.payloads = [json.dumps(bad, ensure_ascii=False)]
        r = _befine(tmp_path / "out", mock_model)
        assert r.returncode == 0, r.stdout + r.stderr
        node = json.loads((tmp_path / "out" / "nodes" / "item-18.json").read_text())
        desc = next(s["description"] for s in node["signals"]["excellence"] if s["id"] == "18-E1")
        assert "proactive" not in desc.lower() and "flexible" not in desc.lower(), (
            "AUTH-1 finding must be repaired, got: " + desc
        )
        decisions = [
            json.loads(line)
            for line in (tmp_path / "out" / "compile-decisions.jsonl").read_text().splitlines()
            if line.strip()
        ]
        assert any(
            "AUTH-1" in d.get("rationale", "") for d in decisions if d.get("step") == "b-e-repair"
        )

    def test_halts_on_persistent_auth1(self, tmp_path: Path, mock_model: str) -> None:
        _run_loop(tmp_path / "out")
        bad = json.loads(json.dumps(CANNED_REFINEMENT))
        bad["excellence"][0]["description"] = "agent is proactive and flexible in adapting guidance"
        MockLocalModel.payloads = [json.dumps(bad, ensure_ascii=False)] * 5
        before = (tmp_path / "out" / "nodes" / "item-18.json").read_text()
        r = _befine(tmp_path / "out", mock_model)
        assert r.returncode == 2, "persistent AUTH-1 findings must halt"
        after = (tmp_path / "out" / "nodes" / "item-18.json").read_text()
        assert before == after

    def test_halts_on_persistent_empty(self, tmp_path: Path, mock_model: str) -> None:
        _run_loop(tmp_path / "out")
        MockLocalModel.payloads = [""] * 5
        before = (tmp_path / "out" / "nodes" / "item-18.json").read_text()
        r = _befine(tmp_path / "out", mock_model)
        assert r.returncode == 2, "persistent empty responses must halt"
        after = (tmp_path / "out" / "nodes" / "item-18.json").read_text()
        assert before == after

    def test_halts_after_repair_exhausted(self, tmp_path: Path, mock_model: str) -> None:
        """Persistent missing fields halt after the retry budget — node unchanged."""
        _run_loop(tmp_path / "out")
        bad = json.loads(json.dumps(CANNED_REFINEMENT))
        del bad["fail"][0]["decomposed_from"]
        MockLocalModel.payloads = [json.dumps(bad, ensure_ascii=False)] * 5  # exhaust retries
        before = (tmp_path / "out" / "nodes" / "item-18.json").read_text()
        r = _befine(tmp_path / "out", mock_model)
        assert r.returncode == 2, f"must halt after retries, got {r.returncode}"
        after = (tmp_path / "out" / "nodes" / "item-18.json").read_text()
        assert before == after, "node must be UNCHANGED on exhausted repair"

    def test_records_model_identity(self, tmp_path: Path, mock_model: str) -> None:
        _run_loop(tmp_path / "out")
        r = _befine(tmp_path / "out", mock_model)
        assert r.returncode == 0
        decisions = [
            json.loads(line)
            for line in (tmp_path / "out" / "compile-decisions.jsonl").read_text().splitlines()
            if line.strip()
        ]
        refined = [d for d in decisions if d.get("step") == "b-e-refine"]
        assert refined and all(d.get("model") == "deepseek-v4-flash-local" for d in refined), (
            "decisions must record the model identity"
        )
