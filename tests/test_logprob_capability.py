"""Acceptance tests for 9020 M0 — stack-agnostic logprob capability probe.

M0 answers B2.a: does the serving stack expose top-k logprobs at a token
position, at what k, and by which path. This is a property of the runtime API,
not of weights or hardware, so it is answerable against whatever stack D21
settles on (llama.cpp here). The capacity half — throughput on the production
model — is M6, in tests/test_capacity_measurement.py; it is NOT checked here.

A missing artifact FAILS rather than skips: M0 cannot flip on an empty promise.

See docs/exec-plans/active/9020-continuous-proposer-and-provenance-separation.md
"""

from __future__ import annotations

import json
import py_compile
import re
from datetime import datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_DIR = REPO_ROOT / "docs" / "experiments" / "9020-logprob-capability"
ARTIFACT = EXPERIMENT_DIR / "output.json"
RUN_SCRIPT = EXPERIMENT_DIR / "run.py"

ISO8601 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")

MISSING_ARTIFACT = (
    f"No measurement artifact at {ARTIFACT.relative_to(REPO_ROOT)}.\n"
    f"Run {RUN_SCRIPT.relative_to(REPO_ROOT)} to produce it. Do not hand-author "
    f"it — the capability answer must come from a real probe of the stack."
)


def load_artifact() -> dict:
    if not ARTIFACT.exists():
        pytest.fail(MISSING_ARTIFACT)
    try:
        return json.loads(ARTIFACT.read_text())
    except json.JSONDecodeError as exc:
        pytest.fail(f"{ARTIFACT.relative_to(REPO_ROOT)} is not valid JSON: {exc}")


def _positive_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def test_capability_record_is_complete():
    """The artifact declares top-k availability, the G used, and its provenance."""
    record = load_artifact()
    failures: list[str] = []

    if "topk_available" not in record:
        failures.append("missing 'topk_available' — B2.a is what M0 resolves")
    elif not isinstance(record["topk_available"], bool):
        failures.append("'topk_available' must be a bool, not a guess or a string")
    elif record["topk_available"] and not _positive_number(record.get("topk_ceiling")):
        failures.append(
            "'topk_available' is true but 'topk_ceiling' is not a positive number"
        )

    if "g_used" not in record:
        failures.append("missing 'g_used'")
    elif not _positive_number(record["g_used"]):
        failures.append("'g_used' must be a positive number")

    stack = record.get("stack")
    if not isinstance(stack, dict):
        failures.append("missing 'stack' object — a capability is not portable across stacks")
    else:
        for field in ("runtime", "model_id"):
            if not str(stack.get(field, "")).strip():
                failures.append(f"stack.{field} is empty")

    measured_at = record.get("measured_at", "")
    if not ISO8601.match(str(measured_at)):
        failures.append(f"'measured_at' must be ISO-8601 UTC, got {measured_at!r}")
    else:
        stamped = datetime.strptime(
            str(measured_at).split(".")[0], "%Y-%m-%dT%H:%M:%SZ"
        )
        if stamped > datetime.utcnow():
            failures.append(f"'measured_at' {measured_at} is in the future")

    assert not failures, "Incomplete capability record:\n  - " + "\n  - ".join(failures)


def test_g_used_within_measured_ceiling():
    """G never exceeds the k the stack was observed to expose."""
    record = load_artifact()
    g_used = record.get("g_used")
    assert _positive_number(g_used), f"'g_used' must be a positive number, got {g_used!r}"

    if not record.get("topk_available"):
        assert g_used == 1, (
            f"no top-k exposure, so the proposer falls back to argmax and g_used "
            f"must be 1, not {g_used}. D19 reduces to argmax; M2 is rewritten."
        )
        return

    ceiling = record.get("topk_ceiling")
    assert _positive_number(ceiling), f"'topk_available' true but ceiling {ceiling!r}"
    assert g_used <= ceiling, (
        f"g_used={g_used} exceeds measured ceiling {ceiling}; extraction would "
        f"silently truncate the distribution the expectation is taken over."
    )
    assert g_used >= 2, (
        f"g_used={g_used} with top-k available: a one-point scale is argmax in "
        f"a continuous costume."
    )


def test_expectation_is_computable():
    """The artifact shows D19's continuous score is real: an expectation over the
    distribution, distinct from the argmax. This is the whole reason to adopt a
    finer proposed score.
    """
    record = load_artifact()
    demo = record.get("expectation_demo")
    assert isinstance(demo, dict), "missing 'expectation_demo' block"
    assert "error" not in demo, f"expectation_demo recorded an error: {demo.get('error')}"
    for field in ("expectation_index", "argmax_index", "differs_from_argmax"):
        assert field in demo, f"expectation_demo missing '{field}'"
    assert isinstance(demo["differs_from_argmax"], bool)
    # On a real distribution the expectation and argmax differ; that difference
    # is exactly the resolution D19 buys over an argmax score.
    assert demo["differs_from_argmax"] is True, (
        "expectation equals argmax — either the probe is degenerate or the scale "
        "is too coarse to distinguish them; D19 buys nothing in that case."
    )


def test_run_script_exists_and_compiles():
    assert RUN_SCRIPT.exists(), (
        f"Missing {RUN_SCRIPT.relative_to(REPO_ROOT)} — the artifact must be "
        f"reproducible, not hand-authored."
    )
    try:
        py_compile.compile(str(RUN_SCRIPT), doraise=True)
    except py_compile.PyCompileError as exc:
        pytest.fail(f"{RUN_SCRIPT.relative_to(REPO_ROOT)} does not compile: {exc}")
