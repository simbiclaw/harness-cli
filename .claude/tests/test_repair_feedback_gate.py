"""Structural test for the PEV repair feedback gate.

Enforces that REJECTED adversarial verification verdicts produce the
appropriate implementation notes entries before the next PEV iteration:

    semantic → [human-todo] entry must exist
    constraint-violation → [deviation] entry must exist
    mechanical → no entry required (auto-retry)

This closes the feedback loop: the repair loop writes structured
feedback to the notes file, and this test verifies the write happened.

See docs/conventions/implementation-notes.md and docs/conventions/verification-floor.md.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACTIVE_DIR = REPO_ROOT / "docs" / "exec-plans" / "active"

# Locate the Decision Log section within an ExecPlan
DECISION_HEADER = re.compile(
    r"^##+\s+\d+\.\s+Decision Log\s*$",
    re.MULTILINE | re.IGNORECASE,
)
NEXT_HEADER = re.compile(r"^##+\s+\d+\.\s+", re.MULTILINE)

# Match an adversarial verification entry within a Decision Log section
ADV_VERIFY_ENTRY_RE = re.compile(
    r"^M(\d+) adversarial verification",
    re.MULTILINE,
)
VERDICT_RE = re.compile(r"^Verdict:\s*(CONFIRMED|REJECTED)\s*$", re.MULTILINE)
FAILURE_CLASS_RE = re.compile(r"^failure_class:\s*(\S+)", re.MULTILINE)

# Valid failure classes and their required notes entry types
REQUIRED_ENTRY = {
    "semantic": "[human-todo]",
    "constraint-violation": "[deviation]",
}
# mechanical → no entry required


def _notes_dir_for(plan_path: Path) -> Path:
    """Return the notes directory for a plan file."""
    return plan_path.parent / f"{plan_path.stem}-notes"


def _extract_decision_log(text: str) -> str:
    """Extract the Decision Log section body from an ExecPlan."""
    m = DECISION_HEADER.search(text)
    if not m:
        return ""
    start = m.end()
    nxt = NEXT_HEADER.search(text, pos=start)
    end = nxt.start() if nxt else len(text)
    return text[start:end]


def _parse_adv_verify_entries(text: str) -> tuple[list[dict], list[dict]]:
    """Parse all adversarial verification entries from the Decision Log section.

    Returns a tuple of (rejected, confirmed) lists. Each entry dict has keys:
    milestone, verdict, failure_class (REJECTED only), text_offset.
    """
    rejected: list[dict] = []
    confirmed: list[dict] = []
    section = _extract_decision_log(text)
    if not section:
        return rejected, confirmed

    # Split on ### to isolate individual Decision Log entries
    parts = re.split(r"^###\s+", section, flags=re.MULTILINE)
    for i, part in enumerate(parts):
        if not part.strip():
            continue

        adv_match = ADV_VERIFY_ENTRY_RE.match(part)
        if not adv_match:
            continue

        m_num = int(adv_match.group(1))

        verdict_match = VERDICT_RE.search(part)
        verdict = verdict_match.group(1) if verdict_match else None

        if verdict is None:
            continue

        if verdict == "CONFIRMED":
            confirmed.append({
                "milestone": m_num,
                "verdict": "CONFIRMED",
                "text_offset": i,
            })
            continue

        fc_match = FAILURE_CLASS_RE.search(part)
        failure_class = fc_match.group(1) if fc_match else None

        if failure_class is None:
            failure_class = "mechanical"
            rejected.append({
                "milestone": m_num,
                "verdict": "REJECTED",
                "failure_class": failure_class,
                "flagged": "missing failure_class — defaulting to mechanical",
            })
        else:
            rejected.append({
                "milestone": m_num,
                "verdict": "REJECTED",
                "failure_class": failure_class,
            })

    return rejected, confirmed


def test_rejected_verdicts_have_notes_entries():
    """Every REJECTED adversarial verdict has the required notes entry."""
    if not ACTIVE_DIR.exists():
        return

    failures: list[str] = []

    for plan_path in sorted(ACTIVE_DIR.glob("*.md")):
        text = plan_path.read_text()
        rel = str(plan_path.relative_to(REPO_ROOT))
        rejected_entries, _ = _parse_adv_verify_entries(text)

        for entry in rejected_entries:
            m_num = entry["milestone"]
            fc = entry["failure_class"]
            notes_file = _notes_dir_for(plan_path) / f"M{m_num}.md"

            if "flagged" in entry:
                failures.append(
                    f"{rel}: M{m_num} REJECTED but {entry['flagged']}."
                )

            if fc == "mechanical":
                continue  # no entry required for auto-retry

            if fc not in REQUIRED_ENTRY:
                failures.append(
                    f"{rel}: M{m_num} has unknown failure_class '{fc}'. "
                    f"Must be one of: {', '.join(sorted(REQUIRED_ENTRY.keys()))}, mechanical."
                )
                continue

            expected = REQUIRED_ENTRY[fc]
            notes_rel = str(notes_file.relative_to(REPO_ROOT))

            if not notes_file.exists():
                failures.append(
                    f"{rel}: M{m_num} REJECTED with failure_class '{fc}' "
                    f"but notes file missing: {notes_rel}. "
                    f"Must contain a {expected} entry with B's findings."
                )
                continue

            content = notes_file.read_text()
            if expected not in content:
                failures.append(
                    f"{rel}: M{m_num} REJECTED with failure_class '{fc}' "
                    f"but notes file '{notes_rel}' does not contain "
                    f"a {expected} entry. Must document B's findings."
                )

    assert not failures, (
        "Repair feedback gate violations — REJECTED verdicts without required notes entries:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )


def test_confirmed_verdicts_do_not_trigger_gate():
    """CONFIRMED verdicts are not incorrectly classified as REJECTED."""
    if not ACTIVE_DIR.exists():
        return

    for plan_path in sorted(ACTIVE_DIR.glob("*.md")):
        text = plan_path.read_text()
        rel = str(plan_path.relative_to(REPO_ROOT))
        rejected, confirmed = _parse_adv_verify_entries(text)

        # Every CONFIRMED entry should indeed have verdict CONFIRMED
        for entry in confirmed:
            assert entry["verdict"] == "CONFIRMED", (
                f"{rel}: M{entry['milestone']} parsed as CONFIRMED "
                f"but has verdict '{entry['verdict']}'."
            )

        # Every REJECTED entry should indeed have verdict REJECTED
        for entry in rejected:
            assert entry["verdict"] == "REJECTED", (
                f"{rel}: M{entry['milestone']} parsed as REJECTED "
                f"but has verdict '{entry['verdict']}'."
            )
