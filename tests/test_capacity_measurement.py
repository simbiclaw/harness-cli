"""Acceptance tests for 9020 M6 — pinned capacity measurement.

M6 is the capacity half split from the original M0. Where M0 asks a
weight-independent API question, M6 asks a hardware- and model-pinned one:
what is the real decode throughput, per call type, for the PRODUCTION model on
the target serving hardware. The same run.py harness produces the numbers, but
only a run with `--synthetic` omitted, against the pinned model, yields a
representative artifact.

These tests fail on a synthetic run BY DESIGN: that is what keeps M6 honestly
pending until a real measurement exists. A missing artifact also fails.

See docs/exec-plans/active/9020-continuous-proposer-and-provenance-separation.md
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = REPO_ROOT / "docs" / "experiments" / "9020-logprob-capability" / "output.json"

REQUIRED_CALL_TYPES = ("hunt", "score")

MISSING = (
    f"No artifact at {ARTIFACT.relative_to(REPO_ROOT)}. M6 needs a throughput "
    f"run against the pinned production model on target hardware."
)


def load_artifact() -> dict:
    if not ARTIFACT.exists():
        pytest.fail(MISSING)
    return json.loads(ARTIFACT.read_text())


def _positive_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def test_capacity_is_representative():
    """The throughput numbers must come from the production model, not a synthetic one.

    A synthetic-weight run sets throughput_representative=false with a caveat;
    that artifact must NOT satisfy M6. This is the gate that keeps the capacity
    milestone from flipping on a decode rate that does not represent the model
    that will actually serve.
    """
    record = load_artifact()
    representative = record.get("throughput_representative")
    assert representative is True, (
        f"throughput_representative is {representative!r}. M6 requires a run "
        f"against the pinned production model (drop --synthetic). The current "
        f"artifact is a capability probe on a synthetic model; its throughput "
        f"does not represent production. Caveat on record: "
        f"{record.get('throughput_caveat')!r}."
    )
    assert record.get("throughput_caveat") in (None, ""), (
        f"a representative measurement carries no caveat, but one is present: "
        f"{record.get('throughput_caveat')!r}"
    )


def test_per_call_type_throughput_present():
    record = load_artifact()
    throughput = record.get("throughput")
    assert isinstance(throughput, dict), "missing 'throughput' object"
    failures: list[str] = []
    for call_type in REQUIRED_CALL_TYPES:
        entry = throughput.get(call_type)
        if not isinstance(entry, dict):
            failures.append(f"missing throughput for '{call_type}'")
            continue
        if not _positive_number(entry.get("single_stream_tok_s")):
            failures.append(f"{call_type}.single_stream_tok_s must be positive")
        samples = entry.get("samples")
        if not (isinstance(samples, int) and samples >= 2):
            failures.append(f"{call_type}.samples must be >= 2 (one run is an anecdote)")
        if "batched_tok_s" not in entry:
            failures.append(f"{call_type} must carry 'batched_tok_s' (a number, or null with a reason)")
        elif entry["batched_tok_s"] is None:
            if not str(entry.get("batched_unavailable_reason", "")).strip():
                failures.append(f"{call_type}.batched_tok_s is null without a reason")
        elif not _positive_number(entry["batched_tok_s"]):
            failures.append(f"{call_type}.batched_tok_s must be a positive number or null")
    assert not failures, "Capacity throughput incomplete:\n  - " + "\n  - ".join(failures)


def test_stack_and_model_pinned():
    """A representative measurement names the model that produced it."""
    record = load_artifact()
    stack = record.get("stack", {})
    failures: list[str] = []
    if stack.get("synthetic_weights") is not False:
        failures.append("stack.synthetic_weights must be false for a pinned measurement")
    if not str(stack.get("model_id", "")).strip():
        failures.append("stack.model_id is empty")
    if str(stack.get("model_hash", "")).strip() in ("", "unrecorded"):
        failures.append("stack.model_hash must be a real pinned hash, not 'unrecorded'")
    assert not failures, "Model not pinned:\n  - " + "\n  - ".join(failures)
