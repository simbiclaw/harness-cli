#!/usr/bin/env python3
"""
PreToolUse hook for Claude Code.

Multiplexes five guards:
  0. Single-checkbox-flip guard (Harness 4: one milestone flip per edit).
  1. Uncommitted-flip guard (Harness 4: commit flip before writing code).
  2. Sensitive-path guard (Harness 1: Tier C escalation).
  3. Package-manager guard (Harness 1 + Harness 3: dep vetting).
  4. Force-push guard (Harness 4: commit hygiene).

Hook contract: read JSON event from stdin. Print JSON to stdout.
Exit 0 with {"continue": true} to allow.
Exit 0 with {"continue": false, "reason": "..."} to block.

See: https://docs.claude.com/en/docs/claude-code/hooks
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SENSITIVE_PATHS_FILE = REPO_ROOT / ".claude" / "sensitive-paths.txt"
ACTIVE_PLANS_DIR = REPO_ROOT / "docs" / "exec-plans" / "active"

CHECKBOX_LINE = re.compile(r"^- \[x\]", re.MULTILINE)


def _is_arbiter() -> bool:
    """Detect whether this session is the PEV arbiter.

    The PEV tmux script sets PEV_ARBITER=true when spawning the arbiter
    Claude Code session. This gives the arbiter autonomy to flip checkboxes
    and edit .pev-signals/ without triggering guard blocks.
    """
    return os.environ.get("PEV_ARBITER", "").lower() == "true"


# ---------------------------------------------------------------------------
# sensitive-path helpers
# ---------------------------------------------------------------------------

def load_sensitive_patterns() -> list[str]:
    if not SENSITIVE_PATHS_FILE.exists():
        return []
    return [
        line.strip()
        for line in SENSITIVE_PATHS_FILE.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


def path_is_sensitive(path: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(path, f"./{pat}"):
            return True
    return False


def has_resolved_steering_for(path: str) -> bool:
    """Check whether any active ExecPlan has 'Awaiting Steering: resolved'
    referencing this path."""
    if not ACTIVE_PLANS_DIR.exists():
        return False
    for plan in ACTIVE_PLANS_DIR.glob("*.md"):
        text = plan.read_text()
        if "Awaiting Steering: resolved" in text and path in text:
            return True
    return False


# ---------------------------------------------------------------------------
# checkbox-flip helpers
# ---------------------------------------------------------------------------

def is_active_plan(target: str) -> bool:
    """Check whether *target* is a file under docs/exec-plans/active/."""
    try:
        Path(target).resolve().relative_to(ACTIVE_PLANS_DIR)
        return True
    except (ValueError, OSError):
        return False


def count_checked(text: str) -> int:
    return len(CHECKBOX_LINE.findall(text))


def simulate_after_edit(file_path: str, params: dict) -> str | None:
    """Return what the file would look like after this edit, or None."""
    path = Path(file_path)
    if not path.exists():
        return None
    current = path.read_text()

    if "old_string" in params:
        old = params["old_string"]
        new = params.get("new_string", "")
        if params.get("replace_all"):
            return current.replace(old, new)
        else:
            return current.replace(old, new, 1)
    elif "content" in params:
        return params["content"]
    return None


def count_new_flips(file_path: str, params: dict) -> int:
    """How many NEW [x] checkboxes would this edit introduce?"""
    after = simulate_after_edit(file_path, params)
    if after is None:
        return 0
    path = Path(file_path)
    before = path.read_text() if path.exists() else ""
    delta = count_checked(after) - count_checked(before)
    return max(delta, 0)


def has_uncommitted_flip() -> bool:
    """Return True if git diff shows a new [x] checkbox in any active plan."""
    if not ACTIVE_PLANS_DIR.exists():
        return False
    try:
        result = subprocess.run(
            ["git", "diff", "--", "docs/exec-plans/active/"],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False

    # A new [x] checkbox appears as an added line starting with "+- [x]"
    for line in result.stdout.splitlines():
        if line.startswith("+") and CHECKBOX_LINE.search(line):
            return True
    return False


# ---------------------------------------------------------------------------
# PEV verification gate helpers
# ---------------------------------------------------------------------------

CHECKBOX_FLIP_RE = re.compile(r"^- \[ \] M(\d+)", re.MULTILINE)
CHECKBOX_FLIPPED_RE = re.compile(r"^- \[x\] M(\d+)", re.MULTILINE)
STATE_FILE = REPO_ROOT / ".pev-signals" / "state.json"
VERDICT_BADGE_RE = re.compile(
    r"\[(?:plan-confirmed|deviation|human-todo|discovery)\]",
)


def _milestones_being_flipped(file_path: str, params: dict) -> list[int]:
    """Return milestone numbers that change from [ ] to [x] in this edit."""
    after = simulate_after_edit(file_path, params)
    if after is None:
        return []
    path = Path(file_path)
    before = path.read_text() if path.exists() else ""

    before_unchecked = {int(m.group(1)) for m in CHECKBOX_FLIP_RE.finditer(before)}
    after_checked = {int(m.group(1)) for m in CHECKBOX_FLIPPED_RE.finditer(after)}

    # Milestones that were unchecked before and checked after
    return sorted(before_unchecked & after_checked)


def _check_pev_verification(plan_path: str, milestones: list[int]) -> bool:
    """Check that each milestone has PEV verification completed.

    Returns True if all milestones are verified, False if any are not.
    Blocks the edit (prints JSON to stdout) if verification is missing.
    """
    plan = Path(plan_path)
    notes_dir = plan.parent / f"{plan.stem}-notes"

    # Read state.json for milestone status
    state_milestones = {}
    if STATE_FILE.exists():
        try:
            import json
            state = json.loads(STATE_FILE.read_text())
            state_milestones = state.get("milestones", {})
        except (json.JSONDecodeError, OSError):
            pass

    unverified = []
    for m_num in milestones:
        key = f"M{m_num}"
        state_ok = state_milestones.get(key) == "confirmed"

        notes_file = notes_dir / f"M{m_num}.md"
        notes_ok = notes_file.exists() and bool(
            VERDICT_BADGE_RE.search(notes_file.read_text())
        )

        # Either state.json confirmation OR notes with verdict is sufficient.
        # (notes are the canonical record; state.json is a cache)
        if not (state_ok or notes_ok):
            unverified.append(str(m_num))

    if unverified:
        rel = str(plan.relative_to(REPO_ROOT))
        ms = ", ".join(unverified)
        print(json.dumps({
            "continue": False,
            "reason": (
                f"Milestone(s) M{ms} checkbox flip blocked: no adversarial "
                f"verification found. PEV requires subagent B to write a "
                f"verdict to {plan.stem}-notes/M<N>.md before the checkbox "
                f"can be flipped. See postmortem "
                f"docs/postmortems/2026-07-29-pev-without-pev.md."
            ),
        }))
        return False

    return True


# ---------------------------------------------------------------------------
# package-install helpers
# ---------------------------------------------------------------------------

PKG_MGR_PATTERNS = [
    re.compile(r"\buv\s+add\s+(--dev\s+)?([\w\-\.\[\]]+)"),
    re.compile(r"\buv\s+pip\s+install\s+([\w\-\.\[\]]+)"),
    re.compile(r"\bpip\s+install\s+([\w\-\.\[\]]+)"),
    re.compile(r"\bpipx\s+install\s+([\w\-\.\[\]]+)"),
]


def parse_pkg_install(cmd: str) -> str | None:
    for pat in PKG_MGR_PATTERNS:
        m = pat.search(cmd)
        if m:
            raw = m.groups()[-1]
            return raw.split("[", 1)[0]
    return None


def has_dep_vet_for(package: str) -> bool:
    vet_file = REPO_ROOT / "docs" / "decisions" / f"dep-vet-{package}.md"
    return vet_file.exists()


def is_force_push(cmd: str) -> bool:
    if "git push" not in cmd:
        return False
    return "--force" in cmd or " -f " in cmd or "--force-with-lease" in cmd


# ---------------------------------------------------------------------------
# PEV agent gate helpers
# ---------------------------------------------------------------------------

REQUIRED_AGENT_IDS = {"p_agent_id", "e_agent_id", "v_agent_id"}


def _pev_agents_spawned() -> bool:
    """Check whether state.json records P, E, V agent IDs.

    The Arbiter must spawn three persistent subagents per ExecPlan
    (docs/conventions/pev-loop.md § The three agents). After spawning,
    the Arbiter writes their agent IDs to state.json. This function
    verifies that all three IDs are present.
    """
    if not STATE_FILE.exists():
        return False
    try:
        state = json.loads(STATE_FILE.read_text())
        agent_ids = state.get("agent_ids", {})
        return bool(
            agent_ids.get("p_agent_id")
            and agent_ids.get("e_agent_id")
            and agent_ids.get("v_agent_id")
        )
    except (json.JSONDecodeError, OSError):
        return False


def _is_arbiter_safe_path(target: str) -> bool:
    """Paths the Arbiter may edit without spawning P/E/V agents.

    The Arbiter is allowed to edit:
    - Active ExecPlan files (docs/exec-plans/active/*.md)
    - Implementation notes (docs/exec-plans/active/*-notes/*.md)
    - PEV coordination files (.pev-signals/*)

    Everything else requires P/E/V agents to be spawned first.
    """
    try:
        rel = str(Path(target).resolve().relative_to(REPO_ROOT))
    except (ValueError, OSError):
        return False

    return (
        rel.startswith("docs/exec-plans/active/")
        or rel.startswith(".pev-signals/")
        or rel == "CLAUDE.md"
        or rel.startswith("docs/conventions/")
    )


# ---------------------------------------------------------------------------
# harness-branch guard helpers
# ---------------------------------------------------------------------------

# Match git commands that add commits to the current branch.
# commit, merge, and cherry-pick all create new commits.
COMMIT_LIKE_RE = re.compile(
    r"(?:^|;|&&|\|\|)\s*git\s+(commit|merge)\b"
)


def is_on_harness() -> bool:
    """True if HEAD is the harness branch."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=5,
        )
        return result.stdout.strip() == "harness"
    except (OSError, subprocess.TimeoutExpired):
        return False


def is_cherry_pick(cmd: str) -> bool:
    """True if cmd is a git cherry-pick."""
    return bool(re.search(r"(?:^|;|&&|\|\|)\s*git\s+cherry-pick\b", cmd))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    event = json.load(sys.stdin)
    tool = event.get("tool_name", "")
    params = event.get("tool_input", {})

    if tool in ("Edit", "Write", "MultiEdit", "Create"):
        target = params.get("file_path") or params.get("path") or ""

        # ---- Guard 0: single checkbox flip ----
        # Arbiter exemption: the arbiter flips checkboxes autonomously;
        # skip the single-flip guard for arbiter-originated edits.
        if is_active_plan(target) and not _is_arbiter():
            flips = count_new_flips(target, params)
            if flips > 1:
                print(json.dumps({
                    "continue": False,
                    "reason": (
                        f"This edit would flip {flips} milestone checkboxes "
                        f"in one go, but at most 1 is allowed per commit "
                        f"(docs/conventions/commit-hygiene.md). "
                        f"Flip one checkbox, commit, then flip the next."
                    ),
                }))
                return 0

        # ---- Guard 0.5: PEV verification gate ----
        # Block checkbox flips unless the milestone has been verified by
        # subagent B and the verdict is recorded in implementation notes.
        # Promotes Lesson 2 from postmortem 2026-07-29-pev-without-pev.md.
        if is_active_plan(target) and not _is_arbiter():
            flips = count_new_flips(target, params)
            if flips > 0:
                # Determine which milestones are being flipped
                flipped = _milestones_being_flipped(target, params)
                if flipped:
                    verified = _check_pev_verification(target, flipped)
                    if not verified:
                        return 0

        # ---- Guard 1: uncommitted flip blocks code edits ----
        # Arbiter exemption: the arbiter edits plan files and .pev-signals/
        # autonomously; skip the uncommitted-flip blocker for arbiter sessions.
        if not is_active_plan(target) and not _is_arbiter():
            if has_uncommitted_flip():
                print(json.dumps({
                    "continue": False,
                    "reason": (
                        "An active ExecPlan has an uncommitted milestone "
                        "checkbox flip. Commit the flip first "
                        "(docs/conventions/commit-hygiene.md: one flip "
                        "per commit, commit before continuing), then "
                        "resume editing code."
                    ),
                }))
                return 0

        # ---- Guard 2: sensitive path ----
        rel = ""
        if target:
            try:
                rel = str(Path(target).resolve().relative_to(REPO_ROOT))
            except (ValueError, OSError):
                rel = ""
        patterns = load_sensitive_patterns()
        if rel and path_is_sensitive(rel, patterns):
            if not has_resolved_steering_for(rel):
                print(json.dumps({
                    "continue": False,
                    "reason": (
                        f"Path '{rel}' matches a sensitive pattern (see "
                        f".claude/sensitive-paths.txt). This is a Tier C "
                        f"decision per docs/conventions/ask-threshold.md. "
                        f"Stop, open an 'Awaiting Steering' section in the "
                        f"active ExecPlan describing the change you intend, "
                        f"and wait for the human. Once resolved, mark the "
                        f"section 'Awaiting Steering: resolved' and reference "
                        f"the path '{rel}' so this hook will allow the edit."
                    ),
                }))
                return 0

        # ---- Guard 2.5: PEV agent gate ----
        # Block implementation edits when P/E/V subagents haven't been
        # spawned for the current ExecPlan. The Arbiter must spawn three
        # persistent agents (P, E, V) before touching any code outside
        # docs/exec-plans/active/ and .pev-signals/.
        if not _is_arbiter_safe_path(target) and not _pev_agents_spawned():
            print(json.dumps({
                "continue": False,
                "reason": (
                    "No PEV agents spawned for this ExecPlan. Per "
                    "docs/conventions/pev-loop.md § The three agents, "
                    "every ExecPlan requires three persistent subagents "
                    "(P, E, V) before implementation begins. Spawn them "
                    "via the Agent tool, then record their agent IDs in "
                    ".pev-signals/state.json under 'agent_ids': "
                    '{"p_agent_id": "...", "e_agent_id": "...", '
                    '"v_agent_id": "..."}. Plan files, notes, and '
                    ".pev-signals/ remain editable by the Arbiter."
                ),
            }))
            return 0

    # ---- Guard 3 + 4: Bash command guards ----
    if tool == "Bash":
        cmd = params.get("command", "")

        # Force-push.
        if is_force_push(cmd) and os.environ.get("CLAUDE_FORCE_PUSH_OK") != "1":
            print(json.dumps({
                "continue": False,
                "reason": (
                    "Force-push is blocked. Per "
                    "docs/conventions/commit-hygiene.md, force-pushes "
                    "require an explicit unlock and a Decision Log entry "
                    "explaining why. Do not bypass without human approval."
                ),
            }))
            return 0

        # Package install.
        package = parse_pkg_install(cmd)
        if package and not has_dep_vet_for(package):
            print(json.dumps({
                "continue": False,
                "reason": (
                    f"Package '{package}' has no dep-vet record at "
                    f"docs/decisions/dep-vet-{package}.md. Per "
                    f"docs/conventions/deps-and-secrets.md, run the "
                    f"dep-vetter skill on '{package}' first. If approved, "
                    f"the skill writes the dep-vet file and this hook will "
                    f"allow the install."
                ),
            }))
            return 0

        # ---- Guard 5: block direct commits on harness ----
        if is_on_harness() and COMMIT_LIKE_RE.search(cmd) and not is_cherry_pick(cmd):
            print(json.dumps({
                "continue": False,
                "reason": (
                    "Direct commits and merges on the harness branch are "
                    "blocked. All changes must land on main first. Harness-type "
                    "commits are cherry-picked from main to harness by "
                    "automation. If you need to add harness commits to this "
                    "branch, use git cherry-pick from main."
                ),
            }))
            return 0

        # ---- Guard 6: commit authority — only the Arbiter commits ----
        # Per docs/conventions/pev-loop.md § Commit authority, only the
        # Arbiter may commit. P, E, and V subagents never commit. Their
        # changes accumulate in the working tree; the Arbiter bundles
        # everything into one commit per milestone after CONFIRMED.
        if COMMIT_LIKE_RE.search(cmd) and not _is_arbiter():
            print(json.dumps({
                "continue": False,
                "reason": (
                    "git commit is blocked. Per "
                    "docs/conventions/pev-loop.md § Commit authority, "
                    "only the Arbiter commits. P, E, and V subagents "
                    "never commit — their work accumulates in the "
                    "working tree. The Arbiter bundles all changes "
                    "(contract, implementation, verdict, checkbox flip) "
                    "into one commit per milestone after V CONFIRMED. "
                    "If you are P/E/V, do not commit — hand off to the "
                    "Arbiter. If you are the Arbiter, set "
                    "PEV_ARBITER=true in your environment."
                ),
            }))
            return 0

    # Default allow.
    print(json.dumps({"continue": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
