"""Acceptance tests for 9010 M0 — logprob capability spike and capacity measurement.

M0's deliverable is a committed measurement artifact at
`docs/experiments/9010-logprob-capability/output.json`, produced by running
`run.py` on the target serving box (Apple Silicon, MLX). These tests validate
that the artifact is complete and internally consistent. They do not re-run the
measurement — the measurement needs hardware no CI runner has.

A missing artifact FAILS rather than skips. M0's checkbox cannot flip until the
measurement has actually been taken, and a skip would let it flip on an empty
promise. The failure message names the script that produces the artifact.

Two invariants carry the milestone (see the plan's M0 Acceptance Test line):

- `test_capability_record_is_complete` — the artifact declares `topk_available`,
  `g_used`, and per-call-type throughput; a record missing any of the three fails.
- `test_g_used_within_measured_ceiling` — the recorded `g_used` never exceeds the
  measured top-k ceiling.

See docs/exec-plans/active/9010-continuous-proposer-and-provenance-separation.md
"""

from __future__ import annotations

import json
import py_compile
import re
from datetime import datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_DIR = REPO_ROOT / "docs" / "experiments" / "9010-logprob-capability"
ARTIFACT = EXPERIMENT_DIR / "output.json"
RUN_SCRIPT = EXPERIMENT_DIR / "run.py"

# Call types the plan names: a long-generation hunt pass and a single-token
# score pass. They are distinct call types with distinct configs (D21), so
# throughput is recorded per type rather than as one number.
REQUIRED_CALL_TYPES = ("hunt", "score")

ISO8601 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")

MISSING_ARTIFACT = (
    f"No measurement artifact at {ARTIFACT.relative_to(REPO_ROOT)}.\n"
    f"M0 is a measurement milestone: run "
    f"{RUN_SCRIPT.relative_to(REPO_ROOT)} on the target serving box and commit "
    f"the artifact it writes. Do not hand-author this file — the plan's whole "
    f"point is that the capacity arithmetic is an estimate and must be replaced "
    f"by measurement before the serving shape is fixed."
)


def load_artifact() -> dict:
    """Return the parsed measurement artifact, or fail with a pointer to run.py."""
    if not ARTIFACT.exists():
        pytest.fail(MISSING_ARTIFACT)
    try:
        return json.loads(ARTIFACT.read_text())
    except json.JSONDecodeError as exc:
        pytest.fail(f"{ARTIFACT.relative_to(REPO_ROOT)} is not valid JSON: {exc}")


