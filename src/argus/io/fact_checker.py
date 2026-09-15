# argus/io/fact_checker.py
"""Ported from simbi `core/fact_checker.py` @ 929d5a7, re-namespaced.

**Path A only.** `_path_b` (the WikiChat LLM route) is deleted with its prompt
import and its `verify_all` routing branch — M7 suspends path B until M13
gives it a real source, because its evidence is unanchorable under I2 (M12).
B's M3 deletions (no `reliability`, no path C) are already absent from the
source this was read at.

Deviations from the source text, each forced by the seam:

- **The constructor takes the constructed NLI object**, not a model name:
  `FactChecker(nli, llm_client)`. Constructing `NLIModel` inside the checker
  bound it to a download; the caller now owns construction
  (`argus.io.nli.NLIModel(model_name)` in production, a fake in tests) and
  `run_session` passes it through.
- **Verdict weights come from the kb context, not a config table.** B's
  `_get_weight` read `config.rubric_items.RUBRIC_BY_ID`, which is not on M7's
  import list; the same 27-row sheet arrives in
  `kb_context.all_rubric_items`, so `verify_all` builds the id→weight map
  from it and threads it through to `_get_weight`. Same lookup semantics:
  unknown or absent rubric_id → weight 1.0.
- **Unsupported claim types refuse loudly instead of falling through.** B's
  routing left any unhandled `claim_type` with no verdict at all — a silent
  drop. `EXTERNAL_FACT`/`INTERNAL_POLICY` have no path B in this port
  (suspended until M13); each now raises `UnsupportedClaimType` rather than
  shipping a fabricated verdict — the `Verdict.checking_path` literal offers
  no honest letter for a routed verdict, and a silent drop is the one
  disposition I2 forbids. The catch-all `else` is what remains of path C:
  9023 M3 retired `ClaimType.ASR_UNCERTAIN` at the pin, so the branch now
  guards against a claim type this enum does not contain rather than naming
  the one it used to.

`HIGH_CONF`/`LOW_CONF` stay module constants, as in B (0.85/0.60). B's
`config["confidence"]` block is dead config nothing reads; these constants
are where the values actually live, so they are supplied the same way.
"""
import asyncio
from argus.types.pipeline import (
    Session, Subquestion, Verdict, EvidenceItem,
    VerdictResult, ClaimType, SessionKBContext
)

HIGH_CONF = 0.85
LOW_CONF = 0.60


class UnsupportedClaimType(ValueError):
    """A question's claim_type has no fact-checking path in this port.

    `EXTERNAL_FACT`/`INTERNAL_POLICY` wait on M13's source (path B is
    suspended; M12 holds the anchoring gate). Raised instead of returning a
    verdict so the refusal is loud: the `checking_path` literal has no honest
    value for "no path ran".
    """


class FactChecker:

    def __init__(self, nli, llm_client):
        self.nli = nli
        self.llm = llm_client

    async def verify_all(
        self,
        questions: list[Subquestion],
        session: Session,
        kb_context: SessionKBContext
    ) -> list[Verdict]:

        weights = {
            r.id: r.weight for r in kb_context.all_rubric_items
        }

        tasks = []
        for q in questions:
            if q.applicability == "NA":
                tasks.append(self._na_verdict(q))
            elif q.claim_type == ClaimType.DIALOGUE_CONSISTENCY:
                tasks.append(self._path_a(q, session, weights))
            elif q.claim_type in [
                ClaimType.EXTERNAL_FACT, ClaimType.INTERNAL_POLICY
            ]:
                raise UnsupportedClaimType(
                    f"{q.id}: claim_type {q.claim_type.value} has no "
                    "fact-checking path in this port — path B is suspended "
                    "until M13 supplies a source whose evidence I2 can "
                    "anchor (M12)."
                )
            else:
                raise UnsupportedClaimType(
                    f"{q.id}: claim_type {q.claim_type.value} has no "
                    "fact-checking path in this port."
                )

        return await asyncio.gather(*tasks)

    async def _path_a(
        self, q: Subquestion, session: Session, weights: dict[int, float]
    ) -> Verdict:
        """路径A：ClaimDecomp NLI方法"""
        turns = session.turns
        scores_pos, scores_neg = [], []

        # Batch NLI scoring
        for turn in turns:
            s_pos = self.nli.score(turn.text, q.hypothesis_pos)
            s_neg = self.nli.score(turn.text, q.hypothesis_neg)
            scores_pos.append((turn.id, turn.text, s_pos))
            scores_neg.append((turn.id, turn.text, s_neg))

        # Max pooling → Top-2 证据
        top_pos = sorted(scores_pos, key=lambda x: x[2], reverse=True)[:2]
        top_neg = sorted(scores_neg, key=lambda x: x[2], reverse=True)[:2]

        best_pos = top_pos[0][2] if top_pos else 0
        best_neg = top_neg[0][2] if top_neg else 0

        if best_pos > best_neg:
            result = VerdictResult.PASS
            confidence = best_pos
            evidence = [
                EvidenceItem(turn_id=tid, text=txt,
                             score=s, supports=True)
                for tid, txt, s in top_pos
            ]
        else:
            result = VerdictResult.FAIL
            confidence = best_neg
            evidence = [
                EvidenceItem(turn_id=tid, text=txt,
                             score=s, supports=False)
                for tid, txt, s in top_neg
            ]

        return self._build_verdict(q, result, confidence, evidence, "A",
                                   weights)

    async def _na_verdict(self, q: Subquestion) -> Verdict:
        """NA项：不计入分母"""
        return Verdict(
            question_id=q.id,
            rubric_id=q.rubric_id,
            result=VerdictResult.NA,
            confidence=1.0,
            score=0.0,
            weight=0.0,  # NA不计入
            evidence=[],
            requires_human_review=False,
            checking_path="A"
        )

    def _build_verdict(
        self, q: Subquestion, result: VerdictResult,
        confidence: float, evidence: list,
        path: str, weights: dict[int, float],
        review_reason: str = None
    ) -> Verdict:

        requires_review = (
            result == VerdictResult.NEI or
            confidence < LOW_CONF or
            q.q_type == "implied" or
            q.is_veto
        )

        reasons = []
        if result == VerdictResult.NEI:
            reasons.append("知识库无对应信息")
        if confidence < LOW_CONF:
            reasons.append(f"置信度低({confidence:.2f})")
        if q.q_type == "implied":
            reasons.append("Implied Q需人工审阅")
        if q.is_veto:
            reasons.append("一票否决项")
        if review_reason:
            reasons.append(review_reason)

        return Verdict(
            question_id=q.id,
            rubric_id=q.rubric_id,
            result=result,
            confidence=confidence,
            score=1.0 if result == VerdictResult.PASS else
                  0.5 if result == VerdictResult.NEI else 0.0,
            weight=self._get_weight(q.rubric_id, weights),
            evidence=evidence,
            requires_human_review=requires_review,
            review_reason="；".join(reasons) if reasons else None,
            checking_path=path
        )

    def _get_weight(
        self, rubric_id: int | None, weights: dict[int, float]
    ) -> float:
        if rubric_id and rubric_id in weights:
            return weights[rubric_id]
        return 1.0
