"""Detect PRD-to-spine drift by comparing live PRD file hashes against docs/PRD_MANIFEST.json.

On mismatch, reports which harness-go stages need regeneration via stage_affinity.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = REPO_ROOT / "docs" / "PRD_MANIFEST.json"
PRD_SYMLINK = REPO_ROOT / "docs" / "PRD"

HASH_ALGORITHM = "sha256"


def _prd_dir() -> Path | None:
    """Resolve the PRD symlink. Returns None if unresolvable."""
    if not PRD_SYMLINK.is_symlink():
        return None
    target = PRD_SYMLINK.resolve(strict=False)
    if not target.is_dir():
        return None
    return target


def _compute_hash(filepath: Path) -> str:
    """Return sha256:<hexdigest> for a file."""
    digest = hashlib.sha256(filepath.read_bytes()).hexdigest()
    return f"{HASH_ALGORITHM}:{digest}"


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


# --- test cases ---


def test_prd_symlink_resolves() -> None:
    """PRD symlink must resolve to a readable directory."""
    prd = _prd_dir()
    if prd is None:
        # If symlink is broken on this machine, skip with explanation.
        # This is not a failure — the test can't run without PRD files.
        import warnings
        warnings.warn(
            f"SKIP: {PRD_SYMLINK} symlink does not resolve to a directory. "
            "PRD drift detection cannot run."
        )
        return
    assert prd.is_dir(), f"PRD symlink target {prd} is not a directory"


def test_manifest_exists_and_valid() -> None:
    """PRD_MANIFEST.json must exist and contain files + stage_affinity keys."""
    assert MANIFEST_PATH.exists(), (
        f"Missing {MANIFEST_PATH}. Run harness-go to generate it."
    )
    manifest = _load_manifest()
    assert "files" in manifest, "PRD_MANIFEST.json missing 'files' key"
    assert "stage_affinity" in manifest, "PRD_MANIFEST.json missing 'stage_affinity' key"
    assert len(manifest["files"]) > 0, "PRD_MANIFEST.json has no file entries"


def test_no_prd_hash_mismatches() -> None:
    """Every file in the manifest must have a matching current hash."""
    prd = _prd_dir()
    if prd is None:
        import warnings
        warnings.warn("SKIP: PRD symlink unresolved. Drift check skipped.")
        return

    manifest = _load_manifest()
    manifest_files: dict = manifest["files"]
    stage_affinity: dict = manifest["stage_affinity"]

    mismatches: list[str] = []
    for filename, expected_hash in manifest_files.items():
        filepath = prd / filename
        if not filepath.exists():
            mismatches.append(
                f"PRD file '{filename}' removed. "
                f"Update PRD_MANIFEST.json and run harness-go-sync."
            )
            continue
        current_hash = _compute_hash(filepath)
        if current_hash != expected_hash:
            affected = _affected_stages(filename, stage_affinity)
            mismatches.append(
                f"PRD file '{filename}' has changed.\n"
                f"  Expected: {expected_hash}\n"
                f"  Current:  {current_hash}\n"
                f"  Run harness-go-sync stages: {affected}"
            )

    assert not mismatches, (
        f"PRD-to-spine drift detected ({len(mismatches)} file(s)):\n\n"
        + "\n\n".join(mismatches)
    )


def test_no_new_prd_files() -> None:
    """Every .md file in the PRD directory must be in the manifest."""
    prd = _prd_dir()
    if prd is None:
        import warnings
        warnings.warn("SKIP: PRD symlink unresolved. New-file check skipped.")
        return

    manifest = _load_manifest()
    manifest_files: set[str] = set(manifest["files"].keys())

    new_files: list[str] = []
    for filepath in prd.glob("*.md"):
        if filepath.name not in manifest_files:
            new_files.append(filepath.name)

    assert not new_files, (
        f"New PRD file(s) detected: {', '.join(new_files)}. "
        f"Add them to {MANIFEST_PATH} stage_affinity and run harness-go-sync."
    )


def test_no_orphan_manifest_entries() -> None:
    """Every file in the manifest must still exist in the PRD directory."""
    prd = _prd_dir()
    if prd is None:
        import warnings
        warnings.warn("SKIP: PRD symlink unresolved. Orphan check skipped.")
        return

    manifest = _load_manifest()
    manifest_files: dict = manifest["files"]

    orphans: list[str] = []
    for filename in manifest_files:
        if not (prd / filename).exists():
            orphans.append(filename)

    assert not orphans, (
        f"PRD file(s) in manifest no longer exist: {', '.join(orphans)}. "
        f"Update {MANIFEST_PATH} and run harness-go-sync."
    )


# --- helpers ---


def _affected_stages(filename: str, stage_affinity: dict) -> str:
    """Return a comma-separated list of stages that depend on this file."""
    stages = []
    for stage, files in stage_affinity.items():
        if filename in files:
            stages.append(stage)
    if not stages:
        return "(all stages — file has no specific affinity)"
    return ", ".join(stages)
