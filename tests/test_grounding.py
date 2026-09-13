"""Acceptance tests for 9021 M12 — the grounding gate (S3).

M12's Contract: *Deliverable* — S3, the grounding gate. *Binding constraint* —
I2, plus the two grounding fences: the gate imports neither the proposer nor a
matching model. *Acceptance property* — a finding that anchors to nothing real
is routed, never dropped, and quote fidelity is verified against the transcript
rather than asserted.

Every failing direction I2 names has a test here, and each asserts on the
public partition rather than on an internal predicate: a gate whose checks are
right but whose caller drops the result is still a gate that loses findings.

On path B, the plan's advisory is directionally right and specifically wrong —
see the module docstring of `core/grounding.py` for what upstream actually
does, with file:line. The test below only fixes the behaviour: path B routes to
`ungrounded` even when its anchor is perfectly formed.
"""

from __future__ import annotations

import ast
import random
from pathlib import Path

import pytest
from pydantic import ValidationError

from argus.core.grounding import (
    GroundingResult,
    ProposedFinding,
    UngroundedReason,
    ground,
)
from argus.types.anchored import AnchoredEvidence, Span

TRANSCRIPT = (
    "客户: 我的CA锁登录不了。\n"
    "客服: 请问您贵姓？\n"
    "客户: 免贵姓王，我昨天刚办的延期。\n"
    "客服: 好的王先生，我帮您查询一下。\n"
)

EPOCH = "a" * 40
OTHER_EPOCH = "b" * 40

NODES = frozenset({"证书/延期/办理进度", "服务/开场/身份确认"})


def _ev(
    quote: str,
    *,
    start: int | None = None,
    sha: str = EPOCH,
    turn_id: str | None = "t1",
    doc_path: str | None = None,
) -> AnchoredEvidence:
    """An anchored evidence item, spanned by locating `quote` in the transcript.

    `start` is overridable so a test can point a true quote at the wrong place
    (quote mismatch) or past the end (out of range) without hand-counting
    offsets.
    """
    begin = TRANSCRIPT.index(quote) if start is None else start
    return AnchoredEvidence(
        turn_id=turn_id,
        doc_path=doc_path,
        text=quote,
        score=0.91,
        supports=False,
        span=Span(start=begin, end=begin + len(quote)),
        quote=quote,
        intents_sha=sha,
    )


def _finding(
    finding_id: str = "F1",
    *,
    node: str = "证书/延期/办理进度",
    path: str = "A",
    evidence: tuple[AnchoredEvidence, ...] | None = None,
) -> ProposedFinding:
    return ProposedFinding(
        finding_id=finding_id,
        rubric_id=7,
        intents_node=node,
        violation="未确认客户身份即受理业务",
        checking_path=path,
        evidence=(_ev("请问您贵姓？"),) if evidence is None else evidence,
    )


def _ground(*findings: ProposedFinding, epoch: str = EPOCH) -> GroundingResult:
    return ground(
        findings,
        transcript=TRANSCRIPT,
        intents_nodes=NODES,
        epoch=epoch,
    )


# ── the happy direction, so the failing ones mean something ───────────────


def test_a_real_anchor_grounds():
    result = _ground(_finding())

    assert [g.finding.finding_id for g in result.grounded] == ["F1"]
    assert result.ungrounded == ()
    assert result.grounded[0].epoch == EPOCH


# ── I2: anchor or quarantine, one failing direction at a time ─────────────


def test_quote_that_does_not_match_its_span_is_ungrounded():
    """Fidelity is verified against the transcript, not asserted by the record.

    The quote is real and the span is in range; they simply do not describe the
    same text. Only reading the transcript can tell.
    """
    stray = _ev("请问您贵姓？", start=0)
    result = _ground(_finding(evidence=(stray,)))

    assert result.grounded == ()
    assert result.ungrounded[0].reason is UngroundedReason.QUOTE_MISMATCH
    assert "请问您贵姓？" in result.ungrounded[0].detail


def test_span_past_the_end_of_the_transcript_is_ungrounded():
    past_end = _ev("免贵姓王", start=len(TRANSCRIPT) - 2)
    result = _ground(_finding(evidence=(past_end,)))

    assert result.grounded == ()
    assert result.ungrounded[0].reason is UngroundedReason.QUOTE_MISMATCH
    assert "outside" in result.ungrounded[0].detail


def test_intents_node_that_does_not_resolve_is_ungrounded():
    result = _ground(_finding(node="证书/延期/不存在的节点"))

    assert result.grounded == ()
    assert result.ungrounded[0].reason is UngroundedReason.UNKNOWN_NODE
    assert "不存在的节点" in result.ungrounded[0].detail


def test_evidence_pinned_at_another_epoch_is_ungrounded():
    """I4 — one evaluation, one epoch. The anchor here is otherwise perfect."""
    result = _ground(_finding(evidence=(_ev("请问您贵姓？", sha=OTHER_EPOCH),)))

    assert result.grounded == ()
    assert result.ungrounded[0].reason is UngroundedReason.EPOCH_MISMATCH
    assert OTHER_EPOCH in result.ungrounded[0].detail


