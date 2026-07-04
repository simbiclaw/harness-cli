"""Acceptance Test for M1 of 0000-upgrade-spine-to-v6.md.

Asserts ARCHITECTURE.md is scoped to Argus-only with five domains mapped
onto the five layers .importlinter enforces.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text()


def _parse_importlinter_layers() -> list[str]:
    """Return layer names from .importlinter, low-to-high (types → ... → cli)."""
    text = _read(".importlinter")
    # The layers are listed high-to-low in the config; extract them.
    in_layers = False
    layers: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("layers"):
            in_layers = True
            # First value may be on same line
            rest = line.split("=", 1)[1].strip()
            if rest:
                layers.append(rest)
            continue
        if in_layers:
            stripped = line.strip()
            if not stripped or stripped.startswith("[") or stripped.startswith("containers"):
                break
            layers.append(stripped)
    # Reverse to get low-to-high (types first)
    return list(reversed(layers))


def _parse_domain_table(text: str) -> list[dict]:
    """Parse the domain inventory markdown table, returning list of {name, why, consumed_by}."""
    # Find the domain inventory section (## 1. Domain inventory)
    section_match = re.search(
        r"## 1\. Domain inventory.*?(?=## 2\.|\Z)", text, re.DOTALL
    )
    if not section_match:
        return []

    section = section_match.group(0)
    domains: list[dict] = []
    in_table = False
    for line in section.splitlines():
        line = line.strip()
        if line.startswith("| # |") or line.startswith("|---"):
            in_table = True
            continue
        if in_table and line.startswith("|") and not line.startswith("| # |"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) >= 4:
                # Extract domain name from bold markup
                name = cells[1].replace("**", "").strip()
                domains.append({
                    "number": cells[0].strip(),
                    "name": name,
                    "why": cells[2].strip(),
                    "consumed_by": cells[3].strip(),
                })
        elif in_table and not line.startswith("|"):
            break

    return domains


def test_five_domains_map_to_importlinter_layers() -> None:
    """M1 Acceptance Test: ARCHITECTURE.md names exactly 5 Argus domains,
    maps them onto .importlinter layers, and names no non-Argus domains."""
    arch_text = _read("ARCHITECTURE.md")

    # 1. Parse the domain inventory
    domains = _parse_domain_table(arch_text)

    assert domains, "ARCHITECTURE.md must have a domain inventory table in Section 1"

    domain_names = {d["name"] for d in domains}

    # 2. Assert exactly the five Argus domains are present
    #    providers+utils may be one combined row or two separate rows
    core_domains = {"types", "config", "core", "cli"}
    provider_utils_patterns = {"providers", "utils", "providers + utils"}

    has_core = core_domains & domain_names
    has_providers_or_utils = provider_utils_patterns & domain_names

    assert has_core == core_domains, (
        f"Missing core Argus domains. Expected {core_domains}, found {has_core}. "
        f"All domains in table: {domain_names}"
    )
    assert has_providers_or_utils, (
        f"Missing providers/utils domain. Expected one of {provider_utils_patterns}. "
        f"All domains in table: {domain_names}"
    )

    # Total domain rows must be exactly 5 (combined) or 6 (separate providers, utils)
    assert len(domains) in (5, 6), (
        f"Expected 5 (combined providers+utils) or 6 (separate) domain rows, "
        f"found {len(domains)}: {domain_names}"
    )

    # 3. Assert NO non-Argus domains appear in the table
    non_argus_domains = {
        "Audio Intake",
        "Document Ingestion",
        "Conversation Distillation",
        "Knowledge Calibration",
        "Expertise Library",
        "Metis",
        "Hermes",
    }
    offenders = domain_names & non_argus_domains
    assert not offenders, (
        f"ARCHITECTURE.md domain inventory must not list non-Argus domains: {offenders}"
    )

    # 4. Assert .importlinter layers match the layered model
    import_layers = _parse_importlinter_layers()
    assert len(import_layers) == 5, (
        f".importlinter must define exactly 5 layers, found {len(import_layers)}: {import_layers}"
    )
    expected_layers = ["types", "config", "io", "core", "cli"]
    assert import_layers == expected_layers, (
        f".importlinter layers {import_layers} do not match expected {expected_layers}"
    )

    # 5. ARCHITECTURE.md must reference the layer names from .importlinter
    #    The layered model section should name types, config, io, core, cli
    for layer in expected_layers:
        # Look for the layer name in the layered model context
        assert layer.lower() in arch_text.lower(), (
            f"ARCHITECTURE.md must mention layer '{layer}'"
        )

    # 6. Run lint-imports — must pass unchanged
    result = subprocess.run(
        ["uv", "run", "lint-imports"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"lint-imports failed after rescope:\n{result.stderr}\n{result.stdout}"
    )
