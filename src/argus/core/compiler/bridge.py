"""M5 — binary→continuous bridge (B-A..B-D) for the 9003 compiler.

The bridge translates each binary rubric item into the continuous judgment
world: it binds the item to its align.md dimension with its deduction and a
calibration-manifest severity reference (B-A), compiles the NA condition
into an applicability gate (B-B), synthesizes per-dimension hard-fail
routing rules from item subsets (B-C), extracts the item's concrete values
into lexical/threshold specs (B-D), and checks that some dimension
adequately measures the item — unmapped items defer, never force-fit
(AUTH-10).

Purity (I1 quarantine): stdlib only plus the types layer and the M1-M4
modules in the same package. No model client, no clock, no RNG, no I/O —
the same inputs always produce the same bindings.

No-crash contract (B1): every function returns its documented shape for
malformed input — a default result inside the shape, never an exception.

B-verification fix round (W1/W3/W4): an empty/whitespace manifest epoch
degrades to the no-manifest behavior, keyless threshold entries never
fabricate signals, and duplicate item ids dedupe in the hard-fail trigger.

Reference: docs/exec-plans/active/9003-implement-soft-criteria-compiler.md
           docs/retrospectives/soft-criteria-authoring-spec-v4.html
"""

from __future__ import annotations

import math

from argus.core.compiler.agreement import set_deduction_weight

# ──────────────────────────────────────────────────────────────────────────────
# B-A: bind item to dimension
# ──────────────────────────────────────────────────────────────────────────────


def bind_item_to_dimension(
    item: dict, align_map: dict, manifest_epoch: str | None
) -> dict:
    """B-A: attach the item to its align.md dimension, with its deduction
    weight and a severity_map reference into the calibration manifest at its
    current epoch. Without a manifest epoch the node compiles but
    surface-form-sensitive criteria get auto_final: false (AUTH-9); with one,
    the severity ref is calibration://manifest/<epoch>/severity/<id>.
    Malformed input yields the binding shape with item_id None (B1), never a
    crash.
    """
    if not isinstance(item, dict):
        return _binding(None, None, manifest_epoch, set_deduction_weight(item, None))
    item_id = item.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        return _binding(None, None, manifest_epoch, set_deduction_weight(item, None))
    mapping = align_map if isinstance(align_map, dict) else {}
    dimension = mapping.get(item_id)
    return _binding(item_id, dimension, manifest_epoch, set_deduction_weight(item, dimension))


def _binding(
    item_id: str | None, dimension: str | None, manifest_epoch: str | None, deduction: float
) -> dict:
    """The documented DimensionBinding shape. severity_map is a reference into
    the calibration manifest at its current epoch — only when BOTH a usable
    epoch and a bound item exist, so a malformed item never fabricates a ref.
    The epoch is usable when it is a non-empty, non-whitespace string (W1):
    "" or "   " degrades to the no-manifest behavior — no severity ref and
    auto_final withheld (AUTH-9)."""
    has_epoch = isinstance(manifest_epoch, str) and bool(manifest_epoch.strip())
    severity_map = None
    if has_epoch and item_id is not None:
        severity_map = f"calibration://manifest/{manifest_epoch}/severity/{item_id}"
    return {
        "item_id": item_id,
        "dimension": dimension,
        "deduction": deduction,
        "severity_map": severity_map,
        "auto_final_allowed": has_epoch,
    }


# ──────────────────────────────────────────────────────────────────────────────
# B-B: applicability gate
# ──────────────────────────────────────────────────────────────────────────────


def compile_applicability_gate(item: dict) -> dict | None:
    """B-B: translate the item's NA condition into the applicability gate's
    spec — the rule applies only when the condition does not. An item
    without an NA condition (or a malformed item) yields None (B1), never a
    crash; the M1 validator's AUTH-7 rejects an NA-bearing item whose
    compile produced no gate.
    """
    if not isinstance(item, dict):
        return None
    na_condition = item.get("na_condition")
    if not isinstance(na_condition, str) or not na_condition.strip():
        return None
    return {"spec": na_condition.strip(), "logic": "NA → item not applicable"}


# ──────────────────────────────────────────────────────────────────────────────
# B-C: hard-fail synthesis
# ──────────────────────────────────────────────────────────────────────────────


