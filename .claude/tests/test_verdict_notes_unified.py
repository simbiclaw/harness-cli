"""M2: Verdict/notes unification — structural tests.

Acceptance tests for M2:
- test_b_writes_notes_directly: B's goal prompt directs writing to notes files
- test_no_separate_verdict_file: No code path writes to .pev-signals/M<N>-verdict.txt
- Existing test_repair_feedback_gate.py tests must continue to pass
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / ".claude" / "scripts"
TMUX_SCRIPT = SCRIPTS_DIR / "pev_tmux_adversarial.sh"
SIGNAL_DIR = REPO_ROOT / ".pev-signals"
NOTES_PATTERN = re.compile(r"-notes/M")


class TestBWritesNotesDirectly:
    """B's output produces valid notes entries in implementation notes files."""

    def test_b_prompt_mentions_notes_dir(self):
        """B's goal prompt must direct writing to the -notes directory, not verdict files."""
        script = TMUX_SCRIPT.read_text()
        # B's prompt should reference the notes directory
        assert NOTES_PATTERN.search(script), (
            "B's goal prompt must direct writing to docs/exec-plans/active/*-notes/M*.md"
        )

    def test_b_prompt_mentions_entry_types(self):
        """B's goal prompt must mention the implementation notes entry types."""
        script = TMUX_SCRIPT.read_text()
        # B should know which entry types to use
        assert "[plan-confirmed]" in script, (
            "B's prompt must mention [plan-confirmed] entry type for CONFIRMED verdicts"
        )
        assert "[deviation]" in script, (
            "B's prompt must mention [deviation] entry type for constraint-violation"
        )
        assert "[human-todo]" in script, (
            "B's prompt must mention [human-todo] entry type for semantic failures"
        )

    def test_arbiter_prompt_reads_notes(self):
        """Arbiter's prompt must direct reading notes, not separate verdict files."""
        script = TMUX_SCRIPT.read_text()
        # Arbiter should read notes directory to determine routing
        assert NOTES_PATTERN.search(script), (
            "Arbiter's prompt must direct reading from notes directory"
        )


class TestNoSeparateVerdictFile:
    """No code path writes to .pev-signals/M<N>-verdict.txt as a separate artifact."""

    def test_tmux_script_no_verdict_file_write(self):
        """The tmux script must not reference M<N>-verdict.txt as an output target."""
        script = TMUX_SCRIPT.read_text()
        # Should NOT contain directives to write to M<N>-verdict.txt
        verdict_pattern = re.compile(r"M\d+-verdict\.txt")
        matches = verdict_pattern.findall(script)
        assert len(matches) == 0, (
            f"tmux script must not reference separate verdict files. "
            f"Found: {matches}"
        )

    def test_no_verdict_files_in_signals_dir(self):
        """Structural grep: no file under .claude/ should write to M<N>-verdict.txt."""
        claude_dir = REPO_ROOT / ".claude"
        verdict_pattern = re.compile(r"M\w*-verdict\.txt")
        violations = []

        for path in sorted(claude_dir.rglob("*")):
            if path.is_dir():
                continue
            if path.suffix in ('.pyc', '.pyo'):
                continue
            if path == TMUX_SCRIPT:
                continue  # already tested above
            try:
                content = path.read_text()
            except (UnicodeDecodeError, IsADirectoryError):
                continue
            matches = verdict_pattern.findall(content)
            if matches and path.suffix != '.md':
                violations.append(
                    f"  {path.relative_to(REPO_ROOT)}: {matches}"
                )
            # For .md files, only flag if it's an instruction to write (not a reference to the artifact)
            elif matches and path.suffix == '.md':
                # Check if the reference is prescriptive (directing writes) not descriptive
                for m in matches:
                    context_pattern = re.compile(
                        r"(write|create|output|save)\s+.*?" + re.escape(m),
                        re.IGNORECASE
                    )
                    if context_pattern.search(content):
                        violations.append(
                            f"  {path.relative_to(REPO_ROOT)}: directs writing {m}"
                        )

        assert not violations, (
            "Files must not direct writing to separate verdict files:\n"
            + "\n".join(violations)
        )

    def test_signals_watch_references_notes_not_verdict(self):
        """The tmux script's signal watcher should reference notes, not verdict files."""
        script = TMUX_SCRIPT.read_text()
        # The watcher/show loop should reference notes, not verdict files
        verdict_pattern = re.compile(r"M\$\{?m\}?-verdict\.txt")
        matches = verdict_pattern.findall(script)
        assert len(matches) == 0, (
            f"Signal watcher must not display separate verdict files. Found: {matches}"
        )
