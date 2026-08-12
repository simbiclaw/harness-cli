"""M4 — agreement gate seeding, deduction weighting, iteration policy (9003).

A5/A6/A7 from the authoring procedure: A5 seeds the agreement block (tau,
rolling kappa sample plan, escape sample plan + ceiling) for a judgment-
layer node, A6 derives the deduction weight for the deduction setter and
holds the shared provisional W_C constant, and A7 declares the iteration
policy under which the compiled rule may change.

Purity (I1 quarantine): stdlib only plus the types layer and the M1/M2/M3
modules in the same package. No model client, no clock, no RNG, no I/O —
the same inputs always produce the same seeds.

Corroboration moves routing, never the deduction arithmetic (I6): the
deduction weight is read off the item, never scaled by corroborator
counts. And W_C is an agreement/config constant shared across criteria
(patch-1 D6), not a per-item field — the seeder returns the same 0.4
value regardless of the criterion.

No-crash contract (B1): every function returns its documented shape for
malformed input — a default result inside the shape, never an exception.

Reference: docs/exec-plans/active/9003-implement-soft-criteria-compiler.md
           docs/retrospectives/soft-criteria-authoring-spec-v4-patch-1.md
"""

from __future__ import annotations

import math

# ── Shared constants ──────────────────────────────────────────────────────────

# The agreement gate's initial tau (A5): soft entry is gated at 0.8 until a
# rolling human-labeled sample measures the real kappa.
_INITIAL_TAU = 0.8

# W_C — the correlated-signal corroboration weight (I6 weight table).
# 0.4 PROVISIONAL: the correct value is 1 - corr(matcher_error,
# proposer_error) measured on a human-labeled sample; the constant is
# revisited when escape-rate data accumulates. Shared across all criteria
# (patch-1 D6), never a per-item field.
_W_C = 0.4
_W_C_NOTE = (
    "W_C = 0.4 PROVISIONAL — correct value is 1 - corr(matcher_error, proposer_error) "
    "measured on a human-labeled sample; revisit when escape-rate data accumulates"
)

# The AUTH-6 escape ceiling: the fraction of escapes a criterion may
# tolerate before the gate is re-examined.
_ESCAPE_CEILING = 0.05

# The rolling-sample plan for the kappa agreement tail and the escape tail.
_KAPPA_SAMPLE_PLAN = "rolling 200 calls, weekly kappa for {}"
_ESCAPE_SAMPLE_PLAN = "rolling 200 calls, weekly escape rate for {} against the ceiling"


def _criterion_label(criterion: object) -> str:
    """A displayable criterion label for the seeded plan strings; a
    malformed criterion falls back to a neutral label (B1)."""
    if isinstance(criterion, dict):
        raw_id = criterion.get("id")
        if isinstance(raw_id, str) and raw_id.strip():
            return raw_id.strip()
    return "the criterion"


# ──────────────────────────────────────────────────────────────────────────────
# A5: agreement gate seeding
# ──────────────────────────────────────────────────────────────────────────────


def seed_agreement_gate(criterion: dict) -> dict:
    """A5: seed the agreement block for a judgment-layer node.

    The seeded block carries BOTH tails so it always passes the M1
    validator's AUTH-3/AUTH-6 checks: the agreement tail (tau + rolling
    kappa sample plan) and the auto-pass escape tail (escape sample plan +
    ceiling). current_kappa initializes null — it is filled by the rolling
    sample at runtime, never by the compiler. Malformed input yields the
    same block with a neutral criterion label (B1), never a crash.
    """
    label = _criterion_label(criterion)
    return {
        "tau": _INITIAL_TAU,
        "kappa_sample_plan": _KAPPA_SAMPLE_PLAN.format(label),
        "escape_sample_plan": _ESCAPE_SAMPLE_PLAN.format(label),
        "escape_ceiling": _ESCAPE_CEILING,
        "current_kappa": None,
    }


# ──────────────────────────────────────────────────────────────────────────────
# A6: deduction weighting
# ──────────────────────────────────────────────────────────────────────────────


def set_deduction_weight(item: dict, dimension: str) -> float:
    """A6: the deduction weight the setter writes onto the node's deduction.

    The item's own deduction_weight when it is a FINITE real number, else
    the default 1.0 (B-verification F1/F2): out-of-float-range ints,
    NaN, Inf, -Inf, strings, bools, and None are all 1.0. Never scaled by
    corroborators — corroboration moves routing, never the deduction
    arithmetic (I6); a corroborator-carrying item returns its weight
    unchanged. Malformed input yields 1.0 (B1), never a crash.
    """
    if not isinstance(item, dict):
        return 1.0
    weight = item.get("deduction_weight")
    if isinstance(weight, bool) or not isinstance(weight, (int, float)):
        return 1.0
    try:
        converted = float(weight)
    except (OverflowError, ValueError, TypeError):
        return 1.0
    if not math.isfinite(converted):
        return 1.0
    return converted


def set_w_c(criterion: dict) -> dict:
    """A6: the shared W_C corroboration weight.

    W_C is an agreement/config constant, not a per-item field (patch-1
    D6): every criterion receives the same value, 0.4 PROVISIONAL, with
    the empirical measurement that will replace it named in the note.
    Malformed input yields the same constant shape (B1), never a crash.
    """
    return {"value": _W_C, "provisional": True, "note": _W_C_NOTE}


# ──────────────────────────────────────────────────────────────────────────────
# A7: iteration policy
# ──────────────────────────────────────────────────────────────────────────────


def set_iteration_policy(criterion: dict) -> str:
    """A7: the policy under which this compiled rule may change.

    Argus is a consumer of the rubric, never an editor: re-grounding
    happens only via write-time epoch commits upstream — no rule edits
    from Argus output. Malformed input yields the same policy (B1), never
    a crash.
    """
    return (
        "re-ground via write-time epoch commit only; no rule edits from Argus output"
    )
