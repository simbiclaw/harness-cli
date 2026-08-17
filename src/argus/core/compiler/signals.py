"""M2 — signal decomposition and evidence authoring for the 9003 compiler.

The compiler's deterministic decomposition core (A1, A2, A2-ac, A2-ph from
the authoring procedure). Each function is pure: stdlib only plus the types
layer and the M1 validator in the same package. No model client, no clock,
no RNG, no I/O (I1 quarantine) — the same inputs always produce the same
signals.

The four-layer chain (Patch 1 D10) replaces the old trigger.spec: the
human_version text decomposes into FAIL/EXCELLENCE signals, each signal is
audited for gate-checkability (B-F), and every signal is backed by a
programmatic or model_based facet (D5/D9). The acoustic indicator framework
and the phrase lexicon are authored as pure EvidenceEntry data, not
AuthoredNodes (Patch 1 D2, D16).

No-crash contract (B-verification B1): every function returns its documented
shape for malformed input — an error marker inside the shape, never an
exception. Classification rules (B-verification B3/B4/B5, B2 round F1-F4):
real ordered forms (先X再Y, 先X然后Y, 先X后Y, "acknowledge before resolve",
"... THEN ...") never silently vanish — with the 后 of 然后 never consumed
as the marker, the second element cut at the first clause separator, the
English comma form recognized, and the sentence prefix trimmed off;
unmatched standards become model_based signals; adjective standards with a
concrete referent are model-judged (not flat-rejected); only the RubricItem
pydantic shape is plumbed in; model_based descriptions never embed raw
standard text (so checkable=False signals always audit "model_only"); and
every signal's audit_result is the output of audit_gate_checkable called
on its own description. B3 round (BLOCK-1, WARN-1..4): the second ordered
element cuts at the next occurrence of ANY connective (然后/再/后), a
degenerate empty first element is not an ordered match, the English comma
form needs no whitespace after the comma, the literal id "None" sanitizes,
and non-str standards never regex-match their repr. B4 round (F1/F2): the
first element cuts at the first connective too, and a pair with an empty
first or second element is never emitted — both parts must be
connective-free and non-empty. B5 round: the cuts are word-aware — a cut
or leading strip never splits a real word (售后 / 后来 / 后台 / 随后 /
最后 / 然后). B6 round: the bare-后 marker never anchors at a 后 inside a
protected word — with no viable marker the standard falls to model_based.

Reference: docs/exec-plans/active/9003-implement-soft-criteria-compiler.md
           docs/retrospectives/soft-criteria-authoring-spec-v4-patch-1.md
           docs/retrospectives/soft-criteria-authoring-spec-v4-patch-2.md
"""

from __future__ import annotations

import re

from argus.core.compiler.validator import (
    _ADJECTIVES,
    _names_concrete_referent,
    _normalize_description,
)
from argus.types.compiler_schemas import RubricItem

# ──────────────────────────────────────────────────────────────────────────────
# Shared pattern families
# ──────────────────────────────────────────────────────────────────────────────

# The M1 validator's adjective families (AUTH-1) cover Chinese simplified /
# traditional and English evaluative adjectives; M2 extends them with the
# empathy-family terms the M2 fixture ("agent should sound empathetic")
# exercises.
_ADJECTIVE_FAMILIES = (*_ADJECTIVES, "empathetic", "empathic")

# Ordered-relation patterns: Chinese service patterns 先<X>再<Y> and
# 先<X>然后<Y>. The bare 先<X>后<Y> marker is matched position-by-position
# in _match_hou_marker — the 后 of 然后 (F1) and word-internal 后s (B6)
# are never the marker. The English "acknowledge before resolve" /
# "... THEN ..." shape is case-insensitive and comma-tolerant (F3).
_ORDERED_RE = re.compile(r"先(.+?)再(.+)")
_ORDERED_RANHOU_RE = re.compile(r"先(.+?)然后(.+)")
# The connector may be preceded by whitespace OR by a comma (ASCII or
# full-width) with no required trailing whitespace (F3, WARN-2).
_EN_ORDERED_RE = re.compile(
    r"([\w\s,，-]*?)(?:\s+|[,，]\s*)(?:before|then)\s+([\w\s,，-]*)", re.IGNORECASE
)

