"""Structural test: Decision Log Experiment references point to real directories.

Walks all ExecPlan Decision Log sections for 'Experiment: docs/experiments/<name>/'
references. Asserts each referenced directory exists and contains a runnable
script (run.py or run.sh) plus at least one output artifact.

See docs/conventions/i-dont-know-protocol.md.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLANS_DIRS = [
    REPO_ROOT / "docs" / "exec-plans" / d for d in ("active", "completed", "archived")
]

DECISION_HEADER = re.compile(
    r"^##+\s+Decision Log\s*$", re.IGNORECASE | re.MULTILINE
)
NEXT_SECTION = re.compile(r"^##+\s+", re.MULTILINE)
EXPERIMENT_RE = re.compile(r"\bExperiment:\s*(docs/experiments/[\w\-/]+)")

RUNNABLE = ("run.py", "run.sh")
OUTPUTS = ("output.txt", "output.json", "results")


def decision_log_text(text: str) -> str:
    m = DECISION_HEADER.search(text)
    if not m:
        return ""
    nxt = NEXT_SECTION.search(text, pos=m.end())
    end = nxt.start() if nxt else len(text)
    return text[m.end():end]


def experiment_refs(text: str) -> list[str]:
    return [m.group(1).rstrip("/") for m in EXPERIMENT_RE.finditer(text)]


def test_experiment_dirs_exist_and_complete():
    failures: list[str] = []
    seen: set[str] = set()

    for plans_dir in PLANS_DIRS:
        if not plans_dir.exists():
            continue
        for plan in plans_dir.glob("*.md"):
            log = decision_log_text(plan.read_text())
            for ref in experiment_refs(log):
                if ref in seen:
                    continue
                seen.add(ref)

                exp_dir = REPO_ROOT / ref
                if not exp_dir.is_dir():
                    failures.append(
                        f"{plan.relative_to(REPO_ROOT)} references "
                        f"'{ref}' but directory does not exist."
                    )
                    continue

                has_runnable = any((exp_dir / f).exists() for f in RUNNABLE)
                if not has_runnable:
                    failures.append(
                        f"{plan.relative_to(REPO_ROOT)} references "
                        f"'{ref}' but no run.py or run.sh found in that "
                        f"directory. See docs/conventions/"
                        f"i-dont-know-protocol.md."
                    )

                has_output = any(
                    (exp_dir / f).exists() or (exp_dir / f).is_dir()
                    for f in OUTPUTS
                )
                if not has_output:
                    failures.append(
                        f"{plan.relative_to(REPO_ROOT)} references "
                        f"'{ref}' but no output artifact found "
                        f"(output.txt, output.json, or results/)."
                    )

    assert not failures, "\n  ".join([""] + failures)
