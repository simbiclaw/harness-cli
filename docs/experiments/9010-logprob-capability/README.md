# 9010-logprob-capability

This experiment tested whether the MLX serving stack exposes top-k logprobs at a chosen token position with k ≥ 20, and what a hunt pass and a score pass actually cost on the target box. **The answer is: not yet known — the measurement has not been run.** The harness is committed and ready; it requires the target hardware, which neither CI nor the authoring session has.

## Question

Two questions, both contingencies for the rest of plan 9010.

**B2.a — top-k exposure.** D19 computes `proposed_score` as the expectation over the distribution of scoring-token logits on a single-token letter scale at G=20. That requires the stack to return at least 20 ranked logprobs at the scoring position. Whether it does is unverified. The declared fallback is not "give up": set G to whatever k the stack exposes and record G per evaluation, so the number stays interpretable across a capability change. If no top-k is exposed at all, D19 reduces to argmax scores, only D20 survives, and M2 is rewritten before it starts.

**Capacity.** The patch's arithmetic — 3000 calls/day ≈ 28.8 s/call at 24/7 utilization, an 8-bit 27B decoding roughly 20–25 tok/s single-stream (~35–40 with speculative decoding), a hunt pass plausibly 1500–2000 output tokens — does not close single-stream. That arithmetic is an estimate and is explicitly not evidence. This experiment exists to replace it with measurement before the serving shape (Q4) is fixed.

## Methodology

`run.py`, executed on the target box:

1. Imports MLX and loads the pinned model. If the stack is absent it exits non-zero and writes nothing.
2. Probes top-k exposure empirically — it asks the stack what it returns at one scoring position rather than trusting a documented signature, trying `generate_step` then `stream_generate` and recording which entry point answered and how wide the returned distribution was. This is deliberate: the milestone exists precisely because that exposure is unverified.
3. Resolves `g_used` as `min(20, observed ceiling)`, or `1` if nothing is exposed.
4. Times a hunt pass (long generation, `--hunt-tokens`, default 1800) and a score pass (single token) over `--samples` runs each, single-stream, and batched where the build exposes a batch entry point. Where batched cannot be measured it records `batched_tok_s: null` with an explicit reason rather than omitting it — Q4 turns on that number.
5. Writes `output.json`.

Invocation:

    python3 docs/experiments/9010-logprob-capability/run.py \
        --model mlx-community/<model> \
        --model-hash <pinned-hash> \
        --quantization 8bit \
        --transcript <a real call transcript> \
        --hunt-tokens 1800 --samples 3 --batch-size 8

Pass a real transcript. Without one the script warns and falls back to filler, which measures decode rate but not retrieval difficulty — usable for the capacity arithmetic, misleading if read as hunt quality.

To measure the speculative-decoding delta, run twice and compare: once plain, once with `--drafter`/`--spec-mode`/`--spec-cap` set. Expect the delta to appear in the hunt pass and to be absent from the score pass — a single scoring token has nothing to amortize.

## Conclusion

Pending. `output.json` is absent, and `tests/test_logprob_capability.py` fails until it exists — deliberately, so M0's checkbox cannot flip on an unmeasured claim. The artifact is not to be hand-authored: the acceptance test rejects a future-dated `measured_at` and requires the stack identity that produced the numbers, because a G is uninterpretable without the stack it came from.

When the run happens, three things downstream read the result: M2's scale (G, and whether the continuous score exists at all), Q4's serving-shape decision (the batched-vs-single-stream numbers), and M1's KV-cache criterion (the score-pass cost is what makes per-dimension scoring affordable or not).
