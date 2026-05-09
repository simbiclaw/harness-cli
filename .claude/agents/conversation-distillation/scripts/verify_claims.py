"""
Verify atomic claims against the four gates from claim_schema.md.

Used both as a CLI (verify a JSONL file) and as a library (the extraction
script calls it inline before writing to the library). Failures are
diagnostic — the verifier doesn't delete claims, it tells you which IDs
failed and why.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


REQUIRED_TOP_LEVEL = {
    "id", "schema_version", "claim_type", "speaker_role", "proposition",
    "source", "decontextualisation", "extraction_method", "extractor_version",
}

VALID_CLAIM_TYPES = {"assertion", "inquiry", "commitment", "complaint", "preference"}
VALID_SPEAKER_ROLES = {"customer", "agent", "unknown"}

# Pronouns and underspecified phrases that, when standing alone in a
# proposition, indicate an unresolved reference. The regex matches
# whole-word tokens, case-insensitive.
# Hard-fail pronouns: words that, when standing alone in a proposition,
# are almost always unresolved references. NOTE: "that" and "this" are
# excluded because they're complementizers ("complained that the order
# arrived") and determiners ("this filing") far more often than bare
# demonstratives, producing high false-positive rates. Bare demonstrative
# uses are caught by the LLM-side decontextualisation reasoning.
PRONOUN_STOPLIST = [
    r"\bit\b",
    r"\bthese\b", r"\bthose\b",
    r"\bthey\b", r"\bthem\b", r"\btheir\b", r"\btheirs\b",
    r"\bhe\b", r"\bshe\b", r"\bhim\b", r"\bher\b", r"\bhis\b", r"\bhers\b",
    r"\bhere\b", r"\bthere\b", r"\bnow\b", r"\bthen\b",
]
PRONOUN_RE = re.compile("|".join(PRONOUN_STOPLIST), re.IGNORECASE)

# Antecedent patterns: noun phrases that can be the in-sentence referent
# of a following pronoun. When one of these appears earlier in the
# proposition than the pronoun, the pronoun has a grammatical antecedent
# in scope and should not be flagged. Examples that pass with this rule:
#   "The customer reported being unable to log into their account."
#   "The agent committed to email their corrected invoice."
# Examples that still fail (no antecedent):
#   "They want a refund."
#   "It hasn't arrived."
ANTECEDENT_RE = re.compile(
    r"\b(?:the customer|the agent|the user|the caller|the speaker|the manager|the supervisor)\b",
    re.IGNORECASE,
)

# Soft-warn pronouns: flag as warnings, not failures. These have legitimate
# non-pronoun uses but bare-demonstrative uses are worth surfacing.
SOFT_PRONOUN_RE = re.compile(r"\b(this|that)\b", re.IGNORECASE)


def _has_in_text_antecedent(prop: str, pronoun_match: re.Match) -> bool:
    """
    Return True if a likely noun-phrase antecedent appears before this pronoun
    in the proposition. Uses both a fixed phrase list ("the customer", "the
    agent", etc.) and a heuristic for proper nouns (capitalized non-leading
    words longer than 2 chars).
    """
    text_before = prop[: pronoun_match.start()]
    if ANTECEDENT_RE.search(text_before):
        return True
    # Capitalized non-leading words → likely proper noun antecedents
    words = text_before.split()
    for w in words[1:]:
        # Strip surrounding punctuation
        bare = re.sub(r"^[\W_]+|[\W_]+$", "", w)
        if len(bare) > 2 and bare[0].isupper():
            return True
    return False

# Underspecified noun phrases. These are flagged but with weaker signal —
# many false positives ("the form 8-K" contains "the form"). The verifier
# requires that they be followed by something specific (a proper noun,
# a number, or a quoted name). Otherwise it warns.
UNDERSPECIFIED_NOUN_PATTERNS = [
    r"\bthe form\b(?!\s+[A-Z0-9])",
    r"\bthe order\b(?!\s+(?:placed|number|of|on|for|by))",
    r"\bthe issue\b",
    r"\bthe problem\b",
    r"\bthe page\b",
    r"\bthe link\b",
    r"\bthe document\b",
    r"\bthe account\b(?!\s+(?:was|number|of|for))",
    r"\brecently\b",
    r"\bthe other day\b",
    r"\blast (?:week|month|year)\b",
    r"\bnext (?:week|month|year)\b",
]
UNDERSPECIFIED_RE = re.compile("|".join(UNDERSPECIFIED_NOUN_PATTERNS), re.IGNORECASE)


@dataclass
class VerificationResult:
    claim_id: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def verify_claim(claim: dict) -> VerificationResult:
    cid = claim.get("id", "<no-id>")
    failures: list[str] = []
    warnings: list[str] = []

    # Gate 0: structural — required fields present and well-typed
    missing = REQUIRED_TOP_LEVEL - set(claim.keys())
    if missing:
        failures.append(f"missing_fields: {sorted(missing)}")
        # Without these, the rest of the checks are moot — return early.
        return VerificationResult(claim_id=cid, passed=False, failures=failures)

    if claim["claim_type"] not in VALID_CLAIM_TYPES:
        failures.append(f"invalid_claim_type: {claim['claim_type']!r}")
    if claim["speaker_role"] not in VALID_SPEAKER_ROLES:
        failures.append(f"invalid_speaker_role: {claim['speaker_role']!r}")

    # Gate 4 (checked early because it's structural): source-cited
    src = claim.get("source") or {}
    if not src.get("audio_id"):
        failures.append("source_missing: audio_id")
    seg_ids = src.get("segment_ids") or []
    if not seg_ids:
        failures.append("source_missing: segment_ids must be non-empty")
    elif not all(isinstance(s, int) for s in seg_ids):
        failures.append("source_bad_type: segment_ids must be ints")

    # Gate 1: single proposition (heuristic — split markers + conjunction)
    proposition = claim.get("proposition", "") or ""
    if not proposition.strip():
        failures.append("proposition_empty")
    else:
        prop_failures, prop_warnings = _check_single_proposition(proposition)
        failures.extend(prop_failures)
        warnings.extend(prop_warnings)

        # Gate 2: de-contextualised
        decon_failures, decon_warnings = _check_decontextualised(claim)
        failures.extend(decon_failures)
        warnings.extend(decon_warnings)

        # Gate 3: not a Q&A pair
        qa_failures = _check_not_qa(proposition)
        failures.extend(qa_failures)

    return VerificationResult(
        claim_id=cid,
        passed=not failures,
        failures=failures,
        warnings=warnings,
    )


def _check_single_proposition(prop: str) -> tuple[list[str], list[str]]:
    """
    Heuristic check. Two sentences = two propositions (split). A coordinating
    conjunction joining two clauses with both verb predicates = two propositions.
    The check is conservative — false negatives (missed splits) are fine, but
    false positives that block legitimate compound nouns are not.
    """
    failures: list[str] = []
    warnings: list[str] = []

    # Sentence count
    # Strip trailing period for the split-check, count internal sentence ends.
    stripped = prop.rstrip(". ")
    sentence_ends = len(re.findall(r"[.!?](?:\s|$)", stripped))
    if sentence_ends >= 1:
        # Two or more sentences in the proposition
        warnings.append(
            "multiple_sentences: proposition contains multiple sentence "
            "boundaries — consider splitting into separate claims"
        )

    # "X and Y" where both X and Y look like full clauses with their own verb.
    # We approximate by checking for " and " followed later by another verb.
    # Highly heuristic; emit as warning, not failure.
    if re.search(r"\b\w+ed\b.+\band\b.+\b\w+ed\b", prop) or \
       re.search(r"\b(was|were|is|are|will|has|have)\b.+\band\b.+\b(was|were|is|are|will|has|have)\b", prop):
        warnings.append(
            "compound_clause_suspected: 'and' joining two clauses with "
            "independent verbs — consider whether two claims are warranted"
        )

    return failures, warnings


def _check_decontextualised(claim: dict) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    prop = claim["proposition"]

    # Pronouns: hard fail — UNLESS the pronoun has an in-sentence antecedent
    # (e.g., "the customer ... their account") or appears inside a quoted span
    # (e.g., reported speech: "the customer said 'I want it'").
    pronoun_matches = list(PRONOUN_RE.finditer(prop))
    if pronoun_matches:
        # Suppress matches that are inside quoted spans (single or double quotes)
        unquoted_prop = re.sub(r'"[^"]*"', lambda m: " " * len(m.group()), prop)
        unquoted_prop = re.sub(r"'[^']*'", lambda m: " " * len(m.group()), unquoted_prop)
        unquoted_matches = list(PRONOUN_RE.finditer(unquoted_prop))

        # For remaining matches, check for in-sentence antecedent
        bare_pronouns = []
        for m in unquoted_matches:
            if not _has_in_text_antecedent(unquoted_prop, m):
                bare_pronouns.append(m.group())

        if bare_pronouns:
            failures.append(
                f"unresolved_pronouns: {sorted(set(p.lower() for p in bare_pronouns))}"
            )

    # Soft-warn for "this"/"that" — high false-positive (complementizer/determiner),
    # but bare demonstrative uses worth surfacing to the operator.
    soft_matches = SOFT_PRONOUN_RE.findall(prop)
    if soft_matches:
        unquoted = re.sub(r'["\'][^"\']*["\']', "", prop)
        unquoted_soft = SOFT_PRONOUN_RE.findall(unquoted)
        if unquoted_soft:
            warnings.append(
                f"possible_demonstrative: {sorted(set(m.lower() for m in unquoted_soft))} — "
                "verify these are complementizers/determiners, not bare demonstratives"
            )

    # Underspecified noun phrases: warn rather than fail (high false-positive
    # rate). The user-side log of warnings is the diagnostic.
    underspec = UNDERSPECIFIED_RE.findall(prop)
    if underspec:
        warnings.append(
            f"possibly_underspecified: {sorted(set(m.lower() for m in underspec))}"
        )

    # Resolution consistency: every resolved_references entry's surface form
    # should not appear as a bare pronoun in the proposition.
    decon = claim.get("decontextualisation") or {}
    resolved = decon.get("resolved_references") or []
    for r in resolved:
        surface = r.get("surface", "")
        resolved_to = r.get("resolved_to", "")
        if not surface or not resolved_to:
            failures.append("malformed_resolution_entry")
            continue
        # If surface is a pronoun and it still appears in the proposition,
        # that's a contradiction — the resolution claims to have replaced it
        # but didn't.
        if PRONOUN_RE.fullmatch(surface) and re.search(rf"\b{re.escape(surface)}\b", prop, re.IGNORECASE):
            unquoted = re.sub(r'["\'][^"\']*["\']', "", prop)
            if re.search(rf"\b{re.escape(surface)}\b", unquoted, re.IGNORECASE):
                failures.append(
                    f"resolution_inconsistent: claimed to resolve {surface!r} "
                    f"but it still appears in proposition"
                )

    return failures, warnings


def _check_not_qa(prop: str) -> list[str]:
    """
    Q&A patterns to flag:
      "asked X and was told Y"
      "the customer asked ... the agent said ..."
      "in response to ..., the agent ..."
    """
    failures: list[str] = []
    qa_patterns = [
        r"\basked\b.+\b(?:was told|was informed|was advised)\b",
        r"\bcustomer asked\b.+\bagent\b",
        r"\bagent (?:replied|responded|answered)\b.+\bcustomer\b",
        r"\bin response to\b.+\bthe (?:agent|customer)\b",
        r"\bwhen asked\b.+\b(?:agent|customer)\b",
    ]
    for pat in qa_patterns:
        if re.search(pat, prop, re.IGNORECASE):
            failures.append(f"qa_pattern_detected: matched /{pat}/")
            break  # one is enough
    return failures


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def verify_file(path: Path) -> tuple[int, int, list[VerificationResult]]:
    """Returns (n_passed, n_total, failed_results)."""
    n_total = 0
    n_passed = 0
    failed: list[VerificationResult] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n_total += 1
            try:
                claim = json.loads(line)
            except json.JSONDecodeError as e:
                failed.append(VerificationResult(
                    claim_id=f"<line:{n_total}>", passed=False,
                    failures=[f"invalid_json: {e}"],
                ))
                continue
            r = verify_claim(claim)
            if r.passed:
                n_passed += 1
            else:
                failed.append(r)
    return n_passed, n_total, failed


def main() -> int:
    p = argparse.ArgumentParser(description="Verify atomic claims against the four gates.")
    p.add_argument("--input", "-i", required=True, type=Path,
                   help="Path to a JSONL file of claims to verify")
    p.add_argument("--show-warnings", action="store_true",
                   help="Also print warnings (low-signal flags)")
    p.add_argument("--max-failures", type=int, default=20,
                   help="Stop printing after this many failures (default: 20)")
    args = p.parse_args()

    if not args.input.exists():
        print(f"ERROR: {args.input} does not exist", file=sys.stderr)
        return 2

    n_passed, n_total, failed = verify_file(args.input)
    print(f"Verified {n_total} claims; {n_passed} passed; {len(failed)} failed.")

    for i, r in enumerate(failed):
        if i >= args.max_failures:
            print(f"... and {len(failed) - args.max_failures} more failures (truncated)")
            break
        print(f"\n  [{r.claim_id}] FAIL")
        for f in r.failures:
            print(f"      - {f}")
        if args.show_warnings:
            for w in r.warnings:
                print(f"      ~ warning: {w}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
