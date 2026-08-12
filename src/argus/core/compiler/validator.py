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

import functools
import re

from argus.types.compiler_schemas import AuthoredNode

# ── AUTH-1: evaluative adjectives that name no observable referent ───────────
# Patch-2 S6 list: an adjective is only admissible when the description
# points at what a gate could actually verify (a named phrase, a pattern).

_ADJECTIVES = (
    # Chinese simplified (patch-2 S6)
    "灵活",
    "积极",
    "混乱",
    "清晰",
    "死板",
    "主动",
    "耐心",
    "认真",
    # Chinese traditional (B-finding F3)
    "靈活",
    "積極",
    "混亂",
    "清晰",
    "死板",
    "主動",
    "耐心",
    "認真",
    # English (patch-2 S6)
    "substantive",
    "engaged",
    "adapted",
    "enthusiastic",
    "proactive",
    "flexible",
    # English noun forms (W1)
    "flexibility",
    "proactiveness",
    "adaptability",
    "responsiveness",
    "enthusiasm",
)

# Orthographic mutations must not bypass the adjective check (W1/F12): "灵 活",
# zero-width / invisible format characters, "pro-active", "pro active", and
# case variants all collapse onto the same token before matching.
# Format-family invisible characters (F12): U+200B..U+200F (zero-width space,
# ZWNJ/ZWJ, LRM/RLM), U+2060..U+2064 (word joiner + invisible operators),
# U+FEFF (zero-width no-break space), U+00AD (soft hyphen).
_INVISIBLE_CHARS = frozenset(
    chr(c)
    for c in list(range(0x200B, 0x2010)) + list(range(0x2060, 0x2065)) + [0xFEFF, 0x00AD]
)
_HYPHENS = {"-", "—"}


def _normalize_description(description: str) -> str:
    """Drop all unicode whitespace, invisible format chars, and hyphens, then
    lowercase (F11) so that mutated adjectives still match their canonical
    spelling — the adjective list is lowercase."""
    out: list[str] = []
    for char in description:
        if char.isspace() or char in _INVISIBLE_CHARS or char in _HYPHENS:
            continue
        out.append(char)
    return "".join(out).lower()


def _guarded(label: str):
    """B1 no-crash guard: a check must return an error string for malformed
    input — never raise AttributeError/TypeError (the validate_node contract
    is no-crash for ANY dict input, schema-valid or not)."""

    def decorator(check_fn):
        @functools.wraps(check_fn)
        def wrapper(*args, **kwargs):
            try:
                return check_fn(*args, **kwargs)
            except (AttributeError, TypeError) as exc:
                return [f"malformed {label}: {exc}"]

        return wrapper

    return decorator

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


@_guarded("signals")
def check_no_adjective_signals(node: dict) -> list[str]:
    """AUTH-1: reject signals described with evaluative adjectives that carry
    no concrete referent ("坐席表现灵活" without naming the observable)."""
    errors: list[str] = []
    signals = node.get("signals")
    if signals is None:
        return []
    if not isinstance(signals, dict):
        return ["AUTH-1: malformed signals — must be a dict with fail/excellence lanes"]
    for lane in ("fail", "excellence"):
        lane_entries = signals.get(lane)
        if not isinstance(lane_entries, list):
            errors.append(f"AUTH-1: malformed signals.{lane} — must be a list")
            continue
        for signal in lane_entries:
            if not isinstance(signal, dict):
                errors.append(f"AUTH-1: malformed {lane} signal entry (must be a dict)")
                continue
            raw_description = signal.get("description")
            if not isinstance(raw_description, str):
                errors.append("AUTH-1: malformed signal description (must be a str)")
                continue
            # Adjective matching runs on the orthographically normalized text;
            # the concrete-referent check runs on the original text (its
            # markers are whitespace-sensitive).
            description = _normalize_description(raw_description)
            for adjective in _ADJECTIVES:
                if adjective in description and not _names_concrete_referent(raw_description):
                    signal_id = signal.get("id") or "?"
                    errors.append(
                        f"AUTH-1: signal {signal_id} description uses evaluative adjective "
                        f"{adjective!r} without a concrete referent"
                    )
                    break  # one error per signal
    return errors


