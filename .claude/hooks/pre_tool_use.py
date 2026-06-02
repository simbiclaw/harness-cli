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
# merge-into-harness guard helpers
# ---------------------------------------------------------------------------

MERGE_MAIN_RE = re.compile(r"\bgit\s+merge\s+.*\b(?:origin/)?main\b")


def is_merge_main_into_harness(cmd: str) -> bool:
    """True if cmd is a git merge targeting (origin/)main while on harness."""
    if not MERGE_MAIN_RE.search(cmd):
        return False
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=5,
        )
        return result.stdout.strip() == "harness"
    except (OSError, subprocess.TimeoutExpired):
        return False


def main_has_non_harness_commits() -> bool:
    """True if main has non-harness commits not yet on harness."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "harness..main"],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False  # fail open — can't determine, let it through

    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        # Harness commits have subject prefix "harness(" or "harness:"
        if not re.match(r"^\w+\s+harness[\(\:]", line):
            return True
    return False


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
        if is_active_plan(target):
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

        # ---- Guard 1: uncommitted flip blocks code edits ----
        if not is_active_plan(target):
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

        # ---- Guard 5: block merge main→harness when non-harness commits exist ----
        if is_merge_main_into_harness(cmd):
            if main_has_non_harness_commits():
                print(json.dumps({
                    "continue": False,
                    "reason": (
                        "Merge from main into harness blocked: main has "
                        "non-harness commits that are not on harness. "
                        "Cherry-pick only harness-type commits, or ensure "
                        "all commits on main follow the harness commit type "
                        "convention before merging."
                    ),
                }))
                return 0

    # Default allow.
    print(json.dumps({"continue": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
