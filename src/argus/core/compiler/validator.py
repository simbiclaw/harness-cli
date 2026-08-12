"""M1 validator — the ten AUTH prohibitions plus the patch-2 checks (9003).

Each check is a discrete pure function returning a list of error strings
(empty list = pass). Context-dependent checks (manifest, align_map,
siblings, sources) take their context as arguments — the Planner/
orchestrator invokes them; `validate_node` aggregates the node-only
checks, which is the runner's contract.

Purity (I1 quarantine): this module imports only stdlib and the types
layer. No model client, no clock, no RNG, no I/O — the AUTH prohibitions
are deterministic functions of their inputs.

Reference: docs/exec-plans/active/9003-implement-soft-criteria-compiler.md
           docs/retrospectives/soft-criteria-authoring-spec-v4-patch-2.md
"""

from __future__ import annotations

from argus.types.compiler_schemas import AuthoredNode

# ── AUTH-1: evaluative adjectives that name no observable referent ───────────
# Patch-2 S6 list: an adjective is only admissible when the description
# points at what a gate could actually verify (a named phrase, a pattern).

_ADJECTIVES = (
    # Chinese (patch-2 S6)
    "灵活",
    "积极",
    "混乱",
    "清晰",
    "死板",
    "主动",
    "耐心",
    "认真",
    # English (patch-2 S6)
    "substantive",
    "engaged",
    "adapted",
    "enthusiastic",
    "proactive",
    "flexible",
)

_REFERENT_MARKERS = (
    "named phrase",
    "contains",
    "transcript",
    "pattern",
    "appears",
    "quoted",
    "出现",
    "包含",
    "短语",
    "文本",
)


def _names_concrete_referent(description: str) -> bool:
    """A description names an observable referent when it points at a quoted
    span or a phrase/pattern artifact the gate can locate in the transcript."""
    if any(q in description for q in ('"', "「", "」", "『", "』")):
        return True
    return any(marker in description for marker in _REFERENT_MARKERS)


def check_no_adjective_signals(node: dict) -> list[str]:
    """AUTH-1: reject signals described with evaluative adjectives that carry
    no concrete referent ("坐席表现灵活" without naming the observable)."""
    errors: list[str] = []
    signals = node.get("signals") or {}
    for lane in ("fail", "excellence"):
        for signal in signals.get(lane) or []:
            description = (signal or {}).get("description") or ""
            for adjective in _ADJECTIVES:
                if adjective in description and not _names_concrete_referent(description):
                    signal_id = (signal or {}).get("id") or "?"
                    errors.append(
                        f"AUTH-1: signal {signal_id} description uses evaluative adjective "
                        f"{adjective!r} without a concrete referent"
                    )
                    break  # one error per signal
    return errors


# ── AUTH-2: residue must be declared ─────────────────────────────────────────


def check_residue_declared(node: dict) -> list[str]:
    """AUTH-2: a judgment-layer node must declare what it cannot capture —
    the lossy-projection ledger needs a ground-truth residue statement."""
    residue = node.get("residue_declared")
    if not isinstance(residue, str) or residue.strip() == "":
        return [
            "AUTH-2: judgment-layer node must declare residue_declared (a non-empty "
            "statement of what this rule cannot capture)"
        ]
    return []


# ── AUTH-3: agreement gate (tau + kappa_sample_plan) ─────────────────────────


def check_agreement_gate(node: dict) -> list[str]:
    """AUTH-3: the agreement block must carry both an initial tau and a
    rolling-sample plan — no ungated soft entry."""
    agreement = node.get("agreement")
    if not isinstance(agreement, dict):
        return ["AUTH-3: judgment-layer node requires an agreement block (tau + kappa_sample_plan)"]
    errors: list[str] = []
    if agreement.get("tau") is None:
        errors.append("AUTH-3: agreement.tau must be set")
    kappa_plan = agreement.get("kappa_sample_plan")
    if not isinstance(kappa_plan, str) or kappa_plan.strip() == "":
        errors.append("AUTH-3: agreement.kappa_sample_plan must be a non-empty rolling-sample plan")
    return errors


# ── AUTH-4: no redundant corroborator (incl. D16) ────────────────────────────

_RUBRIC_REF_PREFIXES = ("_rubric/evidence/acoustic/", "_rubric/evidence/phrase-keyword/")


