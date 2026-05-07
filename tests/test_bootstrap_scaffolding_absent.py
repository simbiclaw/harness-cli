"""M6 CI rule: bootstrap scaffolding must not exist on main.

After the bootstrap exec-plan completes, the scaffolding artefacts
(MAP.md routing aid, harness-spine-bootstrap sentinel in CLAUDE.md)
must be absent. This test enforces that permanently.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_map_file_absent():
    """docs/MAP.md must not exist — bootstrap scaffolding is torn down."""
    map_file = REPO_ROOT / "docs" / "MAP.md"
    assert not map_file.exists(), (
        f"{map_file} exists — bootstrap scaffolding was not torn down. "
        f"MAP.md is a routing aid that must be removed after bootstrap completes."
    )


def test_no_sentinel_block_in_claude_md():
    """CLAUDE.md must not contain harness-spine-bootstrap sentinel."""
    claude_md = REPO_ROOT / "CLAUDE.md"
    content = claude_md.read_text()
    assert "harness-spine-bootstrap:begin" not in content, (
        "harness-spine-bootstrap sentinel found in CLAUDE.md — "
        "the bootstrap block must be removed after bootstrap completes."
    )
