"""M6a acceptance tests — rubric-compiler skill (9003).

Gated on M1–M5 via `pytest.importorskip`: until `argus.core.compiler` lands,
these tests SKIP (CI stays green) — that is the documented M6a test-first
RED. When the core lands they auto-activate and exercise the real validator.

Tests drive the runner headlessly with `--evaluator mock` (deterministic,
byte-reproducible) and always stage output to a pytest tmp_path — they never
write through the INTENTS symlink.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("argus.core.compiler")  # M6a Requires: M5 — skip until core lands
from argus.core.compiler.validator import validate_node
from argus.types.compiler_schemas import AuthoredNode

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "rubric-compiler"
RUNNER = SKILL_DIR / "scripts" / "run_compile.py"
FIXTURES = SKILL_DIR / "fixtures"


def _run_loop(tmp_path: Path, inputs: Path | None = None) -> tuple[subprocess.CompletedProcess, Path]:
    """Drive the runner's mock loop headlessly; return (result, staging dir)."""
    if inputs is None:
        inputs = FIXTURES
    out = tmp_path / "out"
    cmd = [
        sys.executable,
        str(RUNNER),
        "loop",
        "--inputs", str(inputs),
        "--evaluator", "mock",
        "--out", str(out),
        "--no-epoch-commit",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    return result, out


def _emitted_nodes(out: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted((out / "nodes").glob("item-*.json"))]


def test_skill_loop_output_passes_validator(tmp_path: Path) -> None:
    result, out = _run_loop(tmp_path)

    # The loop completes and freezes the full output contract.
    assert result.returncode == 0, result.stdout + result.stderr
    nodes = _emitted_nodes(out)
    assert len(nodes) == 6, "6 items compile; item 24 is a coverage gap (no node)"
    assert (out / "tree" / "_rubric" / "gates").is_dir()
    assert (out / "tree" / "_meta" / "residue-manifest.yaml").exists()

    # (a) every emitted node parses and validates as AuthoredNode
    for raw in nodes:
        AuthoredNode(**raw)

    # (b) every node passes the full M1 validator
    for raw in nodes:
        assert validate_node(AuthoredNode(**raw)) == [], f"validator findings on {raw['node_id']}"

    # (c) Item 21's depends_on resolves to Item 20's emitted signal IDs (S3 order)
    item20 = next(n for n in nodes if n["node_id"] == "item-20")
    item21 = next(n for n in nodes if n["node_id"] == "item-21")
    item20_signal_ids = {s["id"] for s in item20["signals"]["fail"]}
    assert item21["depends_on"] == ["20"]
    refs = set(item21["applicability_gate"]["refs"])
    assert refs and refs <= item20_signal_ids, f"Item 21 gate refs {refs} not in Item 20 signals {item20_signal_ids}"

    # (d) residue manifest present with the dimension_coverage_gap row (AUTH-5)
    manifest = json.loads((out / "tree" / "_meta" / "residue-manifest.yaml").read_text())
    gap_rows = [r for r in manifest["rows"] if r["kind"] == "dimension_coverage_gap"]
    assert any("24" in r["source_items"] for r in gap_rows)

    # (e) every model-judged step has a recorded decision line
    decisions = [json.loads(l) for l in (out / "compile-decisions.jsonl").read_text().splitlines() if l.strip()]
    assert decisions, "compile-decisions.jsonl must not be empty"
    assert all(d.get("step") and d.get("rationale") for d in decisions)


def test_skill_halt_on_source_conflict(tmp_path: Path) -> None:
    # Build a conflict inputs dir: valid rubric/skill/align + the CONFLICTING companion variant.
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    for f in ("specific-rubric.yaml", "generic-skill.yaml", "align.md"):
        shutil.copy(FIXTURES / f, inputs / f)
    shutil.copytree(FIXTURES / "companions-conflict", inputs / "companions")

    result, out = _run_loop(tmp_path, inputs=inputs)

    # S2: halt with a conflict report, zero nodes emitted.
    assert result.returncode == 2, result.stdout + result.stderr
    report = out / "conflict-report.yaml"
    assert report.exists()
    text = report.read_text()
    assert "T001" in text and "CONFLICT" in text
    assert not (out / "nodes").exists() or not list((out / "nodes").glob("item-*.json")), "no nodes may be emitted"
