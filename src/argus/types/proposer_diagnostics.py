"""Proposer diagnostics: the quarantined proposed_score block (9020 M2).

This module carries the QUARANTINED half of the proposer's output — the
continuous per-dimension `proposed_score` and the G it was computed at. The
quarantine is the point: a proposed score is a model self-report (D7/D8, I7),
so it never enters the shipped `raw`/`adjusted` and never touches the replay
hash (I5). It exists to feed the divergence diagnostic (M3) and to order the
hunt/escape budget — nothing that disposes.

Provisional stand-ins. `GroundedFinding`, `QuarantinedFindingGraph`,
`EvaluationResult`, `replay_hash`, and `derive_evaluation` are minimal
placeholders for 9002's real `FindingGraph`/`EvaluationResult` and the pure
`score`/`adjust` stages, which are unstarted. They exist here only to make the
quarantine and replay invariants testable now; 9002 replaces them. Their job is
to demonstrate one property and nothing more: the shipped outputs are a pure
function of grounded evidence, never of a proposed score.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProposedScores:
    """Quarantined per-dimension continuous scores + the G actually used.

    Non-replay-bearing: nothing in here may reach a disposer input. Stored
    alongside the FindingGraph as a diagnostic, read only by the divergence
    probe (M3).
    """

    scores: dict[str, float]
    g_used: int


@dataclass(frozen=True)
class GroundedFinding:
    """A replay-bearing finding: the criterion it hit and the rubric deduction.

    Provisional — 9002's `Finding` carries the span, anchor, and signals. Here
    only the fields the shipped score depends on are modeled.
    """

    dimension: str
    deduction: float


@dataclass(frozen=True)
class QuarantinedFindingGraph:
    """Grounded findings (replay-bearing) + an optional quarantined block.

    The `proposed_scores` and `proposer_id` fields are diagnostics; they are
    deliberately excluded from `replay_hash` and `derive_evaluation`. That
    exclusion is the invariant M2 lands.
    """

    grounded: list[GroundedFinding]
    intents_sha: str
    rubric_version: str
    proposed_scores: ProposedScores | None = None
    proposer_id: str | None = None


@dataclass(frozen=True)
class EvaluationResult:
    """The shipped result. Derives from grounded evidence only."""

    raw: float
    adjusted: float
    replay_hash: str


def _replay_payload(graph: QuarantinedFindingGraph) -> dict:
    """The replay-bearing inputs — grounded findings, epoch, rubric version.

    Explicitly NOT proposed_scores or proposer_id. If either leaked in here,
    proposer nondeterminism would infect the replay contract.
    """
    return {
        "grounded": sorted(
            ([f.dimension, f.deduction] for f in graph.grounded),
        ),
        "intents_sha": graph.intents_sha,
        "rubric_version": graph.rubric_version,
    }


def replay_hash(graph: QuarantinedFindingGraph) -> str:
    """A stable hash of the grounded inputs only (I5)."""
    payload = json.dumps(_replay_payload(graph), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def derive_evaluation(graph: QuarantinedFindingGraph) -> EvaluationResult:
    """Re-derive the shipped result from grounded evidence (provisional).

    Provisional stand-in for 9002's pure `score` then `adjust`. `raw` is
    1.0 minus the summed deductions (clamped); `adjusted` equals `raw` here
    because precedent application is 9002's `adjust`. Crucially, the proposed
    score is never read — passing a graph with or without one yields the same
    result, which is exactly `test_d19_quarantine`.
    """
    raw = 1.0 - sum(f.deduction for f in graph.grounded)
    raw = max(0.0, min(1.0, raw))
    adjusted = raw
    return EvaluationResult(raw=raw, adjusted=adjusted, replay_hash=replay_hash(graph))
