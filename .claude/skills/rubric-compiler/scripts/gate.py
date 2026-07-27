#!/usr/bin/env python3
"""rubric-compiler deterministic gate (prototype, SPEC v1.2).

Pure code, no model calls. Subcommands:
  epoch      --specs DIR                          -> print spec-epoch hash
  precompile --specs DIR --config DIR --run DIR   -> S1-S3: validate, conflicts, DAG
  item       --run DIR --item ID --phase contract|compiled [--proposal FILE]
  rg         --run DIR                            -> run-level gate

Exit codes: 0 pass, 1 BLOCK/fail, 2 usage/environment error.
BLOCK -> fail; WARN -> recorded in report, never fails.
"""
import argparse, hashlib, json, re, sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("gate.py: PyYAML required (uv pip install pyyaml)", file=sys.stderr)
    sys.exit(2)

EXPERTISE_FALLBACK = [
    "acoustic_feature_analysis", "rules_and_criteria", "best_practice_cookbook",
    "error_case_library", "product_introduction", "operation_manual",
    "dynamic_knowledge_base", "phrase_keyword_library",
]
DEP_RE = re.compile(r"\bitem_\d+\.S\d+\b")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_yaml(p: Path):
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def spec_epoch(specs: Path) -> dict:
    """Content hash over I1-I3 + all pinned companion docs (D5)."""
    parts, files = [], {}
    core = ["rubric.md", "evaluator-skill.md", "align.md"]
    for name in core:
        p = specs / name
        if p.exists():
            files[name] = sha256_file(p)
    manifest = specs / "companion_docs.yaml"
    if manifest.exists():
        files["companion_docs.yaml"] = sha256_file(manifest)
        m = load_yaml(manifest) or {}
        for item, docs in sorted(m.items()):
            for d in docs or []:
                cp = specs / d["path"]
                if cp.exists():
                    files[d["path"]] = sha256_file(cp)
    for k in sorted(files):
        parts.append(f"{k}:{files[k]}")
    return {"epoch": hashlib.sha256("\n".join(parts).encode()).hexdigest(),
            "files": files}


