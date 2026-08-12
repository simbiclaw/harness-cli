#!/usr/bin/env python3
"""Headless runner for the rubric-compiler skill (9003 M6a).

Deterministic orchestration of the 9003 compile loop (Planner → Generator →
Evaluator → freeze) over the compiler's inputs. Two modes:

- Real mode (default): requires the deterministic core (`argus.core.compiler`,
  M1–M5). M6a `Requires: M5` — without it the runner exits with a remediation
  message.
- `--evaluator mock`: template-based deterministic path (fixture-driven node
  construction, rule-based verdicts) so the loop is exercisable before M1–M5
  land and the acceptance tests stay byte-reproducible. When the core lands,
  tests switch to the real validator.

Never writes through the INTENTS symlink unless `freeze --dest INTENTS` is
explicit; never commits an epoch unless `--epoch-commit` is given.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / ".claude" / "skills" / "rubric-compiler" / "fixtures"

# --- sys.path bootstrap (mirrors tests/conftest.py) -------------------------
try:  # pragma: no cover
    import argus  # noqa: F401
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(REPO_ROOT / "src"))

# --- core availability gate (M6a Requires: M5) ------------------------------
try:
    from argus.core.compiler import validator as _validator  # noqa: F401

    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False

REMEDIATION = (
    "M6a Requires: M5 — argus.core.compiler is not landed yet. "
    "Land M1–M5 first, or run with --evaluator mock for the deterministic "
    "template path."
)

ADJECTIVE_RE = re.compile(r"灵活|积极|混乱|清晰|死板|主动|耐心|认真")

CONFLICT_LINE_RE = re.compile(r"^(T\d+)\s*:\s*(.+?)\s*(?:#.*)?$")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs(inputs_dir: Path) -> dict[str, Any]:
    rubric = yaml.safe_load((inputs_dir / "specific-rubric.yaml").read_text())
    skill = yaml.safe_load((inputs_dir / "generic-skill.yaml").read_text())
    align = (inputs_dir / "align.md").read_text()
    items = rubric["items"]
    dims = {d["name"] for d in skill["dimensions"]}
    return {"rubric": rubric, "skill": skill, "align": align, "items": items, "dims": dims}


def parse_align(align: str) -> dict[str, str | None]:
    """Parse the item→dimension table from align.md. A row with '—' or empty
    dimension maps to None (no dimension covers — coverage gap)."""
    mapping: dict[str, str | None] = {}
    for line in align.splitlines():
        m = re.match(r"\|\s*(\d+)\s*\|\s*([^|]+)\s*\|", line)
        if not m:
            continue
        item, dim = m.group(1), m.group(2).strip()
        mapping[item] = None if (not dim or dim.startswith("—") or dim.startswith("-")) else dim
    return mapping


# ──────────────────────────────────────────────────────────────────────────
# Planner (S1 companion pinning, S2 source validation, S3 topological order)
# ──────────────────────────────────────────────────────────────────────────


def validate_sources(items: list[dict[str, Any]], companions_dir: Path) -> list[dict[str, Any]]:
    r"""Structural source validation (S2, mock). Parses each companion doc's
    machine header (`T\d+: keywords`) and flags trigger IDs redefined with
    different keyword sets — the patch-2 Surprise 2 conflict pattern."""
    conflicts: list[dict[str, Any]] = []
    seen: dict[str, tuple[str, int]] = {}
    for doc in sorted(companions_dir.glob("*.md")):
        for lineno, line in enumerate(doc.read_text().splitlines(), start=1):
            m = CONFLICT_LINE_RE.match(line)
            if not m:
                continue
            tid, keywords = m.group(1), m.group(2).strip()
            if tid in seen:
                prev_kw, prev_line = seen[tid]
                if prev_kw != keywords:
                    conflicts.append(
                        {
                            "trigger_id": tid,
                            "first": {"file": str(doc), "line": prev_line, "keywords": prev_kw},
                            "second": {"file": str(doc), "line": lineno, "keywords": keywords},
                        }
                    )
            else:
                seen[tid] = (keywords, lineno)
    return conflicts


def topological_order(items: list[dict[str, Any]]) -> list[str]:
    """Kahn's algorithm over depends_on (S3). Cycle → raise."""
    deps = {it["id"]: list(it.get("depends_on", [])) for it in items}
    order: list[str] = []
    ready = [i for i, d in deps.items() if not d]
    remaining = {i: set(d) for i, d in deps.items()}
    while ready:
        ready.sort()
        nxt = ready.pop(0)
        order.append(nxt)
        for item in remaining:
            remaining[item].discard(nxt)
            if not remaining[item] and item not in order and item not in ready:
                ready.append(item)
    if len(order) != len(items):
        cycled = [i for i in deps if i not in order]
        raise ValueError(f"dependency cycle among items: {sorted(cycled)}")
    return order