def _positive_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def test_capability_record_is_complete():
    """The artifact declares top-k availability, the G used, and throughput per call type."""
    record = load_artifact()
    failures: list[str] = []

    # --- Top-k exposure (resolves carried-open B2.a) ---
    if "topk_available" not in record:
        failures.append("missing 'topk_available' — B2.a is what M0 exists to resolve")
    elif not isinstance(record["topk_available"], bool):
        failures.append("'topk_available' must be a bool, not a guess or a string")
    elif record["topk_available"] and not _positive_number(record.get("topk_ceiling")):
        failures.append(
            "'topk_available' is true but 'topk_ceiling' is not a positive number — "
            "record the k that was actually observed"
        )

    # --- G actually used ---
    if "g_used" not in record:
        failures.append("missing 'g_used'")
    elif not _positive_number(record["g_used"]):
        failures.append("'g_used' must be a positive number")

    # --- Per-call-type throughput ---
    throughput = record.get("throughput")
    if not isinstance(throughput, dict):
        failures.append("missing 'throughput' object")
    else:
        for call_type in REQUIRED_CALL_TYPES:
            entry = throughput.get(call_type)
            if not isinstance(entry, dict):
                failures.append(f"missing throughput for call type '{call_type}'")
                continue
            if not _positive_number(entry.get("single_stream_tok_s")):
                failures.append(
                    f"throughput.{call_type}.single_stream_tok_s must be a positive number"
                )
            if not _positive_number(entry.get("output_tokens")):
                failures.append(
                    f"throughput.{call_type}.output_tokens must be a positive number"
                )
            if not _positive_number(entry.get("samples")):
                failures.append(
                    f"throughput.{call_type}.samples must be a positive number — "
                    f"one timed run is an anecdote"
                )
            # Q4 (serving shape) turns on the batched number, so its absence
            # must be explicit rather than silent.
            if "batched_tok_s" not in entry:
                failures.append(
                    f"throughput.{call_type} must carry 'batched_tok_s' (null is "
                    f"allowed with a reason) — Q4 turns on this measurement"
                )
            elif entry["batched_tok_s"] is None:
                if not str(entry.get("batched_unavailable_reason", "")).strip():
                    failures.append(
                        f"throughput.{call_type}.batched_tok_s is null without a "
                        f"'batched_unavailable_reason'"
                    )
            elif not _positive_number(entry["batched_tok_s"]):
                failures.append(
                    f"throughput.{call_type}.batched_tok_s must be a positive number or null"
                )

    # --- Provenance: a G is uninterpretable without the stack that produced it ---
    stack = record.get("stack")
    if not isinstance(stack, dict):
        failures.append("missing 'stack' object — G is not portable across stacks")
    else:
        for field in ("runtime", "model_id"):
            if not str(stack.get(field, "")).strip():
                failures.append(f"stack.{field} is empty")

    measured_at = record.get("measured_at", "")
    if not ISO8601.match(str(measured_at)):
        failures.append(
            f"'measured_at' must be an ISO-8601 UTC timestamp, got {measured_at!r}"
        )
    else:
        # A measurement dated in the future is a hand-authored artifact.
        stamped = datetime.strptime(
            str(measured_at).split(".")[0], "%Y-%m-%dT%H:%M:%SZ"
        )
        if stamped > datetime.utcnow():
            failures.append(f"'measured_at' {measured_at} is in the future")

    assert not failures, "Incomplete capability record:\n  - " + "\n  - ".join(failures)


def test_g_used_within_measured_ceiling():
    """G never exceeds the k the stack was observed to expose.

    The declared fallback is not "give up": set G to whatever k the stack
    exposes and record it, so the number stays interpretable across a
    capability change. If no top-k is exposed at all, D19 reduces to argmax
    scores — g_used == 1 — and only D20 survives.
    """
    record = load_artifact()
    g_used = record.get("g_used")
    assert _positive_number(g_used), f"'g_used' must be a positive number, got {g_used!r}"

    if not record.get("topk_available"):
        assert g_used == 1, (
            f"no top-k exposure was observed, so the proposer falls back to argmax "
            f"scores and g_used must be 1, not {g_used}. D19 reduces to argmax and "
            f"M2 is rewritten before it starts."
        )
        return

    ceiling = record.get("topk_ceiling")
    assert _positive_number(ceiling), (
        f"'topk_available' is true but 'topk_ceiling' is {ceiling!r}"
    )
    assert g_used <= ceiling, (
        f"g_used={g_used} exceeds the measured top-k ceiling {ceiling}. "
        f"Extraction would silently truncate the distribution the expectation "
        f"is computed over."
    )
    assert g_used >= 2, (
        f"g_used={g_used} with top-k available: a scale of one point is argmax "
        f"wearing a continuous name."
    )


def test_run_script_exists_and_compiles():
    """The measurement harness is committed and syntactically runnable.

    The artifact is only trustworthy if the script that produced it is in the
    repo and can be re-run to reproduce it.
    """
    assert RUN_SCRIPT.exists(), (
        f"Missing {RUN_SCRIPT.relative_to(REPO_ROOT)} — the artifact must be "
        f"reproducible, not hand-authored."
    )
    try:
        py_compile.compile(str(RUN_SCRIPT), doraise=True)
    except py_compile.PyCompileError as exc:
        pytest.fail(f"{RUN_SCRIPT.relative_to(REPO_ROOT)} does not compile: {exc}")
