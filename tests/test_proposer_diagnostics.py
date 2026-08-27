"""Acceptance tests for 9010 M2 — proposed_score quarantine (I7) and I5 replay.

These use provisional stand-ins for 9002's FindingGraph/EvaluationResult
(clearly marked in the module) to demonstrate two invariants:

- I7 quarantine: a continuous proposed_score reaches neither the shipped `raw`
  nor `adjusted` nor the replay hash.
- I5 replay: two graphs with identical grounded findings but different
  proposed_scores (and proposer_id) re-derive an identical EvaluationResult.

See docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation.md
"""

from __future__ import annotations

from argus.types.proposer_diagnostics import (
    GroundedFinding,
    ProposedScores,
    QuarantinedFindingGraph,
    derive_evaluation,
    replay_hash,
)


def _graph(proposed=None, proposer_id=None):
    return QuarantinedFindingGraph(
        grounded=[GroundedFinding("procedural", 0.2), GroundedFinding("empathy", 0.1)],
        intents_sha="abc123",
        rubric_version="v1",
        proposed_scores=proposed,
        proposer_id=proposer_id,
    )


def test_d19_quarantine():
    """A proposed_score reaches neither raw, adjusted, nor the replay hash."""
    proposed = ProposedScores(scores={"procedural": 17.3, "empathy": 2.1}, g_used=20)
    with_ps = _graph(proposed=proposed, proposer_id="model-A@hash")
    without_ps = _graph(proposed=None, proposer_id=None)

    r_with = derive_evaluation(with_ps)
    r_without = derive_evaluation(without_ps)

    # The shipped numbers are byte-identical whether or not a proposed score exists.
    assert r_with.raw == r_without.raw
    assert r_with.adjusted == r_without.adjusted
    assert r_with.replay_hash == r_without.replay_hash

    # And the distinctive proposed value never appears in the derived outputs.
    assert r_with.raw != 17.3 and r_with.adjusted != 17.3
    assert "17.3" not in r_with.replay_hash


def test_proposed_scores_non_replay_bearing():
    """Different proposed_scores/proposer_id, identical grounded → identical result."""
    a = _graph(ProposedScores({"procedural": 1.0, "empathy": 19.0}, g_used=20), "model-A@h1")
    b = _graph(ProposedScores({"procedural": 18.0, "empathy": 0.0}, g_used=8), "model-B@h2")

    ra, rb = derive_evaluation(a), derive_evaluation(b)
    assert ra.replay_hash == rb.replay_hash
    assert (ra.raw, ra.adjusted) == (rb.raw, rb.adjusted)


def test_replay_hash_moves_with_grounded_evidence():
    """Sanity: the hash is a real function of the grounded inputs it does bind to."""
    base = _graph()
    changed = QuarantinedFindingGraph(
        grounded=[GroundedFinding("procedural", 0.5), GroundedFinding("empathy", 0.1)],
        intents_sha="abc123",
        rubric_version="v1",
        proposed_scores=None,
        proposer_id=None,
    )
    assert replay_hash(base) != replay_hash(changed)
