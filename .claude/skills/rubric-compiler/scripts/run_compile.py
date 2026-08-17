#!/usr/bin/env python3
"""Headless runner for the rubric-compiler skill (9003 M6a).

Deterministic orchestration of the 9003 compile loop (Planner → Generator →
Evaluator → freeze) over the compiler's inputs. Round-3 decision 1: the
M1–M5 deterministic core (`argus.core.compiler`) is the loop's backbone —
every emitted node IS the core's derivation, stored verbatim. The
`--evaluator mock` flag stays accepted for backward compatibility with the
acceptance tests, but both modes run the same deterministic real-core path
(no template path anymore).

Never writes through the INTENTS symlink unless `freeze --dest INTENTS` is
explicit; never commits an epoch unless `--epoch-commit` is given.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]  # scripts/ → rubric-compiler/ → skills/ → .claude/ → repo
FIXTURES = REPO_ROOT / ".claude" / "skills" / "rubric-compiler" / "fixtures"

# --- sys.path bootstrap (mirrors tests/conftest.py) -------------------------
try:  # pragma: no cover
    import argus  # noqa: F401
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(REPO_ROOT / "src"))

# --- core availability gate (M6a Requires: M5) ------------------------------
try:
    from argus.core.compiler.agreement import (  # M4
        seed_agreement_gate,
        set_deduction_weight,
        set_iteration_policy,
    )
    from argus.core.compiler.bridge import (  # M5
        bind_item_to_dimension,
        check_dimension_coverage,
        compile_applicability_gate,
        extract_values,
        synthesize_hard_fail,
    )
    from argus.core.compiler.classify import (  # M3
        assign_escape_tier,
        classify_corroborators,
        classify_gap,
        declare_residue,
    )
    from argus.core.compiler.signals import (  # M2
        assign_facets,
        audit_gate_checkable,
        decompose_signals,
    )
    from argus.core.compiler.validator import (  # M1
        check_calibration_coverage,
        check_depends_on,
        check_edited_consistency,
        check_exclusion_set_adversarial,
        check_manifest_present,
        check_no_forced_mapping,
        validate_node,
    )

    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False

# --- manifest channel import (M7: independent — ungated, io layer only) -----
try:
    from argus.io.calibration_io import apply_manifest_epoch, load_manifest

    MANIFEST_IO_AVAILABLE = True
except ImportError:  # pragma: no cover
    MANIFEST_IO_AVAILABLE = False

REMEDIATION = (
    "M6a Requires: M5 — argus.core.compiler is not landed yet. "
    "Land M1–M5 first; the runner has no template fallback."
)

CONFLICT_LINE_RE = re.compile(r"^(T\d+)\s*:\s*(.+?)\s*(?:#.*)?$")


def _external_head_sha() -> str:
    """The external INTENTS tree's pinned epoch — the value a run stamps.

    Resolves the repo's INTENTS symlink. EPOCH.yaml is the single source of
    truth for the pin (I4 — its own comment: "Consumers pin this SHA in
    argus.intents_sha"): return its `epoch` field when it is a non-empty,
    non-all-zero 40-hex string — the content baseline, not the metadata
    stamp commit. Otherwise fall back to the tree's git HEAD; on any
    failure — missing or dangling symlink, bad yaml, git error, timeout —
    return "staging", a clear non-zero marker: the zero placeholder must
    never appear in output again (9003 round-3 d3).
    """
    tree = REPO_ROOT / "INTENTS"
    try:
        resolved = tree.resolve(strict=True)
        epoch_file = resolved / "EPOCH.yaml"
        if epoch_file.is_file():
            declared = yaml.safe_load(epoch_file.read_text())
            if isinstance(declared, dict):
                epoch = declared.get("epoch")
                if (
                    isinstance(epoch, str)
                    and re.fullmatch(r"[0-9a-fA-F]{40}", epoch)
                    and epoch != "0" * 40
                ):
                    return epoch
        result = subprocess.run(
            ["git", "-C", str(resolved), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        sha = result.stdout.strip()
        if result.returncode == 0 and sha:
            return sha
    except (OSError, ValueError, yaml.YAMLError, subprocess.SubprocessError):
        pass
    return "staging"


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
    """Kahn's algorithm over depends_on (S3). A depends_on ref to an item
    that does not exist is reported as an unknown prerequisite (W4), never
    mislabeled as a cycle; a true cycle → raise."""
    deps = {it["id"]: list(it.get("depends_on", [])) for it in items}
    known = set(deps)
    for item_id, item_deps in deps.items():
        for prerequisite in item_deps:
            if prerequisite not in known:
                raise ValueError(f"unknown prerequisite {prerequisite} of item {item_id}")
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
    # F4(c): the plan command must work on a fresh out dir.
    args.out.mkdir(parents=True, exist_ok=True)
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
            "resolution": "CONFLICT — human adjudication required (patch-2 S2) — "
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
        "items": items,
    }
    (args.out / "compile-plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False))
    print(f"plan ok: {len(order)} items, batches simple={simple}")
    return 0


# ──────────────────────────────────────────────────────────────────────────
# Generator (real core chain: M1–M5 outputs stored verbatim in the node)
# ──────────────────────────────────────────────────────────────────────────


def build_node(item: dict[str, Any], dim: str, plan: dict[str, Any]) -> dict[str, Any]:
    """AuthoredNode construction over the M1–M5 pure core (round-3 decision
    1): every judgment-layer field IS the corresponding core function's
    output, stored verbatim. Deterministic — no model call, no clock, no RNG
    (I1 quarantine)."""
    item_id = item["id"]
    signals = decompose_signals(item)  # M2 — rejected entries stay informational
    gap = classify_gap(item, dim, signals)  # M3
    gap_type = gap["gap_type"]
    facets = assign_facets(signals, gap_type)  # M2
    residue = declare_residue(signals, dim)  # M3
    agreement = seed_agreement_gate({"id": f"C{item_id}"})  # M4
    deduction = set_deduction_weight(item, dim)  # M4
    # manifest_epoch None for fixture runs: no manifest exists yet, so
    # auto-final is withheld on surface-form criteria (AUTH-9) and the
    # severity_map ref stays null.
    binding = bind_item_to_dimension(item, plan["align"], None)  # M5
    gate = compile_applicability_gate(item)  # M5
    deps = item.get("depends_on", [])
    if deps:
        gate = {"refs": [f"{d}-S01" for d in deps], **(gate or {})}  # S3 order
    candidates = [
        signal
        for lane in ("fail", "excellence")
        for signal in (signals.get(lane) or [])
        if isinstance(signal, dict)
    ]
    corroborators = [
        c
        for c in classify_corroborators({"id": f"C{item_id}"}, candidates)  # M3
        if isinstance(c.get("node_ref"), str)
    ]
    escape_tier = assign_escape_tier(gap_type)  # M3
    companion_docs = None
    if item.get("companion_docs"):
        companion_docs = [
            {
                "document": cd["document"],
                "role": cd["role"],
                "sha256": plan["companions"][cd["document"]]["sha256"],  # S1 pin
            }
            for cd in item["companion_docs"]
        ]
    return {
        "node_id": f"item-{item_id}",
        "category": "judgment",
        "intents_path": f"/_rubric/rules_criteria/{dim}/item-{item_id}.yaml",
        "intents_sha": _external_head_sha(),
        "layer": "judgment",
        "required_evidence": {},
        "fail_condition": {},
        "deduction": deduction,
        "authored_by": "rubric-compiler (9003 core)",
        "dimension": dim,
        "human_version": {
            "item_number": int(item_id),
            "text": item["text"],
            "na_condition": item.get("na_condition"),
        },
        "machine_criterion": {
            "criterion_id": f"C{item_id}",
            "description": item["pass_standard"],
            "scoring_scale": "1-10",
            "gap_type": gap_type,
            "auto_final_allowed": binding["auto_final_allowed"],  # AUTH-9
            "escape_tier": escape_tier,
        },
        "signals": {"fail": signals["fail"], "excellence": signals["excellence"]},
        "facets": facets,
        "corroborators": corroborators,
        "gap_rationale": gap["rationale"],
        "residue_declared": residue,
        "agreement": agreement,
        "applicability_gate": gate,
        "severity_map": binding["severity_map"],
        "data_dependency": None,
        "gap_type": gap_type,
        "escape_tier": escape_tier,
        "iteration_policy": set_iteration_policy({"id": f"C{item_id}"}),  # M4
        "companion_docs": companion_docs,
        "depends_on": deps,
        "values_extracted": extract_values(item),  # M5 — informational
    }


def cmd_generate(args: argparse.Namespace) -> int:
    # F2: generate runs the pure core — gate it on M5 like the loop.
    if not CORE_AVAILABLE:
        print(REMEDIATION)
        return 2
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
        # Coverage gap (Item 24 pattern): no node; the M5 coverage verdict's
        # row — WITH its data_dependency — lands in the run's coverage rows.
        # F6: a row for an item already present replaces the old one (dedupe
        # by source_items) — standalone generate never accumulates duplicates.
        coverage = check_dimension_coverage(item, mapping, sorted(inputs["dims"]))
        gap = dict(coverage["manifest_row"] or {})
        if coverage["data_dependency"] is not None:
            gap["data_dependency"] = coverage["data_dependency"]
        gaps_file = args.out / "coverage-gaps.jsonl"
        kept: list[str] = []
        if gaps_file.exists():
            for line in gaps_file.read_text().splitlines():
                if not line.strip():
                    continue
                existing = json.loads(line)
                if args.item in (existing.get("source_items") or []):
                    continue  # replaced by the new row below
                kept.append(line)
        kept.append(json.dumps(gap, ensure_ascii=False))
        gaps_file.write_text("\n".join(kept) + "\n")
        print(f"item {args.item}: coverage gap — no node emitted")
        return 0
    node = build_node(item, dim, plan)
    if getattr(args, "fix", None):
        fix = json.loads(args.fix)
        # Targeted fix (W2): after the edit, the signal's checkability is
        # re-audited — audit_result and checkable are recomputed from the
        # edited description (single source of truth, M2 B4/F4).
        matched = False
        for lane in ("fail", "excellence"):
            for s in node["signals"][lane]:
                if s["id"] == fix.get("signal_id"):
                    s[fix["field"]] = fix["suggested_fix"]
                    s["audit_result"] = audit_gate_checkable(s)
                    s["checkable"] = s["audit_result"] != "model_only"
                    matched = True
        # F5: a fix naming a signal the item does not carry is an error,
        # never a silent no-op.
        if not matched:
            print(f"error: unknown signal id {fix.get('signal_id')} for item {args.item}")
            return 2
    (nodes_dir / f"item-{args.item}.json").write_text(json.dumps(node, indent=2, ensure_ascii=False))
    return 0


# ──────────────────────────────────────────────────────────────────────────
# Evaluator (real validator + context checks — the M1 F9 closure)
# ──────────────────────────────────────────────────────────────────────────


def _is_lossy(node: dict[str, Any]) -> bool:
    """A compile is LOSY when the item's emitted signals carry a model_based
    (checkable False) signal that is not one of the compiler's declared
    fallback templates. The fallbacks — "model-judged evidence ... (unmatched
    standard)", "... (adjective standard)", and the generic "model-judged
    excellence evidence" — are structural completeness markers; a model_based
    signal beyond them (like the pass-standard quality evidence) is genuine
    compile residue the manifest must name."""
    for lane in ("fail", "excellence"):
        for signal in (node.get("signals") or {}).get(lane) or []:
            if not signal.get("checkable"):
                description = str(signal.get("description") or "")
                if description.startswith("model-judged"):
                    continue
                return True
    return False


def assemble_manifest(args: argparse.Namespace) -> dict[str, Any]:
    """The provisional residue manifest: schema envelope plus the run's
    coverage rows (including each gap row's data_dependency) and — M8 pilot
    gap closure — a within_dimension residue row for every lossy item,
    naming exactly the residue its node declared, routed to human review."""
    plan = json.loads((args.out / "compile-plan.json").read_text())
    rows: list[dict[str, Any]] = []
    gaps_file = args.out / "coverage-gaps.jsonl"
    if gaps_file.exists():
        rows += [json.loads(line) for line in gaps_file.read_text().splitlines() if line.strip()]
    nodes_dir = args.out / "nodes"
    if nodes_dir.is_dir():
        for path in sorted(nodes_dir.glob("item-*.json")):
            node = json.loads(path.read_text())
            if not _is_lossy(node):
                continue
            node_id = str(node.get("node_id") or path.stem)
            rows.append(
                {
                    "kind": "within_dimension",
                    "dimension": node.get("dimension"),
                    "source_items": [node_id.removeprefix("item-")],
                    "compiled_to": [node_id],
                    "left_behind": node.get("residue_declared"),
                    "disposition": "human_review",
                }
            )
    return {
        "schema_version": "1.0.0",
        "generated_at": "fixture-run",
        "compiler_epoch": _external_head_sha(),
        "sources": {
            "specific_rubric": "specific-rubric.yaml",
            "generic_skill": "generic-skill.yaml",
            "align": "align.md",
            "companions": list(plan.get("companions", {}).keys()),
        },
        "rows": rows,
    }


def sibling_context(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The run's nodes as sibling context for the D8/S3 checks. Node identity
    follows the depends_on reference convention: depends_on carries bare item
    ids while node_id is the item-prefixed filename form, so the context
    projects node_id onto the item id — a depends_on ref must still name a
    real sibling, and every signal ref still resolves to a real signal."""
    out: list[dict[str, Any]] = []
    for node in nodes:
        sibling = dict(node)
        node_id = sibling.get("node_id")
        if isinstance(node_id, str) and node_id.startswith("item-"):
            sibling["node_id"] = node_id.removeprefix("item-")
        out.append(sibling)
    return out


def evaluate_run(
    nodes: list[dict[str, Any]], manifest: dict[str, Any], align_map: dict[str, Any]
) -> list[dict[str, Any]]:
    """The real quality gate (F9 closure): M1 validate_node on every node plus
    the context checks (AUTH-5/9/10, S3, D8) and S5 adversarial exclusion-set
    flags (warn-level, non-blocking)."""
    findings: list[dict[str, Any]] = []
    siblings = sibling_context(nodes)
    for node in nodes:
        node_id = node["node_id"]
        for error in validate_node(node):
            findings.append({"node": node_id, "issue": error, "severity": "block"})
        for error in check_calibration_coverage(node, manifest):
            findings.append({"node": node_id, "issue": error, "severity": "block"})
        for error in check_no_forced_mapping(node, align_map):
            findings.append({"node": node_id, "issue": error, "severity": "block"})
        for error in check_depends_on(node, siblings):
            findings.append({"node": node_id, "issue": error, "severity": "block"})
        for error in check_edited_consistency(node, siblings):
            findings.append({"node": node_id, "issue": error, "severity": "block"})
        for lane in ("fail", "excellence"):
            for signal in (node.get("signals") or {}).get(lane) or []:
                for warning in check_exclusion_set_adversarial(signal):
                    findings.append({"node": node_id, "issue": warning, "severity": "warn"})
    for error in check_manifest_present(manifest, nodes):
        findings.append({"node": "run", "issue": error, "severity": "block"})
    return findings


def cmd_evaluate(args: argparse.Namespace) -> int:
    # F2: evaluate runs the M1 validator — gate it on M5 like the loop.
    if not CORE_AVAILABLE:
        print(REMEDIATION)
        return 2
    nodes = [json.loads(p.read_text()) for p in sorted((args.out / "nodes").glob("item-*.json"))]
    if not nodes:
        print("no nodes to evaluate")
        return 2
    plan = json.loads((args.out / "compile-plan.json").read_text())
    # Both `--evaluator mock` and real mode run the same deterministic
    # real-core path (round-3 decision 1); the flag is backward compat.
    findings = evaluate_run(nodes, assemble_manifest(args), plan.get("align", {}))
    (args.out / "evaluation.json").write_text(json.dumps(findings, indent=2, ensure_ascii=False))
    if findings:
        for f in findings:
            print(f"{f['severity']}: {f['node']} — {f['issue']}")
        return 1
    print("evaluate: CONFIRMED")
    return 0


# ──────────────────────────────────────────────────────────────────────────
# Loop (plan → generate → provisional manifest → evaluate → ≤3 fix rounds →
# freeze)
# ──────────────────────────────────────────────────────────────────────────


def cmd_loop(args: argparse.Namespace) -> int:
    # B1: the M6a Requires: M5 gate applies to BOTH evaluator modes — the
    # mock path IS the real path (round-3 decision 1), so no mode runs
    # without the core.
    if not CORE_AVAILABLE:
        print(REMEDIATION)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    # W3: the run's coverage rows are rebuilt each run — truncate any
    # previous run's rows so re-running into the same out dir never
    # duplicates gap rows.
    (args.out / "coverage-gaps.jsonl").write_text("")
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
                "rationale": "core chain: decompose_signals → classify_gap → assign_facets "
                "→ declare_residue → seed_agreement_gate → bridge (M1-M5)",
            }
        )

    # The provisional manifest is assembled after generate, before evaluate
    # (AUTH-5 — no compile run without a residue manifest).
    manifest = assemble_manifest(args)
    if manifest.get("rows"):
        print(f"provisional manifest: {len(manifest['rows'])} residue row(s)")

    for round_no in range(1, 4):
        rc = cmd_evaluate(args)
        if rc == 0:
            break
        findings = json.loads((args.out / "evaluation.json").read_text())
        blocks = [f for f in findings if f["severity"] == "block"]
        if not blocks:
            break
        # Targeted fixes via the Generator role (deterministic core — fixes
        # only apply when validator findings appear).
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
    raw_items = plan.get("items", [])
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

    # Per-dimension hard-fail gates synthesized by M5 (never copied; a
    # dimension with fewer than two bound items gets no synthesized gate).
    for dim, nodes in by_dim.items():
        dim_items = [it for it in raw_items if plan.get("align", {}).get(it["id"]) == dim]
        rule = synthesize_hard_fail(dim_items, dim)
        if rule is None:
            continue
        (dest / "_rubric" / "gates" / f"{dim}.yaml").write_text(
            "edited_by_human: false\n"
            + yaml.safe_dump(
                {"dimension": dim, "hard_fail_rule": rule},
                sort_keys=False,
                allow_unicode=True,
            )
        )

    manifest = assemble_manifest(args)
    # JSON content under the .yaml path: the M6a acceptance contract reads the
    # manifest with json.loads (the path is the contract, the payload is JSON).
    (dest / "_meta" / "residue-manifest.yaml").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )
    print(f"freeze ok: {sum(len(v) for v in by_dim.values())} nodes, {len(by_dim)} gates, manifest rows={len(manifest['rows'])}")
    return 0


