#!/usr/bin/env python3
"""
Preflight diagnostic for audio-server.

Verifies every endpoint the structural-transcription pipeline uses, with
concrete error messages when something is off. Run this before kicking
off a long pipeline run on a new machine or after a `brew upgrade speech`.

Exit codes:
  0 — all checks passed
  1 — server reachable but at least one endpoint is broken / missing
  2 — server not reachable at all
"""

from __future__ import annotations

import argparse
import sys
import time

import numpy as np

try:
    from server_client import AudioServerClient, wait_for_server
except ImportError:  # pragma: no cover
    from .server_client import AudioServerClient, wait_for_server  # type: ignore


def synth_test_tone(sample_rate: int = 16000, duration_sec: float = 2.0) -> np.ndarray:
    """
    A brief 200 Hz sine + low-amplitude noise. Not real speech, but enough
    to exercise the HTTP path and JSON parsing. Real ASR / diarization may
    return empty results on this input — that is fine; we are checking
    the wire, not the model.
    """
    t = np.arange(int(sample_rate * duration_sec)) / sample_rate
    tone = 0.2 * np.sin(2 * np.pi * 200.0 * t).astype(np.float32)
    noise = (np.random.default_rng(0).standard_normal(len(t)) * 0.01).astype(np.float32)
    return tone + noise


def check(name: str, fn) -> bool:
    """Run a check, print PASS/FAIL with timing, return success flag."""
    t0 = time.monotonic()
    try:
        fn()
    except Exception as e:
        elapsed = time.monotonic() - t0
        print(f"  [{elapsed:5.2f}s] FAIL  {name}: {type(e).__name__}: {e}")
        return False
    elapsed = time.monotonic() - t0
    print(f"  [{elapsed:5.2f}s] PASS  {name}")
    return True


def main() -> int:
    p = argparse.ArgumentParser(description="Diagnose audio-server endpoints")
    p.add_argument("--server", default="http://localhost:8080")
    p.add_argument("--deadline-sec", type=float, default=10.0)
    args = p.parse_args()

    print(f"audio-server preflight against {args.server}")

    client = AudioServerClient(args.server)
    if not wait_for_server(client, deadline_sec=args.deadline_sec):
        print(
            f"  FAIL  audio-server not reachable after {args.deadline_sec}s.\n"
            "        Start it with: audio-server --port 8080 --preload\n"
            "        Or run scripts/start_server.sh"
        )
        return 2
    print("  PASS  socket reachable")

    samples = synth_test_tone()
    sr = 16000

    all_ok = True
    all_ok &= check("/transcribe",
                    lambda: client.transcribe(samples, sr))
    all_ok &= check("/vad",
                    lambda: client.vad(samples, sr))
    all_ok &= check("/diarize",
                    lambda: client.diarize(samples, sr))
    all_ok &= check("/embed-speaker",
                    lambda: client.embed_speaker(samples, sr))

    if not all_ok:
        print(
            "\nOne or more endpoints failed. Common causes:\n"
            "  - audio-server is older than v0.0.2 (missing /diarize, /vad).\n"
            "    Run: brew upgrade speech\n"
            "  - Models not yet downloaded; first call is slow. Run again.\n"
            "  - --preload was not used and a model file is corrupt; check\n"
            "    ~/Library/Caches/qwen3-speech/ for partial downloads."
        )
        return 1

    print("\nAll endpoints OK. Pipeline is ready to run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