def cmd_plan(args: argparse.Namespace) -> int:
    inputs = load_inputs(args.inputs)
    items = inputs["items"]
    mapping = parse_align(inputs["align"])

    # S1: pin companion docs per item.
    companions: dict[str, dict[str, Any]] = {}
    comp_dir = args.inputs / "companions"
    for it in items:
        for cd in it.get("companion_docs", []):
            doc = comp_dir / cd["document"]
            if not doc.exists():
                print(f"companion missing: {doc}")
                return 2
            companions[cd["document"]] = {
                "document": cd["document"],
                "role": cd["role"],
                "sha256": sha256_of(doc),
            }

    # S2: source validation — conflict halts before any node is emitted.
    conflicts = validate_sources(items, comp_dir)
    if conflicts:
        report = {
            "status": "halted",
            "conflicts": conflicts,
            "resolution": "human adjudication required (patch-2 S2) — "
            "reconcile the companion document before compiling",
        }
        (args.out / "conflict-report.yaml").write_text(yaml.safe_dump(report, sort_keys=False))
        for c in conflicts:
            print(f"CONFLICT {c['trigger_id']}: line {c['first']['line']} vs line {c['second']['line']}")
        return 2

    # S3: topological compile order; cycle → halt with report.
    try:
        order = topological_order(items)
    except ValueError as e:
        (args.out / "conflict-report.yaml").write_text(
            yaml.safe_dump({"status": "halted", "conflicts": [{"error": str(e)}]}, sort_keys=False)
        )
        print(str(e))
        return 2

    simple = [
        it["id"]
        for it in items
        if not it.get("companion_docs") and not it.get("depends_on") and it["values"]["named_phrases"]
    ]
    plan = {
        "order": order,
        "batches": {"simple": simple, "complex": [i for i in order if i not in simple]},
        "companions": companions,
        "align": mapping,
    }
    (args.out / "compile-plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False))
    print(f"plan ok: {len(order)} items, batches simple={simple}")
    return 0


# ──────────────────────────────────────────────────────────────────────────
# Generator (mock template path; real core chain wired when M1–M5 land)
# ──────────────────────────────────────────────────────────────────────────


def gap_type_for(item: dict[str, Any]) -> str:
    if item["values"]["named_phrases"]:
        return "values"
    if item["id"] == "21":
        return "calibration_surface_form"
    return "perceiver"


def build_node(item: dict[str, Any], dim: str, plan: dict[str, Any]) -> dict[str, Any]:
    """Template-based AuthoredNode construction (mock). Named phrases → lexical
    FAIL signals (checkable); items without phrases → model_based signal
    (checkable: false). Deterministic — no model call."""
    item_id = item["id"]
    phrases = item["values"]["named_phrases"]
    signals_fail = []
    facets_prog: list[dict[str, Any]] = []
    facets_model: list[dict[str, Any]] = []
    if phrases:
        signals_fail.append(
            {
                "id": f"{item_id}-S01",
                "description": f"transcript contains one of the named phrases: {phrases}",
                "severity": "high",
                "checkable": True,
                "audit_result": "pass",
            }
        )
        facets_prog.append(
            {
                "facet_name": f"{item_id}_phrase_match",
                "enables_signals": [f"{item_id}-S01"],
                "indicator": "phrase presence",
                "calculation": "lexical match over transcript tokens",
                "output_schema": {"type": "boolean"},
            }
        )
    else:
        signals_fail.append(
            {
                "id": f"{item_id}-S01",
                "description": f"model-judged evidence of: {item['text']}",
                "severity": "high",
                "checkable": False,
                "audit_result": "model_only",
            }
        )
        facets_model.append(
            {
                "facet_name": f"{item_id}_semantics",
                "enables_signals": [f"{item_id}-S01"],
                "prompt": f"extract evidence for: {item['pass_standard']}",
                "output_schema": {"type": "string"},
            }
        )

    gap = gap_type_for(item)
    node = {
        "node_id": f"item-{item_id}",
        "category": "judgment",
        "intents_path": f"/_rubric/rules_criteria/{dim}/item-{item_id}.yaml",
        "intents_sha": "0000000000000000000000000000000000000000",
        "layer": "judgment",
        "required_evidence": {},
        "fail_condition": {},
        "deduction": 1.0,
        "authored_by": "rubric-compiler (mock)",
        "dimension": dim,
        "human_version": {"item_number": int(item_id), "text": item["text"]},
        "machine_criterion": {
            "criterion_id": f"C{item_id}",
            "description": item["pass_standard"],
            "scoring_scale": "1-10",
            "gap_type": gap,
            "auto_final_allowed": gap != "calibration_surface_form",
            "escape_tier": "standard",
        },
        "signals": {"fail": signals_fail, "excellence": []},
        "facets": {"programmatic": facets_prog, "model_based": facets_model},
        "corroborators": [],
        "gap_rationale": "mock template classification",
        "agreement": {
            "tau": 0.8,
            "kappa_sample_plan": f"agreement tail for item-{item_id}",
            "escape_sample_plan": f"escape tail for item-{item_id}",
            "escape_ceiling": 0.05,
            "current_kappa": None,
        },
        "applicability_gate": None,
        "severity_map": f"calibration://manifest/epoch-000/severity/{item_id}",
        "data_dependency": None,
        "gap_type": gap,
        "escape_tier": "aggressive" if gap in ("proxy", "coverage") else "standard",
        "iteration_policy": "re-ground via write-time epoch commit only; no rule edits from Argus output",
        "companion_docs": item.get("companion_docs"),
        "depends_on": item.get("depends_on", []),
    }
    deps = item.get("depends_on", [])
    if deps:
        node["applicability_gate"] = {
            "spec": f"gate references prerequisite signals of item(s) {deps}",
            "refs": [f"{d}-S01" for d in deps],
        }
    return node


def cmd_generate(args: argparse.Namespace) -> int:
    plan = json.loads((args.out / "compile-plan.json").read_text())
    inputs = load_inputs(args.inputs)
    mapping = plan["align"]
    item = next((it for it in inputs["items"] if it["id"] == args.item), None)
    if item is None:
        print(f"unknown item: {args.item}")
        return 2
    dim = mapping.get(args.item)
    nodes_dir = args.out / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    if dim is None:
        # Coverage gap (Item 24 pattern): no node; row lands in the manifest.
        gap = {
            "kind": "dimension_coverage_gap",
            "source_items": [args.item],
            "measures": "business-knowledge QA",
            "compiled_to": [],
            "data_dependency": {"connected": False},
            "disposition": "defer_until_source_connected",
            "proposes": "new sub-dimension for knowledge accuracy",
        }
        (args.out / "coverage-gaps.jsonl").open("a").write(json.dumps(gap, ensure_ascii=False) + "\n")
        print(f"item {args.item}: coverage gap — no node emitted")
        return 0
    node = build_node(item, dim, plan)
    if getattr(args, "fix", None):
        fix = json.loads(args.fix)
        for s in node["signals"]["fail"]:
            if s["id"] == fix.get("signal_id"):
                s[fix["field"]] = fix["suggested_fix"]
    (nodes_dir / f"item-{args.item}.json").write_text(json.dumps(node, indent=2, ensure_ascii=False))
    return 0


# ──────────────────────────────────────────────────────────────────────────
# Evaluator (mock: structural checks via M0 schemas; real validator when core)
# ──────────────────────────────────────────────────────────────────────────


def mock_evaluate(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from argus.types.compiler_schemas import AuthoredNode

    findings: list[dict[str, Any]] = []
    for node in nodes:
        try:
            AuthoredNode(**node)
        except Exception as e:  # pragma: no cover — defensive
            findings.append({"node": node["node_id"], "issue": f"schema: {e}", "severity": "block"})
        for s in node.get("signals", {}).get("fail", []):
            if s.get("checkable") and ADJECTIVE_RE.search(s.get("description", "")):
                findings.append(
                    {"node": node["node_id"], "issue": f"AUTH-1 adjective in {s['id']}", "severity": "block"}
                )
        for d in node.get("depends_on", []):
            if not any(n["node_id"] == f"item-{d}" for n in nodes):
                findings.append(
                    {"node": node["node_id"], "issue": f"S3 depends_on {d} unresolved", "severity": "block"}
                )
    return findings


def cmd_evaluate(args: argparse.Namespace) -> int:
    nodes = [json.loads(p.read_text()) for p in sorted((args.out / "nodes").glob("item-*.json"))]
    if CORE_AVAILABLE and not args.evaluator == "mock":
        from argus.core.compiler.validator import validate_node  # type: ignore[import-not-found]

        findings = [{"node": n["node_id"], "issue": str(e), "severity": "block"} for n in nodes for e in validate_node(n)]
    else:
        findings = mock_evaluate(nodes)
    (args.out / "evaluation.json").write_text(json.dumps(findings, indent=2, ensure_ascii=False))
    if findings:
        for f in findings:
            print(f"{f['severity']}: {f['node']} — {f['issue']}")
        return 1
    print("evaluate: CONFIRMED")
    return 0


# ──────────────────────────────────────────────────────────────────────────
# Loop (plan → generate → evaluate → ≤3 fix rounds → freeze)
# ──────────────────────────────────────────────────────────────────────────


def cmd_loop(args: argparse.Namespace) -> int:
    if not args.evaluator == "mock" and not CORE_AVAILABLE:
        print(REMEDIATION)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    decisions: list[dict[str, Any]] = []

    rc = cmd_plan(args)
    if rc:
        return rc
    plan = json.loads((args.out / "compile-plan.json").read_text())

    for item_id in plan["order"]:
        args.item = item_id
        rc = cmd_generate(args)
        if rc:
            return rc
        decisions.append(
            {
                "step": "generate",
                "item": item_id,
                "rationale": "mock template: named phrases → lexical signals; no phrases → model_based",
            }
        )

    for round_no in range(1, 4):
        rc = cmd_evaluate(args)
        if rc == 0:
            break
        findings = json.loads((args.out / "evaluation.json").read_text())
        blocks = [f for f in findings if f["severity"] == "block"]
        if not blocks:
            break
        # Mock fix: rewrite the offending description deterministically.
        for f in blocks:
            m = re.search(r"([A-Z0-9]+-S\d+)", f["issue"])
            if m:
                item_id = f["node"].replace("item-", "")
                fix = {"signal_id": m.group(1), "field": "description",
                       "issue": f["issue"], "suggested_fix": "observable pattern reference"}
                args.fix = json.dumps(fix)
                cmd_generate(args)
                decisions.append({"step": f"fix-round-{round_no}", "item": item_id,
                                  "rationale": f"targeted fix: {f['issue']}"})
    else:
        print("loop: AWAITING_STEERING after 3 fix rounds")
        return 1

    with (args.out / "compile-decisions.jsonl").open("w") as fh:
        for d in decisions:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")

    args.dest = "staging"
    return cmd_freeze(args)


# ──────────────────────────────────────────────────────────────────────────
# Freeze (output contract: nodes + gates + residue manifest)
# ──────────────────────────────────────────────────────────────────────────


def cmd_freeze(args: argparse.Namespace) -> int:
    dest: Path
    if getattr(args, "dest", None) == "INTENTS":
        dest = REPO_ROOT / "INTENTS"
        if not dest.is_symlink() or not dest.exists():
            print("INTENTS symlink missing or dangling — cannot freeze to the external tree")
            return 2
        dest = dest.resolve()
    else:
        dest = args.out / "tree"
    nodes_dir = args.out / "nodes"
    if not nodes_dir.exists():
        print("no nodes to freeze")
        return 2

    (dest / "_rubric" / "rules_criteria").mkdir(parents=True, exist_ok=True)
    (dest / "_rubric" / "gates").mkdir(parents=True, exist_ok=True)
    (dest / "_meta").mkdir(parents=True, exist_ok=True)

    plan = json.loads((args.out / "compile-plan.json").read_text())
    by_dim: dict[str, list[dict[str, Any]]] = {}
    for f in sorted(nodes_dir.glob("item-*.json")):
        node = json.loads(f.read_text())
        by_dim.setdefault(node["dimension"], []).append(node)
        dim_dir = dest / "_rubric" / "rules_criteria" / node["dimension"]
        dim_dir.mkdir(parents=True, exist_ok=True)
        out = dim_dir / f"{f.name}".replace(".json", ".yaml")
        if out.exists() and out.read_text().lstrip().startswith("edited_by_human: true"):
            print(f"skip {out.name}: edited_by_human (D8)")
            continue
        out.write_text("edited_by_human: false\n" + yaml.safe_dump(node, sort_keys=False, allow_unicode=True))

    for dim, nodes in by_dim.items():
        (dest / "_rubric" / "gates" / f"{dim}.yaml").write_text(
            "edited_by_human: false\n"
            + yaml.safe_dump(
                {
                    "dimension": dim,
                    "hard_fail_rule": {
                        "trigger": {"items": [n["node_id"] for n in nodes]},
                        "action": "route_to_human",
                        "synthesized": True,
                    },
                },
                sort_keys=False,
                allow_unicode=True,
            )
        )

    rows: list[dict[str, Any]] = []
    gaps_file = args.out / "coverage-gaps.jsonl"
    if gaps_file.exists():
        rows += [json.loads(line) for line in gaps_file.read_text().splitlines() if line.strip()]
    manifest = {
        "schema_version": "1.0.0",
        "generated_at": "fixture-run",
        "compiler_epoch": "0000000000000000000000000000000000000000",
        "sources": {
            "specific_rubric": "specific-rubric.yaml",
            "generic_skill": "generic-skill.yaml",
            "align": "align.md",
            "companions": list(plan["companions"].keys()),
        },
        "rows": rows,
    }
    (dest / "_meta" / "residue-manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True)
    )
    print(f"freeze ok: {sum(len(v) for v in by_dim.values())} nodes, {len(by_dim)} gates, manifest rows={len(rows)}")
    return 0


# ──────────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="rubric-compiler headless runner (9003 M6a)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan")
    p.add_argument("--inputs", type=Path, default=FIXTURES)
    p.add_argument("--out", type=Path, required=True)

    p = sub.add_parser("generate")
    p.add_argument("--inputs", type=Path, default=FIXTURES)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--item", required=True)
    p.add_argument("--fix", default=None)

    p = sub.add_parser("evaluate")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--evaluator", default="real")

    p = sub.add_parser("loop")
    p.add_argument("--inputs", type=Path, default=FIXTURES)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--evaluator", default="real")
    p.add_argument("--no-epoch-commit", action="store_true")

    p = sub.add_parser("freeze")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--dest", default="staging", choices=["staging", "INTENTS"])
    p.add_argument("--epoch-commit", action="store_true")

    args = parser.parse_args()
    handlers = {
        "plan": cmd_plan,
        "generate": cmd_generate,
        "evaluate": cmd_evaluate,
        "loop": cmd_loop,
        "freeze": cmd_freeze,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