# ── AUTH-2: residue must be declared ─────────────────────────────────────────

# Vacuous declarations carry no information and must not satisfy AUTH-2
# (B-finding F10: "None" / "N/A" / "null" / "无" are placeholders, not residue).
_VACUOUS_RESIDUE = {"none", "n/a", "null", "无"}


@_guarded("residue_declared")
def check_residue_declared(node: dict) -> list[str]:
    """AUTH-2: a judgment-layer node must declare what it cannot capture —
    the lossy-projection ledger needs a ground-truth residue statement."""
    residue = node.get("residue_declared")
    if (
        not isinstance(residue, str)
        or residue.strip() == ""
        or residue.strip().casefold() in _VACUOUS_RESIDUE
    ):
        return [
            "AUTH-2: judgment-layer node must declare residue_declared (a non-empty, "
            "non-vacuous statement of what this rule cannot capture)"
        ]
    return []


# ── AUTH-3: agreement gate (tau + kappa_sample_plan) ─────────────────────────


@_guarded("agreement")
def check_agreement_gate(node: dict) -> list[str]:
    """AUTH-3: the agreement block must carry both an initial tau and a
    rolling-sample plan — no ungated soft entry."""
    agreement = node.get("agreement")
    if not isinstance(agreement, dict):
        return ["AUTH-3: judgment-layer node requires an agreement block (tau + kappa_sample_plan)"]
    errors: list[str] = []
    tau = agreement.get("tau")
    # tau must be a real number in (0, 1] — bool/str/degenerate values are
    # not gates (B-findings F4): a string tau or tau=0 would admit ungated
    # soft entry.
    if isinstance(tau, bool) or not isinstance(tau, (int, float)) or not 0 < tau <= 1:
        errors.append("AUTH-3: agreement.tau must be a real number in (0, 1]")
    kappa_plan = agreement.get("kappa_sample_plan")
    if not isinstance(kappa_plan, str) or kappa_plan.strip() == "":
        errors.append("AUTH-3: agreement.kappa_sample_plan must be a non-empty rolling-sample plan")
    return errors


# ── AUTH-4: no redundant corroborator (incl. D16) ────────────────────────────


@_guarded("corroborators")
def check_no_redundant_corroborator(node: dict) -> list[str]:
    """AUTH-4: reject soft⊕soft corroboration — redundant-class signals
    corroborate nothing (D5), and framework/lexicon refs are rubric, not
    corroborators (D16)."""
    errors: list[str] = []
    corroborators = node.get("corroborators")
    if corroborators is None:
        return []
    if not isinstance(corroborators, list):
        return ["AUTH-4: malformed corroborators — must be a list"]
    for corroborator in corroborators:
        if not isinstance(corroborator, dict):
            errors.append("AUTH-4: malformed corroborator entry (must be a dict)")
            continue
        ref = corroborator.get("node_ref")
        if not isinstance(ref, str):
            errors.append("AUTH-4: malformed corroborator node_ref (must be a str)")
            continue
        # Case-insensitive class comparison (B-finding F5): "Redundant" must
        # not slip through a case-sensitive equality check.
        independence_class = (corroborator.get("independence_class") or "").strip().casefold()
        if independence_class == "redundant":
            errors.append(
                f"AUTH-4: corroborator {ref!r} is redundant-class — redundant signals "
                "corroborate nothing (D5)"
            )
        if _refs_into_rubric(ref):
            errors.append(
                f"AUTH-4: corroborator {ref!r} points into the rubric (acoustic framework / "
                "phrase lexicon are rubric, not corroborating signals — D16)"
            )
    return errors


# Segment-boundary D16 match (W3): "evidence/acoustic" and
# "evidence/phrase-keyword" only when the segment ends cleanly — a sibling
# dir like "evidence/acousticfoo" is not the framework.
_D16_REF_RE = re.compile(r"(^|/)evidence/(acoustic|phrase-keyword)(/|$)")


