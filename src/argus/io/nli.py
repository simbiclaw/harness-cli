# argus/io/nli.py
"""Ported from simbi `utils/nli.py` @ 929d5a7, re-namespaced.

Two deviations from the source text, both mechanical and documented:

- `utils/logger.py` is not on M7's import list, so `get_logger` becomes
  stdlib `logging.getLogger`.
- `from transformers import pipeline` moved from module scope into
  `NLIModel.__init__`. The harness venv does not install transformers (torch
  behind it), and M7's acceptance test is the module's *import*; a module that
  cannot import fails that claim before any code runs. Deferring the import
  keeps the module importable everywhere and behaviour identical wherever
  transformers exists — the same defensive reasoning this file already applies
  to `torch` inside `_resolve_device`. The real NLI is constructed by the
  caller (`NLIModel(model_name)`), never at import time.
"""
import logging

logger = logging.getLogger(__name__)


def _resolve_device() -> int:
    """CUDA or MPS if either is available, CPU otherwise.

    `-1` is transformers' sentinel for CPU. The integer index is passed straight through to
    `pipeline`, which resolves it against every backend it knows about and, on releases up to and
    including 4.46.3, raises when none of them is available:

        else:
            raise ValueError(f"{device} unrecognized or not available.")

    4.47.0 replaces that branch with `self.device = torch.device("cpu")`. Nothing keeps the raising
    releases out — `pyproject.toml` and `requirements.txt` both ask for `transformers>=4.40.0` —
    so the accelerator check has to happen here rather than being left to `pipeline`. The boundary
    was established by reading `pipelines/base.py` at every release tag from 4.40.0 through 4.49.0
    (26 releases raise, from 4.47.0 onward they do not, and no release does neither); this
    docstring is the only place in the code that states it.

    **The predicates below are deliberately the ones `pipeline` itself uses.** Its
    `is_torch_cuda_available()` is literally `torch.cuda.is_available()`, and its
    `is_torch_mps_available()` is `is_available() and is_built()` — not `is_available()` alone.
    Checking less than the chain checks is how a probe comes to answer `0` on a host where the
    chain will raise: if this asked only `is_available()`, a torch reporting MPS available but not
    built would send `0` into the raising branch. `is_available()` does imply `is_built()` in
    every torch today, so that disagreement is unreachable — but "unreachable by an argument about
    PyTorch internals" is a worse guarantee than "cannot be expressed", and costs one clause.

    Both checks are needed. An earlier revision tested only `cuda`, which is false on Apple
    Silicon — so it answered `-1` there and quietly moved a working MPS pipeline onto the CPU.

    "Available" here means CUDA and MPS. transformers also resolves MLU, MUSA, NPU and XPU, so a
    host with only one of those gets `-1` and a CPU pipeline — correct, and slower than it needs
    to be. Widening the probe is a question for whoever first runs this on one.

    torch arrives with transformers but is imported defensively: the only thing being asked of it
    is whether an accelerator exists, and "no" is the safe answer when it cannot be asked.
    """
    try:
        import torch
    except ImportError:
        return -1
    if torch.cuda.is_available():
        return 0
    backends = getattr(torch, "backends", None)
    mps = getattr(backends, "mps", None) if backends is not None else None
    if mps is not None and mps.is_available() and mps.is_built():
        return 0
    return -1


class NLIModel:
    """
    NLI 封装
    s_ij = P(Entailment | premise, hypothesis)
    对应 ClaimDecomp 中的证据检索公式
    """

    def __init__(self, model_name: str, device: int | None = None):
        """`device` defaults to `_resolve_device()`; pass it to override the choice."""
        from transformers import pipeline

        logger.info(f"Loading NLI model: {model_name}")
        self.pipe = pipeline(
            "text-classification",
            model=model_name,
            device=_resolve_device() if device is None else device,
            truncation=True,
            max_length=512
        )

    def score(self, premise: str, hypothesis: str) -> float:
        """返回 P(Entailment | premise, hypothesis)"""
        try:
            results = self.pipe(
                f"{premise} [SEP] {hypothesis}"
            )
            for r in results:
                if r["label"].upper() == "ENTAILMENT":
                    return r["score"]
            return 0.0
        except Exception as e:
            return 0.0

    def batch_score(
        self,
        pairs: list[tuple[str, str]]
    ) -> list[float]:
        """批量打分，避免逐条调用"""
        inputs = [
            f"{p} [SEP] {h}" for p, h in pairs
        ]
        try:
            results = self.pipe(inputs, batch_size=16)
            scores = []
            for result in results:
                if isinstance(result, list):
                    score = next(
                        (r["score"] for r in result
                         if r["label"].upper() == "ENTAILMENT"),
                        0.0
                    )
                else:
                    score = (result["score"]
                             if result["label"].upper() == "ENTAILMENT"
                             else 0.0)
                scores.append(score)
            return scores
        except Exception:
            return [0.0] * len(pairs)
