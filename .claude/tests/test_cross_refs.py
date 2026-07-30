"""Structural test: cross-reference integrity for PEV subagent documentation.

Verifies that active documentation does not reference deprecated PEV
implementations (pev_tmux_adversarial.sh, pev_orchestrator.js, pev_repair.py)
except where explicitly documenting the deprecation.

Part of M7 cleanup (9006-pev-tmux-convergence).
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Active docs that should NOT reference deprecated implementations
# except in explicit deprecation notices
ACTIVE_DOCS = [
    "docs/conventions/pev-loop.md",
    "docs/conventions/verification-floor.md",
    "docs/conventions/implementation-notes.md",
    "docs/PLANS.md",
    "CLAUDE.md",
]

# Deprecated implementations to check for in active docs.
# Any non-deprecation-context reference triggers a failure.
DEPRECATED_REFS = {
    "pev_orchestrator.js": re.compile(r"pev_orchestrator\.js"),
    "pev_repair.py": re.compile(r"pev_repair\.py"),
    "pev_tmux_adversarial.sh": re.compile(r"pev_tmux_adversarial\.sh"),
}


def _is_deprecation_context(text_around: str) -> bool:
    """Check if a reference to deprecated code is in a deprecation notice."""
    lower = text_around.lower()
    return any(
        kw in lower
        for kw in ["deprecated", "replaced by", "superseded", "archived", "9006"]
    )


def test_active_docs_dont_reference_deprecated():
    """Active docs should not reference deprecated PEV implementations
    except in explicit deprecation notices."""
    failures = []

    for doc_rel in ACTIVE_DOCS:
        doc_path = REPO_ROOT / doc_rel
        if not doc_path.exists():
            continue

        text = doc_path.read_text()

        for name, pattern in DEPRECATED_REFS.items():
            for match in pattern.finditer(text):
                # Get surrounding context (~80 chars)
                start = max(0, match.start() - 40)
                end = min(len(text), match.end() + 40)
                context = text[start:end]

                if _is_deprecation_context(context):
                    continue

                line_num = text[: match.start()].count("\n") + 1
                failures.append(
                    f"  {doc_rel}:{line_num}: references '{name}' "
                    f"outside deprecation context"
                )

    assert not failures, (
        "Active docs must not reference deprecated PEV implementations:\n"
        + "\n".join(failures)
        + "\n\nUpdate these references to point to pev_subagent_adversarial.sh "
        "(plan 9006)."
    )


def test_subagent_script_is_primary_implementation():
    """The subagent script must exist and be the documented primary implementation."""
    subagent_script = REPO_ROOT / ".claude" / "scripts" / "pev_subagent_adversarial.sh"
    assert subagent_script.exists(), (
        "pev_subagent_adversarial.sh must exist as primary PEV implementation"
    )

    # Verify it's executable
    assert subagent_script.stat().st_mode & 0o111, (
        "pev_subagent_adversarial.sh must be executable"
    )