def _refs_into_rubric(ref: str) -> bool:
    """D16: a corroborator may not reference the acoustic framework or the
    phrase lexicon — bare, canonical-prefixed, or relative forms (W3), with
    case and padding normalized first (F13)."""
    return bool(_D16_REF_RE.search(ref.strip().casefold()))


# ── AUTH-5: no compile run without a residue manifest ────────────────────────


@_guarded("manifest")
def check_manifest_present(manifest: dict | None, nodes: list[dict]) -> list[str]:
    """AUTH-5: a run that emits nodes must also emit the residue manifest —
    lossy projections would otherwise go unrecorded. None or an empty dict
    is not a manifest (B-finding F10)."""
    if not isinstance(manifest, dict) or not manifest:
        return ["AUTH-5: compile run emitted nodes without a residue manifest"]
    return []


# ── AUTH-6: escape plan required ─────────────────────────────────────────────


@_guarded("agreement")
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


@_guarded("applicability_gate")
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


@_guarded("data_dependency")
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
    connected = _parse_connected(dependency.get("connected"))
    if connected is None:
        # B-finding F1: only real bools and 'true'/'false' strings are
        # acceptable — a truthy string like "false" must not masquerade.
        errors.append(
            "AUTH-8: data_dependency.connected must be a bool or the strings 'true'/'false'"
        )
    elif connected is False:
        # B-finding F2: positive whitelist, not substring — "no defer" or
        # "deferral impossible" are denials, not deferrals.
        disposition = dependency.get("disposition")
        if not isinstance(disposition, str):
            errors.append("AUTH-8: malformed disposition — must be a str")
        elif disposition.strip().casefold() not in (
            "defer_until_source_connected",
            "defer",
            "deferred",
        ):
            errors.append(
                "AUTH-8: data_dependency connected=false must carry a defer disposition "
                "(no silent bypass while the source is disconnected)"
            )
    return errors


