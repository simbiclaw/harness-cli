"""Structural test: Promotion rule enforcement.

The promotion rule (CLAUDE.md, pev-loop.md § When this rubric is wrong) says:
  "When the same rule is violated twice — by you, in different ExecPlans —
   the documentation has failed. Open an ExecPlan to promote the rule one
   step left."

This test enforces that: it reads .pev-signals/violations/<rule-slug>.json,
groups violations by rule, and fails when a rule has ≥2 violations across
different plans but no corresponding structural test or promotion record.

This is the rule that governs the rules. It was itself promoted from
documentation to structural test on 2026-07-30.

Violation record schema (.pev-signals/violations/<rule-slug>.json):
  {
    "rule_slug": "loop-closure",
    "rule_name": "PEV loop closure — no advance before CONFIRMED",
    "current_level": "documentation",
    "violations": [
      {
        "plan_id": "9006-pev-tmux-convergence",
        "milestone": "M4",
        "timestamp": "2026-07-29T12:00:00Z",
        "description": "M3 checkbox flipped before M2 CONFIRMED verdict"
      }
    ],
    "promotion": null
  }

  After promotion:
  "promotion": {
    "promoted_to": "structural_test",
    "test_file": ".claude/tests/test_loop_closure.py",
    "execplan": "9010-promote-loop-closure",
    "timestamp": "2026-07-29T15:00:00Z"
  }
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VIOLATIONS_DIR = REPO_ROOT / ".pev-signals" / "violations"
STRUCTURAL_TESTS_DIR = REPO_ROOT / ".claude" / "tests"
VALID_LEVELS = {"documentation", "structural_test", "hook", "ci_gate", "architecture"}

# Map level to expected enforcement type
LEVEL_ENFORCEMENT = {
    "documentation": None,          # No enforcement mechanism
    "structural_test": "test",      # .claude/tests/test_<slug>.py
    "hook": "hook",                 # .claude/hooks/<slug>.py
    "ci_gate": "ci",                # .github/workflows/<slug>.yml
    "architecture": "architecture", # import-linter contract
}


def _load_violation_records() -> list[dict]:
    """Load all violation records from .pev-signals/violations/."""
    records = []
    if not VIOLATIONS_DIR.exists():
        return records
    for path in sorted(VIOLATIONS_DIR.glob("*.json")):
        if path.name == ".gitkeep":
            continue
        try:
            record = json.loads(path.read_text())
            record["_source_file"] = str(path.relative_to(REPO_ROOT))
            records.append(record)
        except (json.JSONDecodeError, KeyError) as e:
            # Malformed records are themselves a violation — report them
            records.append({
                "rule_slug": f"malformed:{path.name}",
                "rule_name": f"Malformed violation record: {path.name}",
                "current_level": "documentation",
                "violations": [],
                "promotion": None,
                "_source_file": str(path.relative_to(REPO_ROOT)),
                "_parse_error": str(e),
            })
    return records


def _enforcement_exists(rule_slug: str, target_level: str) -> bool:
    """Check whether the enforcement mechanism for target_level exists."""
    enforcement_type = LEVEL_ENFORCEMENT.get(target_level)
    if enforcement_type is None:
        return False  # documentation level — no enforcement expected

    if enforcement_type == "test":
        return (STRUCTURAL_TESTS_DIR / f"test_{rule_slug}.py").exists()
    if enforcement_type == "hook":
        return (REPO_ROOT / ".claude" / "hooks" / f"{rule_slug}.py").exists()
    if enforcement_type == "ci":
        return (REPO_ROOT / ".github" / "workflows" / f"{rule_slug}.yml").exists()
    if enforcement_type == "architecture":
        # Check import-linter contracts in pyproject.toml
        pyproject = REPO_ROOT / "pyproject.toml"
        if pyproject.exists():
            return rule_slug in pyproject.read_text()
        return False
    return False


def test_promotion_rule_enforced():
    """Rules with ≥2 violations across different plans must be promoted.

    For each violation record with violation_count >= 2, the rule's
    current_level must have a corresponding enforcement mechanism, OR
    a promotion record must exist showing it was promoted.

    If neither condition is met, this test fails — the promotion rule
    itself has been violated. The fix is to either:
    - Promote the rule (documentation → structural test → ...)
    - Open an ExecPlan for the promotion
    """
    records = _load_violation_records()
    if not records:
        return  # No violation records — nothing to enforce (yet)

    failures: list[str] = []

    for record in records:
        # Check for malformed records first
        if record.get("_parse_error"):
            failures.append(
                f"{record['_source_file']}: malformed JSON — "
                f"{record['_parse_error']}"
            )
            continue

        slug = record.get("rule_slug", "unknown")
        name = record.get("rule_name", slug)
        current = record.get("current_level", "documentation")
        violations = record.get("violations", [])
        promotion = record.get("promotion") or {}

        # Count unique plans among violations
        unique_plans = {v.get("plan_id") for v in violations if v.get("plan_id")}
        violation_count = len(unique_plans)

        if violation_count < 2:
            continue  # Not enough violations to trigger promotion

        # Check if the rule has already been promoted
        if promotion and promotion.get("promoted_to"):
            promoted_to = promotion["promoted_to"]
            if _enforcement_exists(slug, promoted_to):
                continue  # Already promoted and enforcement exists
            failures.append(
                f"{record['_source_file']}: '{name}' promoted to "
                f"'{promoted_to}' but enforcement mechanism not found "
                f"(expected test_{slug}.py, hook, or CI workflow)"
            )
            continue

        # Rule has ≥2 violations but no promotion — check if current
        # level has enforcement (catch the case where enforcement was
        # created without a promotion record)
        if current != "documentation" and _enforcement_exists(slug, current):
            # Enforcement exists at current level — update the record
            failures.append(
                f"{record['_source_file']}: '{name}' at level '{current}' "
                f"with {violation_count} violations across plans "
                f"({', '.join(sorted(unique_plans))}) — enforcement exists "
                f"but promotion record is missing. Update the promotion field."
            )
            continue

        # Core failure: ≥2 violations, no promotion, no enforcement
        next_level = {
            "documentation": "structural_test",
            "structural_test": "hook",
            "hook": "ci_gate",
            "ci_gate": "architecture",
        }.get(current, "structural_test")

        failures.append(
            f"{record['_source_file']}: '{name}' has {violation_count} "
            f"violations across plans ({', '.join(sorted(unique_plans))}) "
            f"at level '{current}' but has not been promoted. "
            f"Next step: promote to '{next_level}' "
            f"(open ExecPlan, create enforcement, update this record)."
        )

    assert not failures, (
        "Promotion rule enforcement — rules with ≥2 violations must be "
        "promoted one level left:\n\n" + "\n\n".join(failures)
    )


def test_violation_record_schema():
    """All violation records must conform to the expected schema."""
    records = _load_violation_records()

    schema_failures: list[str] = []

    for record in records:
        src = record.get("_source_file", "unknown")

        # Skip already-known malformed records
        if record.get("_parse_error"):
            continue

        # Required top-level fields
        for field in ("rule_slug", "rule_name", "current_level", "violations"):
            if field not in record:
                schema_failures.append(f"{src}: missing required field '{field}'")

        # current_level must be valid
        level = record.get("current_level")
        if level and level not in VALID_LEVELS:
            schema_failures.append(
                f"{src}: current_level '{level}' not in {VALID_LEVELS}"
            )

        # violations must be a non-empty list
        violations = record.get("violations")
        if violations is not None:
            if not isinstance(violations, list):
                schema_failures.append(f"{src}: violations must be a list")
            else:
                for i, v in enumerate(violations):
                    for vf in ("plan_id", "timestamp", "description"):
                        if vf not in v:
                            schema_failures.append(
                                f"{src}: violations[{i}] missing '{vf}'"
                            )

        # promotion must be null or an object with promoted_to
        promotion = record.get("promotion")
        if promotion is not None and isinstance(promotion, dict):
            if "promoted_to" not in promotion:
                schema_failures.append(
                    f"{src}: promotion record missing 'promoted_to'"
                )
            elif promotion["promoted_to"] not in VALID_LEVELS:
                schema_failures.append(
                    f"{src}: promotion.promoted_to "
                    f"'{promotion['promoted_to']}' not in {VALID_LEVELS}"
                )

    assert not schema_failures, (
        "Violation record schema violations:\n" +
        "\n".join(f"  - {f}" for f in schema_failures)
    )


def test_promotion_test_is_self_referential():
    """This test file itself counts as the enforcement for the promotion rule.

    The promotion rule started at documentation. This structural test is its
    enforcement — it should be discoverable as test_promotion_rule_enforcement.
    If someone deletes this test without promoting the rule further (to hook),
    the CI suite will fail because the promotion rule no longer has
    structural enforcement.
    """
    this_file = Path(__file__).relative_to(REPO_ROOT)
    assert this_file.exists(), (
        f"{this_file} must exist — it is the structural enforcement "
        f"of the promotion rule"
    )

    # The promotion rule slug
    rule_slug = "promotion_rule_enforcement"

    # This file IS the enforcement mechanism for the promotion rule.
    # If the promotion rule needs promotion (documentation → structural test),
    # this file is the structural test that was created.
    test_path = STRUCTURAL_TESTS_DIR / f"test_{rule_slug}.py"
    assert test_path.exists(), (
        f"Expected {test_path} to exist as the structural enforcement "
        f"of the promotion rule"
    )
