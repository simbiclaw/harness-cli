"""Acceptance tests for M7 — Calibration manifest channel (9003).

RED phase: these tests fail until `src/argus/io/calibration_io.py` and the
`manifest inject` runner subcommand are implemented (import error = the
documented RED state; committed only when green).

Independent channel (round-3 Q8): the manifest is NOT a compiler input — it is
injected alone; severity_map refs re-anchor to the new epoch; AUTH-9 coverage
re-evaluated; signals/corroborators/agreement NEVER recompiled.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from argus.io.calibration_io import (  # noqa: F401  (RED until M7 lands)
    apply_manifest_epoch,
    load_manifest,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "rubric-compiler"
RUNNER = SKILL_DIR / "scripts" / "run_compile.py"
FIXTURES = SKILL_DIR / "fixtures"

EPOCH_1 = "2026-08-12-0123456789abcdef0123456789abcdef01234567"
EPOCH_2 = "2026-08-13-cdef0123456789abcdef0123456789abcdef01ab"


def _run_loop(tmp_path: Path) -> tuple[subprocess.CompletedProcess, Path]:
    out = tmp_path / "out"
    cmd = [
        sys.executable,
        str(RUNNER),
        "loop",
        "--inputs",
        str(FIXTURES),
        "--evaluator",
        "mock",
        "--out",
        str(out),
        "--no-epoch-commit",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    return result, out


def _node(out: Path, item_id: str) -> dict:
    return json.loads((out / "nodes" / f"item-{item_id}.json").read_text())


def _write_manifest(
    tmp_path: Path, epoch: str, fragments: list[dict], name: str | None = None
) -> Path:
    manifest = {
        "epoch_id": epoch,
        "fragments": fragments,
        "source_case_refs": [f["source_case"] for f in fragments],
        "distribution": {"danger_zone_ratio": 2},
    }
    path = tmp_path / (name or f"calibration-manifest.{epoch}.yaml")
    import yaml

    path.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True))
    return path


def _inject(tmp_path: Path, out: Path, manifest_file: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUNNER), "manifest", "inject", str(manifest_file), "--out", str(out)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


class TestManifestInjection:
    def test_manifest_injection_reanchors_severity(self, tmp_path: Path) -> None:
        """severity_map refs update to the new epoch; signals unchanged."""
        result, out = _run_loop(tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
        before = _node(out, "22")
        signals_before = json.dumps(before["signals"], sort_keys=True)

        manifest_file = _write_manifest(tmp_path, EPOCH_2, [])
        r = _inject(tmp_path, out, manifest_file)
        assert r.returncode == 0, r.stdout + r.stderr

        after = _node(out, "22")
        assert after["severity_map"] == f"calibration://manifest/{EPOCH_2}/severity/22"
        assert json.dumps(after["signals"], sort_keys=True) == signals_before, (
            "signals must be unchanged"
        )

    def test_auth9_reevaluated_on_injection(self, tmp_path: Path) -> None:
        """A surface-form node deferred by AUTH-9 gains auto-final when the
        manifest covers its failure surface."""
        result, out = _run_loop(tmp_path)
        assert result.returncode == 0
        before = _node(out, "21")
        assert before["machine_criterion"]["auto_final_allowed"] is False, (
            "fixture starts deferred (AUTH-9)"
        )

        manifest_file = _write_manifest(
            tmp_path,
            EPOCH_2,
            [
                {
                    "fragment_id": "frag-001",
                    "source_case": "errors.case-0042.yaml",
                    "transcript_span": {"start": 1, "end": 2},
                    "human_score": 3,
                    "affected_criterion": "21",
                    "failure_surface": "generic recommendation",
                    "severity_anchor": "emp-sev-v3:low",
                }
            ],
        )
        r = _inject(tmp_path, out, manifest_file)
        assert r.returncode == 0, r.stdout + r.stderr

        after = _node(out, "21")
        assert after["machine_criterion"]["auto_final_allowed"] is True, (
            "AUTH-9 coverage grants auto-final"
        )

    def test_manifest_injection_no_recompile(self, tmp_path: Path) -> None:
        """Injection changes only severity_map + auto_final — never signals,
        corroborators, or agreement blocks."""
        result, out = _run_loop(tmp_path)
        assert result.returncode == 0
        before = _node(out, "20")
        manifest_file = _write_manifest(tmp_path, EPOCH_2, [])
        r = _inject(tmp_path, out, manifest_file)
        assert r.returncode == 0
        after = _node(out, "20")
        for field in (
            "signals",
            "facets",
            "corroborators",
            "agreement",
            "residue_declared",
            "gap_type",
        ):
            assert before[field] == after[field], f"{field} must be untouched by injection"

    def test_manifest_epoch_independent_of_rule_epoch(self, tmp_path: Path) -> None:
        """Manifest epochs advance independently; rule epochs unchanged."""
        result, out = _run_loop(tmp_path)
        assert result.returncode == 0
        before = _node(out, "22")
        _write_manifest(tmp_path, EPOCH_1, [])
        r1 = _inject(tmp_path, out, _write_manifest(tmp_path, EPOCH_1, []))
        assert r1.returncode == 0
        mid = _node(out, "22")
        assert mid["severity_map"] == f"calibration://manifest/{EPOCH_1}/severity/22"
        r2 = _inject(tmp_path, out, _write_manifest(tmp_path, EPOCH_2, []))
        assert r2.returncode == 0
        after = _node(out, "22")
        assert after["severity_map"] == f"calibration://manifest/{EPOCH_2}/severity/22"
        for field in ("intents_sha", "signals", "agreement", "gap_type", "escape_tier"):
            assert after[field] == before[field], f"{field} must not change with the manifest epoch"


class TestManifestLoader:
    def test_loader_validates_source_case_grammar(self, tmp_path: Path) -> None:
        """source_case refs must match conventions.yaml grammar — structural only,
        never existence-checked (the libraries are empty)."""
        ok = _write_manifest(
            tmp_path,
            EPOCH_1,
            [
                {
                    "fragment_id": "f1",
                    "source_case": "cookbook.empathy.yaml",
                    "transcript_span": {},
                    "human_score": 4,
                    "affected_criterion": "22",
                    "failure_surface": "x",
                    "severity_anchor": "s",
                }
            ],
            name=f"calibration-manifest.{EPOCH_1}.yaml",
        )
        manifest = load_manifest(ok)
        assert manifest.epoch_id == EPOCH_1
        assert manifest.fragments[0].source_case == "cookbook.empathy.yaml"
        # never existence-checked: the referenced library file does not exist, yet loads fine

    def test_loader_rejects_non_grammar_source_case(self, tmp_path: Path) -> None:
        bad = _write_manifest(
            tmp_path,
            EPOCH_1,
            [
                {
                    "fragment_id": "f1",
                    "source_case": "bestpractice.txt",
                    "transcript_span": {},
                    "human_score": 4,
                    "affected_criterion": "22",
                    "failure_surface": "x",
                    "severity_anchor": "s",
                }
            ],
            name="calibration-manifest.bad.yaml",
        )
        with pytest.raises(Exception):
            load_manifest(bad)

    def test_loader_epoch_file_alignment(self, tmp_path: Path) -> None:
        """The manifest file's epoch must match its epoch_id (round-3 Q8: URI refs
        align with the manifest file's epoch)."""
        misaligned = _write_manifest(
            tmp_path,
            EPOCH_2,
            [],
            name="calibration-manifest.2026-08-11-0000000000000000000000000000000000000000.yaml",
        )
        with pytest.raises(Exception):
            load_manifest(misaligned)

    def test_loader_malformed_no_crash(self, tmp_path: Path) -> None:
        garbage = tmp_path / "calibration-manifest.garbage.yaml"
        garbage.write_text("::: not yaml :::")
        with pytest.raises(Exception):
            load_manifest(garbage)


