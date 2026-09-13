"""The replay record (9021 M21) — what must be stored for a verdict to survive.

I5: the stored FindingGraph plus `intents_sha` plus the rubric version
re-derive the identical EvaluationResult forever, and the `replay_hash` is a
function of grounded inputs **and anchored precedents** only — never of a
proposed score.

Upstream stores none of this. `core/aggregator.py` returns a `QAReport` and the
verdicts, questions and evidence that produced it are whatever was live in
memory at the time; nothing is written, so no report upstream has ever produced
can be re-derived. That is the gap this closes.

Three decisions.

**The hash takes an explicit allowlist, not the record.** Hashing
`record.model_dump_json()` would be shorter and would silently absorb every
field anyone adds later — including a proposed score, which is precisely the
value I5 names as forbidden. `AnchoredEvidence.score` is already such a field:
it rides along as inherited provenance (upstream's NLI entailment score on path
A, the model's own confidence on path B) and it must not move the hash. So
`_hashable()` names every field it takes, and a new field is excluded until
someone adds it deliberately.

**Precedents are in the hash.** An earlier revision of this milestone said
"grounded inputs only", which would leave the hash unable to detect the change
it exists to detect: two runs citing different precedents would hash
identically while shipping different numbers. The Contract quotes I5 rather
than paraphrasing it for this reason.

**Large inputs are carried by digest, and supplied at replay.** The transcript
is a grounded input — every span indexes into it — but storing it whole in
every record duplicates it without making replay any more verifiable. The
record stores its SHA-256 and `rederive()` refuses a transcript that does not
match. A digest that must agree is a stronger check than a copy nobody
compares.

**Not done here: persistence.** The Contract's deliverable is a stored record,
and the record is what this module defines. Where it goes on disk is not
settled: the manifest path needs an exact-filename glob in
`INTENTS/_meta/ownership.yaml`, assigned to exactly one producer before the
file may exist, and in this environment `INTENTS` is a dangling symlink so the
ledger cannot be read, let alone extended. An on-disk format is also Tier C
(`docs/conventions/ask-threshold.md`) and needs a steering entry. The writer
belongs in `io/` and is M22's, behind both gates.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from argus.core.adjust import AdjustedScore, Precedent, adjust
from argus.core.grounding import GroundedFinding
from argus.core.score import Rubric, ScorableFact, score
from argus.types.anchored import SHA_RE

SCHEMA_VERSION = "1.0.0"


def transcript_digest(transcript: str) -> str:
    """SHA-256 of the transcript as UTF-8. Named so the record and the check agree."""
    return hashlib.sha256(transcript.encode("utf-8")).hexdigest()


class ReplayMismatch(ValueError):
    """A replay input disagrees with what the record was derived from.

    Raised rather than returning a differing result: a replay that silently
    re-derives against a different transcript or a different rubric version
    produces a number that looks authoritative and is not.
    """


class ReplayRecord(BaseModel):
    """Everything the verdict rests on, and deliberately nothing else.

    `findings` is the FindingGraph — the grounded findings, carried for
    provenance and for re-running the gate. `facts` is what actually reached
    the arithmetic. Both are stored because they answer different questions:
    the graph says what was believed and why, the facts say what was counted.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    intents_sha: str
    rubric_version: str
    transcript_sha256: str

    findings: tuple[GroundedFinding, ...] = Field(default_factory=tuple)
    facts: tuple[ScorableFact, ...] = Field(default_factory=tuple)
    precedents: tuple[Precedent, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _epoch_and_digest_are_real(self) -> ReplayRecord:
        if not SHA_RE.match(self.intents_sha):
            raise ValueError(
                f"intents_sha {self.intents_sha!r} is not a 40-character git object "
                f"name; a record that does not pin an epoch cannot replay (I4)"
            )
        if len(self.transcript_sha256) != 64 or not set(self.transcript_sha256) <= set(
            "0123456789abcdef"
        ):
            raise ValueError(
                f"transcript_sha256 {self.transcript_sha256!r} is not a SHA-256 digest"
            )
        for precedent in self.precedents:
            if precedent.intents_sha != self.intents_sha:
                raise ValueError(
                    f"precedent {precedent.precedent_id} is anchored at "
                    f"{precedent.intents_sha} but this record pins "
                    f"{self.intents_sha}; one evaluation, one epoch (I4)"
                )
        return self


def _hashable(record: ReplayRecord) -> dict:
    """The hash's input, field by named field.

    Every key here is a grounded input or an anchored precedent. Nothing is
    included by virtue of being on the record, which is what keeps
    `AnchoredEvidence.score` — a model-proposed number — out of the hash
    without anyone having to remember to exclude it.

    `violation` and `intents_node` are in: they are what the finding claims and
    what it claims it about, and two runs disagreeing on either are not the
    same evaluation. `detail` strings and the schema version are out: prose
    about a failure is not an input to the arithmetic.
    """
    return {
        "intents_sha": record.intents_sha,
        "rubric_version": record.rubric_version,
        "transcript_sha256": record.transcript_sha256,
        "findings": sorted(
            (
                {
                    "finding_id": g.finding.finding_id,
                    "rubric_id": g.finding.rubric_id,
                    "intents_node": g.finding.intents_node,
                    "violation": g.finding.violation,
                    "checking_path": g.finding.checking_path,
                    "evidence": [
                        {
                            "turn_id": e.turn_id,
                            "doc_path": e.doc_path,
                            "span": [e.span.start, e.span.end],
                            "quote": e.quote,
                            "intents_sha": e.intents_sha,
                        }
                        for e in g.finding.evidence
                    ],
                }
                for g in record.findings
            ),
            key=lambda d: d["finding_id"],
        ),
        "facts": sorted(
            (
                {
                    "finding_id": f.finding_id,
                    "rubric_id": f.rubric_id,
                    "outcome": f.outcome.value,
                }
                for f in record.facts
            ),
            key=lambda d: (d["rubric_id"], d["finding_id"]),
        ),
        "precedents": sorted(
            (
                {
                    "precedent_id": p.precedent_id,
                    "prior_evaluation_id": p.prior_evaluation_id,
                    "rubric_id": p.rubric_id,
                    "ruled_outcome": p.ruled_outcome.value,
                    "intents_sha": p.intents_sha,
                }
                for p in record.precedents
            ),
            key=lambda d: d["precedent_id"],
        ),
    }


def replay_hash(record: ReplayRecord) -> str:
    """A stable digest of the grounded inputs and the anchored precedents.

    Sorted and separator-pinned so the digest depends on the content and not on
    how the record happened to be ordered or serialized — a hash that changes
    when a list is shuffled reports a difference that is not one.
    """
    payload = json.dumps(
        _hashable(record),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def rederive(
    record: ReplayRecord,
    rubric: Rubric,
    *,
    transcript: str | None = None,
) -> AdjustedScore:
    """Re-derive the verdict from the record. Pure, and the same two stages.

    `score` then `adjust`, exactly as the live pipeline runs them — not a
    re-implementation, which is how a replay path drifts from the path it is
    supposed to reproduce.

    `transcript` is optional because the arithmetic does not read it; supplying
    it checks the digest, and a caller replaying a stored verdict against a
    transcript should.
    """
    if rubric.version != record.rubric_version:
        raise ReplayMismatch(
            f"record was derived against rubric {record.rubric_version}, not "
            f"{rubric.version}; the same findings score differently under a "
            f"different sheet"
        )
    if transcript is not None:
        actual = transcript_digest(transcript)
        if actual != record.transcript_sha256:
            raise ReplayMismatch(
                f"transcript digest {actual} does not match the record's "
                f"{record.transcript_sha256}; the spans index into a different text"
            )

    return adjust(score(record.facts, rubric), record.precedents)


def record_for(
    *,
    intents_sha: str,
    rubric_version: str,
    transcript: str,
    findings: Sequence[GroundedFinding],
    facts: Sequence[ScorableFact],
    precedents: Sequence[Precedent] = (),
) -> ReplayRecord:
    """Build a record, digesting the transcript rather than making the caller do it.

    Keyword-only: the arguments are six values of three types, and a positional
    call that swapped `intents_sha` for a transcript digest would construct
    cleanly and replay wrong.
    """
    return ReplayRecord(
        intents_sha=intents_sha,
        rubric_version=rubric_version,
        transcript_sha256=transcript_digest(transcript),
        findings=tuple(findings),
        facts=tuple(facts),
        precedents=tuple(precedents),
    )
