#!/usr/bin/env python3
"""quality-grade-evidence: scan QUALITY_SCORE.md for ungrounded hand-edited grades.

Usage: python3 tools/lint/quality_grade_evidence.py [file]

If no file is given, scans docs/QUALITY_SCORE.md.

A grade cell in the matrix must contain inline evidence (in parentheses) after
the grade letter unless the grade is F.  F-grades at bootstrap are exempt;
non-F grades without parenthetical evidence are violations.

Exit 0 if clean; exit 1 and print violations to stderr otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PATH = ROOT / "docs" / "QUALITY_SCORE.md"

# Matches table cells that start with a letter grade like "A" or "B (...)"
GRADE_CELL = re.compile(r"\s*\*?\*?([A-F])\b\s*(\([^)]*\))?\s*$")
NON_F_GRADE = re.compile(r"[A-E]")


def check_file(path: Path) -> list[str]:
    """Parse the matrix portion of *path* and return violations."""
    violations: list[str] = []
    lines = path.read_text().splitlines()
    in_matrix = False

    for i, line in enumerate(lines, start=1):
        if line.strip().startswith("|") and "Domain" in line and "Layer" in line:
            in_matrix = True
            continue
        if not in_matrix or not line.strip().startswith("|"):
            continue
        if line.strip().startswith("|---"):
            continue
        # End of matrix: line that doesn't start with a domain cell
        if not re.match(r"\|\s*\*?\*?\w", line):
            in_matrix = False
            continue

        cells = line.split("|")
        for cell in cells:
            cell = cell.strip()
            m = GRADE_CELL.match(cell)
            if not m:
                continue
            grade = m.group(1)
            evidence = m.group(2)
            if NON_F_GRADE.match(grade) and not evidence:
                violations.append(
                    f"{path}:{i}: grade '{grade}' without inline evidence in cell '{cell}'"
                )

    return violations


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_PATH
    if not path.is_file():
        print(f"quality-grade-evidence: file not found: {path}", file=sys.stderr)
        return 1
    violations = check_file(path)
    for v in violations:
        print(v, file=sys.stderr)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
