"""The grounding gate (9021 M12) — S3, and the only thing standing between a
proposal and a verdict.

I2: every finding references a real transcript span, exact-quote verified, and
a real INTENTS node at the pinned git-SHA epoch, or it is moved to the
`ungrounded` bucket and routed to a human. Findings are never silently
dropped, so this module partitions rather than filters: `len(grounded) +
len(ungrounded) == len(findings)`, checked at runtime before the result is
returned.

Four things it deliberately refuses to do.

**It does not accept a proposed score.** `ProposedFinding` has no score field
and forbids extras, so `ProposedFinding(..., proposed_score=0.4)` raises at
construction. I7: S3 grounds the violation, the span, and the criterion — a
digit has no span, and there is no code path that carries a model-proposed
number through this gate into a verdict (D8). `AnchoredEvidence.score` rides
along as inherited provenance (upstream's NLI entailment score on path A, the
model's own confidence on path B); the gate neither reads it nor validates it,
and `core/score.py`'s `ScorableFact` has no field that could receive it.

**It does not import the reader that produces the referents.** The resolvable
INTENTS node set arrives as a parameter. `core` may not import `io`
(`docs/conventions/layering.md`, 9021 Q16), and the fence exists precisely so
that a pure stage cannot reach across it for the proposer; M13 builds the
reader on the far side.

**It does not match.** The gate verifies that the proposer's signals resolve
and co-locate — nothing more (D3). An exemplar or case match is a correlated
signal produced in S2; a gate that computed its own would be corroborating
itself, which is why fences 2 and 3 forbid this file from importing either the
proposer or a matching model.

**It does not repair a finding.** If one of a finding's evidence items fails to
anchor, the whole finding is ungrounded — the alternative is to drop the bad
item and ground the remainder, which is silently dropping evidence in the one
module whose job is to never do that.

Path B is unanchorable, and the reason is narrower than the plan says. The
ExecPlan's advisory calls upstream's path-B evidence "model-authored prose
rather than a quotation". The prompt in fact asks for a quotation:
`models/prompts.py:328` requests `"key_evidence": "最关键的证据原文片段"` — the most
critical *verbatim source fragment*. What makes it unanchorable is the rest of
the path:

- the string is whatever came back out of `json.loads` at
  `core/fact_checker.py:98-99`, and nothing upstream ever checks it against a
  source (contrast path A, whose evidence text is `turn.text` copied verbatim
  at `core/fact_checker.py:66-72`);
- it is attributed to `doc_path=kb_context.primary_intent_path`
  (`core/fact_checker.py:114`), which is `matched_paths[0]`
  (`knowledge/intent_retriever.py:110`), while the text the model actually read
  is every primary node concatenated as `"[path]\ncontent[:2000]"`
  (`knowledge/intent_retriever.py:99-103`) and then truncated to 3000
  characters (`core/fact_checker.py:102`). With more than one primary node a
  faithful quote is attributed to the wrong document;
- it is a quote from a knowledge-base document, and what this gate verifies
  against is the transcript. There is no span into a document to check.

So path-B findings route to `ungrounded` unconditionally — before the anchor is
even inspected, since a well-formed anchor on that path would be an anchor
nothing produced. The structural version of the same check is
`NOT_FROM_TRANSCRIPT`: evidence carrying a `doc_path` is not transcript
evidence whatever `checking_path` claims.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from argus.types.anchored import SHA_RE, AnchoredEvidence, resolve_quote


class UngroundedReason(str, Enum):
    """Why a finding could not be anchored. Every one routes to a human (I2)."""

    UNANCHORABLE_PATH = "unanchorable_path"
    NO_EVIDENCE = "no_evidence"
    UNKNOWN_NODE = "unknown_intents_node"
    EPOCH_MISMATCH = "epoch_mismatch"
    NOT_FROM_TRANSCRIPT = "not_from_transcript"
    QUOTE_MISMATCH = "quote_mismatch"


# Upstream's checking paths, by what their evidence is made of:
#   A — `turn.text`, copied verbatim from the transcript (fact_checker.py:66)
#   B — a model-returned string about a knowledge-base document (see above)
#   C — no evidence at all; the verdict is HUMAN_REVIEW (fact_checker.py:124)
# Only A can anchor. C carries nothing to anchor and falls out as NO_EVIDENCE,
# which is the correct answer rather than a special case.
UNANCHORABLE_PATHS: frozenset[str] = frozenset({"B"})


class ProposedFinding(BaseModel):
    """What S2 hands the gate: a claimed violation, its criterion, its referent.

    Note what is *not* here: no score, no confidence, no verdict. `extra` is
    forbidden so that a proposer trying to pass one gets a `ValidationError`
    rather than a field the gate quietly ignores (I7).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    rubric_id: int
    intents_node: str
    violation: str
    checking_path: Literal["A", "B", "C"] = "A"
    evidence: tuple[AnchoredEvidence, ...] = Field(default_factory=tuple)


