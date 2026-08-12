"""M3 — corroborator classification, residue declaration, gap classification (9003).

A3/A4/rev.4 from the authoring procedure: A3 classifies each candidate
corroborator by error-source disjointness (independent / correlated /
redundant, D16-excluding acoustic-framework and phrase-lexicon refs), A4
declares the criterion's residue so AUTH-2 never fails for lack of a
statement, rev.4 classifies the criterion's gap (values / perceiver /
calibration_surface_form / proxy / coverage), and the escape tier derives
from the gap class (standard vs aggressive).

Purity (I1 quarantine): stdlib only plus the types layer and the M1/M2
modules in the same package. No model client, no clock, no RNG, no I/O —
the same inputs always produce the same classifications.

No-crash contract (B1): every function returns its documented shape for
malformed input — an empty/default result inside the shape, never an
exception.

Reference: docs/exec-plans/active/9003-implement-soft-criteria-compiler.md
           docs/retrospectives/soft-criteria-authoring-spec-v4-patch-1.md
"""

from __future__ import annotations

import re

from argus.core.compiler.validator import _D16_REF_RE

# ──────────────────────────────────────────────────────────────────────────────
# A3: error-source disjointness classes
# ──────────────────────────────────────────────────────────────────────────────

# An acoustic measurement is an instrument signal — its error is disjoint
# from the proposer's text judgment, so it corroborates independently
# (weight 1.0). The programmatic/instrument families corroborate the same
# way (F1): lexical/lookup/ordered matches and duration/turn-count
# measurements are instrument or programmatic signals per the I6 weight
# table (independent = acoustic measurement, lexical/lookup/ordered-match),
# and the D5 programmatic facets are model-free. "order_match" is an
# explicit token — the bare "order" substring is deliberately NOT a marker,
# so "disorder" stays correlated (B2 F1-1). An exemplar/case match is a
# model-judged match to a confirmed referent — same error source as the
# proposer, so correlated (W_C = 0.4 PROVISIONAL). Another model-judged
# text criterion on the same span is soft⊕soft — redundant (weight 0.0,
# rejected by AUTH-4 / D5). Marker substrings, so any variant containing
# the family name classifies with its family.
_INDEPENDENT_TYPES = (
    "acoustic_measurement",
    "order_match",
    "lexical",
    "ordered",
    "lookup",
    "duration",
    "turn",
)
_CORRELATED_TYPES = ("error_case_match", "case_match", "exemplar")
_REDUNDANT_TYPES = ("soft_text",)

# D16: the acoustic indicator framework and the phrase lexicon are rubric
# evidence, NOT corroborators — a candidate that IS one of them by signal
# type, or whose node_ref points into _rubric/evidence/acoustic or
# _rubric/evidence/phrase-keyword (the M1 segment-boundary regex), is
# excluded wholesale, never classified. "phrase_keyword" is the normalized
# token for the hyphenated variant (B2 F2-1).
_FRAMEWORK_SIGNAL_TYPES = ("acoustic_framework", "phrase_lexicon", "phrase_keyword")

# Shared type normalization (B2 F1-1/F2-1/F2-2, B3): strip → split
# camelCase boundaries → collapse runs of space/hyphen/underscore to a
# single "_" → casefold, ONCE at entry, so the D16 exclusion and the
# independence classification both see the same canonical token —
# "Acoustic Framework", "phrase-keyword", " phrase_lexicon ",
# "PhraseLexicon", "SoftText" all collapse onto their canonical forms,
# while "acoustic measurement" / "AcousticMeasurement" collapse onto the
# measurement token, never the framework token.
# The camelCase split runs on the ORIGINAL case — the boundary needs the
# uppercase letter, so it must precede the casefold.
_CAMEL_SPLIT_RE = re.compile(r"([a-z0-9])([A-Z])")
_TYPE_NORMALIZE_RE = re.compile(r"[ _-]+")


def _normalize_signal_type(signal_type: object) -> str:
    """The canonical signal-type token: strip, split camelCase boundaries
    ("OrderMatch" → "Order_Match"), collapse runs of space/hyphen/underscore
    to a single underscore, then casefold. Non-str input normalizes to the
    empty token (B1)."""
    if not isinstance(signal_type, str):
        return ""
    split = _CAMEL_SPLIT_RE.sub(r"\1_\2", signal_type.strip())
    return _TYPE_NORMALIZE_RE.sub("_", split).casefold()


