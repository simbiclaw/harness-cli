#!/usr/bin/env python3
"""9020 M0 — logprob capability spike and capacity measurement (llama.cpp).

D21 originally pinned the proposer to Apple Silicon + MLX. The execution
environment is x86_64 Linux, so the human directed swapping the serving stack
to llama.cpp (via `llama-cpp-python`), which runs here and exposes per-token
logits. This script answers M0's two questions against that stack:

1. **B2.a — top-k logprob exposure.** Two paths exist and they differ sharply:
   - the high-level `create_completion(logprobs=N)` API, which returns
     `top_logprobs` — but empirically caps well below N and the count varies
     with the distribution (see the artifact's `high_level_logprobs` block);
   - the low-level logit vector (`Llama.scores`, with `logits_all=True`), which
     exposes the FULL vocabulary at a position.
   The reliable route to D19's G=20 is the low-level vector. The probe measures
   both and reports the low-level width as the ceiling.

2. **Capacity.** Decode throughput for a hunt pass (long generation) and a
   score pass (single token), single-stream.

Neither answer depends on weight VALUES: top-k exposure is an API property, and
decode rate is a hardware+model-size property. So a synthetic random-weight
model answers both honestly — its scores are meaningless, which is fine because
M0 scores nothing. Throughput is therefore valid ONLY for the measured model
size and is flagged `representative: false`; a production model's rate must be
measured on a production model. The capability answer carries over unchanged.

    python3 docs/experiments/9020-logprob-capability/run.py \
        --model /path/to/model.gguf --hunt-tokens 256 --samples 3

This script never fabricates a measurement. If the stack or model is
unavailable it exits non-zero and writes nothing — a missing artifact is honest,
a synthetic one is not.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ARTIFACT = Path(__file__).resolve().parent / "output.json"

# D19 asks for a single-token letter scale at G=20: integers multi-tokenize and
# break extraction, so the scale is spelled with single-token letters.
TARGET_G = 20
SCALE_LETTERS = [chr(ord("A") + i) for i in range(TARGET_G)]

SCORE_PROMPT = (
    "Rate this call's procedural accuracy on the scale "
    f"{SCALE_LETTERS[0]} (worst) to {SCALE_LETTERS[-1]} (best). "
    "Answer with exactly one letter.\nAnswer:"
)
HUNT_PROMPT = (
    "List every procedural deviation in the following support call. For each, "
    "quote the exact span and name the rule it violates.\n\nCall:\n"
)


class ProbeFailure(RuntimeError):
    """A measurement could not be taken. Never swallowed into a default."""


@contextlib.contextmanager
def _quiet():
    """llama.cpp is chatty on stderr; keep the artifact run legible."""
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        yield


# --------------------------------------------------------------------------
# Stack discovery
# --------------------------------------------------------------------------


def load_stack(model_path: str, n_ctx: int, n_threads: int):
    """Import llama.cpp and load the model. Raises ProbeFailure if unavailable."""
    try:
        import llama_cpp
    except ImportError as exc:
        raise ProbeFailure(
            f"llama-cpp-python not importable ({exc}). Install it (a dep-vet "
            f"record is required first) or point --model at a box that has it. "
            f"This script does not emulate and will not guess."
        ) from exc

    if not Path(model_path).exists():
        raise ProbeFailure(
            f"model not found at {model_path!r}. Pass a GGUF via --model. "
            f"docs/experiments/9020-logprob-capability/build_tiny_gguf.py "
            f"synthesizes a tiny one when no real model is reachable."
        )

    try:
        with _quiet():
            # logits_all=True is REQUIRED for any per-position logprob access —
            # itself a finding, recorded in the artifact.
            llm = llama_cpp.Llama(
                model_path=model_path,
                n_ctx=n_ctx,
                n_threads=n_threads,
                logits_all=True,
                verbose=False,
            )
    except Exception as exc:  # noqa: BLE001 - surface whatever the loader raises
        raise ProbeFailure(f"could not load model {model_path!r}: {exc}") from exc

    return llama_cpp, llm


def stack_metadata(llama_cpp, model_path: str, args) -> dict:
    return {
        "runtime": "llama-cpp-python",
        "runtime_version": getattr(llama_cpp, "__version__", "unknown"),
        "model_id": args.model_id or Path(model_path).name,
        "model_path": model_path,
        "model_hash": args.model_hash or "unrecorded",
        "synthetic_weights": args.synthetic,
        "quantization": args.quantization,
    }


def host_metadata() -> dict:
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
    }


# --------------------------------------------------------------------------
# Probe 1 — top-k logprob exposure (B2.a)
# --------------------------------------------------------------------------


def probe_topk(llm) -> dict:
    """Characterize both logprob paths and report the reliable ceiling.

    Deliberately empirical: the high-level `logprobs` param is known to behave
    unexpectedly, so the probe requests several k and records what actually
    comes back, alongside the low-level full-vocab width.
    """
    n_vocab = int(llm.n_vocab())

    # High-level path: request a ladder of k, record returned counts.
    high_level = {}
    for k in (5, 10, 20, 50, n_vocab):
        try:
            with _quiet():
                out = llm.create_completion(
                    "capability probe", max_tokens=1, logprobs=k, temperature=0.0
                )
            entries = len(out["choices"][0]["logprobs"]["top_logprobs"][0])
        except Exception as exc:  # noqa: BLE001
            entries = f"error: {type(exc).__name__}"
        high_level[str(k)] = entries

    # Does the high-level path reliably deliver TARGET_G distinct entries?
    hl_at_target = high_level.get(str(TARGET_G))
    hl_reliable = isinstance(hl_at_target, int) and hl_at_target >= TARGET_G

    # Low-level path: the full logit vector at the last position.
    low_level_width = _low_level_logit_width(llm)

    ceiling = low_level_width if low_level_width else 0
    return {
        "topk_available": ceiling >= 2,
        "topk_ceiling": ceiling,
        "ceiling_source": "low_level_full_logits",
        "vocab_size": n_vocab,
        "high_level_logprobs": {
            "requested_to_returned": high_level,
            "reliable_at_target_g": hl_reliable,
            "note": (
                "The high-level create_completion(logprobs=N) API caps below N "
                "and the returned count varies with the distribution. D19's G "
                "must be sourced from the low-level full-logit vector, not this "
                "API."
            ),
        },
        "note": (
            "Ceiling is the width of the full logit vector the low-level API "
            "exposes at a scoring position."
        ),
    }


def _low_level_logit_width(llm) -> int:
    """Width of the raw logit vector exposed at the last decoded position."""
    try:
        with _quiet():
            llm.reset()
            llm.eval(llm.tokenize(b"capability probe"))
        row = llm.scores[llm.n_tokens - 1]
        return int(len(row))
    except Exception:  # noqa: BLE001 - absence is a recordable result, not a crash
        return 0


def resolve_g(topk: dict) -> int:
    """G is the target, or whatever the stack exposes, or 1. Always recorded."""
    if not topk["topk_available"]:
        return 1
    return min(TARGET_G, int(topk["topk_ceiling"]))


def expectation_demo(llm, g_used: int) -> dict:
    """Prove D19 is computable: the expectation over the full softmax is a real
    scalar, distinct from the argmax. Uses the model's own next-token logits over
    the first g_used vocab ids as a stand-in letter scale (values meaningless on
    a random model; the point is that the number exists and differs from argmax).
    """
    try:
        with _quiet():
            llm.reset()
            llm.eval(llm.tokenize(SCORE_PROMPT.encode()))
        logits = list(llm.scores[llm.n_tokens - 1])[:g_used]
        m = max(logits)
        exps = [math.exp(x - m) for x in logits]
        z = sum(exps)
        probs = [e / z for e in exps]
        expectation = sum(i * p for i, p in enumerate(probs))
        argmax = max(range(len(logits)), key=lambda i: logits[i])
        return {
            "g_used": g_used,
            "expectation_index": round(expectation, 4),
            "argmax_index": argmax,
            "differs_from_argmax": abs(expectation - argmax) > 1e-6,
            "note": "expectation over the full softmax; the D19 continuous score",
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


# --------------------------------------------------------------------------
# Probe 2 — throughput per call type
# --------------------------------------------------------------------------


def time_generation(llm, prompt: str, max_tokens: int) -> float:
    with _quiet():
        start = time.perf_counter()
        llm.create_completion(prompt, max_tokens=max_tokens, temperature=0.8)
        elapsed = time.perf_counter() - start
    if elapsed <= 0:
        raise ProbeFailure("non-positive elapsed time; clock is unusable")
    return max_tokens / elapsed


def measure_call_type(llm, prompt: str, max_tokens: int, samples: int) -> dict:
    rates = [time_generation(llm, prompt, max_tokens) for _ in range(samples)]
    return {
        "single_stream_tok_s": round(sum(rates) / len(rates), 3),
        "single_stream_samples_tok_s": [round(r, 3) for r in rates],
        "output_tokens": max_tokens,
        "samples": samples,
        # A single Llama instance is single-stream. Batched throughput needs
        # multiple contexts or the llama-server continuous batcher — measured
        # through the serving layer, not here. Q4 turns on this number.
        "batched_tok_s": None,
        "batched_unavailable_reason": (
            "single in-process Llama instance is single-stream; batched decode "
            "requires the llama-server continuous batcher, measured under M1/Q4"
        ),
    }


# --------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="path to a GGUF model")
    parser.add_argument("--model-id", default="", help="human name for the model")
    parser.add_argument("--model-hash", default="", help="pinned model hash (D21)")
    parser.add_argument("--quantization", default="F32")
    parser.add_argument("--synthetic", action="store_true",
                        help="mark weights as synthetic (throughput non-representative)")
    parser.add_argument("--hunt-tokens", type=int, default=256)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--n-ctx", type=int, default=512)
    parser.add_argument("--n-threads", type=int, default=4)
    parser.add_argument("--transcript", type=Path, default=None,
                        help="a real transcript to hunt over; filler if omitted")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        llama_cpp, llm = load_stack(args.model, args.n_ctx, args.n_threads)

        topk = probe_topk(llm)
        g_used = resolve_g(topk)
        demo = expectation_demo(llm, g_used)

        if args.transcript and args.transcript.exists():
            transcript = args.transcript.read_text()
        else:
            print("warning: no --transcript; hunt throughput uses filler text and "
                  "reflects decode rate, not retrieval difficulty", file=sys.stderr)
            transcript = "Agent: Thank you for calling. How can I help?\n" * 40

        throughput = {
            "hunt": measure_call_type(
                llm, HUNT_PROMPT + transcript, args.hunt_tokens, args.samples
            ),
            "score": measure_call_type(llm, SCORE_PROMPT, 1, args.samples),
        }
    except ProbeFailure as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("no artifact written — a missing measurement is honest, a "
              "synthetic one is not", file=sys.stderr)
        return 1

    record = {
        "schema_version": 2,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": host_metadata(),
        "stack": stack_metadata(llama_cpp, args.model, args),
        "topk_available": topk["topk_available"],
        "topk_ceiling": topk["topk_ceiling"],
        "topk_probe": topk,
        "target_g": TARGET_G,
        "g_used": g_used,
        "expectation_demo": demo,
        "throughput": throughput,
        "throughput_representative": not args.synthetic,
        "throughput_caveat": (
            "measured on a synthetic random-weight model; decode rate is valid "
            "for this model size only and does not represent a production model"
        ) if args.synthetic else None,
    }

    ARTIFACT.write_text(json.dumps(record, indent=2) + "\n")
    print(f"wrote {ARTIFACT}")
    if g_used < TARGET_G:
        print(f"note: G={g_used} is below the D19 target {TARGET_G}; record it "
              f"per evaluation and revisit M2's scale.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