# The second ordered element cuts at the FIRST clause separator, a 最后
# marker, or the NEXT occurrence of any ordered connective (然后/再/后)
# (F1 + BLOCK-1) — doubled connectives and enumerations never glue onto
# the ordered pair.
_CLAUSE_CUT_RE = re.compile(r"[，、。；;]|最后|然后|再|后")

# A leftover connective may LEAD the second element ("先A然后再B" captures
# group2="再B" under the 然后 connector) — strip it before cutting so the
# cut never lands at index 0 (BLOCK-1).
_LEADING_CONNECTIVE_RE = re.compile(r"^(?:然后|再|后)+")

# The first ordered element cuts at the FIRST connective (再/然后/后) — the
# mirror of the second-element guard (B4 round F1): "先A再然后B" captures
# group1="A再" under the 然后 connector and must not keep the 再 glued on.
_FIRST_CUT_RE = re.compile(r"再|然后|后")

# Real words containing 再/后/然后 that a connective cut must never split
# (B5): cutting 售后 at its 后 — or stripping the 后 off 后台 — would
# corrupt the word.
_NON_SPLIT_WORDS = ("售后", "后来", "后台", "随后", "最后", "然后")

# Leading subject/auxiliary tokens stripped from an English first ordered
# element (F3): "agent must acknowledge" → "acknowledge".
_EN_PREFIX_STOPWORDS = frozenset(
    {"agent", "the", "must", "we", "they", "should", "need", "to", "has", "have", "had", "a", "an"}
)

# B-F split triggers: a standard demanding context-appropriateness plus a
# recommendation term auto-splits into a programmatic (temporal proximity)
# and a model_based (context adaptation) sibling.
_SPLIT_PATTERNS = ("结合场景", "结合客户场景", "适当", "context-appropriate")
_RECOMMENDATION_TERMS = ("推荐", "recommendation", "recommend")

# Concrete action/object terms that give an adjective standard a real
# referent (B-verification B5): an adjective WITH one of these is model-
# judged, only a pure adjective (none of these) is rejected. The list
# deliberately excludes framing words like 表现 / 应 / 坐席 so that
# "坐席表现混乱" stays a pure-adjective rejection.
_REFERENT_TERMS = (
    "处理",
    "投诉",
    "推荐",
    "道歉",
    "用语",
    "安抚",
    "查询",
    "记录",
    "跟进",
    "告知",
    "复述",
    "倾听",
    "引导",
    "说明",
    "确认",
    "提供",
    "转接",
    "升级",
    "handle",
    "complaint",
    "recommend",
    "apologize",
    "apology",
    "terms",
    "words",
)

# Concrete-action verbs for A1 dimension decomposition: a clause naming one
# of these actions is signal-decomposable; anything else is judgment residue.
_CONCRETE_VERBS = (
    "识别",
    "推荐",
    "处理",
    "查询",
    "表达",
    "安抚",
    "道歉",
    "引导",
    "确认",
    "说明",
    "询问",
    "复述",
    "倾听",
    "记录",
    "跟进",
    "提供",
    "告知",
    "acknowledge",
    "resolve",
    "identify",
    "recommend",
    "offer",
    "explain",
    "confirm",
    "ask",
    "follow",
    "provide",
    "escalate",
    "greet",
    "summarize",
)

# Clause separators for A1: both Chinese enumeration marks and Western
# punctuation.
_CLAUSE_SEP_RE = re.compile(r"[，、；;：:。．\n/]+")

# B-F gate-checkability audit markers (S4), in precedence order — the
# observable-pattern markers are checked FIRST, then the split markers
# (B-verification B4): a description naming an observable pattern a gate
# could locate audits "pass" even when it also mentions context terms
# (e.g. "transcript contains one of the named phrases: 适当回应" → "pass").
_OBSERVABLE_MARKERS = ("transcript", "contains", "phrase", "named", "present")
_SPLIT_MARKERS = ("proximity", "context adaptation", "结合场景", "适当", "context-appropriate")