def classify_corroborators(criterion: dict, available_signals: list[dict]) -> list[dict]:
    """A3: classify candidate corroborators by error-source disjointness.

    Each candidate {signal_type, node_ref} maps to an independence_class:
    acoustic measurement → "independent" (1.0), exemplar/case match →
    "correlated" (W_C 0.4), another model-judged text criterion
    ("soft_text") → "redundant" (0.0). Candidates that ARE the acoustic
    framework / phrase lexicon, or whose node_ref points into
    _rubric/evidence/acoustic or _rubric/evidence/phrase-keyword, are
    excluded entirely (D16) — they are rubric, not corroborators. An
    unrecognized signal type classifies "correlated": the conservative
    middle that claims no independence it has not earned and is never
    silently dropped (I2). Input order is preserved. Malformed input yields
    the empty list (B1), never a crash.
    """
    if not isinstance(criterion, dict) or not isinstance(available_signals, list):
        return []
    try:
        classified: list[dict] = []
        for candidate in available_signals:
            if not isinstance(candidate, dict):
                continue
            # B2: normalize the type ONCE — both the D16 exclusion and the
            # classification consume the same canonical token.
            signal_type = candidate.get("signal_type")
            normalized_type = _normalize_signal_type(signal_type)
            if _is_framework(candidate, normalized_type):
                continue  # D16: rubric evidence is not a corroborator
            classified.append(
                {
                    "signal_type": signal_type,
                    "node_ref": candidate.get("node_ref"),
                    "independence_class": _independence_class(normalized_type),
                }
            )
        return classified
    except (AttributeError, TypeError):
        return []


def _is_framework(candidate: dict, normalized_type: str) -> bool:
    """D16: a candidate is the rubric's acoustic framework or phrase lexicon
    — by its normalized signal_type (the shared B2 token, so padding, case,
    spaces, and hyphens cannot bypass the exclusion), or by a node_ref
    pointing into the framework evidence segments (case-insensitive,
    segment-boundary regex W3)."""
    if normalized_type in _FRAMEWORK_SIGNAL_TYPES:
        return True
    node_ref = candidate.get("node_ref")
    if not isinstance(node_ref, str):
        return False
    return bool(_D16_REF_RE.search(node_ref.strip().casefold()))


def _independence_class(signal_type: str) -> str:
    """Map a normalized signal type to its independence class by substring
    markers. An unrecognized type defaults to "correlated" — the conservative
    middle that neither claims independence nor vanishes the signal."""
    if any(marker in signal_type for marker in _INDEPENDENT_TYPES):
        return "independent"
    if any(marker in signal_type for marker in _CORRELATED_TYPES):
        return "correlated"
    if any(marker in signal_type for marker in _REDUNDANT_TYPES):
        return "redundant"
    return "correlated"


# ──────────────────────────────────────────────────────────────────────────────
# A4: residue declaration (AUTH-2)
# ──────────────────────────────────────────────────────────────────────────────


def declare_residue(signals: dict, dimension: str) -> str:
    """A4: declare the criterion's residue — the judgment this compile
    cannot capture.

    The declaration is NEVER empty and NEVER vacuous (AUTH-2 / B-verification
    F10): a fully-empty signal set declares "no signals compiled — the full
    criterion is residue", rejected standards are named by their text, and
    every declaration references its dimension. Malformed input yields a
    non-empty declaration naming the malformation (B1), never a crash.
    """
    try:
        dimension_name = _dimension_name(dimension)
        rejected = signals.get("rejected") if isinstance(signals, dict) else None
        standards = [
            str(entry.get("standard")).strip()
            for entry in (rejected or [])
            if isinstance(entry, dict) and entry.get("standard")
        ]
        fail_count = _lane_count(signals, "fail")
        excellence_count = _lane_count(signals, "excellence")

        if standards:
            named = "；".join(f"standard {standard!r}" for standard in standards)
            return (
                f"{dimension_name} 维度 residue: {len(standards)} rejected standard(s) — "
                f"{named}; a pure-adjective standard names no observable a gate could "
                "locate, so the judgment is residue."
            )
        if fail_count + excellence_count == 0:
            return (
                f"{dimension_name} 维度 residue: no signals compiled — the full criterion "
                "is residue until concrete observables are named."
            )
        return (
            f"{dimension_name} 维度 residue: compiled {fail_count} fail and "
            f"{excellence_count} excellence signal(s) capture the named observables; "
            "the holistic judgment beyond them is residue."
        )
    except (AttributeError, TypeError):
        return "the criterion 维度 residue: malformed signals — the full criterion is residue."


def _lane_count(signals: dict, lane: str) -> int:
    """Number of signal entries in one lane of a signals dict; a malformed
    lane contributes zero (B1)."""
    if not isinstance(signals, dict):
        return 0
    entries = signals.get(lane)
    if not isinstance(entries, list):
        return 0
    return sum(1 for entry in entries if isinstance(entry, dict))


