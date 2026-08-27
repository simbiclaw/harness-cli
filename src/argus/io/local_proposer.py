"""Local open-weight proposer Provider (9020 M1).

The proposer is the ONLY component that talks to a model client; it lives in
`io/`, never `core/` — that fence is what keeps the pure stages pure (I1).

Two properties are load-bearing (D21):

- **Batch-shaped interface.** `propose()` takes a *set* of calls and returns a
  set of finding-sets, even when the set has size one. Batched-vs-single-stream
  is then a swap behind this boundary, which is why the serving-shape question
  (Q4) is safe to defer.
- **KV-cache reuse.** The transcript is prefilled once per call; each
  per-dimension scoring pass decodes only its own short suffix, reusing the
  cached transcript prefix. Without this, per-dimension scoring re-prefills the
  transcript once per dimension and D19's resolution is unaffordable at volume.

The model is injected as a `LogitModel` (a small protocol), so the Provider is
testable against a fake that records its decode calls and swappable across
serving stacks. `LlamaLogitModel` adapts `llama_cpp.Llama` to that protocol.

M1 scope is the plumbing: run the passes, reuse the cache, capture the g-wide
logit slice per dimension, and record the sampling params and proposer
identity. Turning those logits into a continuous `proposed_score` is M2;
extracting grounded `Finding`s against 9002's schema is 9002 M6. Both build on
the `FindingSet` this Provider returns.

Stack note: D21 was swapped from Apple Silicon/MLX to llama.cpp on x86_64 by
human direction; the io boundary makes that a loader swap, not an architecture
change.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol, Sequence, runtime_checkable


@runtime_checkable
class LogitModel(Protocol):
    """The minimal model surface the Provider needs.

    Real implementation: `LlamaLogitModel` over `llama_cpp.Llama`. Test
    implementation: a fake that records eval() calls. Nothing here is specific
    to llama.cpp — a different stack implements the same five members.
    """

    def n_vocab(self) -> int: ...
    def tokenize(self, text: bytes, add_bos: bool = ...) -> list[int]: ...
    def reset(self) -> None: ...
    def eval(self, tokens: Sequence[int]) -> None: ...
    @property
    def n_tokens(self) -> int: ...
    @n_tokens.setter
    def n_tokens(self, value: int) -> None: ...


@dataclass(frozen=True)
class ProposerConfig:
    """Deployment contract for one proposer (D21).

    Lives here as a parameter object rather than in `config/`: the config-layer
    landing is Tier C (Q3) and deferred. Proposer identity (`model_id`,
    `model_hash`) is part of the evaluation record, not an ambient setting.
    Hunt and score are distinct call types — `temperature` governs the hunt
    pass; the score pass is greedy and seeded.
    """

    model_id: str
    model_hash: str
    temperature: float
    seed: int
    g: int
    n_ctx: int = 2048
    n_threads: int = 4
    # Speculative-decoding layer: a throughput dependency only. Recorded
    # alongside the other sampling params, never a judgment input.
    drafter: str | None = None
    spec_mode: str | None = None
    spec_cap: int | None = None

    def sampling_params(self) -> dict:
        return {
            "temperature": self.temperature,
            "seed": self.seed,
            "g": self.g,
            "drafter": self.drafter,
            "mode": self.spec_mode,
            "cap": self.spec_cap,
        }

    @property
    def proposer_id(self) -> str:
        return f"{self.model_id}@{self.model_hash}"


@dataclass(frozen=True)
class ProposerCall:
    """One evaluation request into the proposer."""

    call_id: str
    transcript: str
    dimensions: Sequence[str]


@dataclass
class FindingSet:
    """The proposer's output for one call — quarantined, never trusted past S3.

    `findings` is populated by the finding extractor (9002 M6) against the
    real `Finding` schema; M1 returns it empty. `dimension_logits` is the
    g-wide raw logit slice per dimension that M2 turns into a continuous
    `proposed_score`. Neither ships: everything here is proposer-internal.
    """

    call_id: str
    proposer_id: str
    sampling_params: dict
    dimension_logits: dict[str, list[float]]
    findings: list = field(default_factory=list)


# Per-dimension scoring suffix. The model reads the transcript (cached) then
# this short prompt; the last position's logits are the dimension's scoring
# distribution. Kept tiny so the reused-prefix win is the whole cost.
_SCORE_SUFFIX = "\n\nScore dimension '{dim}' (one token):"


class LocalProposer:
    """Batch-shaped proposer with per-call KV-cache reuse."""

    def __init__(self, model: LogitModel, config: ProposerConfig) -> None:
        self._model = model
        self._config = config

    def propose(self, calls: Sequence[ProposerCall]) -> list[FindingSet]:
        """Return one FindingSet per call. A singleton set uses the same path."""
        return [self._propose_one(call) for call in calls]

    def _propose_one(self, call: ProposerCall) -> FindingSet:
        model = self._model
        g = self._config.g

        # Prefill the transcript ONCE.
        model.reset()
        transcript_tokens = model.tokenize(call.transcript.encode())
        model.eval(transcript_tokens)
        prefix_len = model.n_tokens

        dimension_logits: dict[str, list[float]] = {}
        for dim in call.dimensions:
            # Decode only this dimension's suffix; the cached transcript prefix
            # is reused (no re-prefill).
            suffix = _SCORE_SUFFIX.format(dim=dim).encode()
            suffix_tokens = model.tokenize(suffix, add_bos=False)
            model.eval(suffix_tokens)
            logits_row = model.scores[model.n_tokens - 1]
            dimension_logits[dim] = _scale_slice(list(logits_row), g)
            # Rewind to the transcript prefix so the next dimension reuses it.
            model.n_tokens = prefix_len

        return FindingSet(
            call_id=call.call_id,
            proposer_id=self._config.proposer_id,
            sampling_params=self._config.sampling_params(),
            dimension_logits=dimension_logits,
        )


def _scale_slice(logits: list[float], g: int) -> list[float]:
    """The first g logits, in scale order — the g letter-scale token positions.

    NOT the top-g by magnitude: the score scale is ordered (position i is
    score-letter i), so M2's expectation must run over the scale in order.
    Sorting by magnitude would destroy the score axis. The width is capped at G
    (M0's measured, recorded value) so extraction cannot silently over-read.
    Provisional: a real deployment maps the specific letter-token vocab ids
    here; that mapping is a config concern deferred to Q3. The first-g slice is
    the placeholder scale until then.
    """
    return logits[:g]


class LlamaLogitModel:
    """Adapt `llama_cpp.Llama` to the `LogitModel` protocol.

    Imported lazily so the module (and the io layer) carry no hard dependency
    on llama_cpp at import time — tests and other stacks do not need it.
    `logits_all=True` is required for per-position logit access (an M0 finding).
    """

    def __init__(self, model_path: str, n_ctx: int = 2048, n_threads: int = 4) -> None:
        import llama_cpp

        self._llm = llama_cpp.Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            logits_all=True,
            verbose=False,
        )

    def n_vocab(self) -> int:
        return int(self._llm.n_vocab())

    def tokenize(self, text: bytes, add_bos: bool = True) -> list[int]:
        return self._llm.tokenize(text, add_bos=add_bos)

    def reset(self) -> None:
        self._llm.reset()

    def eval(self, tokens: Sequence[int]) -> None:
        self._llm.eval(list(tokens))

    @property
    def scores(self):
        return self._llm.scores

    @property
    def n_tokens(self) -> int:
        return self._llm.n_tokens

    @n_tokens.setter
    def n_tokens(self, value: int) -> None:
        self._llm.n_tokens = value