# ── B-verification fix round (2026-08-12): F1/F2/F3 ─────────────────────────


class TestBFixRound:
    """Findings F1-F3 closed with red tests. RED phase."""

    # F1: AUTH-9 must be re-evaluated in BOTH directions — a regression to a
    # non-covering manifest must REVOKE auto-final, never leave a stale grant.
    def test_f1_auth9_revoked_on_regression(self, tmp_path: Path) -> None:
        result, out = _run_loop(tmp_path)
        assert result.returncode == 0
        covering = _write_manifest(
            tmp_path,
            EPOCH_2,
            [
                {
                    "fragment_id": "frag-001",
                    "source_case": "errors.case-0042.yaml",
                    "transcript_span": {"start": 1, "end": 2},
                    "human_score": 3,
                    "affected_criterion": "21",
                    "failure_surface": "generic recommendation",
                    "severity_anchor": "emp-sev-v3:low",
                }
            ],
        )
        assert _inject(tmp_path, out, covering).returncode == 0
        assert _node(out, "21")["machine_criterion"]["auto_final_allowed"] is True

        # EPOCH_1 covers only criterion 26 — criterion 21 must LOSE auto-final
        non_covering = _write_manifest(
            tmp_path,
            EPOCH_1,
            [
                {
                    "fragment_id": "frag-002",
                    "source_case": "cookbook.empathy.yaml",
                    "transcript_span": {"start": 1, "end": 2},
                    "human_score": 4,
                    "affected_criterion": "26",
                    "failure_surface": "empathy",
                    "severity_anchor": "emp-sev-v3:mid",
                }
            ],
        )
        assert _inject(tmp_path, out, non_covering).returncode == 0
        after = _node(out, "21")
        assert after["machine_criterion"]["auto_final_allowed"] is False, (
            "AUTH-9 grant must be revoked when the manifest no longer covers the criterion"
        )

    # F2: a file name whose epoch segment is not a valid epoch cannot align —
    # reject it rather than loading with an unalignable ref
    def test_f2_misnamed_file_rejected(self, tmp_path: Path) -> None:
        misnamed = _write_manifest(
            tmp_path,
            EPOCH_1,
            [],
            name="calibration-manifest.garbage.yaml",
        )
        with pytest.raises(Exception):
            load_manifest(misnamed)

    # F3: affected_criterion must follow the bare-id convention ("21"), never
    # the prefixed form ("C21") that silently never grants
    def test_f3_prefixed_criterion_rejected(self, tmp_path: Path) -> None:
        prefixed = _write_manifest(
            tmp_path,
            EPOCH_1,
            [
                {
                    "fragment_id": "frag-003",
                    "source_case": "cookbook.empathy.yaml",
                    "transcript_span": {"start": 1, "end": 2},
                    "human_score": 4,
                    "affected_criterion": "C21",
                    "failure_surface": "x",
                    "severity_anchor": "s",
                }
            ],
        )
        with pytest.raises(Exception):
            load_manifest(prefixed)