def check_no_redundant_corroborator(node: dict) -> list[str]:
    """AUTH-4: reject soft⊕soft corroboration — redundant-class signals
    corroborate nothing (D5), and framework/lexicon refs are rubric, not
    corroborators (D16)."""
    errors: list[str] = []
    for corroborator in node.get("corroborators") or []:
        if not isinstance(corroborator, dict):
            errors.append("AUTH-4: malformed corroborator entry (must be a dict)")
            continue
        ref = corroborator.get("node_ref") or ""
        if corroborator.get("independence_class") == "redundant":
            errors.append(
                f"AUTH-4: corroborator {ref!r} is redundant-class — redundant signals "
                "corroborate nothing (D5)"
            )
        if ref.startswith(_RUBRIC_REF_PREFIXES):
            errors.append(
                f"AUTH-4: corroborator {ref!r} points into the rubric (acoustic framework / "
                "phrase lexicon are rubric, not corroborating signals — D16)"
            )
    return errors


# ── AUTH-5: no compile run without a residue manifest ────────────────────────


def check_manifest_present(manifest: dict | None, nodes: list[dict]) -> list[str]:
    """AUTH-5: a run that emits nodes must also emit the residue manifest —
    lossy projections would otherwise go unrecorded."""
    if manifest is None:
        return ["AUTH-5: compile run emitted nodes without a residue manifest"]
    return []


# ── AUTH-6: escape plan required ─────────────────────────────────────────────


def check_escape_plan(node: dict) -> list[str]:
    """AUTH-6: the agreement block must carry an escape sample plan and an
    escape ceiling — soft entries need a bounded human-review escape hatch."""
    agreement = node.get("agreement")
    if not isinstance(agreement, dict):
        return ["AUTH-6: escape plan requires an agreement block"]
    errors: list[str] = []
    sample_plan = agreement.get("escape_sample_plan")
    if not isinstance(sample_plan, str) or sample_plan.strip() == "":
        errors.append("AUTH-6: agreement.escape_sample_plan must be a non-empty sample plan")
    if agreement.get("escape_ceiling") is None:
        errors.append("AUTH-6: agreement.escape_ceiling must be set")
    return errors


# ── AUTH-7: NA-carrying item needs an applicability gate ─────────────────────


def check_applicability_gate(node: dict) -> list[str]:
    """AUTH-7: an item with a non-empty na_condition must carry a compiled
    applicability_gate — NA must be gateable, not silently scoped away."""
    human_version = node.get("human_version")
    na_condition = human_version.get("na_condition") if isinstance(human_version, dict) else None
    if isinstance(na_condition, str) and na_condition.strip():
        if node.get("applicability_gate") is None:
            return [
                "AUTH-7: item with a non-empty na_condition must carry an applicability_gate "
                "describing when the rule applies"
            ]
    return []


# ── AUTH-8: data dependency declaration ──────────────────────────────────────


def check_data_dependency(node: dict) -> list[str]:
    """AUTH-8: a declared data dependency must carry connected + disposition,
    and a disconnected source must defer — no silent bypass."""
    dependency = node.get("data_dependency")
    if dependency is None:
        return []
    if not isinstance(dependency, dict):
        return ["AUTH-8: data_dependency must be a dict with connected + disposition"]
    errors: list[str] = []
    if "connected" not in dependency:
        errors.append("AUTH-8: data_dependency must declare connected")
    if "disposition" not in dependency:
        errors.append("AUTH-8: data_dependency must declare disposition")
    disposition = dependency.get("disposition") or ""
    if dependency.get("connected") is False and "defer" not in disposition:
        errors.append(
            "AUTH-8: data_dependency connected=false must carry a defer disposition "
            "(no silent bypass while the source is disconnected)"
        )
    return errors


# ── AUTH-9: no auto-final on uncalibrated surface-form criterion ─────────────


def check_calibration_coverage(node: dict, manifest: dict | None) -> list[str]:
    """AUTH-9: a calibration_surface_form criterion may permit auto-final only
    when the calibration manifest covers its failure surface. Criterion id is
    the last segment of severity_map (…/severity/21 → "21")."""
    criterion = node.get("machine_criterion")
    if not isinstance(criterion, dict) or node.get("gap_type") != "calibration_surface_form":
        return []
    if criterion.get("auto_final_allowed") is not True:
        return []
    severity_map = node.get("severity_map")
    if not isinstance(severity_map, str) or not severity_map:
        return [
            "AUTH-9: calibration_surface_form criterion with auto_final needs a severity_map "
            "ref to prove manifest coverage"
        ]
    criterion_id = severity_map.rsplit("/", 1)[-1]
    covered = manifest.get("covered_criteria") if isinstance(manifest, dict) else None
    if covered is None or criterion_id not in covered:
        return [
            f"AUTH-9: calibration criterion {criterion_id} allows auto-final but is not "
            "covered by the calibration manifest"
        ]
    return []


