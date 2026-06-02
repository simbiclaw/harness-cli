"""Structural test: dep-vet records contain the four required checks.

Walks docs/decisions/dep-vet-*.md and asserts each file has a Checks
section containing Age, Downloads, Activity, and License results.

See docs/conventions/deps-and-secrets.md.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DECISIONS_DIR = REPO_ROOT / "docs" / "decisions"

CHECKS_HEADER = re.compile(r"^#+\s+Checks\s*$", re.MULTILINE | re.IGNORECASE)
AGE_RE = re.compile(r"^\s*Age\s*:\s*(PASS|FAIL)", re.MULTILINE | re.IGNORECASE)
DOWNLOADS_RE = re.compile(
    r"^\s*Downloads\s*:\s*(PASS|FAIL)", re.MULTILINE | re.IGNORECASE
)
ACTIVITY_RE = re.compile(
    r"^\s*Activity\s*:\s*(PASS|FAIL)", re.MULTILINE | re.IGNORECASE
)
LICENSE_RE = re.compile(
    r"^\s*License\s*:\s*(PASS|FAIL)", re.MULTILINE | re.IGNORECASE
)


def checks_section(text: str) -> str:
    m = CHECKS_HEADER.search(text)
    if not m:
        return ""
    # Grab from here to next heading or EOF.
    rest = text[m.end():]
    nxt = re.search(r"^#+\s+\S", rest, re.MULTILINE)
    return rest[:nxt.start()] if nxt else rest


def test_dep_vet_records_have_four_checks():
    if not DECISIONS_DIR.exists():
        return

    failures: list[str] = []
    for vet_file in sorted(DECISIONS_DIR.glob("dep-vet-*.md")):
        text = vet_file.read_text()
        section = checks_section(text)
        rel = vet_file.relative_to(REPO_ROOT)

        if not section:
            failures.append(
                f"{rel}: no 'Checks' section found. Add the four "
                f"required checks (Age, Downloads, Activity, License)."
            )
            continue

        for label, pattern in [
            ("Age", AGE_RE),
            ("Downloads", DOWNLOADS_RE),
            ("Activity", ACTIVITY_RE),
            ("License", LICENSE_RE),
        ]:
            if not pattern.search(section):
                failures.append(
                    f"{rel}: missing '{label}: PASS' or '{label}: FAIL' "
                    f"in Checks section."
                )

    assert not failures, "\n  ".join([""] + failures)
