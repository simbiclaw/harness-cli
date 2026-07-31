"""Structural test: no SKILL.md may claim hooks can trigger skills.

Hooks follow a strict allow/block contract — JSON {"continue": true|false}
plus output text. A hook CANNOT invoke a skill; it can only emit an
instruction the model may follow. Any SKILL.md that claims a hook
"triggers," "invokes," or "automatically calls" the skill is describing
an invocation channel that never had blocking semantics.

The correct pattern is deterministic denial: the hook blocks until evidence
exists (the gate pattern), and the skill is MANUALLY invoked by the model
to create that evidence. See 9005 Surprises & Discoveries.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"

# Phrases that claim a hook causes a skill to run — impossible.
# These are checked against the full SKILL.md text (frontmatter + body).
HOOK_TRIGGER_PATTERNS = [
    re.compile(
        r"Triggered\s+(by|when)\s+.*?\b(hook|PreToolUse|PostToolUse)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(Automatically|auto-?triggered).*?\b(hook|PreToolUse|PostToolUse)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(hook|PreToolUse|PostToolUse)\b.*?\b(trigger|invoke|launch|call|cause)\b.*?\bskill\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(is|are|will be)\s+triggered\b.*?\b(when|by)\b.*?\b(checkbox|check\s+box|flip)\b",
        re.IGNORECASE,
    ),
]

# Preceding text that indicates a NEGATION of the trigger claim.
# We exclude matches immediately preceded by these markers.
NEGATION_RE = re.compile(
    r"\b(NOT|not|never|does not|doesn.t|cannot|can.t|won.t|isn.t)\s+"
    r"(automatically\s+)?(triggered|invoked|called)\s+(by|when)\s+",
    re.IGNORECASE,
)


def _is_negated(text: str, match_start: int) -> bool:
    """Check whether a match is inside a negation context.

    Looks at the ~60 characters preceding the match for negation markers
    that would make this a statement about what hooks CAN'T do.
    """
    before = text[max(0, match_start - 60):match_start]
    return bool(NEGATION_RE.search(before))


def test_no_skill_claims_hook_triggered():
    """No SKILL.md claims that a hook triggers or invokes the skill."""
    if not SKILLS_DIR.exists():
        return

    failures: list[str] = []

    for skill_md in sorted(SKILLS_DIR.rglob("SKILL.md")):
        text = skill_md.read_text()
        rel = str(skill_md.relative_to(REPO_ROOT))

        for pat in HOOK_TRIGGER_PATTERNS:
            for m in pat.finditer(text):
                if _is_negated(text, m.start()):
                    continue  # negation of trigger claim is fine
                # Show the matched phrase and surrounding context
                start = max(0, m.start() - 20)
                end = min(len(text), m.end() + 20)
                context = text[start:end].replace("\n", " ").strip()
                failures.append(
                    f"{rel}:{_line_of(text, m.start())}: "
                    f"'{m.group().strip()}' "
                    f"(context: ...{context}...)"
                )

    assert not failures, (
        "SKILL.md files claim hooks can trigger or invoke skills.\n"
        "Hooks cannot invoke skills — they can only block or allow "
        '({"continue": true|false}). Claims of automatic triggering '
        "describe an invocation channel that never had blocking semantics.\n"
        "\n"
        "Fix: replace with the gate pattern — the hook blocks until "
        "evidence exists (deterministic denial), and the skill is "
        "MANUALLY invoked by the model to create that evidence.\n"
        "\n"
        f"Violations ({len(failures)}):\n"
        + "\n".join(f"  - {f}" for f in failures)
    )


def _line_of(text: str, pos: int) -> int:
    """Return 1-based line number for character position in text."""
    return text[:pos].count("\n") + 1
