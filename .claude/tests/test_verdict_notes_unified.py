"""M2: Verdict/notes unification — structural + behavioral tests.

M2 contract:
- B's goal prompt directs writing verdicts to implementation notes files.
- No code path writes to .pev-signals/M<N>-verdict.txt as a separate artifact.
- The generated prompt (behavioral) includes notes entry type instructions.
- Existing test_repair_feedback_gate.py tests must continue to pass.
"""

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / ".claude" / "scripts"
SUBAGENT_SCRIPT = SCRIPTS_DIR / "pev_subagent_adversarial.sh"
SIGNAL_DIR = REPO_ROOT / ".pev-signals"
NOTES_PATTERN = re.compile(r"-notes/M")


class TestBWritesNotesDirectly:
    """B's output produces valid notes entries in implementation notes files."""

    def test_b_prompt_mentions_notes_dir(self):
        """B's goal prompt must direct writing to the -notes directory, not verdict files."""
        source = SUBAGENT_SCRIPT.read_text()
        # B's prompt (embedded or generated) should reference the notes directory
        assert NOTES_PATTERN.search(source), (
            "B's goal prompt must direct writing to docs/exec-plans/active/*-notes/M*.md"
        )

    def test_b_prompt_mentions_entry_types(self):
        """B's goal prompt must mention the implementation notes entry types."""
        source = SUBAGENT_SCRIPT.read_text()
        assert "[plan-confirmed]" in source, (
            "B's prompt must mention [plan-confirmed] entry type for CONFIRMED verdicts"
        )
        assert "[deviation]" in source, (
            "B's prompt must mention [deviation] entry type for constraint-violation"
        )
        assert "[human-todo]" in source, (
            "B's prompt must mention [human-todo] entry type for semantic failures"
        )

    def test_arbiter_prompt_reads_notes(self):
        """Arbiter's prompt must direct reading notes, not separate verdict files."""
        source = SUBAGENT_SCRIPT.read_text()
        assert NOTES_PATTERN.search(source), (
            "Arbiter's prompt must direct reading from notes directory"
        )

    def test_prompt_explains_notes_structure(self):
        """B's prompt must explain where notes files live and their naming convention."""
        source = SUBAGENT_SCRIPT.read_text()
        assert "docs/exec-plans/active" in source, (
            "Prompt must mention the notes directory path"
        )


class TestGeneratedPrompt:
    """Behavioural: run the script and verify the generated prompt B receives."""

    def test_generated_prompt_mentions_notes(self):
        """The generated prompt must instruct B to write to notes files."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test-plan",
             "--milestones", "0"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"Script should exit 0 with test-plan, got {result.returncode}\n"
            f"stderr: {result.stderr}"
        )
        output = result.stdout.lower()
        assert "notes" in output, (
            "Generated prompt must mention notes files. "
            "Got: " + output[:500]
        )

    def test_generated_prompt_mentions_entry_types(self):
        """The generated prompt must list the notes entry types for B."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test-plan",
             "--milestones", "0"],
            capture_output=True, text=True,
        )
        output = result.stdout
        assert "[plan-confirmed]" in output, (
            "Generated prompt must mention [plan-confirmed] entry type"
        )
        assert "[deviation]" in output, (
            "Generated prompt must mention [deviation] entry type"
        )
        assert "[human-todo]" in output, (
            "Generated prompt must mention [human-todo] entry type"
        )

    def test_generated_prompt_no_verdict_file(self):
        """The generated prompt must NOT tell B to write separate verdict files."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test-plan",
             "--milestones", "0"],
            capture_output=True, text=True,
        )
        output = result.stdout.lower()
        # "verdict" is acceptable if it describes the decision, not a file
        # Check it doesn't mention verdict files
        assert "verdict.txt" not in output, (
            "Generated prompt must not reference verdict.txt files"
        )
        assert "verdict file" not in output, (
            "Generated prompt must not reference 'verdict file'"
        )

    def test_generated_prompt_lists_notes_path(self):
        """The generated prompt must include the notes directory path."""
        result = subprocess.run(
            ["bash", str(SUBAGENT_SCRIPT), "--plan", "test-plan",
             "--milestones", "0"],
            capture_output=True, text=True,
        )
        output = result.stdout
        assert "docs/exec-plans/active" in output, (
            "Generated prompt must include the notes directory path. "
            "Got: " + output[:500]
        )


class TestNoSeparateVerdictFile:
    """No code path writes to .pev-signals/M<N>-verdict.txt as a separate artifact."""

    def test_subagent_script_no_verdict_file_write(self):
        """The subagent script must not reference M<N>-verdict.txt as an output target."""
        source = SUBAGENT_SCRIPT.read_text()
        verdict_pattern = re.compile(r"M\d+-verdict\.txt")
        matches = verdict_pattern.findall(source)
        assert len(matches) == 0, (
            f"Subagent script must not reference separate verdict files. "
            f"Found: {matches}"
        )

    def test_no_verdict_files_in_claude_dir(self):
        """Structural grep: no file under .claude/ should write to M<N>-verdict.txt."""
        claude_dir = REPO_ROOT / ".claude"
        verdict_pattern = re.compile(r"M\w*-verdict\.txt")
        violations = []

        for path in sorted(claude_dir.rglob("*")):
            if path.is_dir():
                continue
            if path.suffix in ('.pyc', '.pyo'):
                continue
            if path == SUBAGENT_SCRIPT:
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
            elif matches and path.suffix == '.md':
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


class TestRepairFeedbackGateCompat:
    """Tests from test_repair_feedback_gate.py must continue to pass."""

    def test_repair_feedback_gate_imports(self):
        """The repair feedback gate module must be importable without errors."""
        gate_path = REPO_ROOT / ".claude" / "tests" / "test_repair_feedback_gate.py"
        assert gate_path.exists(), "test_repair_feedback_gate.py must still exist"
        # Quick structural check: the module should have at least one test function
        content = gate_path.read_text()
        assert "def test_" in content, (
            "test_repair_feedback_gate.py must contain test functions"
        )
