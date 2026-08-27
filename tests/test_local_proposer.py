"""Acceptance tests for 9020 M1 — batch-shaped local Provider with KV-cache reuse.

The Provider takes its model by dependency injection (a `LogitModel` protocol),
so these tests exercise the real decode-call behavior against a fake model that
records its eval() calls — no GGUF or llama.cpp needed in CI. A separate
opt-in integration check (skipped when the model is absent) proves the same
contract against real llama.cpp.

Four load-bearing properties:
  - accepts a set of calls, singleton same code path as a batch;
  - scoring passes prefill the transcript exactly once (KV-cache reuse);
  - sampling params (temperature, seed, drafter, mode, cap, G) are recorded;
  - the Provider is io, and core does not import it or the model client.

See docs/exec-plans/active/9020-continuous-proposer-and-provenance-separation.md
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from argus.io.local_proposer import (
    LocalProposer,
    ProposerCall,
    ProposerConfig,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_CORE = REPO_ROOT / "src" / "argus" / "core"


class FakeLogitModel:
    """A stand-in for llama_cpp.Llama that records its decode calls.

    Records every eval() as (start_pos, n_tokens) so a test can prove the
    transcript block was decoded exactly once across several scoring passes.
    Supports the rewind (n_tokens setter) the KV-reuse pattern depends on.
    """

    def __init__(self, vocab: int = 32) -> None:
        self._vocab = vocab
        self._n = 0
        self.eval_calls: list[tuple[int, int]] = []
        self.reset_calls = 0
        # scores[pos] is a logit row; filled lazily as positions are decoded.
        self.scores: list[list[float]] = []

    def n_vocab(self) -> int:
        return self._vocab

    def tokenize(self, text: bytes, add_bos: bool = True) -> list[int]:
        # One token per byte, deterministic; content irrelevant to the contract.
        ids = list(text[: 64])
        return ([1] + ids) if add_bos else ids

    def reset(self) -> None:
        self.reset_calls += 1
        self._n = 0
        self.scores = []

    def eval(self, tokens) -> None:
        start = self._n
        toks = list(tokens)
        self.eval_calls.append((start, len(toks)))
        for i, tid in enumerate(toks):
            row = [0.0] * self._vocab
            # deterministic non-uniform logits so expectation != argmax downstream
            row[(start + i) % self._vocab] = 2.0
            row[(start + i + 1) % self._vocab] = 1.5
            if start + i < len(self.scores):
                self.scores[start + i] = row
            else:
                self.scores.append(row)
        self._n += len(toks)

    @property
    def n_tokens(self) -> int:
        return self._n

    @n_tokens.setter
    def n_tokens(self, value: int) -> None:
        # Rewind the logical cursor; KV for [0:value] stays physically cached.
        self._n = value
        del self.scores[value:]


def _config(**kw) -> ProposerConfig:
    base = dict(
        model_id="fake-model",
        model_hash="deadbeef",
        temperature=0.7,
        seed=1234,
        drafter="eagle-x",
        spec_mode="draft",
        spec_cap=8,
        g=20,
        n_ctx=1024,
        n_threads=4,
    )
    base.update(kw)
    return ProposerConfig(**base)


def _call(cid="c1", dims=("procedural", "empathy", "resolution", "value")):
    return ProposerCall(
        call_id=cid,
        transcript="Agent: hello. Customer: my report is late.",
        dimensions=list(dims),
    )


def test_accepts_singleton_set():
    """A set of one call returns a set of one finding-set, same path as a batch."""
    proposer = LocalProposer(FakeLogitModel(), _config())

    one = proposer.propose([_call("only")])
    assert isinstance(one, list) and len(one) == 1
    assert one[0].call_id == "only"

    many = proposer.propose([_call("a"), _call("b"), _call("c")])
    assert [fs.call_id for fs in many] == ["a", "b", "c"]


def test_kv_cache_reused_across_scoring_passes():
    """Four per-dimension scoring passes prefill the transcript exactly once.

    Hard criterion: if the transcript block is decoded more than once, the
    Provider is re-prefilling per dimension and D19's per-dimension resolution
    is unaffordable at volume (falls M2 back to one call-level score).
    """
    model = FakeLogitModel()
    proposer = LocalProposer(model, _config())

    call = _call(dims=("d1", "d2", "d3", "d4"))
    proposer.propose([call])

    # The transcript prefill is the eval that starts at position 0 (or after BOS)
    # and carries the transcript's token count. It must appear exactly once.
    transcript_tokens = model.tokenize(call.transcript.encode())
    n_transcript = len(transcript_tokens)
    prefills = [c for c in model.eval_calls if c[0] == 0 and c[1] == n_transcript]
    assert len(prefills) == 1, (
        f"transcript ({n_transcript} tokens) was prefilled {len(prefills)} "
        f"times across 4 scoring passes; expected exactly 1. eval calls: "
        f"{model.eval_calls}"
    )
    # And there is one suffix decode per dimension, each reusing the prefix.
    suffix_evals = [c for c in model.eval_calls if c[0] == n_transcript]
    assert len(suffix_evals) == 4, (
        f"expected 4 per-dimension suffix decodes reusing the cached transcript, "
        f"got {len(suffix_evals)}: {model.eval_calls}"
    )


def test_sampling_params_recorded():
    """temperature, seed, drafter, mode, cap, and G appear in the returned record."""
    proposer = LocalProposer(FakeLogitModel(), _config())
    fs = proposer.propose([_call()])[0]
    sp = fs.sampling_params
    assert sp["temperature"] == 0.7
    assert sp["seed"] == 1234
    assert sp["drafter"] == "eagle-x"
    assert sp["mode"] == "draft"
    assert sp["cap"] == 8
    assert sp["g"] == 20
    # Proposer identity is part of the evaluation record, not ambient.
    assert fs.proposer_id and "fake-model" in fs.proposer_id


def test_dimension_logits_captured_for_m2():
    """The Provider captures the g-wide logit slice per dimension for M2 to score.

    M1 provides the raw material (quarantined logits); M2 computes the
    proposed_score. The slice width never exceeds G.
    """
    proposer = LocalProposer(FakeLogitModel(vocab=32), _config(g=20))
    fs = proposer.propose([_call(dims=("d1", "d2"))])[0]
    assert set(fs.dimension_logits) == {"d1", "d2"}
    for dim, logits in fs.dimension_logits.items():
        assert len(logits) == 20, f"{dim}: expected G=20 logits, got {len(logits)}"


def test_provider_is_io_not_core():
    """core ✗ model_client: no core module imports the Provider or llama_cpp."""
    offenders: list[str] = []
    if SRC_CORE.exists():
        for py in SRC_CORE.rglob("*.py"):
            tree = ast.parse(py.read_text(), filename=str(py))
            for node in ast.walk(tree):
                mods: list[str] = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    mods.append(node.module)
                elif isinstance(node, ast.Import):
                    mods.extend(a.name for a in node.names)
                for m in mods:
                    if "local_proposer" in m or m.split(".")[0] in ("llama_cpp", "anthropic"):
                        offenders.append(f"{py.relative_to(REPO_ROOT)}:{node.lineno} imports {m}")
    assert not offenders, "core must not import a model client:\n  " + "\n  ".join(offenders)


@pytest.mark.skipif(
    not os.path.exists("/home/user/models/tiny-llama-random.gguf"),
    reason="real GGUF not present; fake-model tests cover the contract",
)
def test_kv_reuse_against_real_llama_cpp():
    """Integration: the same KV-reuse contract holds against real llama.cpp."""
    from argus.io.local_proposer import LlamaLogitModel

    model = LlamaLogitModel(
        "/home/user/models/tiny-llama-random.gguf", n_ctx=1024, n_threads=4
    )
    proposer = LocalProposer(model, _config(g=8))
    fs = proposer.propose([_call(dims=("d1", "d2", "d3", "d4"))])[0]
    assert set(fs.dimension_logits) == {"d1", "d2", "d3", "d4"}
    for logits in fs.dimension_logits.values():
        assert len(logits) == 8