def synthesize_hard_fail(items: list[dict], dimension: str) -> dict | None:
    """B-C: synthesize a many-to-one hard-fail routing rule for a dimension
    from the collective failure of its binary items — a routing rule, not a
    deduction, and synthesized, never copied from the template's single
    threshold (the rule carries no "threshold" key). Requires at least two
    bound items; fewer (or malformed input) yields None (B1), never a crash.
    """
    if not isinstance(items, list):
        return None
    valid = [
        item.get("id")
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and item.get("id").strip()
    ]
    # The collective-failure count reads the raw items (duplicates count as
    # two failures), but the trigger lists each item once (W4): duplicate
    # ids dedupe into the sorted unique set.
    if len(valid) < 2:
        return None
    bound = sorted(set(valid))
    return {
        "dimension": dimension,
        "trigger": {"items": [f"item-{item_id}" for item_id in bound]},
        "action": "route_to_human",
        "synthesized": True,
        "basis": "collective failure of all binary items in the dimension",
    }


# ──────────────────────────────────────────────────────────────────────────────
# B-D: value extraction
# ──────────────────────────────────────────────────────────────────────────────


def extract_values(item: dict) -> list[dict]:
    """B-D: extract the item's concrete values — the named phrases become a
    lexical spec (match any), each numeric threshold becomes a threshold
    spec, both at confidence 1.0. Empty or malformed values yield the empty
    list (B1), never a crash — the gate gets no fabricated value.
    """
    if not isinstance(item, dict):
        return []
    values = item.get("values")
    if not isinstance(values, dict):
        return []
    extractions: list[dict] = []
    raw_phrases = values.get("named_phrases")
    if isinstance(raw_phrases, list):
        phrases = [phrase for phrase in raw_phrases if isinstance(phrase, str)]
        if phrases:
            extractions.append(
                {
                    "kind": "lexical",
                    "spec": {"phrases": phrases, "match": "any"},
                    "confidence": 1.0,
                }
            )
    raw_thresholds = values.get("numeric_thresholds")
    if isinstance(raw_thresholds, list):
        for threshold in raw_thresholds:
            if not isinstance(threshold, dict):
                continue
            name = threshold.get("name")
            if not isinstance(name, str) or not name.strip():
                continue  # W3: no usable name → no threshold signal
            if not _usable_threshold(threshold.get("threshold")):
                continue  # W3: no real finite threshold → no fabricated signal
            extractions.append(
                {
                    "kind": "threshold",
                    "spec": {
                        "name": name,
                        "threshold": threshold.get("threshold"),
                        "unit": threshold.get("unit") or None,
                    },
                    "confidence": 1.0,
                }
            )
    return extractions


def _usable_threshold(value: object) -> bool:
    """A threshold is usable when it is a real finite number — bools, NaN,
    Inf, strings, and None are not (W3); a keyless entry never fabricates a
    threshold signal at confidence 1.0."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError, TypeError):
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Coverage check (no force-fit)
# ──────────────────────────────────────────────────────────────────────────────


def check_dimension_coverage(
    item: dict, align_map: dict, dimensions: list[str]
) -> dict:
    """The coverage check every item must pass: does some dimension
    adequately measure what this item measures? An item whose align.md
    dimension is None or names a dimension the compile does not know is a
    coverage gap (Item 24) — it defers with a data_dependency and a
    dimension_coverage_gap manifest row, never force-fit (AUTH-10). A
    covered item binds cleanly with no dependency and no row. Malformed
    input yields the uncovered shape with neither dependency nor row (B1),
    never a crash.
    """
    if not isinstance(item, dict):
        return {"covered": False, "data_dependency": None, "manifest_row": None}
    item_id = item.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        return {"covered": False, "data_dependency": None, "manifest_row": None}
    mapping = align_map if isinstance(align_map, dict) else {}
    known_dimensions = dimensions if isinstance(dimensions, list) else []
    dimension = mapping.get(item_id)
    if dimension is None or dimension not in known_dimensions:
        return {
            "covered": False,
            "data_dependency": {
                "connected": False,
                "disposition": "defer_until_source_connected",
            },
            "manifest_row": {
                "kind": "dimension_coverage_gap",
                "source_items": [item_id],
                "measures": "no dimension adequately measures this criterion",
                "compiled_to": [],
                "disposition": "defer_until_source_connected",
                "proposes": None,
            },
        }
    return {"covered": True, "data_dependency": None, "manifest_row": None}
