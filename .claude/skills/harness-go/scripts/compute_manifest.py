"""Compute PRD file hashes and update docs/PRD_MANIFEST.json.

Usage:
  python3 .claude/skills/harness-go/scripts/compute_manifest.py

Resolves the docs/PRD symlink, computes SHA256 of every .md file,
updates the manifest, and reports what changed.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
PRD_SYMLINK = REPO_ROOT / "docs" / "PRD"
MANIFEST_PATH = REPO_ROOT / "docs" / "PRD_MANIFEST.json"


def resolve_prd_dir() -> Path:
    """Resolve the PRD symlink to its target directory."""
    if not PRD_SYMLINK.is_symlink():
        sys.exit(f"ERROR: {PRD_SYMLINK} is not a symlink")
    target = PRD_SYMLINK.resolve(strict=False)
    if not target.is_dir():
        sys.exit(f"ERROR: PRD symlink target {target} is not a directory")
    return target


def compute_hash(filepath: Path) -> str:
    """Return 'sha256:<hexdigest>' for a file."""
    digest = hashlib.sha256(filepath.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def get_head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT
    )
    if result.returncode != 0:
        sys.exit(f"ERROR: git rev-parse HEAD failed: {result.stderr}")
    return result.stdout.strip()


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        sys.exit(f"ERROR: {MANIFEST_PATH} not found. Run harness-go first.")
    return json.loads(MANIFEST_PATH.read_text())


def main() -> None:
    prd_dir = resolve_prd_dir()
    manifest = load_manifest()

    old_files: dict = manifest.get("files", {})
    stage_affinity: dict = manifest.get("stage_affinity", {})

    new_files: dict = {}
    added: list[str] = []
    updated: list[str] = []
    removed: list[str] = []

    # Hash every .md file in the PRD directory.
    for f in sorted(prd_dir.glob("*.md")):
        h = compute_hash(f)
        new_files[f.name] = h
        if f.name not in old_files:
            added.append(f.name)
        elif h != old_files[f.name]:
            updated.append(f.name)

    # Detect removed files.
    for name in old_files:
        if name not in new_files:
            removed.append(name)

    if not (added or updated or removed):
        print("PRD_MANIFEST.json is current. No changes.")
        return

    # Report.
    if added:
        print(f"Added:   {', '.join(added)}")
    if updated:
        print(f"Updated: {', '.join(updated)}")
    if removed:
        print(f"Removed: {', '.join(removed)}")

    # Update manifest.
    manifest["generated_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    manifest["harness_go_commit"] = get_head_sha()
    manifest["files"] = new_files
    manifest["stage_affinity"] = stage_affinity

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