# ──────────────────────────────────────────────────────────────────────────────
# A1: dimension decomposition
# ──────────────────────────────────────────────────────────────────────────────


def decompose_dimension(dimension: dict) -> dict:
    """A1: split a dimension description into signal-decomposable candidates
    and non-decomposable judgment residue.

    The head before the first colon names the dimension topic — a label, not
    an observable — and lands in residue. The remaining clauses are candidates
    when they name a concrete action, residue when they carry only judgment.
    Malformed input yields the documented empty shape (B1), never a crash.
    """
    if not isinstance(dimension, dict):
        return {"candidates": [], "residue": []}
    try:
        description = str(dimension.get("description", ""))
        candidates: list[dict] = []
        residue: list[dict] = []

        head, separator, body = description.partition("：")
        if not separator:
            head, separator, body = description.partition(":")

        if separator and head.strip():
            residue.append(
                {"text": head.strip(), "reason": "dimension topic label, not a decomposable signal"}
            )
            clauses = _split_clauses(body)
        else:
            clauses = _split_clauses(description)

        for clause in clauses:
            if _names_concrete_action(clause):
                candidates.append({"text": clause, "signal_decomposable": True})
            else:
                residue.append(
                    {"text": clause, "reason": "judgment part without a named observable"}
                )

        # A description with no decomposable content is residue wholesale —
        # the dimension's judgment core is still declared, never silently
        # dropped.
        if not candidates and not residue and description.strip():
            residue.append(
                {
                    "text": description.strip(),
                    "reason": "judgment part without a named observable",
                }
            )
        return {"candidates": candidates, "residue": residue}
    except (AttributeError, TypeError):
        return {"candidates": [], "residue": []}


def _split_clauses(text: str) -> list[str]:
    """Split a description into clauses on enumeration marks and punctuation,
    dropping empties and whitespace."""
    return [clause.strip() for clause in _CLAUSE_SEP_RE.split(text) if clause.strip()]


def _names_concrete_action(clause: str) -> bool:
    """A clause is signal-decomposable when it names a concrete action verb."""
    lowered = clause.casefold()
    return any(verb in lowered for verb in _CONCRETE_VERBS)


# ──────────────────────────────────────────────────────────────────────────────
# A2 + B-E: FAIL/EXCELLENCE signal decomposition
# ──────────────────────────────────────────────────────────────────────────────