# ──────────────────────────────────────────────────────────────────────────────
# rev.4: gap classification + escape tier
# ──────────────────────────────────────────────────────────────────────────────


def classify_gap(item: dict, dimension: str, signals: dict) -> dict:
    """rev.4: classify the criterion's gap — what kind of ground truth the
    compiled signals provide.

    Deterministic rule order:
      1. values — the item names lexical phrases (gate-checkable values).
      2. proxy — numeric thresholds stand in for the criterion (with no
         named phrases — rule 1 already ruled those out).
      3. values — ANY compiled signal is gate-checkable: checkable coverage
         exists, so the criterion is never "coverage" on mixed signals (F3).
      4. calibration_surface_form — every compiled signal is model_based
         (checkable False) AND the item depends on sibling items.
      5. perceiver — every compiled signal is model_based.
      6. coverage — no compiled signals (all rejected / malformed input).

    Malformed input yields the coverage classification (B1), never a crash.
    """
    if not isinstance(item, dict):
        return _gap_result("coverage", dimension, "malformed item — no signals compiled")
    try:
        values = item.get("values")
        if not isinstance(values, dict):
            values = {}

        raw_phrases = values.get("named_phrases")
        named_phrases = (
            [phrase for phrase in raw_phrases if isinstance(phrase, str)]
            if isinstance(raw_phrases, list)
            else []
        )
        raw_thresholds = values.get("numeric_thresholds")
        numeric_thresholds = raw_thresholds if isinstance(raw_thresholds, list) else []

        raw_depends_on = item.get("depends_on")
        depends_on = raw_depends_on if isinstance(raw_depends_on, list) else []

        if named_phrases:
            return _gap_result(
                "values",
                dimension,
                f"{len(named_phrases)} named phrase(s) give the gate a checkable lexical value",
            )

        if numeric_thresholds:
            return _gap_result(
                "proxy",
                dimension,
                f"{len(numeric_thresholds)} numeric threshold(s) proxy the criterion",
            )

        compiled = _compiled_signals(signals)
        if any(signal.get("checkable") for signal in compiled):
            # F3: mixed checkable + model_based coverage is never "coverage"
            # — gate-checkable coverage exists and bridges the gap.
            return _gap_result(
                "values",
                dimension,
                "at least one gate-checkable signal compiles — checkable coverage exists "
                "(bridge gap)",
            )

        if compiled and all(not signal.get("checkable") for signal in compiled):
            if depends_on:
                return _gap_result(
                    "calibration_surface_form",
                    dimension,
                    "all signals are model_based and the item depends on sibling items — "
                    "surface-form judgment gated by calibration",
                )
            return _gap_result(
                "perceiver",
                dimension,
                "all signals are model_based with no checkable observable — perceiver judgment",
            )

        return _gap_result(
            "coverage",
            dimension,
            "no compiled signals — the criterion is not covered by any gate-checkable signal",
        )
    except (AttributeError, TypeError):
        return _gap_result("coverage", dimension, "malformed item — no signals compiled")


def _compiled_signals(signals: dict) -> list[dict]:
    """The compiled signal entries across the fail and excellence lanes; a
    malformed signals dict or lane contributes nothing (B1)."""
    if not isinstance(signals, dict):
        return []
    compiled: list[dict] = []
    for lane in ("fail", "excellence"):
        entries = signals.get(lane)
        if isinstance(entries, list):
            compiled.extend(entry for entry in entries if isinstance(entry, dict))
    return compiled


def _gap_result(gap_type: str, dimension: str, rationale: str) -> dict:
    """The documented classify_gap shape: {"gap_type", "rationale"} with the
    dimension named in the rationale."""
    return {"gap_type": gap_type, "rationale": f"{_dimension_name(dimension)}: {rationale}"}


def _dimension_name(dimension: object) -> str:
    """A displayable dimension name; a malformed dimension falls back to a
    neutral label (B1)."""
    if isinstance(dimension, str) and dimension.strip():
        return dimension.strip()
    return "the criterion"


def assign_escape_tier(gap_type: str) -> str:
    """Map a gap class to its escape tier.

    "proxy" and "coverage" criteria carry no direct ground truth — every
    verdict is an estimate, so they escape to aggressive human review.
    "values", "perceiver", and "calibration_surface_form" keep the standard
    tier; an unknown gap class defaults to "standard" (the plan's default),
    and malformed input is "standard" too (B1) — never a crash.
    """
    if not isinstance(gap_type, str):
        return "standard"
    normalized = gap_type.strip().casefold()
    if normalized in ("proxy", "coverage"):
        return "aggressive"
    return "standard"
