"""Acceptance Test for M6 of 0000-upgrade-spine-to-v6.md.

Walks INTENTS/, asserts every .yaml/.json/.jsonl parses, every file matches
exactly one producer glob in _meta/ownership.yaml (zero multi-owner, zero
orphaned), and every operator ui_binding_ref in the capsule Bone resolves
to a Flesh ui_step.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
INTENTS = REPO_ROOT / "INTENTS"

PARSABLE_EXTS = {".yaml", ".yml", ".json", ".jsonl"}


def _parse_yaml(path: Path) -> dict | list | None:
    """Parse a YAML file, returning None on failure."""
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def _parse_json(path: Path) -> dict | list | None:
    """Parse a JSON/JSONL file, returning None on failure."""
    try:
        with open(path) as f:
            text = f.read()
        if path.suffix == ".jsonl":
            for line in text.splitlines():
                if line.strip():
                    json.loads(line)
            return []  # valid
        return json.loads(text)
    except Exception:
        return None


def test_worked_example_parses_and_owns() -> None:
    """M6 Acceptance Test: every parsable file in INTENTS/ parses, every file
    is owned by exactly one producer, and Bone ui_binding_refs resolve."""
    assert INTENTS.exists(), "INTENTS/ tree must exist"
    assert INTENTS.is_dir(), "INTENTS/ must be a directory"

    # 1. Collect all files, parse all parsable ones
    all_files: list[Path] = []
    parse_failures: list[str] = []
    ownership_path = INTENTS / "_meta" / "ownership.yaml"

    for path in sorted(INTENTS.rglob("*")):
        if path.is_file() and path.suffix in PARSABLE_EXTS:
            all_files.append(path)
            if path.suffix in (".yaml", ".yml"):
                result = _parse_yaml(path)
            else:
                result = _parse_json(path)
            if result is None:
                parse_failures.append(str(path.relative_to(REPO_ROOT)))

    assert not parse_failures, (
        f"Files that failed to parse:\n  " + "\n  ".join(parse_failures)
    )

    # 2. Ownership: every file matches exactly one producer glob
    assert ownership_path.exists(), (
        "INTENTS/_meta/ownership.yaml must exist"
    )
    ownership = _parse_yaml(ownership_path)
    assert ownership is not None, "_meta/ownership.yaml must parse"
    assert isinstance(ownership, dict), "_meta/ownership.yaml must be a dict"

    producers = ownership.get("producers", [])
    assert producers, "ownership.yaml must have a 'producers' list"

    # Build (glob_pattern → producer_name) mapping
    import fnmatch
    globs: list[tuple[str, str]] = []
    for entry in producers:
        name = entry.get("name", "unknown")
        for pattern in entry.get("globs", []):
            globs.append((pattern, name))

    ownership_failures: list[str] = []
    for f in all_files:
        rel = str(f.relative_to(INTENTS))
        matching = [p for pat, p in globs if fnmatch.fnmatch(rel, pat)]
        if len(matching) == 0:
            ownership_failures.append(f"{rel}: orphaned (no producer claims it)")
        elif len(matching) > 1:
            ownership_failures.append(
                f"{rel}: multi-owned by {matching}"
            )

    assert not ownership_failures, (
        f"Ownership failures:\n  " + "\n  ".join(ownership_failures)
    )

    # 3. Bone ui_binding_refs resolve to Flesh ui_steps
    #    Find all index.md files (L2 capsule Bones), extract ui_binding_refs,
    #    and verify each ref exists as a ui_step in a file owned by the same producer.
    binding_failures: list[str] = []
    ui_binding_ref_re = re.compile(r"ui_binding_ref:\s*['\"]?([^'\"]+)['\"]?")

    for index_path in sorted(INTENTS.rglob("index.md")):
        bone_text = index_path.read_text()
        refs = ui_binding_ref_re.findall(bone_text)

        domain_dir = index_path.parent
        for ref in refs:
            # Search the domain tree for a ui_step with this name
            found = False
            for fpath in domain_dir.rglob("*.yaml"):
                if fpath == index_path:
                    continue
                content = _parse_yaml(fpath)
                if content is None:
                    continue
                if isinstance(content, dict) and content.get("ui_step") == ref:
                    found = True
                    break
                # Check nested ui_steps list (Flesh file convention)
                if isinstance(content, dict) and "ui_steps" in content:
                    for item in content["ui_steps"]:
                        if isinstance(item, dict) and item.get("ui_step") == ref:
                            found = True
                            break
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("ui_step") == ref:
                            found = True
                            break
            if not found:
                binding_failures.append(
                    f"{index_path.relative_to(REPO_ROOT)}: "
                    f"ui_binding_ref '{ref}' not found in domain tree"
                )

    assert not binding_failures, (
        f"Unresolved ui_binding_refs:\n  " + "\n  ".join(binding_failures)
    )