def decompose_signals(item: RubricItem | dict) -> dict:
    """A2 + B-E: translate a rubric item's failure/pass standards into
    FAIL and EXCELLENCE signals, and reject pure-adjective standards.

    Deterministic rule order (ids increment S01, S02, ... in this order):
      1. Lexical — non-empty named phrases produce a gate-checkable FAIL
         signal naming the phrases.
      2. Ordered relation — a fail standard matching 先<X>再<Y> / 先<X>后<Y>
         (or English "acknowledge before resolve" / "... THEN ...") produces
         a FAIL signal with an ordered-relation evidence shape.
      3. Split (B-F) — a standard demanding a context-appropriate
         recommendation auto-splits into two FAIL siblings: a programmatic
         "temporal proximity" signal (checkable) and a model_based "context
         adaptation" signal (not checkable).
      4. Excellence — the pass standard produces an excellence signal: an
         ordered-relation signal when it carries an ordered marker; a
         model_based quality signal for adjective standards with a concrete
         referent (B5) or unobservable pass standards; a model_based
         "model-judged excellence evidence" signal otherwise. The lane NEVER
         reuses the fail lane's named phrases (M8 — failure markers like
         思路混乱 must not appear as excellence evidence).

    No silent drops (B3): an unmatched fail standard becomes a model_based
    signal, never vanish. Pure-adjective standards (no concrete referent)
    are rejected (AUTH-1), never silently dropped. Every signal's
    audit_result IS audit_gate_checkable(signal) (B4) — the battery test
    holds by construction. RubricItem instances are normalized via
    model_dump (B2); None/non-str/empty ids sanitize to the "item" prefix
    (W3); malformed input yields the error shape (B1), never a crash.
    """
    if isinstance(item, RubricItem):
        item = item.model_dump()
    elif hasattr(item, "model_dump"):
        # Only the annotated RubricItem shape is plumbed in; any other
        # pydantic model (AlignMap, SpecificRubric, AuthoredNode, ...) is a
        # plumbing error (F2) — malformed shape, no fabricated signals.
        return _malformed_signals(item)
    if not isinstance(item, dict):
        return _malformed_signals(item)
    try:
        raw_id = item.get("id")
        # The literal string "None" sanitizes exactly like None (WARN-3) —
        # ids must never read "None-...".
        item_id = (
            raw_id
            if isinstance(raw_id, str) and raw_id.strip() and raw_id.strip().casefold() != "none"
            else "item"
        )
        values = item.get("values")
        if not isinstance(values, dict):
            values = {}
        # Non-str phrase entries are skipped (B1: no "、".join crash).
        named_phrases = [
            phrase for phrase in (values.get("named_phrases") or []) if isinstance(phrase, str)
        ]
        numeric_thresholds = list(values.get("numeric_thresholds") or [])
        # Non-str standards never regex-match their repr (WARN-4) — they are
        # treated as absent and fall to the model_based lane.
        pass_standard_raw = item.get("pass_standard")
        fail_standard_raw = item.get("fail_standard")
        pass_standard = pass_standard_raw if isinstance(pass_standard_raw, str) else ""
        fail_standard = fail_standard_raw if isinstance(fail_standard_raw, str) else ""

        fail: list[dict] = []
        excellence: list[dict] = []
        rejected: list[dict] = []
        counter = 1

        def next_signal_id() -> str:
            nonlocal counter
            signal_id = f"{item_id}-S{counter:02d}"
            counter += 1
            return signal_id

        def make_signal(description: str, checkable: bool, **extra) -> dict:
            signal = {
                "id": next_signal_id(),
                "description": description,
                "checkable": checkable,
                **extra,
            }
            signal["audit_result"] = audit_gate_checkable(signal)
            return signal

        def reject(standard: str) -> None:
            rejected.append({"standard": standard, "reason": "adjective without concrete referent"})

        # 1. Lexical signals from the item's named phrases (B-D).
        if named_phrases:
            fail.append(
                make_signal(
                    "transcript contains one of the named phrases: " + "、".join(named_phrases),
                    True,
                    severity="high",
                )
            )

        # 2. Ordered relation from the failure standard — a sequence the gate
        #    can deterministically verify. Unmatched standards fall through to
        #    a model_based signal (B3), never silently vanish.
        if not _is_split_standard(fail_standard):
            ordered_fail = _match_ordered(fail_standard)
            if ordered_fail is not None:
                first, second = ordered_fail
                fail.append(
                    make_signal(
                        f"transcript must show {first} before {second}",
                        True,
                        evidence_shape={
                            "shape": "ordered_relation",
                            "first": first,
                            "second": second,
                        },
                    )
                )
            elif _is_pure_adjective(fail_standard, named_phrases, numeric_thresholds):
                reject(fail_standard)
            else:
                # The raw standard text is deliberately NOT embedded (F4):
                # a description that scans as observable would mis-audit a
                # model_based signal as "pass".
                fail.append(
                    make_signal(
                        f"model-judged evidence for criterion C{item_id} (unmatched standard)",
                        False,
                    )
                )

        # 3. B-F auto-split: a context-appropriate-recommendation standard
        #    decomposes into a programmatic sibling (temporal proximity) and a
        #    model_based sibling (context adaptation). Either standard may
        #    carry the pattern; the siblings land in the FAIL lane.
        if _is_split_standard(fail_standard) or _is_split_standard(pass_standard):
            _emit_split_siblings(fail, next_signal_id)

        # 4. Excellence lane from the pass standard. A split pass standard was
        #    consumed by step 3. Adjectives with a concrete referent are
        #    model-judged, not flat-rejected (B5). The lane NEVER reuses the
        #    fail lane's named phrases (M8 pilot-gap closure — the semantic
        #    inversion where failure markers like 思路混乱 appear as
        #    excellence): an ordered pass standard yields the ordered
        #    excellence signal; an unmarked pass standard yields model_based
        #    excellence evidence.
        if _is_split_standard(pass_standard):
            pass
        elif _match_ordered(pass_standard) is not None:
            first, second = _match_ordered(pass_standard)
            excellence.append(
                make_signal(
                    f"transcript must show {first} before {second}",
                    True,
                    evidence_shape={
                        "shape": "ordered_relation",
                        "first": first,
                        "second": second,
                    },
                )
            )
        elif _is_pure_adjective(pass_standard, named_phrases, numeric_thresholds):
            reject(pass_standard)
        elif not named_phrases and _has_adjective(pass_standard):
            # Same F4 rule as the unmatched fallback: no raw standard text
            # embedded in a model_based description.
            fail.append(
                make_signal(
                    f"model-judged evidence for criterion C{item_id} (adjective standard)",
                    False,
                )
            )
        elif not named_phrases:
            # No named phrases: the pass standard's evidence is unresolvable
            # judgment — model_based quality evidence, never a fabricated
            # observable.
            excellence.append(
                make_signal(
                    "quality of the agent's handling as judged against the pass standard",
                    False,
                )
            )
        elif _pass_cites_fail_standard(pass_standard, fail_standard, named_phrases):
            # M8: the pass standard's only named-phrase content also names
            # failure examples (item 18's 客服系统 appears in the fail
            # standard's worked example) — the pass and fail vocabularies are
            # entangled, so the excellence evidence is model-judged against
            # the pass standard, never a phrase reuse.
            excellence.append(
                make_signal(
                    "quality of the agent's handling as judged against the pass standard",
                    False,
                )
            )
        else:
            excellence.append(
                make_signal(
                    f"model-judged excellence evidence for criterion C{item_id}",
                    False,
                )
            )

        return {"fail": fail, "excellence": excellence, "rejected": rejected}
    except (AttributeError, TypeError):
        return _malformed_signals(item)


