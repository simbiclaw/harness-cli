"""M1 acceptance test: verify the three convention files exist with required sections."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_required_convention_files_present():
    files = {
        "docs/conventions/verification-floor.md": [
            "Per-layer test floor",
            "Repo",
            "Service",
            "Runtime",
            "UI",
        ],
        "docs/conventions/i-dont-know-protocol.md": [
            "Rationale",
            "Cited",
            "Empirical",
            "Marked-as-guess",
            "Forbidden phrases",
        ],
        "docs/conventions/commit-hygiene.md": [
            "One commit per milestone-checkbox flip",
            "Structural tests pass before any flip",
        ],
        "docs/conventions/implementation-notes.md": [
            "Entry types",
            "plan-confirmed",
            "discovery",
            "deviation",
            "human-todo",
            "What the plan said",
            "What the code revealed",
            "Conservative choice",
            "Revisit",
        ],
    }

    for rel_path, required_sections in files.items():
        full_path = REPO_ROOT / rel_path
        assert full_path.exists(), f"Missing convention file: {rel_path}"

        content = full_path.read_text()
        for section in required_sections:
            assert section in content, f"Missing required section '{section}' in {rel_path}"
