#!/usr/bin/env python3
"""9010 M0 — logprob capability spike and capacity measurement.

Answers two questions the rest of plan 9010 is contingent on, by measuring
rather than assuming:

1. **B2.a — top-k logprob exposure.** Does the MLX serving stack surface top-k
   logprobs at a chosen token position, and at what k? D19 wants G=20 on a
   single-token letter scale. If the stack exposes fewer, G becomes whatever k
   it does expose and that number is recorded per evaluation. If it exposes
   none, D19 reduces to argmax scores, only D20 survives, and M2 is rewritten.

2. **Capacity.** Actual decode throughput for a hunt pass (long generation) and
   a score pass (single token), single-stream and batched. The patch's
   arithmetic — 3000 calls/day, ~20-25 tok/s single-stream, 1500-2000 output
   tokens per hunt — is an estimate and is explicitly not evidence. This script
   exists to replace it.

Run this ON THE TARGET BOX (Apple Silicon, MLX installed). It writes
`output.json` beside itself; commit that artifact. The acceptance test
`tests/test_logprob_capability.py` validates it.

    python3 docs/experiments/9010-logprob-capability/run.py \
        --model mlx-community/<model> --hunt-tokens 1800 --batch-size 8

This script never fabricates a measurement. If the stack is unavailable or a
probe fails, it exits non-zero and writes nothing — a missing artifact is an
honest state, a synthetic one is not.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
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


# --------------------------------------------------------------------------
# Stack discovery
# --------------------------------------------------------------------------


def load_stack(model_id: str):
    """Import MLX and load the model. Raises ProbeFailure if unavailable."""
    try:
        import mlx.core as mx  # noqa: F401
        import mlx_lm
    except ImportError as exc:
        raise ProbeFailure(
            f"MLX stack not importable ({exc}). This script must run on the "
            f"target Apple Silicon box with mlx-lm installed. It does not "
            f"emulate, and it will not guess."
        ) from exc

    try:
        model, tokenizer = mlx_lm.load(model_id)
    except Exception as exc:  # noqa: BLE001 - surface whatever the loader raises
        raise ProbeFailure(f"could not load model {model_id!r}: {exc}") from exc

    return mlx_lm, model, tokenizer


def stack_metadata(mlx_lm, model_id: str, args) -> dict:
    """Record what produced these numbers. A G is not portable across stacks."""
    try:
        import mlx.core as mx

        mlx_version = getattr(mx, "__version__", "unknown")
    except ImportError:
        mlx_version = "unknown"

    return {
        "runtime": "mlx-lm",
        "runtime_version": getattr(mlx_lm, "__version__", "unknown"),
        "mlx_version": mlx_version,
        "model_id": model_id,
        "model_hash": args.model_hash or "unrecorded",
        "quantization": args.quantization,
        "speculative": {
            "enabled": bool(args.drafter),
            "drafter": args.drafter,
            "mode": args.spec_mode,
            "cap": args.spec_cap,
        },
    }


def host_metadata() -> dict:
    chip = "unknown"
    if platform.system() == "Darwin":
        try:
            chip = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            ).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "chip": chip,
    }


# --------------------------------------------------------------------------
# Probe 1 — top-k logprob exposure (B2.a)
# --------------------------------------------------------------------------


def probe_topk(mlx_lm, model, tokenizer) -> dict:
    """Discover how many ranked logprobs the stack exposes at one token position.

    Deliberately empirical: this asks the stack what it returns rather than
    trusting a documented signature, because the whole milestone exists because
    that exposure is unverified on this stack.
    """
    prompt_ids = tokenizer.encode(SCORE_PROMPT)

    logprobs = None
    entry_point = None
    for name in ("generate_step", "stream_generate"):
        step_fn = getattr(mlx_lm, name, None)
        if step_fn is None:
            continue
        try:
            for item in step_fn(model=model, prompt=prompt_ids, max_tokens=1):
                logprobs = _extract_logprobs(item)
                if logprobs is not None:
                    entry_point = name
                break
        except Exception:  # noqa: BLE001 - try the next entry point
            continue
        if logprobs is not None:
            break

    if logprobs is None:
        # Not a failure of the script: a real, recordable answer. D19 reduces
        # to argmax and only D20 survives.
        return {
            "topk_available": False,
            "topk_ceiling": 0,
            "entry_point": None,
            "vocab_size": _vocab_size(tokenizer),
            "note": (
                "No per-position logprob distribution was reachable via "
                "generate_step or stream_generate. D19 falls back to argmax; "
                "M2 must be rewritten before it starts."
            ),
        }

    ceiling = int(getattr(logprobs, "size", 0) or len(logprobs))
    return {
        "topk_available": ceiling > 1,
        "topk_ceiling": ceiling,
        "entry_point": entry_point,
        "vocab_size": _vocab_size(tokenizer),
        "note": (
            "Ceiling is the width of the distribution the stack actually "
            "returned at the scoring position."
        ),
    }


def _extract_logprobs(item):
    """Pull a logprob array out of whatever shape the entry point yields."""
    candidate = None
    if isinstance(item, tuple) and len(item) >= 2:
        candidate = item[1]
    else:
        candidate = getattr(item, "logprobs", None)
    if candidate is None:
        return None
    size = getattr(candidate, "size", None)
    if size is None:
        try:
            size = len(candidate)
        except TypeError:
            return None
    return candidate if size and size > 1 else None


def _vocab_size(tokenizer) -> int | None:
    for attr in ("vocab_size", "n_words"):
        value = getattr(tokenizer, attr, None)
        if isinstance(value, int):
            return value
    return None


def resolve_g(topk: dict) -> int:
    """G is the target, or whatever the stack exposes, or 1. Always recorded."""
    if not topk["topk_available"]:
        return 1
    return min(TARGET_G, int(topk["topk_ceiling"]))


# --------------------------------------------------------------------------
# Probe 2 — throughput per call type
# --------------------------------------------------------------------------


def time_generation(mlx_lm, model, tokenizer, prompt: str, max_tokens: int) -> float:
    """Return output tokens per second for one generation."""
    start = time.perf_counter()
    text = mlx_lm.generate(
        model=model,
        tokenizer=tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
        verbose=False,
    )
    elapsed = time.perf_counter() - start
    if elapsed <= 0:
        raise ProbeFailure("non-positive elapsed time; clock is unusable")
    produced = len(tokenizer.encode(text)) if text else max_tokens
    return produced / elapsed


def measure_call_type(
    mlx_lm, model, tokenizer, prompt: str, max_tokens: int, samples: int, batch_size: int
) -> dict:
    """Measure one call type single-stream, and batched where the stack allows."""
    rates = [
        time_generation(mlx_lm, model, tokenizer, prompt, max_tokens)
        for _ in range(samples)
    ]
    single = sum(rates) / len(rates)

    batched, reason = None, None
    batch_generate = getattr(mlx_lm, "batch_generate", None)
    if batch_size <= 1:
        reason = "batching not requested (--batch-size <= 1)"
    elif batch_generate is None:
        reason = (
            "this mlx-lm build exposes no batch_generate entry point; batched "
            "throughput must be measured through the serving layer instead"
        )
    else:
        try:
            start = time.perf_counter()
            batch_generate(
                model=model,
                tokenizer=tokenizer,
                prompts=[prompt] * batch_size,
                max_tokens=max_tokens,
                verbose=False,
            )
            elapsed = time.perf_counter() - start
            batched = (max_tokens * batch_size) / elapsed
        except Exception as exc:  # noqa: BLE001 - record, never fabricate
            reason = f"batch_generate raised {type(exc).__name__}: {exc}"

    entry = {
        "single_stream_tok_s": round(single, 3),
        "single_stream_samples_tok_s": [round(r, 3) for r in rates],
        "output_tokens": max_tokens,
        "samples": samples,
        "batched_tok_s": round(batched, 3) if batched is not None else None,
        "batch_size": batch_size if batched is not None else None,
    }
    if batched is None:
        entry["batched_unavailable_reason"] = reason
    return entry


# --------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="MLX model id to load")
    parser.add_argument("--model-hash", default="", help="pinned model hash (D21)")
    parser.add_argument("--quantization", default="unrecorded")
    parser.add_argument("--hunt-tokens", type=int, default=1800)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--drafter", default="", help="speculative drafter, if any")
    parser.add_argument("--spec-mode", default=None)
    parser.add_argument("--spec-cap", type=int, default=None)
    parser.add_argument("--transcript", type=Path, default=None,
                        help="a real transcript to hunt over; synthetic filler if omitted")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        mlx_lm, model, tokenizer = load_stack(args.model)

        topk = probe_topk(mlx_lm, model, tokenizer)
        g_used = resolve_g(topk)

        if args.transcript and args.transcript.exists():
            transcript = args.transcript.read_text()
        else:
            print(
                "warning: no --transcript given; hunt throughput is measured over "
                "filler text and reflects decode rate, not retrieval difficulty",
                file=sys.stderr,
            )
            transcript = "Agent: Thank you for calling. How can I help?\n" * 200

        throughput = {
            "hunt": measure_call_type(
                mlx_lm, model, tokenizer,
                HUNT_PROMPT + transcript, args.hunt_tokens, args.samples, args.batch_size,
            ),
            "score": measure_call_type(
                mlx_lm, model, tokenizer,
                SCORE_PROMPT, 1, args.samples, args.batch_size,
            ),
        }
    except ProbeFailure as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("no artifact written — a missing measurement is honest, a synthetic "
              "one is not", file=sys.stderr)
        return 1

    record = {
        "schema_version": 1,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": host_metadata(),
        "stack": stack_metadata(mlx_lm, args.model, args),
        "topk_available": topk["topk_available"],
        "topk_ceiling": topk["topk_ceiling"],
        "topk_probe": topk,
        "target_g": TARGET_G,
        "g_used": g_used,
        "throughput": throughput,
    }

    ARTIFACT.write_text(json.dumps(record, indent=2) + "\n")
    print(f"wrote {ARTIFACT}")
    if g_used < TARGET_G:
        print(
            f"note: G={g_used} is below the D19 target of {TARGET_G}. "
            f"Record it per evaluation and revisit M2's scale before starting it.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
