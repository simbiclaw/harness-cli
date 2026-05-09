"""
State I/O for the conversation-distillation subagent.

Three durable state files, all under `state/`:

    intent_tree.json       — working tree (the source of truth for cluster identity)
    claim_library.jsonl    — append-only claim library
    unassigned_pool.jsonl  — claims awaiting cluster discovery

Plus an audit log:

    audit_log.jsonl        — append-only event stream for protocol-relevant events

This module provides:
  - typed loaders/savers for each
  - a snapshot/rollback wrapper for risky multi-file mutations
  - canonical hashing for tree publishing
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def state_dir() -> Path:
    """Resolve the state dir. Defaults to the state/ alongside this file's scripts/."""
    env = os.environ.get("CD_STATE_DIR")
    if env:
        return Path(env).resolve()
    # Walk up looking for a `state/` sibling to `.claude/` (legacy layout)
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".claude").is_dir() and (parent / "state").is_dir():
            return (parent / "state").resolve()
    # Self-contained layout: scripts/ → parent → state/
    file_parent = Path(__file__).resolve().parent.parent
    if (file_parent / "state").is_dir():
        return (file_parent / "state").resolve()
    # Fallback: ./state relative to cwd
    return (cwd / "state").resolve()


# ---------------------------------------------------------------------------
# Tree (intent_tree.json)
# ---------------------------------------------------------------------------


def tree_path() -> Path:
    return state_dir() / "intent_tree.json"


def load_tree() -> dict:
    """
    Load the working tree. Returns an empty skeleton if the file doesn't exist
    yet — this is the only place we synthesize an empty tree, so first-run
    behaviour is consistent.
    """
    p = tree_path()
    if not p.exists():
        return {"schema_version": "1.0", "tree": []}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tree(tree: dict) -> None:
    p = tree_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False, allow_nan=False)
    os.replace(tmp, p)


def canonical_tree_hash(tree: dict) -> str:
    """
    SHA-256 over the canonical JSON serialization of `tree["tree"]`.
    Excludes `publish_metadata` so the hash captures content, not provenance.
    Two trees with identical content but different generated_at timestamps
    hash identically.
    """
    payload = tree.get("tree", [])
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Claim library (claim_library.jsonl)
# ---------------------------------------------------------------------------


def claim_library_path() -> Path:
    return state_dir() / "claim_library.jsonl"


def iter_claims() -> Iterator[dict]:
    p = claim_library_path()
    if not p.exists():
        return
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def append_claims(claims: Iterable[dict]) -> int:
    """Append claims to the library. Returns the number written."""
    p = claim_library_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(p, "a", encoding="utf-8") as f:
        for c in claims:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
            n += 1
    return n


def claim_count() -> int:
    """Cheap line-count of the library."""
    p = claim_library_path()
    if not p.exists():
        return 0
    with open(p, "rb") as f:
        return sum(1 for _ in f)


# ---------------------------------------------------------------------------
# Unassigned pool (unassigned_pool.jsonl)
# ---------------------------------------------------------------------------


def pool_path() -> Path:
    return state_dir() / "unassigned_pool.jsonl"


def append_to_pool(claim_ids: Iterable[str]) -> int:
    """
    Pool entries are minimal: just the claim ID. The full claim is in the
    library; the pool is an index of unassigned ones.
    """
    p = pool_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(p, "a", encoding="utf-8") as f:
        for cid in claim_ids:
            f.write(json.dumps({"claim_id": cid}) + "\n")
            n += 1
    return n


def read_pool() -> list[str]:
    p = pool_path()
    if not p.exists():
        return []
    out = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line)["claim_id"])
    return out


def replace_pool(claim_ids: list[str]) -> None:
    """Atomically replace the pool with a new list — used after discovery."""
    p = pool_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for cid in claim_ids:
            f.write(json.dumps({"claim_id": cid}) + "\n")
    os.replace(tmp, p)


# ---------------------------------------------------------------------------
# Audit log (audit_log.jsonl)
# ---------------------------------------------------------------------------


