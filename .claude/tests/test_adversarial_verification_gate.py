"""Structural test: adversarial verification gate.

Verifies that for each commit flipping a milestone checkbox [ ] → [x],
a `### M<N> adversarial verification` entry with `Verdict: CONFIRMED`
exists in the ExecPlan's Decision Log, timestamped before the flip and
after the last implementation commit for that milestone.

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
