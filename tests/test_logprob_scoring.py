"""Acceptance tests for 9010 M2 — continuous per-dimension proposed_score (io).

The scorer turns M1's captured g-wide logit slice into a continuous
proposed_score: the expectation over the softmax, not the argmax. It records
the G actually used per evaluation, so the number stays interpretable across a
capability change (M0's fallback contract).

See docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation.md
"""

from __future__ import annotations

import math

from argus.io.logprob_scoring import continuous_proposed_score, score_dimensions


def test_expectation_not_argmax():
    """A distribution whose argmax and expectation differ yields the expectation."""
    # Bimodal-ish logits: argmax at index 0, but mass spread to high indices so
    # the expectation sits well above 0.
    logits = [3.0, 0.0, 0.0, 0.0, 2.9, 2.9, 2.9]
    argmax = max(range(len(logits)), key=lambda i: logits[i])
    assert argmax == 0

    score = continuous_proposed_score(logits, g=len(logits))
    # Expectation over the softmax, computed independently here.
    m = max(logits)
    w = [math.exp(x - m) for x in logits]
    z = sum(w)
    expected = sum(i * wi / z for i, wi in enumerate(w))
    assert abs(score - expected) < 1e-9
    # And it is genuinely not the argmax — the whole point of D19.
    assert abs(score - argmax) > 0.5


def test_g_truncates_to_first_g_scale_positions():
    """Only the first g scale positions enter the expectation; the rest are ignored.

    The scale is ordered, so truncation drops the tail of the scale, not the
    magnitude-weak logits. A large logit past position g-1 has no effect.
    """
    # index 9 has the largest logit but lies past the first 2 scale positions.
    logits = [5.0, 4.9] + [0.0] * 7 + [10.0]
    score_top2 = continuous_proposed_score(logits, g=2)
    # Only positions 0 and 1 survive; their logits are near-equal so the
    # expectation is ~0.5 and the far index-9 spike is ignored entirely.
    assert score_top2 < 1.0
    score_all = continuous_proposed_score(logits, g=len(logits))
    assert score_all > score_top2  # the index-9 mass now pulls it up


def test_g_recorded_per_evaluation():
    """score_dimensions records the G actually used, not an assumed constant."""
    dim_logits = {
        "procedural": [2.0, 1.0, 0.5],
        "empathy": [1.0, 3.0, 0.5],
    }
    # Ask for g=10 but only 3 logits exist per dimension.
    scored = score_dimensions(dim_logits, g=10)
    assert scored.g_used == 3, "g_used must reflect the logits actually present"
    assert set(scored.scores) == {"procedural", "empathy"}
    for v in scored.scores.values():
        assert isinstance(v, float)


def test_empty_dimension_is_skipped_not_faked():
    """A dimension with no logits gets no score, rather than a fabricated 0."""
    scored = score_dimensions({"procedural": [1.0, 2.0], "empty": []}, g=5)
    assert "procedural" in scored.scores
    assert "empty" not in scored.scores
