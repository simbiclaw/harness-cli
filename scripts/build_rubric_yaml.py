#!/usr/bin/env python3
"""Generate `docs/rubric/specific-rubric-27.yaml` from the upstream sheet.

9021 M15. The rubric is a real operational QA standard transcribed from a
client's internal scoring sheet; rebuilding it needs the client's QA team, not
engineering time. So it is **generated**, not retyped: this script imports
`config/rubric_items.py` from the upstream checkout and serialises what is
actually there.

M5 was rejected for the failure a hand transcription invites — enum members
rewritten from memory, with an acceptance test that could not see it. A
mechanical transformation removes that whole class of error: there is no step
where a human reads one file and types another.

Two annotations are added on top of the faithful copy, and both are recorded
rather than silently applied:

- `data_dependency` on items 6 and 7. Neither is checkable from a transcript
  alone — one needs a service-record store, the other a workflow system. They
  stay in the sheet so the exclusion is auditable and reversible; deleting them
  would make it neither.
- `fail_criteria_missing` on any row whose failure standard is empty upstream.
  Item 1 is such a row. That is a defect in the source sheet, not a copying
  slip, and an empty string fed verbatim into a prompt produces nothing while
  looking like it worked.

Usage:  python3 scripts/build_rubric_yaml.py [--upstream /home/user/sim]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "docs" / "rubric" / "specific-rubric-27.yaml"

UPSTREAM_REPO = "simbiclaw/sim"
UPSTREAM_COMMIT = "0c2cccd"
UPSTREAM_PATH = "config/rubric_items.py"

# Why each excluded item cannot be scored from a transcript. Stated as the
# system that would be needed, so a later reader can tell when it is available.
DATA_DEPENDENCY = {
    6: "服务记录系统 — the service-record store is not readable by this evaluator",
    7: "工单/升级流程系统 — the escalation workflow system is not readable by this evaluator",
}


def load_upstream_items(upstream: Path) -> list:
    """Import the upstream sheet and return its RubricItem list."""
    if not (upstream / UPSTREAM_PATH).exists():
        raise SystemExit(
            f"upstream sheet not found at {upstream / UPSTREAM_PATH}.\n"
            f"Pass --upstream pointing at a {UPSTREAM_REPO} checkout."
        )
    sys.path.insert(0, str(upstream))
    from config.rubric_items import RUBRIC_ITEMS  # noqa: PLC0415

    return RUBRIC_ITEMS


def to_row(item) -> dict:
    """One sheet row as plain data, in the upstream field order."""
    row: dict = {
        "id": item.id,
        "category": item.category.value,
        "name": item.name,
        "pass_criteria": item.pass_criteria,
        "fail_criteria": item.fail_criteria,
        "na_criteria": item.na_criteria,
        "is_weighted": item.is_weighted,
        "weight": item.weight,
        "always_check": item.always_check,
        "requires_domain_kb": item.requires_domain_kb,
        "trigger_keywords": list(item.trigger_keywords),
        "is_veto": item.is_veto,
    }
    if not str(item.fail_criteria).strip():
        row["fail_criteria_missing"] = True
    if item.id in DATA_DEPENDENCY:
        row["data_dependency"] = DATA_DEPENDENCY[item.id]
    return row


def build(upstream: Path) -> dict:
    items = load_upstream_items(upstream)
    rows = [to_row(i) for i in items]
    scored = [r for r in rows if "data_dependency" not in r]
    return {
        "source": {
            "repo": UPSTREAM_REPO,
            "commit": UPSTREAM_COMMIT,
            "path": UPSTREAM_PATH,
        },
        "generated_by": "scripts/build_rubric_yaml.py",
        "note": (
            "Generated, not transcribed. Regenerate rather than hand-editing: a "
            "manual change here silently diverges from the source sheet."
        ),
        "row_count": len(rows),
        "scored_count": len(scored),
        "items": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--upstream", type=Path, default=Path("/home/user/sim"))
    args = ap.parse_args()

    doc = build(args.upstream)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    print(f"wrote {OUT.relative_to(REPO_ROOT)}: {doc['row_count']} rows, {doc['scored_count']} scored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