def test_path_b_is_ungrounded_even_with_a_well_formed_anchor():
    """Upstream's path-B evidence is a model-returned string about a KB
    document, never checked against one and never present in the transcript. An
    anchor on that path would be an anchor nothing produced, so the path is
    quarantined before the anchor is inspected."""
    result = _ground(_finding(path="B"))

    assert result.grounded == ()
    assert result.ungrounded[0].reason is UngroundedReason.UNANCHORABLE_PATH


def test_evidence_about_a_document_is_ungrounded_whatever_the_path_claims():
    """The structural half of the path-B rule: `doc_path` provenance has no
    transcript span, even on a finding labelled path A."""
    result = _ground(
        _finding(evidence=(_ev("请问您贵姓？", turn_id=None, doc_path="证书/延期.md"),))
    )

    assert result.grounded == ()
    assert result.ungrounded[0].reason is UngroundedReason.NOT_FROM_TRANSCRIPT


def test_a_finding_with_no_evidence_is_ungrounded():
    """Upstream's path C carries no evidence at all. It references no span, so
    it cannot be grounded — that is the rule applying, not a special case."""
    result = _ground(_finding(path="C", evidence=()))

    assert result.grounded == ()
    assert result.ungrounded[0].reason is UngroundedReason.NO_EVIDENCE


def test_one_bad_item_ungrounds_the_whole_finding():
    """The gate does not repair. Grounding the good half and discarding the bad
    one is silently dropping evidence, in the module whose job is not to."""
    result = _ground(
        _finding(evidence=(_ev("请问您贵姓？"), _ev("免贵姓王", start=0)))
    )

    assert result.grounded == ()
    assert result.ungrounded[0].reason is UngroundedReason.QUOTE_MISMATCH


# ── routed, never dropped ─────────────────────────────────────────────────


def test_nothing_is_dropped_on_a_mixed_batch():
    """Count in == count out, and every input id appears exactly once out.

    The count alone would pass if the gate swapped a finding for another; the
    id multiset is what says each proposal is still there.
    """
    findings = (
        _finding("F1"),
        _finding("F2", path="B"),
        _finding("F3", node="不存在"),
        _finding("F4", evidence=(_ev("请问您贵姓？", start=0),)),
        _finding("F5", evidence=()),
        _finding("F6", evidence=(_ev("免贵姓王", sha=OTHER_EPOCH),)),
        _finding("F7"),
    )
    result = _ground(*findings)

    assert result.total == len(findings)
    out_ids = [g.finding.finding_id for g in result.grounded]
    out_ids += [u.finding.finding_id for u in result.ungrounded]
    assert sorted(out_ids) == sorted(f.finding_id for f in findings)
    assert out_ids.count("F2") == 1

    assert [g.finding.finding_id for g in result.grounded] == ["F1", "F7"]
    assert {u.finding.finding_id for u in result.ungrounded} == {
        "F3",
        "F4",
        "F5",
        "F6",
        "F2",
    }
    assert all(u.detail for u in result.ungrounded), "an ungrounded finding with no detail is not actionable"


def test_the_partition_is_order_independent():
    """Same proposals in any order, byte-identical record (I5)."""
    findings = [
        _finding("F1"),
        _finding("F2", path="B"),
        _finding("F3", node="不存在"),
        _finding("F4"),
    ]
    baseline = _ground(*findings).model_dump_json()

    shuffled = list(findings)
    random.Random(20260913).shuffle(shuffled)
    assert _ground(*shuffled).model_dump_json() == baseline


def test_an_epoch_that_is_not_a_commit_is_a_caller_defect():
    """I4 — raised, not quarantined. Routing every finding behind a bad pin
    would hide the fault in the pin."""
    with pytest.raises(ValueError, match="git object name"):
        _ground(_finding(), epoch="HEAD")


# ── I7: no proposed number passes through the gate ────────────────────────


def test_a_finding_cannot_carry_a_proposed_score():
    """A digit has no span. The field does not exist and extras are forbidden,
    so a proposer that tries to ship a number gets an error rather than a field
    the gate quietly ignores."""
    with pytest.raises(ValidationError):
        ProposedFinding(
            finding_id="F1",
            rubric_id=7,
            intents_node="证书/延期/办理进度",
            violation="v",
            proposed_score=0.4,
        )


# ── the fences, on the source ─────────────────────────────────────────────

MODEL_CLIENTS = {
    "anthropic",
    "openai",
    "transformers",
    "torch",
    "chromadb",
    "httpx",
    "sentence_transformers",
    "faiss",
    "sklearn",
}


def test_grounding_no_model_import():
    """Fences 2 and 3 — the gate imports neither a model client nor `argus.io`.

    Checked on the source rather than on `sys.modules`, so an import that is
    present but unreached still fails. Redundant with `tests/test_fences.py` on
    purpose: that file skips this check while `core/grounding.py` does not
    exist, and this one is the milestone's own floor.
    """
    source = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "argus"
        / "core"
        / "grounding.py"
    )
    tree = ast.parse(source.read_text(encoding="utf-8"))

    roots: set[str] = set()
    argus_imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
            if node.module.startswith("argus."):
                argus_imports.add(node.module)

    assert MODEL_CLIENTS.isdisjoint(roots), f"model client reached the gate: {roots & MODEL_CLIENTS}"

    for module in argus_imports:
        layer = module.split(".")[1]
        assert layer in {"types", "config", "core"}, f"grounding imports {module}"
