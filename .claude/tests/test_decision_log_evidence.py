"""Structural test: every Decision Log entry has a recognized Rationale.

Three permitted shapes:
  - Cited:       has a 'Source:' line with a URL or path:line reference.
  - Empirical:   has an 'Experiment:' line pointing to docs/experiments/.
  - Marked-low:  has 'Confidence: low' and 'Revisit:' lines.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLANS_DIRS = [
    REPO_ROOT / "docs" / "plans" / d for d in ("active", "completed", "archived")
]

DECISION_HEADER = re.compile(
    r"^##+\s+Decision Log\s*$", re.IGNORECASE | re.MULTILINE
)
NEXT_HEADER = re.compile(r"^##+\s+\S", re.MULTILINE)
ENTRY_DELIM = re.compile(r"^###\s+", re.MULTILINE)

URL_RE = re.compile(r"https?://\S+")
PATH_LINE_RE = re.compile(r"\b[\w./\-]+\.\w+:\d+(?:-\d+)?\b")
EXPERIMENT_RE = re.compile(r"docs/experiments/[\w\-/]+")
LOW_CONF_RE = re.compile(
    r"^\s*Confidence:\s*low\s*$", re.MULTILINE | re.IGNORECASE
)
REVISIT_RE = re.compile(r"^\s*Revisit:\s*\S+", re.MULTILINE | re.IGNORECASE)


def extract_decision_log(text: str) -> str | None:
    m = DECISION_HEADER.search(text)
    if not m:
        return None
    start = m.end()
    nxt = NEXT_HEADER.search(text, pos=start)
    end = nxt.start() if nxt else len(text)
    return text[start:end]


def entries(section: str) -> list[str]:
    parts = ENTRY_DELIM.split(section)
    return [p.strip() for p in parts[1:] if p.strip()]


def entry_is_valid(entry: str) -> tuple[bool, str]:
    cited = bool(URL_RE.search(entry) or PATH_LINE_RE.search(entry))
    empirical = bool(EXPERIMENT_RE.search(entry))
    marked_low = bool(LOW_CONF_RE.search(entry) and REVISIT_RE.search(entry))
    if cited or empirical or marked_low:
        return True, ""
    return False, (
        "Decision entry lacks recognized rationale shape. Add ONE of:\n"
        "  Source: <URL or path:line>\n"
        "  Experiment: docs/experiments/<name>/\n"
        "  Confidence: low\n  Revisit: <milestone or YYYY-MM-DD>"
    )


def test_decision_log_entries_have_evidence():
    failures: list[str] = []
    for plans_dir in PLANS_DIRS:
        if not plans_dir.exists():
            continue
        for plan in plans_dir.glob("*.md"):
            text = plan.read_text()
            section = extract_decision_log(text)
            if section is None:
                continue
            for i, entry in enumerate(entries(section), start=1):
                ok, msg = entry_is_valid(entry)
                if not ok:
                    first_line = entry.splitlines()[0] if entry else "(empty)"
                    failures.append(
                        f"{plan.relative_to(REPO_ROOT)} entry #{i} "
                        f"({first_line[:60]}): {msg}"
                    )
    assert not failures, "\n  ".join([""] + failures)
