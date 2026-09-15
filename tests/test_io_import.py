# tests/test_io_import.py
"""9024 M7 — the port: B's proposal half lives in `io/`, behaviour-identical.

The contract is M7's data-flow table, not a module list: seven modules move
re-namespaced (`llm_client`, `nli`, `prompts`, `fact_checker` path A only,
`atomizer`, `question_generator`, `qa_agent` rewired), the arguments they used
to take from dropped modules are supplied — `Session` from the call record
(`argus.io.call_record`), `SessionKBContext` from a test-owned stub (the
baseline's rubric items as data) until 9025's Provider lands — and the orchestrator's ingest stages are gone. What must be true:
the port produces the **same output as 9023 M4's baseline on the same
transcript** (captured from simbi into `tests/fixtures/io_import_baseline.json`
with the same fakes), and nothing in `io/` re-decides a producer's.

The fakes (`tests/fakes.py`) mirror simbi's reply-for-reply, so both sides of
the comparison are fed identical answers.

The interface the tests pin, per the data-flow table and the 2026-09-15 Q29
ruling (roles must be established or the call is not processed):

    session    = call_record.build_session(record)   # declines if roles absent
    kb_context = <test-owned stub: the baseline's rubric items as data>
    report     = qa_agent.run_session(session, kb_context=..., llm_client=..., nli_model=..., nli=...)
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GOLDEN = REPO / "tests" / "fixtures" / "io_import_baseline.json"
RECORD = REPO / "tests" / "fixtures" / "call_record_baseline.json"

PORTED_MODULES = (
    "argus.io.llm_client",
    "argus.io.nli",
    "argus.io.prompts",
    "argus.io.fact_checker",
    "argus.io.atomizer",
    "argus.io.question_generator",
    "argus.io.qa_agent",
)


def test_the_seven_ported_modules_live_in_io():
    """The import list is the port's existence claim."""
    for name in PORTED_MODULES:
        importlib.import_module(name)


def test_no_producer_logic_in_io():
    """No ported module re-decides what a producer decides.

    M7's four prohibitions, structural: no role inference from transcript text
    (the keyword lists and LLM role-detection 9023 M2 deleted), no call-level
    intent assignment (audio2tree's D5 protocol), no knowledge-tree traversal
    (M13's Provider is the sole read surface), no ASR-text parsing of call
    records (the producer's `calls/*.json` already carries the structure).
    Scoped to the seven ported modules — 9020's residents (`local_proposer`
    etc.) are not this milestone's imports.
    """
    io_dir = REPO / "src" / "argus" / "io"
    for name in PORTED_MODULES:
        filename = name.split("io.", 1)[1] + ".py"
        path = io_dir / filename
        assert path.exists(), f"missing ported module: io/{filename}"
        text = path.read_text(encoding="utf-8")

    forbidden = (
        "AGENT_INDICATORS", "AGENT_OPENING", "_verify_roles",
        "should_swap", "ROLE_SWAPPED", "role_swap",
        "asr_quality", "ASRQuality", "_parse_raw",
        "bottom_up",            # call-level intent assignment
        "rglob",                # knowledge-tree traversal
    )
    for name in PORTED_MODULES:
        filename = name.split("io.", 1)[1] + ".py"
        text = (io_dir / filename).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"io/{filename} re-decides a producer's: {token!r}"


def test_pipeline_runs_from_io_matches_the_m4_baseline():
    """The port is behaviour-identical: same input, same output as M4's baseline.

    The input is the synthetic call record encoding `TRANSCRIPT_NORMAL` (the
    golden's own input), with speaker roles established. The kb context is the
    stub the sequencing note allows until 9025 lands. Every field of the
    report is compared — the port does not get to differ quietly.
    """
    from tests.fakes import FakeLLM, FakeNLI

    from argus.io import call_record, qa_agent
    from argus.types.pipeline import RubricItem, SessionKBContext

    record = json.loads(RECORD.read_text(encoding="utf-8"))
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["report"]
    items_data = json.loads(
        (REPO / "tests" / "fixtures" / "rubric_items_baseline.json").read_text(encoding="utf-8")
    )["items"]

    # The kb stub the sequencing note allows: the 25-item rubric the baseline
    # was captured with, as data, until 9026's compiled nodes and 9025's
    # Provider replace this fixture with the real referent.
    items = [RubricItem.model_validate(i) for i in items_data]
    kb_context = SessionKBContext(
        all_rubric_items=items, applicable_rubrics=items
    )

    session = call_record.build_session(record)
    report = qa_agent.run_session(
        session,
        kb_context=kb_context,
        llm_client=FakeLLM(),
        nli_model="cross-encoder/nli-deberta-v3-large",
        nli=FakeNLI(),
    )

    assert report.model_dump() == golden
