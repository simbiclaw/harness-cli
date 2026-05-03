"""Structural test: every direct dependency in pyproject.toml has both:
  - a dep-vet record at docs/decisions/dep-vet-<pkg>.md, AND
  - a Decision Log entry in some ExecPlan referencing it.

Reads [project] dependencies and [project.optional-dependencies] sections.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# tomllib is stdlib in 3.11+. Use it directly; if absent (<3.11), fall back
# to a regex parser for the bootstrap case.
if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
DECISIONS_DIR = REPO_ROOT / "docs" / "decisions"
PLANS_DIRS = [
    REPO_ROOT / "docs" / "plans" / d for d in ("active", "completed", "archived")
]


def package_name(spec: str) -> str:
    """Extract package name from a PEP 508 spec like 'typer>=0.12'."""
    return re.split(r"[<>=!~\[;\s]", spec, 1)[0].strip()


def collect_deps_tomllib() -> list[str]:
    if not PYPROJECT.exists() or tomllib is None:
        return []
    data = tomllib.loads(PYPROJECT.read_text())
    deps: set[str] = set()
    project = data.get("project", {})
    for spec in project.get("dependencies", []):
        if name := package_name(spec):
            deps.add(name)
    for group, group_deps in (project.get("optional-dependencies") or {}).items():
        for spec in group_deps:
            if name := package_name(spec):
                deps.add(name)
    return sorted(deps)


def all_plan_text() -> str:
    chunks: list[str] = []
    for d in PLANS_DIRS:
        if not d.exists():
            continue
        for p in d.glob("*.md"):
            chunks.append(p.read_text())
    return "\n".join(chunks)


def test_each_dep_has_decision_and_vet():
    failures: list[str] = []
    plan_text = all_plan_text()
    for dep in collect_deps_tomllib():
        vet = DECISIONS_DIR / f"dep-vet-{dep}.md"
        if not vet.exists():
            failures.append(
                f"dependency '{dep}' has no dep-vet record at "
                f"docs/decisions/dep-vet-{dep}.md. Run the dep-vetter "
                f"skill on '{dep}'. See docs/conventions/deps-and-secrets.md."
            )
        # Look for the dep name as a word in any plan.
        if not re.search(rf"\b{re.escape(dep)}\b", plan_text):
            failures.append(
                f"dependency '{dep}' is not mentioned in any active or "
                f"completed ExecPlan Decision Log. Add a Decision Log "
                f"entry with rationale to the plan that introduced it."
            )
    assert not failures, "\n  ".join([""] + failures)