# ---------------------------------------------------------------- precompile
def cmd_precompile(a) -> int:
    specs, run = Path(a.specs), Path(a.run)
    run.mkdir(parents=True, exist_ok=True)
    blocks, report = [], {"halt": False, "conflicts": [], "dispatch_order": [],
                          "held": {}, "simple": [], "shared_extraction": {}}

    # S1: core specs + companion existence / SHA
    for name in ["rubric.md", "evaluator-skill.md", "align.md"]:
        if not (specs / name).exists():
            blocks.append(f"missing spec: {name}")
    manifest = {}
    mp = specs / "companion_docs.yaml"
    if mp.exists():
        manifest = load_yaml(mp) or {}
        for item, docs in manifest.items():
            for d in docs or []:
                cp = specs / d["path"]
                if not cp.exists():
                    blocks.append(f"{item}: companion doc missing: {d['path']}")
                elif d.get("sha256") and sha256_file(cp) != d["sha256"]:
                    blocks.append(f"{item}: SHA mismatch: {d['path']}")

    # parse rubric items
    rubric = specs / "rubric.md"
    items, cur = {}, None
    if rubric.exists():
        for line in rubric.read_text(encoding="utf-8").splitlines():
            m = re.match(r"##\s+(item_\d+)\b", line)
            if m:
                cur = m.group(1); items[cur] = []
            elif cur:
                items[cur].append(line)
    items = {k: "\n".join(v) for k, v in items.items()}
    report["items"] = sorted(items)

    # S2: duplicate trigger/rule IDs with divergent definitions in companions
    seen = {}
    for item, docs in manifest.items():
        for d in docs or []:
            cp = specs / d["path"]
            if not cp.exists():
                continue
            for m in re.finditer(r"^\s*(?:trigger|rule)[_\- ]?id\s*[:=]\s*(\S+)\s*$(?:\n\s*keywords\s*[:=]\s*(.+))?",
                                 cp.read_text(encoding="utf-8"), re.M | re.I):
                tid, kw = m.group(1), (m.group(2) or "").strip()
                if tid in seen and seen[tid][1] != kw:
                    report["conflicts"].append({
                        "id": tid,
                        "definitions": [
                            {"source": seen[tid][0], "keywords": seen[tid][1]},
                            {"source": str(d["path"]), "keywords": kw}]})
                    blocks.append(f"conflicting definitions for {tid} "
                                  f"({seen[tid][0]} vs {d['path']})")
                else:
                    seen[tid] = (str(d["path"]), kw)
    # shared extraction: keyword sets per source (generators never re-read files)
    extraction = {}
    for tid, (src, kw) in seen.items():
        extraction.setdefault(src, {})[tid] = [k.strip() for k in kw.split(",") if k.strip()]
    report["shared_extraction"] = extraction

    # S3: dependency scan -> DAG -> toposort
    deps = {i: set() for i in items}
    for i, text in items.items():
        for m in DEP_RE.finditer(text):
            tgt = m.group(0).split(".")[0]
            if tgt != i:
                deps[i].add(tgt)
        dm = re.search(r"depends_on\s*[:=]\s*\[?([^\]\n]+)", text)
        if dm:
            for t in re.findall(r"item_\d+", dm.group(1)):
                if t != i:
                    deps[i].add(t)
    order, tmp, perm = [], set(), set()

    def visit(n, stack):
        if n in perm:
            return True
        if n in tmp:
            blocks.append("dependency cycle: " + " -> ".join(stack + [n]))
            return False
        tmp.add(n)
        for d in sorted(deps.get(n, ())):
            if d in deps and not visit(d, stack + [n]):
                return False
        tmp.discard(n); perm.add(n); order.append(n)
        return True

    for n in sorted(deps):
        if not visit(n, []):
            break
    report["dispatch_order"] = order
    report["held"] = {i: sorted(d) for i, d in deps.items() if d}
    report["simple"] = [i for i in order
                        if not deps[i] and i not in manifest]

    ep = spec_epoch(specs)
    (run / "spec-epoch.json").write_text(json.dumps(ep, indent=2))
    if blocks:
        report["halt"] = True
        entry = ["", "## PRE-COMPILE HALT (Awaiting Steering)", ""]
        entry += [f"- {b}" for b in blocks]
        for c in report["conflicts"]:
            entry.append(f"- resolution options for {c['id']} "
                         f"(existing source text, choose one):")
            for d in c["definitions"]:
                entry.append(f"    - {d['source']}: `{d['keywords']}`")
        with open(run / "steering.md", "a", encoding="utf-8") as f:
            f.write("\n".join(entry) + "\n")
    (run / "precompile-report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({"halt": report["halt"], "blocks": blocks}, indent=2))
    return 1 if blocks else 0


# ----------------------------------------------------------------- item gate
def _load_config(cfg: Path):
    adjectives = []
    ap = cfg / "auth1-adjectives.txt"
    if ap.exists():
        adjectives = [w.strip().lower() for w in ap.read_text().splitlines()
                      if w.strip() and not w.startswith("#")]
    etypes = EXPERTISE_FALLBACK
    ep = cfg / "expertise-types.yaml"
    if ep.exists():
        etypes = load_yaml(ep) or EXPERTISE_FALLBACK
    frames = []
    fp = cfg / "adversarial-frames.yaml"
    if fp.exists():
        frames = (load_yaml(fp) or {}).get("known_positive_frames", [])
    return adjectives, etypes, frames


def _match(pattern: dict, text: str) -> bool:
    t = text.lower()
    anyk = [k.lower() for k in pattern.get("any", [])]
    nonek = [k.lower() for k in pattern.get("none", [])]
    return (not anyk or any(k in t for k in anyk)) and not any(k in t for k in nonek)


def cmd_item(a) -> int:
    run, cfg = Path(a.run), Path(a.config)
    idir = run / "items" / a.item
    src = Path(a.proposal) if a.proposal else (
        idir / ("compiled.yaml" if a.phase == "compiled" else "contract.yaml"))
    if not src.is_absolute() and not src.exists():
        src = idir / src.name
    if not src.exists():
        print(f"BLOCK: artifact not found: {src}"); return 1
    doc = load_yaml(src) or {}
    adjectives, etypes, frames = _load_config(cfg)
    blocks, warns = [], []

    # G1 schema
    for field in ["item_id", "operationalization", "coverage"]:
        if field not in doc:
            blocks.append(f"G1 schema: missing `{field}`")
    signals = (doc.get("operationalization") or {}).get("signals") or []
    if not signals:
        blocks.append("G1 schema: no signals")
    for s in signals:
        for field in ["id", "description", "checkable", "grounding_refs", "severity_key"]:
            if field not in s:
                blocks.append(f"G1 schema: signal {s.get('id','?')} missing `{field}`")

    # G2 referential integrity
    sev_keys = None
    cal = Path(a.specs) / "calibration-manifest.yaml" if a.specs else None
    if cal and cal.exists():
        sev_keys = set((load_yaml(cal) or {}).get("severity_map", {}).keys())
    for s in signals:
        for g in s.get("grounding_refs", []):
            if g not in etypes:
                blocks.append(f"G2: signal {s.get('id')} grounding_ref `{g}` "
                              f"not an expertise type")
        if sev_keys is not None and s.get("severity_key") not in sev_keys:
            blocks.append(f"G2: signal {s.get('id')} severity_key "
                          f"`{s.get('severity_key')}` not in calibration manifest")
    for cd in doc.get("companion_docs", []) or []:
        cp = Path(a.specs) / cd["path"] if a.specs else None
        if cp and cp.exists() and cd.get("sha256") and sha256_file(cp) != cd["sha256"]:
            blocks.append(f"G2: companion SHA stale: {cd['path']}")

    # G3 coverage entry present
    clauses = (doc.get("coverage") or {}).get("clauses") or []
    if not clauses:
        blocks.append("G3: no coverage entry (Axiom 6)")

    # G4 round bound (contract phase, from disk)
    reviews = sorted(idir.glob("review-r*.md"))
    if a.phase == "contract" and len(reviews) > 3:
        blocks.append(f"G4: {len(reviews)} rounds recorded > R=3")

    # G5 CONFIRMED record (skip for generator pre-submit via --proposal)
    if not a.proposal:
        confirmed = False
        for rv in reviews:
            head = rv.read_text(encoding="utf-8").split("---")
            if len(head) >= 3:
                fm = yaml.safe_load(head[1]) or {}
                if fm.get("verdict") == "CONFIRMED":
                    confirmed = True
        if not confirmed:
            blocks.append("G5: no evaluator CONFIRMED record on disk")

    # GM1 AUTH-1 adjective scan (BLOCK)
    for s in signals:
        desc = str(s.get("description", "")).lower()
        hits = [w for w in adjectives if re.search(rf"\b{re.escape(w)}\b", desc)]
        if hits:
            blocks.append(f"GM1 AUTH-1: signal {s.get('id')} bare adjectives "
                          f"{hits} without observable referent")

    # GM2 checkability structure (BLOCK)
    for s in signals:
        if s.get("checkable") is True:
            if not s.get("gate_pattern"):
                blocks.append(f"GM2: signal {s.get('id')} checkable without gate_pattern")
            if not s.get("audit_result"):
                blocks.append(f"GM2: signal {s.get('id')} missing B-F audit_result")
        if s.get("checkable") is False and s.get("quarantine") != "S2":
            blocks.append(f"GM2: signal {s.get('id')} non-checkable but not S2-quarantined")

    # GM3 gate-logic consistency (BLOCK)
    for s in signals:
        gp = s.get("gate_pattern") or {}
        inter = set(map(str.lower, gp.get("any", []))) & set(map(str.lower, gp.get("none", [])))
        if inter:
            blocks.append(f"GM3: signal {s.get('id')} keyword both required "
                          f"and excluded: {sorted(inter)}")

    # GM4 exclusion-set adversarial test (WARN) — S5 templated cases
    for s in signals:
        gp = s.get("gate_pattern") or {}
        pos = gp.get("any", [])
        for excl in gp.get("none", []):
            for frame in frames:
                if pos:
                    case = frame.format(P=f"{excl} {pos[0]}")
                    if not _match(gp, case):
                        warns.append(f"GM4: signal {s.get('id')} exclusion "
                                     f"`{excl}` suppresses known-positive frame")
            if not _match(gp, excl):
                pass  # exclusion alone correctly suppressed
            else:
                warns.append(f"GM4: signal {s.get('id')} exclusion `{excl}` "
                             f"alone still fires")

    # GM5 trigger completeness (WARN)
    pre = run / "precompile-report.json"
    if pre.exists():
        extraction = (json.loads(pre.read_text()) or {}).get("shared_extraction", {})
        declared = set(map(str.lower, doc.get("trigger_keywords", []) or []))
        expected = {k.lower() for kws in extraction.values()
                    for lst in kws.values() for k in lst}
        for cd in doc.get("companion_docs", []) or []:
            missing = {k.lower() for kws in [extraction.get(cd["path"], {})]
                       for lst in kws.values() for k in lst} - declared
            if missing:
                warns.append(f"GM5: trigger_keywords missing {sorted(missing)} "
                             f"from {cd['path']}")

    # GM6 signal coverage (WARN)
    sig_ids = {s.get("id") for s in signals}
    for c in clauses:
        if not c.get("signal_ids"):
            warns.append(f"GM6: clause `{str(c.get('clause',''))[:50]}` has no signal")
        for sid in c.get("signal_ids", []):
            if sid not in sig_ids:
                blocks.append(f"GM6: clause references unknown signal {sid}")

    warns = list(dict.fromkeys(warns))  # dedupe, order-preserving
    rep = {"item": a.item, "phase": a.phase, "blocks": blocks, "warns": warns,
           "pass": not blocks}
    idir.mkdir(parents=True, exist_ok=True)
    (idir / "gate-report.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))
    return 0 if not blocks else 1


# ------------------------------------------------------------------- run gate
def cmd_rg(a) -> int:
    run = Path(a.run)
    blocks, warns = [], []
    locked, all_signals, covered = {}, {}, set()
    for idir in sorted((run / "items").glob("item_*")):
        gr = idir / "gate-report.json"
        c = idir / "contract.yaml"
        if gr.exists() and json.loads(gr.read_text()).get("pass") and c.exists():
            doc = load_yaml(c) or {}
            sigs = (doc.get("operationalization") or {}).get("signals") or []
            locked[idir.name] = {s["id"] for s in sigs if "id" in s}
            for s in sigs:
                all_signals[f"{idir.name}.{s.get('id')}"] = s
            for cl in (doc.get("coverage") or {}).get("clauses", []):
                for sid in cl.get("signal_ids", []):
                    covered.add(f"{idir.name}.{sid}")
            for dep in doc.get("depends_on", []) or []:
                for m in DEP_RE.finditer(str(doc)):
                    it, sid = m.group(0).split(".")
                    if it in locked and sid not in locked[it]:
                        blocks.append(f"RG cross-item: {idir.name} refs "
                                      f"{it}.{sid} not among locked IDs")
    # orphan signals
    for key in all_signals:
        if key not in covered:
            warns.append(f"RG orphan signal: {key} not referenced by any clause")
    # residue completeness
    rm = run / "residue-manifest.yaml"
    residue = (load_yaml(rm) or {}) if rm.exists() else {}
    entries = {e.get("item") for e in residue.get("entries", [])} if residue else set()
    for item, sids in locked.items():
        lossy = any(all_signals[f"{item}.{s}"].get("checkable") is False
                    for s in sids if f"{item}.{s}" in all_signals)
        if lossy and item not in entries:
            blocks.append(f"RG residue: {item} has quarantined signals but no "
                          f"residue-manifest entry")
    rep = {"blocks": blocks, "warns": warns, "pass": not blocks,
           "gated_items": sorted(locked)}
    (run / "rg-report.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))
    return 0 if not blocks else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("epoch"); e.add_argument("--specs", required=True)
    p = sub.add_parser("precompile")
    p.add_argument("--specs", required=True); p.add_argument("--config", default="config")
    p.add_argument("--run", required=True)
    i = sub.add_parser("item")
    i.add_argument("--run", required=True); i.add_argument("--item", required=True)
    i.add_argument("--phase", choices=["contract", "compiled"], default="contract")
    i.add_argument("--proposal"); i.add_argument("--config", default="config")
    i.add_argument("--specs")
    r = sub.add_parser("rg"); r.add_argument("--run", required=True)
    a = ap.parse_args()
    if a.cmd == "epoch":
        print(json.dumps(spec_epoch(Path(a.specs)), indent=2)); return 0
    return {"precompile": cmd_precompile, "item": cmd_item, "rg": cmd_rg}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
