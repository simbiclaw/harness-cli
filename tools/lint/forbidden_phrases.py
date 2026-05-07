#!/usr/bin/env python3
"""forbidden-phrases: scan .md files for unjustified appeals to authority.

Usage: python3 tools/lint/forbidden_phrases.py [file ...]

If no files given, scans docs/**/*.md and the four top-level .md files
(ARCHITECTURE.md, DESIGN.md, PRODUCT_SENSE.md, QUALITY_SCORE.md).

Forbidden phrases: "best practice", "industry standard", "clean architecture",
"follows convention". A violation is a forbidden phrase NOT followed within
3 lines by a citation, experiment reference, or Confidence: low marker.

Exit 0 if clean; exit 1 and print violations to stderr otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

FORBIDDEN = [
    "best practice",
    "industry standard",
    "clean architecture",
    "follows convention",
]

CITATION_PATTERNS = [
    re.compile(r"https?://"),  # URL
    re.compile(r"^Source:", re.M),  # Source: citation
    re.compile(r"^Experiment:", re.M),  # Experiment: reference
    re.compile(r"Confidence:\s*low", re.I),  # Marked-as-guess
    re.compile(r"docs/"),  # file-path citation
    re.compile(r"`[^`]+\.md`"),  # inline file reference
]

ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = ROOT / "docs"
ROOT_MD_FILES = [
    ROOT / "ARCHITECTURE.md",
    ROOT / "DESIGN.md",
    ROOT / "PRODUCT_SENSE.md",
    ROOT / "QUALITY_SCORE.md",
]


def _has_citation_nearby(lines: list[str], line_idx: int) -> bool:
    """Check whether the current line or any of the 3 lines after carries a citation."""
    for offset in range(0, 4):
        check_idx = line_idx + offset
        if check_idx >= len(lines):
            break
        combined = lines[check_idx].strip()
        if any(p.search(combined) for p in CITATION_PATTERNS):
            return True
    return False


def check_file(path: Path) -> list[str]:
    """Return list of violation messages for *path*, or empty if clean."""
    violations: list[str] = []
    lines = path.read_text().splitlines()
    for i, line in enumerate(lines):
        lower = line.lower()
        for phrase in FORBIDDEN:
            if phrase in lower and not _has_citation_nearby(lines, i):
                violations.append(
                    f"{path}:{i + 1}: forbidden phrase '{phrase}' "
                    f"without citation, experiment, or Confidence: low"
                )
    return violations


def collect_files(paths: list[str]) -> list[Path]:
    """Resolve file list from args, or default to docs/ + root .md files."""
    if paths:
        result: list[Path] = []
        for p in paths:
            pp = Path(p)
            if pp.is_dir():
                result.extend(sorted(pp.rglob("*.md")))
            else:
                result.append(pp)
        return result

    result: list[Path] = []
    if DOCS_DIR.is_dir():
        result.extend(sorted(DOCS_DIR.rglob("*.md")))
    for f in ROOT_MD_FILES:
        if f.is_file() and f not in result:
            result.append(f)
    return result


def main(argv: list[str]) -> int:
    files = collect_files(argv[1:])
    all_violations: list[str] = []
    for f in files:
        all_violations.extend(check_file(f))
    for v in all_violations:
        print(v, file=sys.stderr)
    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
