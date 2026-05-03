"""Structural test: application tests don't touch the user's real $HOME.

Walks tests/ for code patterns that suggest writing to or reading from a
real user-home location (Path.home(), os.path.expanduser("~"), or string
literals starting with "~/"). Such patterns are a class of bug because they
will write to the developer's actual home during test runs.

Tests should use pytest's tmp_path fixture or set XDG_CONFIG_HOME / HOME
to a temporary directory.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TESTS_DIR = REPO_ROOT / "tests"

SUSPICIOUS = [
    re.compile(r"\bPath\.home\(\)"),
    re.compile(r"\bos\.path\.expanduser\("),
    re.compile(r'"~/'),
    re.compile(r"'~/"),
]


def test_no_real_home_in_tests():
    if not TESTS_DIR.exists():
        return  # bootstrap

    failures: list[str] = []
    for py in TESTS_DIR.rglob("*.py"):
        text = py.read_text()
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            for pattern in SUSPICIOUS:
                if pattern.search(line):
                    failures.append(
                        f"{py.relative_to(REPO_ROOT)}:{lineno}: "
                        f"suspicious real-home reference. Use the pytest "
                        f"tmp_path fixture or set HOME/XDG_CONFIG_HOME to "
                        f"a tmp dir. See "
                        f"docs/conventions/verification-floor.md."
                    )
    assert not failures, "\n  ".join([""] + failures)
