"""Structural tests for the PEV orchestrator workflow script.

Validates the script's structure: meta block, phase declarations,
pipeline pattern, schema definitions, and repair loop logic.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / ".claude" / "scripts" / "pev_orchestrator.js"


def test_orchestrator_script_exists():
    assert SCRIPT.exists(), f"Orchestrator script not found: {SCRIPT}"


def test_orchestrator_has_meta_block():
    text = SCRIPT.read_text()
    assert "export const meta" in text
    assert "'pev-orchestrator'" in text
    assert "phases" in text


def test_orchestrator_has_three_phases():
    text = SCRIPT.read_text()
    assert "title: 'Plan'" in text
    assert "title: 'Execute'" in text
    assert "title: 'Verify'" in text


def test_orchestrator_has_schemas():
    text = SCRIPT.read_text()
    assert "PLAN_SCHEMA" in text
    assert "EXECUTE_SCHEMA" in text
    assert "VERIFY_SCHEMA" in text
    # Verify schema has CONFIRMED/REJECTED enum
    assert "CONFIRMED" in text
    assert "REJECTED" in text


def test_orchestrator_uses_pipeline():
    text = SCRIPT.read_text()
    assert "pipeline(" in text


def test_orchestrator_has_pev_stages():
    text = SCRIPT.read_text()
    assert "pevPlan" in text
    assert "pevExecute" in text
    assert "pevVerify" in text


def test_orchestrator_has_repair_loop():
    text = SCRIPT.read_text()
    assert "pevRepair" in text
    assert "failure_class" in text
    assert "mechanical" in text
    assert "semantic" in text
    assert "constraint-violation" in text


def test_orchestrator_parses_milestones():
    text = SCRIPT.read_text()
    assert "parseMilestones" in text
    assert "acceptanceTest" in text
    assert "allowedWrites" in text
    assert "requires" in text
    assert "riskTier" in text


def test_orchestrator_topological_sort():
    text = SCRIPT.read_text()
    assert "topological" in text.lower() or "sort" in text
    assert "requires" in text


def test_orchestrator_returns_summary():
    text = SCRIPT.read_text()
    assert "confirmed" in text
    assert "rejected" in text
    assert "blocked" in text