# ── AUTH-10: no forced mapping ───────────────────────────────────────────────


def check_no_forced_mapping(node: dict, align_map: dict[str, str | None] | None) -> list[str]:
    """AUTH-10: no item with no adequate dimension in align.md may be forced
    into a nearest dimension — silent miscoding is worse than honest defer."""
    errors: list[str] = []
    mapping = align_map or {}
    for item in node.get("source_binary_items") or []:
        if mapping.get(item) is None:
            errors.append(
                f"AUTH-10: source item {item!r} has no adequate dimension in align.md but was "
                f"forced into {node.get('dimension')!r}"
            )
    return errors


# ── S1: companion docs carry pinned SHA + role ───────────────────────────────


def check_companion_docs(node: dict) -> list[str]:
    """S1: every companion_docs entry must pin document, role, and sha256 —
    compile inputs are reproducible only when the exact text is identifiable."""
    docs = node.get("companion_docs")
    if not docs:
        return []
    errors: list[str] = []
    for entry in docs:
        if not isinstance(entry, dict):
            errors.append("S1: companion_docs entry must be a dict")
            continue
        for key in ("document", "role", "sha256"):
            if not isinstance(entry.get(key), str) or entry[key].strip() == "":
                errors.append(f"S1: companion_docs entry missing non-empty {key}")
    return errors


# ── S3: depends_on refs resolve to sibling signals ───────────────────────────


def _sibling_fail_signal_ids(siblings: list[dict]) -> set[str]:
    """Collect every fail-signal id across the sibling nodes."""
    ids: set[str] = set()
    for sibling in siblings:
        for signal in (sibling.get("signals") or {}).get("fail") or []:
            signal_id = signal.get("id") if isinstance(signal, dict) else None
            if signal_id:
                ids.add(signal_id)
    return ids


def check_depends_on(node: dict, siblings: list[dict]) -> list[str]:
    """S3: applicability_gate refs and depends_on prerequisites must resolve to
    a signal id that actually exists in a sibling node's fail signals."""
    errors: list[str] = []
    sibling_ids = _sibling_fail_signal_ids(siblings)
    gate = node.get("applicability_gate")
    for ref in (gate.get("refs") if isinstance(gate, dict) else None) or []:
        if ref not in sibling_ids:
            errors.append(
                f"S3: applicability_gate ref {ref!r} does not resolve to a sibling fail-signal id"
            )
    for dependency in node.get("depends_on") or []:
        expected = f"{dependency}-S01"
        if expected not in sibling_ids:
            errors.append(
                f"S3: depends_on item {dependency!r} — signal {expected!r} missing from "
                "sibling fail-signals"
            )
    return errors


# ── S4: no implicit checkability claims ──────────────────────────────────────


def check_checkable_audited(node: dict) -> list[str]:
    """S4: every signal must carry an explicit checkable + audit_result —
    checkability may not be implied (B-F audit outcome: pass / split /
    model_only)."""
    errors: list[str] = []
    signals = node.get("signals") or {}
    for lane in ("fail", "excellence"):
        for signal in signals.get(lane) or []:
            if not isinstance(signal, dict):
                errors.append(f"S4: {lane} signal entry must be a dict")
                continue
            missing = [key for key in ("checkable", "audit_result") if key not in signal]
            if missing:
                signal_id = signal.get("id") or "?"
                errors.append(
                    f"S4: signal {signal_id} carries no explicit {', '.join(missing)} — "
                    "checkability may not be implicit"
                )
    return errors


# ── D8: hand-edited nodes keep cross-file consistency ────────────────────────