def _malformed_signals(item) -> dict:
    """B1 error shape: the documented decomposition dict with the malformed
    input named in rejected — never an exception."""
    return {
        "fail": [],
        "excellence": [],
        "rejected": [{"standard": repr(item), "reason": "malformed input: expected item dict"}],
    }


def _match_ordered(standard: str) -> tuple[str, str] | None:
    """Match an ordered-relation pattern: 先<X>然后<Y> / 先<X>再<Y> /
    先<X>后<Y> (Chinese service patterns — the 后 of 然后 never counts as
    the marker, F1) or "<X> before/then <Y>" (English, comma-tolerant with
    the sentence prefix trimmed off, F3). Returns the named (first, second)
    pair, or None. Non-str standards never match their repr (WARN-4), a
    degenerate pair whose first element carries no CJK/alphanumeric
    character (WARN-1) is not an ordered match, a pair whose cleaned first
    or second element is empty (B4 round F1/F2 — connectives or a leading
    separator) is not an ordered match either, and the bare-后 marker never
    anchors inside a protected word (B6); the standard falls to the
    model_based lane."""
    if not isinstance(standard, str) or not standard:
        return None
    for pattern in (_ORDERED_RANHOU_RE, _ORDERED_RE):
        match = pattern.search(standard)
        if match:
            return _clean_pair(match.group(1), match.group(2))
    hou_pair = _match_hou_marker(standard)
    if hou_pair is not None:
        return _clean_pair(hou_pair[0], hou_pair[1])
    match = _EN_ORDERED_RE.search(standard)
    if match:
        first = _clean_first(_trim_verb_prefix(match.group(1)))
        second = _clean_second(match.group(2))
        if not first or not second:
            return None
        return first, second
    return None


