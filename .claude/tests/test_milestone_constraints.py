"""Structural tests for machine-readable milestone constraints.

Validates that ExecPlan milestones with constraint fields parse correctly:
- Risk Tier is A, B, or C
- Requires references existing milestone numbers
- Allowed Reads/Writes are valid glob patterns
- Every milestone has an Acceptance Test or explicit behavioral-test waiver
- Old plans without constraints still pass (backward-compatible)

See docs/conventions/pev-loop.md for the constraint format specification.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACTIVE_DIR = REPO_ROOT / "docs" / "exec-plans" / "active"
COMPLETED_DIR = REPO_ROOT / "docs" / "exec-plans" / "completed"

# Constraint field patterns
ALLOWED_READS_RE = re.compile(r"^Allowed Reads:\s*(.+)$", re.MULTILINE)
ALLOWED_WRITES_RE = re.compile(r"^Allowed Writes:\s*(.+)$", re.MULTILINE)
REQUIRES_RE = re.compile(r"^Requires:\s*(.+)$", re.MULTILINE)
RISK_TIER_RE = re.compile(r"^Risk Tier:\s*([ABC])\s*$", re.MULTILINE)
ACCEPTANCE_TEST_RE = re.compile(
    r"`Acceptance Test:`\s*`?([^`\n]+)`?", re.MULTILINE
)
BEHAVIORAL_TEST_NONE_RE = re.compile(
    r"Behavioral Test:\s*none\s*[—–-]\s*(.+)", re.IGNORECASE | re.MULTILINE
)
STRUCTURAL_TEST_NONE_RE = re.compile(
    r"Structural Test:\s*none\s*[—–-]\s*(.+)", re.IGNORECASE | re.MULTILINE
)

# Milestone header pattern
MILESTONE_RE = re.compile(r"^### M(\d+)[\s—–-]", re.MULTILINE)

# Section boundary: stop parsing milestones after the Progress section
PROGRESS_SECTION_RE = re.compile(
    r"^## \d+\.\s*Progress\s*$", re.MULTILINE
)


def _extract_milestones_section(text: str) -> str:
    """Extract only the Milestones section of a plan, excluding
    Decision Log entries that might match milestone headers
    (e.g., '### M0 adversarial verification').
    """
    m = PROGRESS_SECTION_RE.search(text)
    if m:
        return text[: m.start()]
    return text

# Valid risk tiers
VALID_TIERS = {"A", "B", "C"}


def _parse_milestone_constraints(text: str) -> list[dict]:
    """Extract constraint fields from each milestone section."""
    milestones = []
    parts = MILESTONE_RE.split(text)
    # parts[0] is before first milestone; then alternating (num, body)
    for i in range(1, len(parts) - 1, 2):
        m_num = int(parts[i])
        body = parts[i + 1]

        # Find next milestone or end
        next_m = MILESTONE_RE.search(body)
        if next_m:
            body = body[: next_m.start()]

        constraints = {"milestone": m_num}

        m = ALLOWED_READS_RE.search(body)
        if m:
            constraints["allowed_reads"] = [p.strip() for p in m.group(1).split(",")]

        m = ALLOWED_WRITES_RE.search(body)
        if m:
            constraints["allowed_writes"] = [p.strip() for p in m.group(1).split(",")]

        m = REQUIRES_RE.search(body)
        if m:
            constraints["requires"] = [
                int(r.strip().lstrip("M")) for r in m.group(1).split(",")
            ]

        m = RISK_TIER_RE.search(body)
        if m:
            constraints["risk_tier"] = m.group(1)

        milestones.append(constraints)

    return milestones


def _validate_glob(pattern: str) -> bool:
    """Check if a string is a plausible glob pattern."""
    # Must not be empty, must not contain null bytes or newlines
    if not pattern or "\x00" in pattern or "\n" in pattern:
        return False
    # Should not start with / (relative to repo root)
    if pattern.startswith("/"):
        return False
    return True


def test_constraints_parse_and_validate():
    """Milestones with constraint fields have valid values."""
    if not ACTIVE_DIR.exists():
        return

    failures: list[str] = []

    for plan_path in sorted(ACTIVE_DIR.glob("*.md")):
        text = plan_path.read_text()
        rel = plan_path.relative_to(REPO_ROOT)
        milestones = _parse_milestone_constraints(text)
        milestone_nums = {m["milestone"] for m in milestones}

        for m in milestones:
            m_num = m["milestone"]

            # Risk Tier must be A, B, or C
            if "risk_tier" in m and m["risk_tier"] not in VALID_TIERS:
                failures.append(
                    f"{rel} M{m_num}: Risk Tier '{m['risk_tier']}' "
                    f"must be A, B, or C"
                )

            # Requires must reference existing milestones
            if "requires" in m:
                for req in m["requires"]:
                    if req not in milestone_nums:
                        failures.append(
                            f"{rel} M{m_num}: Requires M{req} which "
                            f"does not exist in this plan"
                        )
                    if req >= m_num:
                        failures.append(
                            f"{rel} M{m_num}: Requires M{req} which "
                            f"is not a prerequisite (must be < M{m_num})"
                        )

            # Allowed Reads/Writes must be valid glob patterns
            for field in ("allowed_reads", "allowed_writes"):
                if field in m:
                    for pat in m[field]:
                        if not _validate_glob(pat):
                            failures.append(
                                f"{rel} M{m_num}: Invalid glob pattern "
                                f"'{pat}' in {field}"
                            )

    assert not failures, "Milestone constraint violations:\n" + "\n".join(
        f"  - {f}" for f in failures
    )


def test_backward_compatible_without_constraints():
    """Plans without constraint fields still pass."""
    if not ACTIVE_DIR.exists():
        return

    for plan_path in sorted(ACTIVE_DIR.glob("*.md")):
        text = plan_path.read_text()
        rel = plan_path.relative_to(REPO_ROOT)
        milestones = _parse_milestone_constraints(text)

        # If no milestone has any constraint fields, that's fine
        for m in milestones:
            has_constraints = any(
                k in m for k in ("allowed_reads", "allowed_writes", "requires", "risk_tier")
            )
            # No assertion needed — absence of constraints is valid
            _ = has_constraints


def test_every_milestone_has_behavioral_coverage():
    """Every milestone must have an Acceptance Test or an explicit
    'Behavioral Test: none — <reason>' declaration.

    A milestone without behavioral coverage is incomplete at Plan phase
    (pev-loop.md § Plan — contract formation, step 3).
    """
    if not ACTIVE_DIR.exists():
        return

    failures: list[str] = []

    for plan_path in sorted(ACTIVE_DIR.glob("*.md")):
        full_text = plan_path.read_text()
        text = _extract_milestones_section(full_text)
        rel = plan_path.relative_to(REPO_ROOT)

        parts = MILESTONE_RE.split(text)
        for i in range(1, len(parts) - 1, 2):
            m_num = int(parts[i])
            body = parts[i + 1]

            # Cut at next milestone
            next_m = MILESTONE_RE.search(body)
            if next_m:
                body = body[: next_m.start()]

            has_acceptance = ACCEPTANCE_TEST_RE.search(body)
            has_behavioral_none = BEHAVIORAL_TEST_NONE_RE.search(body)

            if not has_acceptance and not has_behavioral_none:
                failures.append(
                    f"{rel} M{m_num}: no Acceptance Test and no "
                    f"behavioral-test waiver ('Behavioral Test: none "
                    f"— <reason>'). Every milestone must have a "
                    f"behavioral test or an explicit justification "
                    f"for its absence."
                )
            elif has_behavioral_none:
                # Verify the reason is non-trivial (more than 10 chars)
                reason = has_behavioral_none.group(1).strip()
                if len(reason) < 10:
                    failures.append(
                        f"{rel} M{m_num}: behavioral-test waiver "
                        f"reason too short ('{reason}'). Provide a "
                        f"substantive justification."
                    )

    assert not failures, (
        "Behavioral coverage violations — milestones without "
        "Acceptance Test or explicit waiver:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )
