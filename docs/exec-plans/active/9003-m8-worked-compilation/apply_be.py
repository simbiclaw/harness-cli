#!/usr/bin/env python3
"""Apply the session-model B-E refinement (b-e-signals.yaml) to a compile run.

Human-directed substitute for scripts/befine.py (LAN endpoint unreachable;
steering 2026-08-31: "instead of LAN model, employ session model"). For each
item: drop the deterministic model-judged fallbacks (and any extra_remove
adjudicated signals), append the authored clause-traced signals, regenerate
facets and residue via the real M2/M3 core, set the declared data_dependency,
update gap_rationale, and append b-e-refine decision entries.

Usage: apply_be.py <out-dir>   (run from the repo root with PYTHONPATH=src)
"""

import json
import sys
from pathlib import Path

import yaml

from argus.core.compiler.classify import declare_residue
from argus.core.compiler.signals import assign_facets

RUN_DIR = Path(__file__).resolve().parent
FALLBACK_PREFIXES = ("model-judged",)
FALLBACK_EXACT = "quality of the agent's handling as judged against the pass standard"


def is_fallback(signal: dict) -> bool:
    description = str(signal.get("description") or "")
    return description.startswith(FALLBACK_PREFIXES) or description == FALLBACK_EXACT


def main() -> int:
    out = Path(sys.argv[1])
    library = yaml.safe_load((RUN_DIR / "b-e-signals.yaml").read_text())
    decisions: list[dict] = []
    for item_id, entry in library["items"].items():
        node_path = out / "nodes" / f"item-{item_id}.json"
        node = json.loads(node_path.read_text())
        removed: list[str] = []
        extra = {e["id"]: e["reason"] for e in entry.get("extra_remove", [])}
        for lane in ("fail", "excellence"):
            kept = []
            for signal in node["signals"][lane]:
                if is_fallback(signal) or signal["id"] in extra:
                    removed.append(signal["id"])
                else:
                    kept.append(signal)
            node["signals"][lane] = kept
        for signal in entry["signals"]:
            lane = signal.pop("lane")
            node["signals"][lane].append(signal)
        node["facets"] = assign_facets(node["signals"], node["gap_type"])
        node["residue_declared"] = declare_residue(node["signals"], node["dimension"])
        if entry.get("data_dependency"):
            node["data_dependency"] = entry["data_dependency"]
        node["gap_rationale"] = (
            "B-E refined via skill invocation, session model (2026-08-31, "
            f"human-directed): {entry['note']}"
        )
        node_path.write_text(json.dumps(node, indent=2, ensure_ascii=False))
        decisions.append(
            {
                "step": "b-e-refine",
                "item": item_id,
                "model": "session (human-directed substitute for LAN befine.py)",
                "removed": removed,
                "rationale": entry["note"],
            }
        )
    decisions_path = out / "compile-decisions.jsonl"
    with decisions_path.open("a") as fh:
        for decision in decisions:
            fh.write(json.dumps(decision, ensure_ascii=False) + "\n")
    print(f"b-e applied to {len(library['items'])} items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