def _match_hou_marker(standard: str) -> tuple[str, str] | None:
    """Match the bare-后 ordered marker 先<X>后<Y> position-by-position. A 后
    is never the marker when it belongs to 然后 (F1) or completes a protected
    word — 售后/后台/随后/最后/后来 (B6) — either as the word's tail
    ("坐席先处理售后问题") or its head ("先确认后台处理"). When no viable
    marker remains, the standard is not an ordered match and falls to the
    model_based lane. Returns the raw (first, second) pair."""
    marker_start = standard.find("先")
    if marker_start == -1:
        return None
    for index in range(marker_start + 1, len(standard)):
        if standard[index] != "后":
            continue
        if standard[index - 1] == "然":
            continue  # the 后 of 然后 — never the bare marker
        if _completes_non_split_word(standard, index, index + 1):
            continue  # word-internal 后 — never the bare marker
        return standard[marker_start + 1 : index], standard[index + 1 :]
    return None


def _clean_pair(first_raw: str, second_raw: str) -> tuple[str, str] | None:
    """Clean a raw ordered pair into (first, second); None when the pair is
    degenerate — a first element carrying no CJK/alphanumeric character
    (WARN-1) or an empty first/second after cleaning (B4 round F2, e.g.
    "先A然后，B" → second "，B" cuts to "") — and the standard falls to the
    model_based lane."""
    if not re.search(r"\w", first_raw):
        return None
    first = _clean_first(first_raw)
    second = _clean_second(second_raw)
    if not first or not second:
        return None
    return first, second


def _clean_first(text: str) -> str:
    """Trim a captured first ordered element: cut at the FIRST connective
    (再/然后/后) that does not complete a real word (B5) — connectives never
    glue into the first element (B4 round F1) and words like 售后 survive —
    then trim whitespace and trailing punctuation."""
    cut = _find_cut_index(text, _FIRST_CUT_RE)
    if cut is not None:
        text = text[:cut]
    return text.strip().rstrip("，。．.,;；!！?？")


def _clean_second(text: str) -> str:
    """Cut a captured second ordered element: strip any leading leftover
    connective (word-aware, B5 — 后台 keeps its 后), then cut at the FIRST
    clause separator (，、。；;), a 最后 marker, or the NEXT occurrence of any
    ordered connective (然后/再/后) — enumerations and doubled connectives
    never glue onto the ordered pair (F1, BLOCK-1) — then trim."""
    text = _strip_leading_connectives(text)
    cut = _find_cut_index(text, _CLAUSE_CUT_RE)
    if cut is not None:
        text = text[:cut]
    return text.strip().rstrip("，。．.,;；!！?？")


def _strip_leading_connectives(text: str) -> str:
    """Strip leading connective chars (然后/再/后) one at a time, stopping
    when a match heads a real word (B5): "后台处理" keeps its 后台."""
    while True:
        match = _LEADING_CONNECTIVE_RE.match(text)
        if match is None or _completes_non_split_word(text, match.start(), match.end()):
            return text
        text = text[match.end() :]


def _completes_non_split_word(text: str, start: int, end: int) -> bool:
    """True when the matched span [start, end) is part of a non-split word —
    either the tail of a word ending at the match ("售后": the cut at 后
    after 售) or the head of a word starting at the match ("后台": the 后
    before 台) (B5)."""
    matched = text[start:end]
    for word in _NON_SPLIT_WORDS:
        if word.endswith(matched):
            prefix = word[: len(word) - len(matched)]
            if prefix and text[max(0, start - len(prefix)) : start] == prefix:
                return True
        if word.startswith(matched):
            suffix = word[len(matched) :]
            if suffix and text[end : end + len(suffix)] == suffix:
                return True
    return False


def _find_cut_index(text: str, cut_re: re.Pattern) -> int | None:
    """Index of the first cut-pattern match that does not complete a
    non-split word; None when every match is word-internal (B5)."""
    for match in cut_re.finditer(text):
        if not _completes_non_split_word(text, match.start(), match.end()):
            return match.start()
    return None


