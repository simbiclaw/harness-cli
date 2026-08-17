"""M7 — calibration manifest channel (9003).

Independent io layer for the calibration manifest: `load_manifest` parses and
validates a `calibration-manifest.<epoch>.yaml` file (epoch format, source_case
grammar, file-name alignment), and `apply_manifest_epoch` re-anchors a compile
run's nodes onto the manifest's epoch — severity_map refs point at the new
epoch, AUTH-9 auto-final is re-evaluated against the manifest's fragment
coverage, and nothing else is recompiled.

Independent channel (round-3 Q8): the manifest is NOT a compiler input; it is
injected alone, after the compile, with no recompile of signals,
corroborators, or agreement.

Purity (I1 quarantine): stdlib plus the types layer only — no model client,
no clock, no RNG. `apply_manifest_epoch` performs no I/O (pure
transformation); `load_manifest` is the only reader.

Reference: docs/exec-plans/active/9003-implement-soft-criteria-compiler.md
           docs/retrospectives/soft-criteria-authoring-spec-v4.html
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import yaml

from argus.types.compiler_schemas import CalibrationManifest

# M0 epoch format: YYYY-MM-DD-<40 hex>.
_EPOCH_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[0-9a-f]{40}$")
# The manifest file is calibration-manifest.<epoch>.yaml; the segment between
# "calibration-manifest." and ".yaml" is its epoch candidate.
_MANIFEST_FILE_RE = re.compile(r"^calibration-manifest\.(.+)\.yaml$")
# conventions.yaml grammar: cookbook.<slug>.yaml or errors.<slug>.yaml —
# structural only, never existence-checked (the libraries are empty; the
# first manifest arrives before any library content, round-3 Q8).
_SOURCE_CASE_RE = re.compile(r"^(cookbook|errors)\.[a-z0-9-]+\.yaml$")
# A severity ref: calibration://manifest/<epoch>/severity/<criterion>.
_SEVERITY_REF_RE = re.compile(r"^calibration://manifest/[^/]+/severity/([^/]+)$")
# Bare-id convention: affected_criterion names a numeric item id ("21"),
# never the prefixed form ("C21") that would silently never grant (F3).
_AFFECTED_CRITERION_RE = re.compile(r"^\d+$")


def load_manifest(path: Path) -> CalibrationManifest:
    """Parse and validate a calibration manifest file.

    Validation (structural only — the referenced library files are never
    existence-checked):
      (a) `epoch_id` matches the M0 epoch format `YYYY-MM-DD-<40 hex>`;
      (b) every fragment's `source_case` matches the conventions.yaml grammar
          `cookbook.<slug>.yaml` or `errors.<slug>.yaml`;
      (c) every fragment's `affected_criterion` follows the bare-id
          convention (`^\\d+$` — "21", never "C21");
      (d) the file name's epoch segment equals `epoch_id` — only the exact
          `calibration-manifest.<epoch>.yaml` name loads, so URI refs align
          with the manifest file's epoch.

    Violations raise ValueError with a clear message; malformed YAML raises
    the yaml.YAMLError. A missing `fragments` key is treated as [].
    """
    path = Path(path)
    file_match = _MANIFEST_FILE_RE.match(path.name)
    if not file_match:
        raise ValueError(
            f"manifest file must be named calibration-manifest.<epoch>.yaml, got {path.name!r}"
        )
    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(
            f"manifest {path.name} must be a YAML mapping, got {type(payload).__name__}"
        )
    epoch_id = payload.get("epoch_id")
    if not isinstance(epoch_id, str) or not _EPOCH_RE.match(epoch_id):
        raise ValueError(f"manifest epoch_id must match YYYY-MM-DD-<40 hex>, got {epoch_id!r}")
    file_epoch = file_match.group(1)
    if file_epoch != epoch_id:
        # F2: only the exact calibration-manifest.<epoch_id>.yaml name loads —
        # a segment that is not the epoch (garbage, another epoch) cannot
        # claim an epoch to align refs with.
        raise ValueError(
            f"manifest file epoch {file_epoch!r} does not match epoch_id {epoch_id!r} "
            "(URI refs align with the manifest file's epoch)"
        )
    fragments = payload.get("fragments") or []
    if not isinstance(fragments, list):
        raise ValueError(f"manifest {path.name} fragments must be a list")
    for fragment in fragments:
        if not isinstance(fragment, dict):
            raise ValueError(f"manifest {path.name} fragment must be a mapping")
        source_case = fragment.get("source_case")
        if not isinstance(source_case, str) or not _SOURCE_CASE_RE.match(source_case):
            raise ValueError(
                f"fragment {fragment.get('fragment_id')!r}: source_case {source_case!r} "
                "must match cookbook.<slug>.yaml or errors.<slug>.yaml"
            )
        affected = fragment.get("affected_criterion")
        if not isinstance(affected, str) or not _AFFECTED_CRITERION_RE.match(affected):
            raise ValueError(
                f"fragment {fragment.get('fragment_id')!r}: affected_criterion {affected!r} "
                "must be a bare numeric item id (e.g. '21'), not the prefixed 'C<id>' form"
            )
    return CalibrationManifest.model_validate(payload)


def apply_manifest_epoch(nodes: list[dict], manifest: CalibrationManifest) -> list[dict]:
    """Pure re-anchor of compile nodes onto the manifest's epoch.

    Per node: (a) the severity_map ref re-anchors to `manifest.epoch_id` —
    the criterion segment survives from the old ref, or derives from
    machine_criterion.criterion_id ("C<id>" → "<id>") when no ref exists yet;
    (b) a calibration_surface_form node (gap_type on the node OR its
    machine_criterion) has machine_criterion.auto_final_allowed recomputed
    against THIS manifest's coverage — granted when a fragment's
    affected_criterion covers its criterion id, revoked when not (AUTH-9
    re-evaluation in both directions, F1); (c) everything else is
    byte-identical — signals, facets, corroborators, agreement,
    residue_declared, gap_type, escape_tier, intents_sha are never
    recompiled.

    Pure transformation: no I/O, no RNG, no model — the same nodes and
    manifest always produce the same result. Garbage nodes pass through
    unchanged (B1), never a crash.
    """
    result = copy.deepcopy(nodes)
    if not isinstance(result, list):
        return result
    epoch_id = getattr(manifest, "epoch_id", None)
    if not isinstance(epoch_id, str) or not epoch_id:
        return result
    fragments = getattr(manifest, "fragments", None) or []
    covered = {_affected_criterion(fragment) for fragment in fragments}
    for node in result:
        if not isinstance(node, dict):
            continue
        criterion = _criterion_id(node)
        if criterion is None:
            continue
        node["severity_map"] = f"calibration://manifest/{epoch_id}/severity/{criterion}"
        if _is_surface_form(node):
            # F1: AUTH-9 coverage is recomputed in BOTH directions — a
            # regression to a non-covering manifest revokes a stale grant.
            machine = node.get("machine_criterion")
            if isinstance(machine, dict):
                machine["auto_final_allowed"] = criterion in covered
    return result


def _affected_criterion(fragment: Any) -> str | None:
    """A fragment's affected criterion id — pydantic attribute or dict key."""
    value = getattr(fragment, "affected_criterion", None)
    if value is None and isinstance(fragment, dict):
        value = fragment.get("affected_criterion")
    return value if isinstance(value, str) else None


def _criterion_id(node: dict) -> str | None:
    """The criterion id a node's severity ref points at: the last segment of
    an existing calibration://manifest/<epoch>/severity/<id> ref, else the
    machine_criterion's criterion_id with its leading "C" stripped. A node
    with neither stays ref-less (deterministic)."""
    severity_map = node.get("severity_map")
    if isinstance(severity_map, str):
        match = _SEVERITY_REF_RE.match(severity_map)
        if match:
            return match.group(1)
    machine = node.get("machine_criterion")
    if isinstance(machine, dict):
        criterion_id = machine.get("criterion_id")
        if (
            isinstance(criterion_id, str)
            and criterion_id.startswith("C")
            and bool(criterion_id[1:])
        ):
            return criterion_id[1:]
    return None


def _is_surface_form(node: dict) -> bool:
    """Whether the node carries the calibration_surface_form gap — on the
    node itself or on its machine_criterion (AUTH-9 coverage applies)."""
    if node.get("gap_type") == "calibration_surface_form":
        return True
    machine = node.get("machine_criterion")
    return isinstance(machine, dict) and machine.get("gap_type") == "calibration_surface_form"