class GroundedFinding(BaseModel):
    """A finding that cleared every I2 check, with the epoch it cleared at.

    The proposal is carried whole rather than flattened: the gate's output is
    the input plus a judgement, and a downstream stage that wants the original
    should not have to reconstruct it.
    """

    model_config = ConfigDict(frozen=True)

    finding: ProposedFinding
    epoch: str


class UngroundedFinding(BaseModel):
    """A finding that anchors to nothing real — routed, not dropped.

    `detail` carries the specific failure (which span, which node, whose
    message) because a human is the next reader, and "ungrounded" alone is not
    actionable.
    """

    model_config = ConfigDict(frozen=True)

    finding: ProposedFinding
    reason: UngroundedReason
    detail: str


class GroundingResult(BaseModel):
    """The partition. Nothing left, nothing arrived: `total == len(findings)`."""

    model_config = ConfigDict(frozen=True)

    epoch: str
    grounded: tuple[GroundedFinding, ...] = Field(default_factory=tuple)
    ungrounded: tuple[UngroundedFinding, ...] = Field(default_factory=tuple)

    @property
    def total(self) -> int:
        return len(self.grounded) + len(self.ungrounded)


def _failure(
    finding: ProposedFinding,
    transcript: str,
    intents_nodes: Collection[str],
    epoch: str,
) -> tuple[UngroundedReason, str] | None:
    """The first reason this finding cannot be grounded, or `None`.

    The order is categorical-before-specific: a path-B finding is unanchorable
    whatever its anchor looks like, so reporting a quote mismatch on it would
    name a defect that is not the one to fix.
    """
    if finding.checking_path in UNANCHORABLE_PATHS:
        return (
            UngroundedReason.UNANCHORABLE_PATH,
            f"checking path {finding.checking_path} produces evidence about a "
            f"knowledge-base document, unverified against it and not present "
            f"in the transcript; there is no span to check",
        )

    if not finding.evidence:
        return (
            UngroundedReason.NO_EVIDENCE,
            "finding carries no evidence, so it references no transcript span",
        )

    if finding.intents_node not in intents_nodes:
        return (
            UngroundedReason.UNKNOWN_NODE,
            f"INTENTS node {finding.intents_node!r} does not resolve at epoch "
            f"{epoch}",
        )

    for item in finding.evidence:
        if item.intents_sha != epoch:
            # I4: one evaluation, one epoch. Evidence resolved against some
            # other tree says nothing about the referents of this one.
            return (
                UngroundedReason.EPOCH_MISMATCH,
                f"evidence pinned at {item.intents_sha} but this evaluation is "
                f"pinned at {epoch}",
            )

        if item.turn_id is None or item.doc_path is not None:
            return (
                UngroundedReason.NOT_FROM_TRANSCRIPT,
                f"evidence provenance is doc_path={item.doc_path!r}, "
                f"turn_id={item.turn_id!r}; a span into the transcript needs a "
                f"turn it came from",
            )

        try:
            resolve_quote(item, transcript)
        except ValueError as exc:
            # M6's check, run rather than trusted: quote fidelity is verified
            # against the transcript, never asserted by the record.
            return (UngroundedReason.QUOTE_MISMATCH, str(exc))

    return None


def ground(
    findings: Sequence[ProposedFinding],
    *,
    transcript: str,
    intents_nodes: Collection[str],
    epoch: str,
) -> GroundingResult:
    """Partition proposed findings into grounded and ungrounded. Pure.

    No clock, no RNG, no model, no I/O: the transcript and the resolvable node
    set are arguments, so the same inputs re-derive the same partition forever
    (I4, I5). Both output sequences are sorted by `finding_id`, so a caller
    that shuffles its proposals gets a byte-identical record.

    Raises `ValueError` if `epoch` is not a 40-character git object name. That
    is a caller defect rather than a property of any finding — an epoch that is
    not a commit pins nothing, and quarantining every finding behind it would
    hide the real fault (I4).
    """
    if not SHA_RE.match(epoch):
        raise ValueError(
            f"epoch {epoch!r} is not a 40-character git object name; an "
            f"evaluation pins the INTENTS tree at a single commit (I4)"
        )

    nodes = frozenset(intents_nodes)
    grounded: list[GroundedFinding] = []
    ungrounded: list[UngroundedFinding] = []

    for finding in findings:
        failure = _failure(finding, transcript, nodes, epoch)
        if failure is None:
            grounded.append(GroundedFinding(finding=finding, epoch=epoch))
        else:
            reason, detail = failure
            ungrounded.append(
                UngroundedFinding(finding=finding, reason=reason, detail=detail)
            )

    if len(grounded) + len(ungrounded) != len(findings):
        # I2's other half. Cheap, and the one bug in this module that would be
        # invisible downstream: a dropped finding leaves no record anywhere.
        raise AssertionError(
            f"grounding lost findings: {len(findings)} in, "
            f"{len(grounded) + len(ungrounded)} out"
        )

    return GroundingResult(
        epoch=epoch,
        grounded=tuple(sorted(grounded, key=lambda g: g.finding.finding_id)),
        ungrounded=tuple(sorted(ungrounded, key=lambda u: u.finding.finding_id)),
    )