def _trim_verb_prefix(text: str) -> str:
    """Strip leading subject/auxiliary tokens so an English first ordered
    element starts at the verb: "agent must acknowledge" → "acknowledge"
    (F3). Only LEADING tokens are dropped — a verb phrase like
    "acknowledge the customer" is untouched."""
    tokens = text.split()
    start = 0
    while start < len(tokens) and (
        tokens[start].casefold().strip("，,.;；:：") in _EN_PREFIX_STOPWORDS
    ):
        start += 1
    return " ".join(tokens[start:])


def _is_split_standard(standard: str) -> bool:
    """B-F: a standard demands a context-appropriate recommendation when it
    carries a context-appropriateness pattern AND a recommendation term."""
    if not standard:
        return False
    lowered = standard.casefold()
    if not any(pattern in lowered for pattern in _SPLIT_PATTERNS):
        return False
    return any(term in lowered for term in _RECOMMENDATION_TERMS)


def _pass_cites_fail_standard(
    pass_standard: str, fail_standard: str, named_phrases: list[str]
) -> bool:
    """M8: True when the pass standard's only named-phrase content overlaps
    the fail standard's own text — the pass and fail vocabularies are
    entangled (item 18's 客服系统 appears in the fail standard's worked
    example), so the excellence evidence is model-judged against the pass
    standard, never a phrase reuse."""
    if not pass_standard or not fail_standard or not named_phrases:
        return False
    return any(phrase in pass_standard and phrase in fail_standard for phrase in named_phrases)


def _emit_split_siblings(fail: list[dict], next_signal_id) -> None:
    """B-F: append the two auto-split FAIL siblings — the programmatic
    temporal-proximity signal and the model_based context-adaptation
    signal. Both audit to "split" via audit_gate_checkable (B4)."""
    siblings = (
        (
            "temporal proximity: the recommendation must be delivered within temporal "
            "proximity of the detected need — context-appropriate recommendation",
            True,
        ),
        (
            "context adaptation: the model judges whether the recommendation is "
            "context-appropriate for the customer's scenario",
            False,
        ),
    )
    for description, checkable in siblings:
        signal = {
            "id": next_signal_id(),
            "description": description,
            "checkable": checkable,
        }
        signal["audit_result"] = audit_gate_checkable(signal)
        fail.append(signal)


def _has_adjective(standard: str) -> bool:
    """True when the standard's normalized text carries an evaluative
    adjective from the shared families (AUTH-1)."""
    normalized = _normalize_description(standard)
    return any(adjective in normalized for adjective in _ADJECTIVE_FAMILIES)


def _names_referent(standard: str) -> bool:
    """True when the standard names a concrete action/object term — the
    difference between "坐席应灵活处理客户投诉" (adjective + referent →
    model-judged) and "坐席表现混乱" (pure adjective → rejected)."""
    lowered = standard.casefold()
    return any(term in lowered for term in _REFERENT_TERMS)


def _is_pure_adjective(
    standard: str, named_phrases: list[str], numeric_thresholds: list[dict]
) -> bool:
    """AUTH-1: a standard is pure-adjective when the item carries no named
    phrases or numeric content AND the standard's content is evaluative
    adjectives with no concrete referent. Only such standards are rejected —
    adjective standards with a referent are model_based signals (B5)."""
    if named_phrases or numeric_thresholds:
        return False
    if not standard:
        return False
    if not _has_adjective(standard):
        return False
    return not _names_referent(standard) and not _names_concrete_referent(standard)


# ──────────────────────────────────────────────────────────────────────────────
# B-F: gate-checkability audit (S4)
# ──────────────────────────────────────────────────────────────────────────────


def audit_gate_checkable(signal: dict) -> str:
    """B-F: audit a signal description for gate-checkability.

    Precedence (B-verification B4): (1) observable-pattern markers
    ("transcript", "contains", "phrase", "named", "present") → "pass";
    (2) split markers ("proximity", "context adaptation", "结合场景",
    "适当", "context-appropriate") → "split"; (3) conclusion-only
    descriptions → "model_only". Malformed signals audit "model_only"
    (B1), never a crash.
    """
    try:
        description = str(signal.get("description") or "").casefold()
    except (AttributeError, TypeError):
        return "model_only"
    if any(marker in description for marker in _OBSERVABLE_MARKERS):
        return "pass"
    if any(marker in description for marker in _SPLIT_MARKERS):
        return "split"
    return "model_only"