def _parse_connected(value: object) -> bool | None:
    """Parse `connected` into a real bool; None for anything invalid (F1)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    return None


# ── AUTH-9: no auto-final on uncalibrated surface-form criterion ─────────────


@_guarded("calibration_coverage")
def check_calibration_coverage(node: dict, manifest: dict | None) -> list[str]:
    """AUTH-9: a calibration_surface_form criterion may permit auto-final only
    when the calibration manifest covers its failure surface. Criterion id is
    the last segment of severity_map (…/severity/21 → "21")."""
    criterion = node.get("machine_criterion")
    if not isinstance(criterion, dict):
        return []
    # gap_type is normalized (strip + casefold, B2) and the gate fires when
    # EITHER the node-level or the machine_criterion gap_type is
    # surface-form — an inconsistency between the two must not skip the gate.
    node_gap = node.get("gap_type")
    criterion_gap = criterion.get("gap_type")
    is_surface_form = (
        isinstance(node_gap, str) and node_gap.strip().casefold() == "calibration_surface_form"
    ) or (
        isinstance(criterion_gap, str)
        and criterion_gap.strip().casefold() == "calibration_surface_form"
    )
    if not is_surface_form:
        return []
    # auto_final_allowed must be a real bool; a string "True"/"false" is
    # treated as UNSAFE and flagged (F6).
    auto_final = criterion.get("auto_final_allowed")
    if not isinstance(auto_final, bool):
        return [
            "AUTH-9: auto_final_allowed must be a real bool — string values are unsafe"
        ]
    if auto_final is False:
        return []
    severity_map = node.get("severity_map")
    if not isinstance(severity_map, str) or not severity_map:
        return [
            "AUTH-9: calibration_surface_form criterion with auto_final needs a severity_map "
            "ref to prove manifest coverage"
        ]
    criterion_id = severity_map.rsplit("/", 1)[-1]
    covered = _manifest_covered(manifest)
    if covered is None or criterion_id not in covered:
        return [
            f"AUTH-9: calibration criterion {criterion_id} allows auto-final but is not "
            "covered by the calibration manifest"
        ]
    return []


def _manifest_covered(manifest: object) -> set[str] | None:
    """Covered criteria from a manifest: the explicit covered_criteria set if
    present, else the union of every row's source_items (the real M6 manifest
    shape; F6). None when neither shape is present."""
    if not isinstance(manifest, dict):
        return None
    if "covered_criteria" in manifest:
        return manifest["covered_criteria"]
    if "rows" in manifest:
        covered: set[str] = set()
        for row in manifest["rows"]:
            if isinstance(row, dict):
                covered.update(row.get("source_items") or [])
        return covered
    return None


# ── AUTH-10: no forced mapping ───────────────────────────────────────────────


@_guarded("source_binary_items")
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


# A pinned sha256 is 64 lowercase hex chars — anything shorter is a
# placeholder, not a pin (B-finding F7).
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@_guarded("companion_docs")
def check_companion_docs(node: dict) -> list[str]:
    """S1: every companion_docs entry must pin document, role, and a
    well-formed sha256 — compile inputs are reproducible only when the exact
    text is identifiable."""
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
        sha = entry.get("sha256")
        if not isinstance(sha, str) or not _SHA256_RE.match(sha.strip()):
            errors.append("S1: companion_docs entry sha256 must be 64 lowercase hex chars")
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


@_guarded("depends_on")
def check_depends_on(node: dict, siblings: list[dict] | None = None) -> list[str]:
    """S3: applicability_gate refs and depends_on prerequisites must resolve to
    a signal id that actually exists in a sibling node's fail signals. None
    siblings are treated as no context (F8)."""
    errors: list[str] = []
    sibling_ids = _sibling_fail_signal_ids(siblings or [])
    gate = node.get("applicability_gate")
    refs = gate.get("refs") if isinstance(gate, dict) else None
    if refs is not None and not isinstance(refs, list):
        errors.append("S3: malformed applicability_gate.refs — must be a list")
        refs = []
    for ref in refs or []:
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


@_guarded("signals")
def check_checkable_audited(node: dict) -> list[str]:
    """S4: every signal must carry an explicit checkable + audit_result —
    checkability may not be implied (B-F audit outcome: pass / split /
    model_only)."""
    errors: list[str] = []
    signals = node.get("signals")
    if signals is None:
        return []
    if not isinstance(signals, dict):
        return ["S4: malformed signals — must be a dict with fail/excellence lanes"]
    for lane in ("fail", "excellence"):
        lane_entries = signals.get(lane)
        if not isinstance(lane_entries, list):
            errors.append(f"S4: malformed signals.{lane} — must be a list")
            continue
        for signal in lane_entries:
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


@_guarded("edited node")
def check_edited_consistency(node: dict, siblings: list[dict] | None = None) -> list[str]:
    """D8: refs across depends_on / applicability_gate.refs / corroborator
    node_ref must resolve to a real sibling node or signal id. With no
    sibling context, corroborator refs cannot be falsified (the corroborated
    node may live in another compile), but hard dependency refs still must
    resolve. None siblings are treated as no context (F8)."""
    errors: list[str] = []
    siblings = siblings or []
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
    refs = gate.get("refs") if isinstance(gate, dict) else None
    if refs is not None and not isinstance(refs, list):
        errors.append("D8: malformed applicability_gate.refs — must be a list")
        refs = []
    for ref in refs or []:
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


@_guarded("signal")
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


@_guarded("sources")
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


@_guarded("node")
def validate_node(node: dict | AuthoredNode) -> list[str]:
    """Aggregate the node-only checks — the runner's contract. A node must be
    an AuthoredNode-shaped dict (or AuthoredNode instance, which is normalized
    via model_dump); anything else is an error, never a crash (F8/B1).
    Context-dependent checks (manifest, align_map, siblings, sources) are
    invoked by the orchestrator with their context arguments."""
    if isinstance(node, AuthoredNode):
        node = node.model_dump()
    if not isinstance(node, dict):
        return [f"invalid node: expected dict, got {type(node).__name__}"]
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
