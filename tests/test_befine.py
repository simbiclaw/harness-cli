"""Acceptance tests for the local-model B-E refinement script (9003 M8).

RED phase: these tests fail until `scripts/befine.py` exists in the
rubric-compiler skill (import/exec error = the documented RED state).

Contract: B-E refinement is executed by the LOCAL model endpoint
(docs/references/ds4-flash-GUIDE.md — LiteLLM at 192.168.3.55:4000,
model deepseek-v4-flash, OpenAI-compatible chat completions), env-overridable
(LOCAL_MODEL_URL / LOCAL_MODEL_NAME / LOCAL_MODEL_API_KEY). HALT semantics:
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
            "id": "18-F1", "severity": "major",
            "description": "解释跳过关键步骤——坐席从问题陈述直接跳到解决方案，中间未出现诊断步骤",
            "decomposed_from": "fail_standard: 思路混乱、发散或完全无方向",
            "gate_checkable_test": {"proposer_can_find_span": "定位坐席解释话轮",
                                    "gate_can_verify": "检查 explanation_span 中 (诊断|原因|方案) 环节"},
            "checkable": True, "audit_result": "pass",
        }
    ],
    "excellence": [
        {
            "id": "18-E1", "severity": "minor",
            "description": "客户困惑后坐席改变了指导策略——从快速概述切换为逐步拆解",
            "decomposed_from": "pass_standard: 适时调整自己的说话方式、指导方法",
            "gate_checkable_test": {"proposer_can_find_span": "定位客户困惑时间戳",
                                    "gate_can_verify": "对比前后话轮 (word_count, technical_term_count)"},
            "checkable": False, "audit_result": "model_only",
        }
    ],
}


class MockLocalModel(BaseHTTPRequestHandler):
    """Canned OpenAI-compatible chat completions endpoint."""

    payload: ClassVar[str] = json.dumps(CANNED_REFINEMENT, ensure_ascii=False)
    status: ClassVar[int] = 200
    malformed: ClassVar[bool] = False
    received: ClassVar[dict] = {}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        MockLocalModel.received = body
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
    server = HTTPServer(("127.0.0.1", 0), MockLocalModel)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _run_loop(out: Path) -> None:
    subprocess.run(
        [sys.executable, str(RUNNER), "loop", "--inputs", str(PILOT), "--out", str(out),
         "--no-epoch-commit"],
        capture_output=True, text=True, cwd=REPO_ROOT, check=True,
    )


def _befine(out: Path, url: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = {"LOCAL_MODEL_URL": url, "LOCAL_MODEL_NAME": "deepseek-v4-flash",
           "LOCAL_MODEL_API_KEY": "sk-test"}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(BEFINE), "--out", str(out)],
        capture_output=True, text=True, cwd=REPO_ROOT, env=env,
    )


class TestBefineLocalModel:
    def test_replaces_fallbacks_via_local_model(self, tmp_path: Path, mock_model: str) -> None:
        _run_loop(tmp_path / "out")
        r = _befine(tmp_path / "out", mock_model)
        assert r.returncode == 0, r.stdout + r.stderr
        node = json.loads((tmp_path / "out" / "nodes" / "item-18.json").read_text())
        ids = {s["id"] for lane in ("fail", "excellence") for s in node["signals"][lane]}
        assert "18-F1" in ids and "18-E1" in ids, "refined signals must land in the node"
        assert not any("unmatched standard" in s["description"] for lane in ("fail", "excellence")
                       for s in node["signals"][lane]), "fallbacks must be replaced"
        # the request must target the OpenAI chat endpoint with deterministic knobs
        req = MockLocalModel.received
        assert req["model"] == "deepseek-v4-flash"
        assert req.get("temperature") == 0, "B-E must run greedy for reproducibility"

    def test_halts_when_endpoint_unreachable(self, tmp_path: Path) -> None:
        _run_loop(tmp_path / "out")
        before = (tmp_path / "out" / "nodes" / "item-18.json").read_text()
        r = _befine(tmp_path / "out", "http://127.0.0.1:1")  # closed port
        assert r.returncode == 2, f"must halt, got {r.returncode}"
        assert "LOCAL_MODEL" in (r.stdout + r.stderr).upper() or "unreachable" in (r.stdout + r.stderr).lower()
        after = (tmp_path / "out" / "nodes" / "item-18.json").read_text()
        assert before == after, "node must be UNCHANGED on halt (no fallback)"

    def test_halts_on_malformed_response(self, tmp_path: Path, mock_model: str) -> None:
        _run_loop(tmp_path / "out")
        MockLocalModel.malformed = True
        r = _befine(tmp_path / "out", mock_model)
        assert r.returncode == 2, f"malformed response must halt, got {r.returncode}"

    def test_records_model_identity(self, tmp_path: Path, mock_model: str) -> None:
        _run_loop(tmp_path / "out")
        r = _befine(tmp_path / "out", mock_model)
        assert r.returncode == 0
        decisions = [json.loads(line) for line in (tmp_path / "out" / "compile-decisions.jsonl").read_text().splitlines()
                     if line.strip()]
        refined = [d for d in decisions if d.get("step") == "b-e-refine"]
        assert refined and all(d.get("model") == "deepseek-v4-flash" for d in refined), (
            "decisions must record the model identity"
        )