# ──────────────────────────────────────────────────────────────────────────────
# D5/D9: signal-shaped facets
# ──────────────────────────────────────────────────────────────────────────────


def assign_facets(signals: dict, gap: str) -> dict:
    """D5/D9: assign a facet to every signal — a programmatic facet with
    indicator + calculation + output_schema for gate-checkable signals, a
    model_based facet with a complete extraction prompt for the rest.
    Malformed input yields the empty shape (B1), never a crash."""
    if not isinstance(signals, dict):
        return {"programmatic": [], "model_based": []}
    try:
        programmatic: list[dict] = []
        model_based: list[dict] = []
        for lane in ("fail", "excellence"):
            for signal in signals.get(lane) or []:
                if not isinstance(signal, dict):
                    continue
                signal_id = str(signal.get("id") or "?")
                description = str(signal.get("description") or signal_id)
                if signal.get("checkable"):
                    programmatic.append(
                        {
                            "facet_name": f"programmatic_{signal_id}",
                            "enables_signals": [signal_id],
                            "indicator": f"{gap}_gate_locates: {description}",
                            "calculation": "1.0 when the named pattern is found in the "
                            "transcript, else 0.0",
                            "output_schema": {
                                "signal_id": signal_id,
                                "present": "bool",
                                "evidence_span": "str (quoted transcript span)",
                            },
                        }
                    )
                else:
                    model_based.append(
                        {
                            "facet_name": f"model_{signal_id}",
                            "enables_signals": [signal_id],
                            "prompt": (
                                "extract evidence for "
                                + description
                                + " with checkpoints: (1) locate the relevant turn(s) in the "
                                "transcript, (2) quote the exact span, (3) judge the span "
                                "against the signal description, (4) output per the schema below"
                            ),
                            "output_schema": {
                                "signal_id": signal_id,
                                "verdict": "bool",
                                "evidence_span": "str (quoted transcript span)",
                                "confidence": "float in [0, 1]",
                            },
                        }
                    )
        return {"programmatic": programmatic, "model_based": model_based}
    except (AttributeError, TypeError):
        return {"programmatic": [], "model_based": []}


# ──────────────────────────────────────────────────────────────────────────────
# A2-ac / A2-ph: evidence authoring (rubric, not corroborators — D16)
# ──────────────────────────────────────────────────────────────────────────────


def compile_acoustic_framework(indicators: list[dict]) -> list[dict]:
    """A2-ac: author the acoustic indicator framework as pure EvidenceEntry
    data — one entry per input indicator, all fields preserved. Malformed
    input yields the empty list (B1), never a crash."""
    if not isinstance(indicators, list):
        return []
    try:
        return [
            {
                "name": str(indicator.get("name", "")),
                "type": "acoustic",
                "values": {
                    "threshold": indicator.get("threshold"),
                    "unit": str(indicator.get("unit", "")),
                    "description": str(indicator.get("description", "")),
                },
            }
            for indicator in indicators
        ]
    except (AttributeError, TypeError):
        return []


def compile_phrase_lexicon(lexicon: dict[str, list[str]]) -> dict[str, list[dict]]:
    """A2-ph: author the phrase lexicon as pure EvidenceEntry data — one
    entry per word, sections preserved exactly. Non-list section values
    yield an empty section (W2), non-str entries are skipped (B1), and
    malformed input yields the empty dict (B1), never a crash."""
    if not isinstance(lexicon, dict):
        return {}
    try:
        result: dict[str, list[dict]] = {}
        for section, words in lexicon.items():
            if not isinstance(words, list):
                result[section] = []
                continue
            result[section] = [
                {"name": word, "type": "phrase", "values": {"patterns": [word]}}
                for word in words
                if isinstance(word, str)
            ]
        return result
    except (AttributeError, TypeError):
        return {}
