"""Structural test: no forbidden phrases in Decision Log sections.

These phrases are tells for unsupported confidence. If a decision deserves
one of them, it deserves a citation or an empirical experiment instead.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLANS_DIRS = [
    REPO_ROOT / "docs" / "plans" / d for d in ("active", "completed", "archived")
]

FORBIDDEN = [
    "standard approach",
    "best practice",
    "industry standard",
    "commonly used",
    "widely accepted",
    "the go-to",
    "people generally",
    "everyone knows",
]
FORBIDDEN_RE = re.compile(
    "|".join(re.escape(p) for p in FORBIDDEN), re.IGNORECASE
)
DECISION_HEADER = re.compile(
    r"^##+\s+Decision Log\s*$", re.IGNORECASE | re.MULTILINE
)
NEXT_HEADER = re.compile(r"^##+\s+\S", re.MULTILINE)


def decision_log_text(text: str) -> str:
    m = DECISION_HEADER.search(text)
    if not m:
        return ""
    nxt = NEXT_HEADER.search(text, pos=m.end())
    end = nxt.start() if nxt else len(text)
    return text[m.end():end]


def test_no_forbidden_phrases():
    failures: list[str] = []
    for plans_dir in PLANS_DIRS:
        if not plans_dir.exists():
            continue
        for plan in plans_dir.glob("*.md"):
            text = plan.read_text()
            log = decision_log_text(text)
            if not log:
                continue
            log_offset = text.find(log)
            for m in FORBIDDEN_RE.finditer(log):
                offset = log_offset + m.start()
                line_no = text[:offset].count("\n") + 1
                failures.append(
                    f"{plan.relative_to(REPO_ROOT)}:{line_no}: "
                    f"forbidden phrase '{m.group()}' in Decision Log. "
                    f"Replace with a citation (Source: URL or path:line), "
                    f"an experiment (Experiment: docs/experiments/...), "
                    f"or a low-confidence marker (Confidence: low + "
                    f"Revisit: ...). See "
                    f"docs/conventions/i-dont-know-protocol.md."
                )
    assert not failures, "\n  ".join([""] + failures)
