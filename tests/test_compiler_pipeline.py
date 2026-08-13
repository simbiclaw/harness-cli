"""M6a acceptance tests — rubric-compiler skill (9003).

Gated on M1-M5 via `pytest.importorskip`: until `argus.core.compiler` lands,
these tests SKIP (CI stays green) — that is the documented M6a test-first
RED. When the core lands they auto-activate and exercise the real validator.

Tests drive the runner headlessly with `--evaluator mock` (deterministic,
byte-reproducible) and always stage output to a pytest tmp_path — they never
write through the INTENTS symlink.
"""

import json
import os
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
    decisions = [json.loads(line) for line in (out / "compile-decisions.jsonl").read_text().splitlines() if line.strip()]
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


def test_runner_uses_core_chain(tmp_path: Path) -> None:
    """M6a rewire contract (round-3 decision 1): the runner's emitted nodes must
    BE the M1-M5 pure-core derivation, not the template path. RED until rewired."""
    import yaml

    from argus.core.compiler.agreement import seed_agreement_gate
    from argus.core.compiler.classify import classify_gap, declare_residue
    from argus.core.compiler.signals import assign_facets, decompose_signals

    result, out = _run_loop(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr

    rubric = yaml.safe_load((FIXTURES / "specific-rubric.yaml").read_text())
    item22 = next(it for it in rubric["items"] if it["id"] == "22")
    signals = decompose_signals(item22)
    gap = classify_gap(item22, "empathy_and_tone", signals)
    facets = assign_facets(signals, gap["gap_type"])
    residue = declare_residue(signals, "empathy_and_tone")
    agreement = seed_agreement_gate({"id": "C22"})

    emitted = json.loads((out / "nodes" / "item-22.json").read_text())
    assert emitted["signals"]["fail"] == signals["fail"], "signals must come from decompose_signals (M2)"
    assert emitted["signals"]["excellence"] == signals["excellence"]
    assert emitted["gap_type"] == gap["gap_type"], "gap must come from classify_gap (M3)"
    assert emitted["facets"] == facets, "facets must come from assign_facets (M2)"
    assert emitted["residue_declared"] == residue, "residue must come from declare_residue (M3)"
    assert emitted["agreement"] == agreement, "agreement must come from seed_agreement_gate (M4)"


def test_gap_row_carries_data_dependency(tmp_path: Path) -> None:
    """M5 drift closure: the coverage-gap row must carry the core's data_dependency."""
    result, out = _run_loop(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((out / "tree" / "_meta" / "residue-manifest.yaml").read_text())
    gap_row = next(r for r in manifest["rows"] if r["kind"] == "dimension_coverage_gap")
    assert gap_row["data_dependency"] == {
        "connected": False,
        "disposition": "defer_until_source_connected",
    }, "gap row must carry the check_dimension_coverage (M5) data_dependency"


# ── B-verification fix round (2026-08-12): B1/B2/W2/W3 ──────────────────────


def _run_runner_args(args: list[str], tmp_path: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )


class TestBFixRound:
    """Findings B1/B2/W2/W3 closed with red tests. RED phase."""

    # B1: the M6a Requires: M5 gate must apply to BOTH evaluator modes
    def test_b1_mock_mode_gates_on_missing_core(self, tmp_path: Path) -> None:
        shim = tmp_path / "shim" / "argus"
        shim.mkdir(parents=True)
        (shim / "__init__.py").write_text("")  # shadows the real argus: core missing
        env = {**os.environ, "PYTHONPATH": str(tmp_path / "shim")}
        for mode in ("mock", "real"):
            r = _run_runner_args(
                ["loop", "--inputs", str(FIXTURES), "--evaluator", mode,
                 "--out", str(tmp_path / f"out-{mode}"), "--no-epoch-commit"],
                tmp_path, env=env,
            )
            assert r.returncode == 2, f"{mode}: expected exit 2, got {r.returncode}"
            assert "Requires: M5" in r.stdout + r.stderr, f"{mode}: remediation message missing"
            assert "Traceback" not in r.stdout + r.stderr, f"{mode}: traceback must not leak"

    # B2: garbage inputs / read-only out → clean exit 2, no traceback
    def test_b2_garbage_inputs_clean_exit(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad-inputs"
        bad.mkdir()
        # missing specific-rubric.yaml
        r = _run_runner_args(
            ["loop", "--inputs", str(bad), "--out", str(tmp_path / "o1"), "--no-epoch-commit"], tmp_path
        )
        assert r.returncode == 2 and "Traceback" not in r.stdout + r.stderr, "missing input must exit clean"
        # malformed YAML
        (bad / "specific-rubric.yaml").write_text("::: not yaml :::")
        (bad / "generic-skill.yaml").write_text("x: 1")
        (bad / "align.md").write_text("")
        r = _run_runner_args(
            ["loop", "--inputs", str(bad), "--out", str(tmp_path / "o2"), "--no-epoch-commit"], tmp_path
        )
        assert r.returncode == 2 and "Traceback" not in r.stdout + r.stderr, "malformed yaml must exit clean"
        # read-only out dir
        ro = tmp_path / "ro"
        ro.mkdir()
        ro.chmod(0o555)
        try:
            r = _run_runner_args(
                ["loop", "--inputs", str(FIXTURES), "--out", str(ro), "--no-epoch-commit"], tmp_path
            )
            assert r.returncode == 2 and "Traceback" not in r.stdout + r.stderr, "read-only out must exit clean"
        finally:
            ro.chmod(0o755)

    # W2: a targeted fix must recompute audit_result + checkable (B4 invariant)
    def test_w2_fix_recomputes_audit(self, tmp_path: Path) -> None:
        from argus.core.compiler.signals import audit_gate_checkable

        result, out = _run_loop(tmp_path)
        assert result.returncode == 0
        fix = json.dumps(
            {"signal_id": "22-S01", "field": "description", "issue": "x",
             "suggested_fix": "agent's emotional handling quality"}
        )
        r = _run_runner_args(
            ["generate", "--inputs", str(FIXTURES), "--out", str(out), "--item", "22", "--fix", fix], tmp_path
        )
        assert r.returncode == 0, r.stdout + r.stderr
        node = json.loads((out / "nodes" / "item-22.json").read_text())
        sig = node["signals"]["fail"][0]
        assert sig["audit_result"] == audit_gate_checkable(sig), "fix must recompute audit_result"
        assert sig["checkable"] == (sig["audit_result"] != "model_only"), "checkable must follow the audit"

    # W3: re-running into the same out dir must not duplicate gap rows
    def test_w3_rerun_same_out_no_duplicate_rows(self, tmp_path: Path) -> None:
        result, out = _run_loop(tmp_path)
        assert result.returncode == 0
        result2, _ = _run_loop(tmp_path)
        assert result2.returncode == 0
        manifest = json.loads((out / "tree" / "_meta" / "residue-manifest.yaml").read_text())
        gap_rows = [r for r in manifest["rows"] if r["kind"] == "dimension_coverage_gap"]
        assert len(gap_rows) == 1, "re-running into the same out dir must not duplicate gap rows"


class TestB2FixRound:
    """Findings F1-F7 closed with red tests. RED phase."""

    # F1: malformed --fix JSON must exit clean, never traceback
    def test_f1_malformed_fix_json_clean_exit(self, tmp_path: Path) -> None:
        result, out = _run_loop(tmp_path)
        assert result.returncode == 0
        for fix in ('{"signal_id": "21-S01", field: description}', "[1,2,3]"):
            r = _run_runner_args(
                ["generate", "--inputs", str(FIXTURES), "--out", str(out), "--item", "21", "--fix", fix], tmp_path
            )
            assert r.returncode == 2, f"fix {fix!r}: expected exit 2, got {r.returncode}"
            assert "Traceback" not in r.stdout + r.stderr, f"fix {fix!r}: traceback leaked"

    # F2: standalone generate/evaluate gate on the core too
    def test_f2_standalone_commands_gate_on_core(self, tmp_path: Path) -> None:
        shim = tmp_path / "shim" / "argus"
        shim.mkdir(parents=True)
        (shim / "__init__.py").write_text("")
        env = {**os.environ, "PYTHONPATH": str(tmp_path / "shim")}
        result, out = _run_loop(tmp_path)  # real core: produce a plan+node first
        assert result.returncode == 0
        for cmd in (["generate", "--item", "01"], ["evaluate"]):
            r = _run_runner_args(
                [*cmd, "--inputs", str(FIXTURES), "--out", str(out)], tmp_path, env=env
            )
            assert r.returncode == 2, f"{cmd}: expected exit 2 without core, got {r.returncode}"
            assert "Requires: M5" in r.stdout + r.stderr
            assert "Traceback" not in r.stdout + r.stderr

    # F3: the default fixtures path must resolve (REPO_ROOT off-by-one)
    def test_f3_default_fixtures_resolve(self, tmp_path: Path) -> None:
        r = _run_runner_args(
            ["loop", "--out", str(tmp_path / "out"), "--no-epoch-commit"], tmp_path
        )
        assert r.returncode == 0, f"default fixtures must resolve: {r.stdout + r.stderr}"

    # F5: --fix with an unknown signal id must error, not silently no-op
    def test_f5_unknown_signal_id_errors(self, tmp_path: Path) -> None:
        result, out = _run_loop(tmp_path)
        assert result.returncode == 0
        fix = json.dumps({"signal_id": "99-S99", "field": "description", "issue": "x", "suggested_fix": "y"})
        r = _run_runner_args(
            ["generate", "--inputs", str(FIXTURES), "--out", str(out), "--item", "21", "--fix", fix], tmp_path
        )
        assert r.returncode == 2, "unknown signal id must error"
        assert "99-S99" in r.stdout + r.stderr

    # F6: standalone generate on the coverage-gap item must not duplicate rows
    def test_f6_standalone_generate_no_duplicate_rows(self, tmp_path: Path) -> None:
        result, out = _run_loop(tmp_path)
        assert result.returncode == 0
        for _ in range(2):
            r = _run_runner_args(
                ["generate", "--inputs", str(FIXTURES), "--out", str(out), "--item", "24"], tmp_path
            )
            assert r.returncode == 0
        rows = [json.loads(line) for line in (out / "coverage-gaps.jsonl").read_text().splitlines() if line.strip()]
        assert len(rows) == 1, "standalone generate on item 24 must not duplicate gap rows"

    # Epoch activation (round-3 decision 3): nodes pin the external tree's
    # real HEAD SHA (I4), never the zero placeholder.
    def test_runner_stamps_real_intents_sha(self, tmp_path: Path) -> None:
        tree = REPO_ROOT / "INTENTS"
        if not (tree.is_symlink() and tree.exists()):
            pytest.skip("external INTENTS tree not present")
        resolved = tree.resolve()
        # I4: the pin is the epoch DECLARED by the tree's EPOCH.yaml — the
        # single source of truth — not the raw git HEAD (which may be a
        # metadata stamp commit on top of the content baseline).
        import yaml

        epoch_declared = yaml.safe_load((resolved / "EPOCH.yaml").read_text())["epoch"]
        assert epoch_declared and "0000000000000000000000000000000000000000" not in epoch_declared

        result, out = _run_loop(tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
        for raw in _emitted_nodes(out):
            assert raw["intents_sha"] == epoch_declared, (
                f"{raw['node_id']} must pin the EPOCH.yaml-declared epoch, got {raw['intents_sha']}"
            )
        manifest = json.loads((out / "tree" / "_meta" / "residue-manifest.yaml").read_text())
        assert manifest["compiler_epoch"] == epoch_declared, "compiler_epoch must be the declared epoch"


class TestBFixRound2:
    # F7: evaluate on an out dir with no nodes must not report CONFIRMED
    def test_f7_evaluate_empty_run_exits_2(self, tmp_path: Path) -> None:
        r = _run_runner_args(
            ["plan", "--inputs", str(FIXTURES), "--out", str(tmp_path / "out")], tmp_path
        )
        assert r.returncode == 0
        r = _run_runner_args(["evaluate", "--out", str(tmp_path / "out")], tmp_path)
        assert r.returncode == 2, "evaluate with zero nodes must not report CONFIRMED"