def audit_log_path() -> Path:
    return state_dir() / "audit_log.jsonl"


def log_event(event: str, **fields: Any) -> None:
    """
    Append a structured event to the audit log. Events are append-only and
    never edited. Use one of the documented event names:

      claim_assigned, cluster_discovered, proposed_new_l1,
      centroid_drift_warning, centroid_drift_block,
      merge_candidate, nodes_merged, node_absorbed,
      node_re_anchored, embedding_model_changed,
      run_started, run_completed, run_aborted
    """
    p = audit_log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event,
        **fields,
    }
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Processed audio IDs (processed_audio_ids.txt)
# ---------------------------------------------------------------------------


def processed_path() -> Path:
    return state_dir() / "processed_audio_ids.txt"


def load_processed() -> set[str]:
    p = processed_path()
    if not p.exists():
        return set()
    return {line.strip() for line in p.read_text().splitlines() if line.strip()}


def mark_processed(audio_ids: Iterable[str]) -> None:
    p = processed_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        for aid in audio_ids:
            f.write(aid + "\n")


# ---------------------------------------------------------------------------
# Protocol config
# ---------------------------------------------------------------------------


DEFAULT_CONFIG = {
    "assignment_threshold": 0.65,
    "discovery_pool_size": 50,
    "discovery_min_cluster_size": 5,
    "parent_fit_threshold": 0.55,
    "drift_threshold_warn": 0.20,
    "drift_threshold_block": 0.40,
    "merge_candidate_threshold": 0.95,
    "retention_floor": 5,
    "retention_floor_runs": 3,
    "embedding_model": "BAAI/bge-base-en-v1.5",
    "embedding_dim": 768,
}


def config_path() -> Path:
    return state_dir() / "protocol_config.json"


def load_config() -> dict:
    p = config_path()
    if not p.exists():
        return dict(DEFAULT_CONFIG)
    with open(p, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    merged = dict(DEFAULT_CONFIG)
    merged.update(loaded)
    return merged


def save_config(cfg: dict) -> None:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


# ---------------------------------------------------------------------------
# Snapshot + rollback
# ---------------------------------------------------------------------------


@dataclass
class Snapshot:
    """Holds copies of all state files captured at snapshot time."""
    snapshot_dir: Path

    def restore(self) -> None:
        """Atomically restore every state file from this snapshot."""
        sd = state_dir()
        for src in self.snapshot_dir.iterdir():
            if not src.is_file():
                continue
            shutil.copy2(src, sd / src.name)


@contextmanager
def state_snapshot() -> Iterator[Snapshot]:
    """
    Take a snapshot of all state files. If the wrapped block raises, restore.
    On clean exit, the snapshot directory is left in place under
    `state/.snapshots/` so post-mortem inspection is possible.

    Use this around any operation that mutates more than one file —
    discovery passes, merges, embedding-model changes.
    """
    sd = state_dir()
    snapshots_dir = sd / ".snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    snap_dir = snapshots_dir / ts
    snap_dir.mkdir(parents=True, exist_ok=True)

    # Copy every state file (excluding the .snapshots dir itself)
    for f in sd.iterdir():
        if f.name == ".snapshots":
            continue
        if f.is_file():
            shutil.copy2(f, snap_dir / f.name)

    snap = Snapshot(snapshot_dir=snap_dir)
    try:
        yield snap
    except Exception:
        snap.restore()
        log_event("run_aborted", snapshot_restored=str(snap_dir))
        raise


__all__ = [
    "state_dir",
    "tree_path", "load_tree", "save_tree", "canonical_tree_hash",
    "claim_library_path", "iter_claims", "append_claims", "claim_count",
    "pool_path", "append_to_pool", "read_pool", "replace_pool",
    "audit_log_path", "log_event",
    "processed_path", "load_processed", "mark_processed",
    "config_path", "load_config", "save_config",
    "state_snapshot", "Snapshot",
    "DEFAULT_CONFIG",
]