def check_edited_consistency(node: dict, siblings: list[dict]) -> list[str]:
    """D8: refs across depends_on / applicability_gate.refs / corroborator
    node_ref must resolve to a real sibling node or signal id. With no
    sibling context, corroborator refs cannot be falsified (the corroborated
    node may live in another compile), but hard dependency refs still must
    resolve."""
    errors: list[str] = []
    sibling_node_ids = {sibling.get("node_id") for sibling in siblings}
    sibling_signal_ids: set[str] = set()
    for sibling in siblings:
        for lane in ("fail", "excellence"):
            for signal in (sibling.get("signals") or {}).get(lane) or []:
                signal_id = signal.get("id") if isinstance(signal, dict) else None
                if signal_id:
                    sibling_signal_ids.add(signal_id)

    for dependency in node.get("depends_on") or []:
        if dependency not in sibling_node_ids:
            errors.append(
                f"D8: depends_on ref {dependency!r} is dangling — no sibling node with that node_id"
            )

    gate = node.get("applicability_gate")
    for ref in (gate.get("refs") if isinstance(gate, dict) else None) or []:
        if ref not in sibling_signal_ids:
            errors.append(
                f"D8: applicability_gate ref {ref!r} is dangling — no sibling signal with that id"
            )

    if siblings:
        for corroborator in node.get("corroborators") or []:
            if isinstance(corroborator, dict):
                ref = corroborator.get("node_ref") or ""
                if ref not in sibling_signal_ids and ref not in sibling_node_ids:
                    errors.append(
                        f"D8: corroborator ref {ref!r} is dangling — no sibling node or "
                        "signal with that id"
                    )
    return errors


# ── S5: exclusion-set adversarial test (warn-level) ──────────────────────────


def check_exclusion_set_adversarial(signal: dict) -> list[str]:
    """S5 (warn-level): the naive AND-NOT gate (positive iff inclusion present
    AND no exclusion present) over-fires whenever an exclusion pattern can
    co-occur with an inclusion pattern in one utterance — and in Chinese
    pragmatics any polite phrase ("您可以选择") can (patch-2 Surprise 5). Any
    non-empty exclusion set on a signal with inclusion patterns therefore
    warns; the compile proceeds. No exclusions → no warnings."""
    inclusion = signal.get("inclusion_patterns") or []
    exclusion = signal.get("exclusion_set") or []
    if not inclusion or not exclusion:
        return []
    warnings: list[str] = []
    for pattern in exclusion:
        for positive in inclusion:
            warnings.append(
                f"S5: exclusion pattern {pattern!r} over-fires on positive pattern {positive!r} — "
                "naive AND-NOT rejects an utterance containing both"
            )
    return warnings


# ── S2: source validation halts on conflict ──────────────────────────────────


def validate_sources(sources: dict[str, dict[str, list[str]]]) -> list[dict]:
    """S2: a trigger_id defined in two documents (or twice in one) with
    different keyword sets is a conflict — the compile must halt with a
    report instead of silently picking a winner."""
    conflicts: list[dict] = []
    first_seen: dict[str, tuple[str, list[str]]] = {}
    for document, triggers in (sources or {}).items():
        for trigger_id, keywords in (triggers or {}).items():
            keywords = list(keywords)
            if trigger_id in first_seen:
                first_document, first_keywords = first_seen[trigger_id]
                if set(first_keywords) != set(keywords):
                    conflicts.append(
                        {
                            "trigger_id": trigger_id,
                            "first": {"document": first_document, "keywords": first_keywords},
                            "second": {"document": document, "keywords": keywords},
                        }
                    )
            else:
                first_seen[trigger_id] = (document, keywords)
    return conflicts


# ── validate_node: aggregate entry (the runner's contract) ───────────────────


def validate_node(node: dict | AuthoredNode) -> list[str]:
    """Aggregate the node-only checks — the runner's contract. A node must be
    an AuthoredNode-shaped dict (or AuthoredNode instance, which is normalized
    via model_dump). Context-dependent checks (manifest, align_map, siblings,
    sources) are invoked by the orchestrator with their context arguments."""
    if isinstance(node, AuthoredNode):
        node = node.model_dump()
    errors: list[str] = []
    errors.extend(check_no_adjective_signals(node))
    errors.extend(check_residue_declared(node))
    errors.extend(check_agreement_gate(node))
    errors.extend(check_no_redundant_corroborator(node))
    errors.extend(check_escape_plan(node))
    errors.extend(check_applicability_gate(node))
    errors.extend(check_data_dependency(node))
    errors.extend(check_companion_docs(node))
    errors.extend(check_checkable_audited(node))
    return errors
