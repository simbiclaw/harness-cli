"""Continuous proposed_score computation (9020 M2, io).

Turns the g-wide logit slice M1's Provider captured per dimension into a
continuous `proposed_score`: the expectation over the softmax of those logits,
NOT the argmax. The finer number makes the M3 divergence diagnostic a real
scalar rather than a tie-saturated near-binary, and lets the hunt/escape budget
be ordered toward likely violation mass.

The result is quarantined (`ProposedScores` in types/proposer_diagnostics.py):
it never enters the shipped `raw`/`adjusted` and never touches the replay hash.

M0 finding: the reliable route to G-wide logits is the low-level full-logit
vector, not llama.cpp's high-level `logprobs` API, which caps unpredictably.
This module takes logits already captured that way by the Provider (M1).
"""

from __future__ import annotations

import math
from typing import Sequence

from argus.types.proposer_diagnostics import ProposedScores


def continuous_proposed_score(logits: Sequence[float], g: int) -> float:
    """Expectation over the softmax of the top-g logits.

    Returns the expected score-letter index under the softmax over the first g
    scale positions — a real number between 0 and k-1 where k = min(g,
    len(logits)). Because it is an expectation over the ORDERED scale, it
    differs from the argmax whenever mass is spread, which is the resolution
    D19 buys. Logits are the scale-token logits in scale order (see M1).
    """
    if g <= 0:
        raise ValueError("g must be positive")
    # The letter scale is ORDERED: position i is score-letter i, so the logits
    # are taken in scale order and truncated to the first g — never sorted by
    # magnitude, which would destroy the score axis.
    scale = list(logits)[:g]
    if not scale:
        raise ValueError("no logits to score")
    m = max(scale)
    weights = [math.exp(x - m) for x in scale]
    z = sum(weights)
    return sum(i * w / z for i, w in enumerate(weights))


def score_dimensions(dimension_logits: dict[str, Sequence[float]], g: int) -> ProposedScores:
    """Score every dimension that has logits; record the G actually used.

    A dimension with no logits is skipped, not scored 0 — a fabricated score is
    worse than an absent one. `g_used` is the real width available (min of the
    requested g and the logits present), so the number stays interpretable
    across a capability change per M0's fallback contract.
    """
    scores: dict[str, float] = {}
    widths: list[int] = []
    for dim, logits in dimension_logits.items():
        if not logits:
            continue
        width = min(g, len(logits))
        widths.append(width)
        scores[dim] = continuous_proposed_score(logits, g)
    g_used = min(widths) if widths else 0
    return ProposedScores(scores=scores, g_used=g_used)