# ──────────────────────────────────────────────────────────────────────────
# Manifest inject (M7: independent calibration channel — never a compile run)
# ──────────────────────────────────────────────────────────────────────────


def cmd_manifest_inject(args: argparse.Namespace) -> int:
    # M7 (round-3 Q8): the manifest is injected ALONE — the compiler inputs
    # are untouched, and no M1–M5 core gate applies (loading/injecting needs
    # only the io layer). The loop's nodes are re-anchored, never recompiled.
    if not MANIFEST_IO_AVAILABLE:
        print("error: argus.io.calibration_io is not importable")
        return 2
    manifest = load_manifest(args.manifest_file)  # ValueError/YAMLError → main() boundary
    paths = sorted((args.out / "nodes").glob("item-*.json"))
    if not paths:
        print("no nodes to inject")
        return 2
    nodes = [json.loads(p.read_text()) for p in paths]
    updated = apply_manifest_epoch(nodes, manifest)
    for path, node in zip(paths, updated, strict=True):
        path.write_text(json.dumps(node, indent=2, ensure_ascii=False))
    print(f"manifest inject ok: {len(updated)} nodes re-anchored to {manifest.epoch_id}")
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
    p.add_argument("--inputs", type=Path, default=FIXTURES)
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

    p = sub.add_parser("manifest")
    msub = p.add_subparsers(dest="manifest_command", required=True)
    pinject = msub.add_parser("inject")
    pinject.add_argument("manifest_file", type=Path)
    pinject.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()
    handlers = {
        "plan": cmd_plan,
        "generate": cmd_generate,
        "evaluate": cmd_evaluate,
        "loop": cmd_loop,
        "freeze": cmd_freeze,
        "manifest": cmd_manifest_inject,
    }
    # B2/F1: exception boundary — missing/malformed inputs, unwritable out
    # dirs, malformed --fix JSON, and garbage plan/node/gap-row payloads all
    # exit with a clean one-line error, never a traceback. (Conflict, cycle,
    # and missing-companion paths already return 2 cleanly.)
    try:
        return handlers[args.command](args)
    except (OSError, yaml.YAMLError, ValueError, AttributeError) as e:
        print(f"error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
