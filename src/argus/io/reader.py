# argus/io/reader.py
"""The S1 read surface — INTENTS at a pinned epoch, and the only path by which
anything under `src/argus/` reads the tree (9031 M3, absorbing 9025 M13).

Three category readers, which are the consumer's end of the architecture's
three epistemic classes (ADR-0001): **versioned rubric** (`_rubric/`),
**descriptive facts** (manifests, capsules, DKB), **accumulated history**
(cookbook/errors shelves). One reader, one epoch: every read resolves through
`git show <epoch>:<relpath>` against the SHA that `EPOCH.yaml` pins, so the
working tree's state cannot leak into an evaluation — an unpinned second
reader is an I4 hole, not untidiness (M13's binding constraint).

The read protocol is `INTENTS/AGENTS.md`'s, implemented by id and never by
content: (1) confirm the call's L1/L2/L3 attribution from the path and the
manifest chain; (2) read that node's `intent_manifest.json`; (3) read the
`_rubric/` items for the cited dimension; (4) a manifest whose `source` is
`audio2tree` defers its manual-reference signals; (5) an L2 with no compiled
item is a routing label, not a scored node.

**One boundary the design already drew, found by measurement (2026-09-18):**
the tree's `.gitignore` excludes `calls/` — *"CallRecord archives (per design:
'Not versioned (no git history per call)')"*. So the epoch pins **knowledge**
(rubric, manifests, capsules, history shelves — read via `git show <epoch>:…`)
and **facts are per-call archives read from the filesystem**, identified by
their path: a call is not a revision of the tree, and 718 of them would bloat
it. "One reader, one epoch" applies to everything the epoch governs; the
record is simply the call.

**Discovery is not this module's job.** Which node a call belongs to is
audio2tree's routing protocol (vectorised request, cosine over L2
descriptions, 0.60 threshold) and it writes `bottom_up` alone. This reader
*confirms* the attribution the call's path already states, and — because 532
of 718 calls sit in `_unassigned` — records explicit absence as a first-class
answer (`None`) rather than guessing: I4 pins which revision of the tree was
read; the attribution records which node was read from it.

Capsule contract (doc2graph's; M13 verified against the tree): a leaf is
`index.md` (+ `assets/`, optional `intent_manifest.json`); `ui_steps.yaml`
does not exist — the Flesh is embedded in `index.md` as one fenced JSON block
per routine after `## Part 1: Bone` / `## Part 2: Flesh`. A routine resolves
by `routine_id`; its ordered-match sequence is `step_instruction` values
ascending by `step_order`. Read by id; do not read `.pipeline/`; no
parent-cascade loading, no model summaries.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml


class UnpinnedRead(Exception):
    """A read was attempted without a resolvable epoch — refuse rather than
    read whatever the working tree happens to say (I4)."""


class NodeNotFound(Exception):
    """The requested path does not exist at the pinned epoch."""


class IntentsReader:
    """Read-only access to the INTENTS tree at a pinned git-SHA epoch.

    `root` is the tree's git working directory; `epoch` overrides the pin for
    tests, but defaults to the SHA in `EPOCH.yaml` — the one unpinned read is
    the pin itself, and it is read from the working tree deliberately: that
    file *is* the pin's source (ADR-0002).
    """

    def __init__(self, root: Path, epoch: str | None = None):
        self.root = Path(root)
        self._epoch = epoch

    # ── the pin ──────────────────────────────────────────────────────────

    @property
    def epoch(self) -> str:
        if self._epoch is None:
            pin = self.root / "EPOCH.yaml"
            if not pin.exists():
                raise UnpinnedRead(f"no EPOCH.yaml under {self.root}")
            self._epoch = yaml.safe_load(pin.read_text(encoding="utf-8"))["epoch"]
        if not re.fullmatch(r"[0-9a-f]{40}", str(self._epoch)):
            raise UnpinnedRead(f"epoch {self._epoch!r} is not a full git SHA")
        return self._epoch

    def _show(self, relpath: str) -> str:
        """The one read primitive: the file's content at the pinned epoch."""
        result = subprocess.run(
            ["git", "-C", str(self.root), "show", f"{self.epoch}:{relpath}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise NodeNotFound(f"{relpath} not present at {self.epoch[:7]}")
        return result.stdout

    # ── facts: the call record (an archive, not a revision) ─────────────

    def read_call_record(self, record_relpath: str) -> dict:
        """The call record from the archive. `calls/` is git-ignored by design
        ("no git history per call"), so this read is the filesystem — the
        record is the fact, identified by its path; the epoch governs the
        knowledge it is evaluated against, not the record itself."""
        path = self.root / record_relpath
        if not path.exists():
            raise NodeNotFound(f"{record_relpath} not in the archive")
        return json.loads(path.read_text(encoding="utf-8"))

    def attribution_of(self, record_relpath: str) -> str | None:
        """The node a call's path attributes it to, or None for `_unassigned`.

        Explicit absence is an answer, not an error: 532 of 718 calls carry it,
        and M13 requires the run to record which node was read (or that none
        was) — two runs against the same epoch with different attributions must
        not replay identically (I5's hash exists to make that detectable).
        """
        parts = Path(record_relpath).parts
        if "_unassigned" in parts:
            return None
        for i, part in enumerate(parts):
            if part == "calls":
                if i == 0:
                    return None
                return "/".join(parts[:i])
        return None

    # ── descriptive facts: manifests and capsules ────────────────────────

    def read_manifest(self, node_relpath: str) -> dict:
        return json.loads(self._show(f"{node_relpath}/intent_manifest.json"))

    def source_of(self, node_relpath: str) -> str:
        return self.read_manifest(node_relpath).get("source", "")

    def read_capsule_routine(self, leaf_relpath: str, routine_id: str) -> list[dict]:
        """A routine's steps, ascending by `step_order`, resolved by id from
        the Flesh blocks of the leaf's `index.md` — never by content match."""
        text = self._show(f"{leaf_relpath}/index.md")
        flesh = text.split("## Part 2: Flesh", 1)
        if len(flesh) < 2:
            raise NodeNotFound(f"{leaf_relpath}/index.md has no Part 2: Flesh")
        for block in re.findall(r"```json\s*(.*?)```", flesh[1], re.S):
            routine = json.loads(block)
            if routine.get("routine_id") == routine_id:
                steps = routine.get("ui_steps", [])
                return sorted(steps, key=lambda s: s["step_order"])
        raise NodeNotFound(f"routine {routine_id!r} not in {leaf_relpath}/index.md")

    # ── versioned rubric ─────────────────────────────────────────────────

    def rubric_items(self, dimension: str) -> list[dict]:
        """The compiled items for one dimension (the four dimension directories
        under `_rubric/rules_criteria/`). Empty list = no compiled item."""
        tree = str(Path("_rubric/rules_criteria") / dimension)
        listing = subprocess.run(
            [
                "git", "-C", str(self.root), "ls-tree", "-r", "--name-only",
                f"{self.epoch}:{tree}",
            ],
            capture_output=True,
            text=True,
        )
        if listing.returncode != 0:
            return []
        items = []
        for entry in listing.stdout.splitlines():
            if not entry.endswith(".yaml"):
                continue
            # ls-tree lists paths relative to the named subtree; re-root them.
            relpath = entry if entry.startswith(tree) else f"{tree}/{entry}"
            items.append(yaml.safe_load(self._show(relpath)))
        return items

    # ── accumulated history ──────────────────────────────────────────────

    def read_history(self, node_relpath: str) -> dict[str, list[dict]]:
        """The node's precedent shelves: `cookbook.*` (confirmed pass) and
        `errors.*` (confirmed fail) — the I6 correlated-class substrate."""
        shelves: dict[str, list[dict]] = {"cookbook": [], "errors": []}
        listing = subprocess.run(
            [
                "git", "-C", str(self.root), "ls-tree", "-r", "--name-only",
                f"{self.epoch}:{node_relpath}",
            ],
            capture_output=True,
            text=True,
        )
        if listing.returncode != 0:
            return shelves
        for entry in listing.stdout.splitlines():
            name = Path(entry).name
            for kind in shelves:
                if name.startswith(f"{kind}."):
                    relpath = entry if entry.startswith(node_relpath) else f"{node_relpath}/{entry}"
                    shelves[kind].append(yaml.safe_load(self._show(relpath)))
        return shelves

    # ── the read protocol's two routing rules ────────────────────────────

    def signal_disposition(self, node_relpath: str, dimension: str) -> str:
        """`scored` | `routing_only` | `deferred`, by AGENTS.md's protocol:

        - a manifest whose `source` is `audio2tree` → its manual-reference
          signals are **deferred** (the manual is doc2graph's; a
          behaviour-discovered node has no manual reference to check);
        - a node with no compiled item for the dimension → **routing_only**
          (the node still routes, but nothing scores against it);
        - otherwise **scored**.
        """
        manifest = self.read_manifest(node_relpath)
        if manifest.get("source") == "audio2tree":
            return "deferred"
        if not self.rubric_items(dimension):
            return "routing_only"
        return "scored"

    def read_rubric_at_epoch(self) -> dict[str, Any]:
        """A small capsule of what this reader pinned — for the run manifest."""
        return {"epoch": self.epoch}
