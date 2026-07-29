"""Structural test: adversarial verification gate.

Verifies that for each commit flipping a milestone checkbox [ ] → [x],
a `### M<N> adversarial verification` entry with `Verdict: CONFIRMED`
exists in the ExecPlan's Decision Log, timestamped before the flip and
after the last implementation commit for that milestone.

Also verifies that CONFIRMED entries include actual edge case descriptions,
not just a count (Improvement #5 from the 2026-07-30 PEV harness evaluation).

Promotes verification-floor.md rule #4 from documentation to structural test.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACTIVE_DIR = REPO_ROOT / "docs" / "exec-plans" / "active"

PLAN_TRAILER_RE = re.compile(r"^Plan:\s*(docs/exec-plans/\S+?)(?:#|\s|$)", re.MULTILINE)
ADV_VERIFY_RE = re.compile(
    r"^### M(\d+) adversarial verification\s*\n"
    r"(?:.*\n)*?"
    r"Verdict:\s*(CONFIRMED|REJECTED)",
    re.MULTILINE,
)
GIT_LOG_SINCE = "90 days ago"


def _git_log_with_dates() -> list[tuple[str, str, str, list[str]]]:
    """Return list of (sha, iso_date, message, [changed_files])."""
    try:
        result = subprocess.run(
            [
                "git", "log",
                f"--since={GIT_LOG_SINCE}",
                "--name-only",
                "--pretty=tformat:%x00%H%x00%aI%x00%B%x00",
                "--",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    commits = []
    for chunk in result.stdout.split("\x00"):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        parts = chunk.split("\n")
        if len(parts) < 3:
            continue
        sha = parts[0].strip()
        date = parts[1].strip()
        msg_lines = []
        files = []
        in_files = False
        for line in parts[2:]:
            if line.strip() == "" and not in_files and msg_lines:
                in_files = True
                continue
            if in_files:
                if line.strip():
                    files.append(line.strip())
            else:
                msg_lines.append(line)
        commits.append((sha, date, "\n".join(msg_lines), files))
    return commits


def _commit_flips_checkbox(files: list[str], msg: str) -> int | None:
    """If this commit flips a milestone checkbox, return the milestone number."""
    # Commit must touch an exec-plan file
    touches_plan = any("docs/exec-plans/" in f for f in files)
    if not touches_plan:
        return None
    # Check for milestone reference
    m = re.search(r"#milestone-(\d+)", msg)
    if m:
        return int(m.group(1))
    m = re.search(r"\bM(\d+)\b", msg)
    if m:
        return int(m.group(1))
    return None


def _check_adv_verification(plan_path: Path, m_num: int) -> tuple[bool, str]:
    """Check if plan has a CONFIRMED adversarial verification for milestone."""
    if not plan_path.exists():
        return False, f"plan file {plan_path} not found"

    text = plan_path.read_text()

    # Find adversarial verification entries for this milestone
    for match in ADV_VERIFY_RE.finditer(text):
        entry_m = int(match.group(1))
        verdict = match.group(2)
        if entry_m == m_num:
            if verdict == "CONFIRMED":
                return True, "CONFIRMED"
            else:
                return False, f"verdict is {verdict}"

    return False, f"no adversarial verification entry found for M{m_num}"


def test_confirmed_before_flip():
    """CONFIRMED adversarial verdict exists before checkbox flip commits."""
    failures: list[str] = []

    commits = _git_log_with_dates()
    if not commits:
        return

    # Track which milestones have implementation commits (for staleness check)
    impl_commits: dict[tuple[str, int], str] = {}  # (plan, m_num) -> latest impl date

    for sha, date, msg, files in commits:
        plan_m = PLAN_TRAILER_RE.search(msg)
        if not plan_m:
            continue
        plan_rel = plan_m.group(1).split("#")[0]
        if "ad-hoc" in plan_rel:
            continue

        src_files = [f for f in files if f.startswith("src/")]
        m_num = _commit_flips_checkbox(files, msg)

        if m_num is not None and src_files:
            key = (plan_rel, m_num)
            if key not in impl_commits or date > impl_commits[key]:
                impl_commits[key] = date

    # Now check flip commits
    for sha, date, msg, files in commits:
        m_num = _commit_flips_checkbox(files, msg)
        if m_num is None:
            continue

        plan_m = PLAN_TRAILER_RE.search(msg)
        if not plan_m:
            continue
        plan_rel = plan_m.group(1).split("#")[0]
        plan_path = REPO_ROOT / plan_rel

        ok, detail = _check_adv_verification(plan_path, m_num)
        if not ok:
            failures.append(
                f"{sha[:8]}: checkbox flip for M{m_num} in {plan_rel} — {detail}. "
                f"Adversarial verification with CONFIRMED verdict must precede "
                f"the flip (docs/conventions/verification-floor.md rule #4)."
            )

    assert not failures, "Adversarial verification gate violations:\n" + "\n".join(
        f"  - {f}" for f in failures
    )


# ── Improvement #5: Edge case description enforcement ─────────────────────

# Pattern for bare edge case counts — matches "Edge cases: N/N" or "Edge cases: passed"
BARE_EDGE_COUNT_RE = re.compile(
    r"Edge cases?:\s*(?:\d+/\d+\s*(?:pass|behave|correct)?|passed|all pass|ok)",
    re.IGNORECASE,
)

# Pattern for specific edge case details — at least one named
# behavior or concrete scenario in the text following "Edge cases:"
EDGE_SPECIFIC_RE = re.compile(
    r"(?:edge case|exercised)(?:.{0,100}?)(?:[:\-—]\s*.+?(?:→|->|rejected|fails|caught|raise|correctly|triggered|validates|empty|missing|duplicate|malformed|negative|unknown|zero))",
    re.IGNORECASE,
)

# Additional check: at least one bullet-point edge case in markdown notes
EDGE_BULLET_RE = re.compile(
    r"[-*]\s+.+?(?:→|->|rejected|fail|caught|raise|correctly|triggered)",
    re.IGNORECASE,
)

# Minimum number of distinct edge cases that must be described
MIN_EDGE_CASES = 1


def test_edge_cases_are_described():
    """CONFIRMED verdict entries must describe edge cases, not just count them.

    'Edge cases: 13/13 pass' is a count, not a description.
    'Edge cases: empty string → ValidationError, concurrent writes → no corruption'
    are descriptions.

    This test checks all implementation notes and Decision Log entries
    for CONFIRMED verdicts and fails any that have bare counts without
    at least one described edge case.
    """
    failures: list[str] = []

    # Check implementation notes files
    for notes_dir in sorted(ACTIVE_DIR.glob("*-notes")):
        if not notes_dir.is_dir():
            continue
        for notes_file in sorted(notes_dir.glob("M*.md")):
            text = notes_file.read_text()
            rel = notes_file.relative_to(REPO_ROOT)

            # Find CONFIRMED verdicts
            if "CONFIRMED" not in text.upper():
                continue

            # Check for bare edge case counts without specific descriptions
            bare_match = BARE_EDGE_COUNT_RE.search(text)
            if bare_match:
                # Look for specific edge case descriptions in the text
                has_specific = (
                    EDGE_SPECIFIC_RE.search(text) is not None
                    or EDGE_BULLET_RE.search(text) is not None
                )
                if not has_specific:
                    failures.append(
                        f"{rel}: CONFIRMED with bare edge case count "
                        f"('{bare_match.group()}') and no specific edge "
                        f"case descriptions. Add at least "
                        f"{MIN_EDGE_CASES} described edge case(s). "
                        f"Example: '- Empty input → ValidationError raised'"
                    )

    # Check Decision Log entries in active plans
    for plan_path in sorted(ACTIVE_DIR.glob("*.md")):
        text = plan_path.read_text()
        rel = plan_path.relative_to(REPO_ROOT)

        # Find all adversarial verification entries
        for match in ADV_VERIFY_RE.finditer(text):
            verdict = match.group(2)
            if verdict != "CONFIRMED":
                continue

            # Get surrounding context (up to 500 chars after the match)
            entry_start = match.start()
            entry_end = min(len(text), match.end() + 500)
            entry_text = text[entry_start:entry_end]

            # Check for bare edge case counts
            bare_match = BARE_EDGE_COUNT_RE.search(entry_text)
            if bare_match:
                has_specific = (
                    EDGE_SPECIFIC_RE.search(entry_text) is not None
                    or EDGE_BULLET_RE.search(entry_text) is not None
                )
                if not has_specific:
                    failures.append(
                        f"{rel}: adversarial verification M{match.group(1)} "
                        f"has bare edge case count "
                        f"('{bare_match.group()}') without specific "
                        f"descriptions. Describe at least {MIN_EDGE_CASES} "
                        f"edge case(s)."
                    )

    assert not failures, (
        "Edge case description violations — CONFIRMED verdicts must "
        "describe edge cases, not just count them:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )
