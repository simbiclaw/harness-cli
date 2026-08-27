# 9020-logprob-capability

This experiment tested whether the local serving stack exposes top-k logprobs at a chosen token position with k ≥ 20, and what a hunt pass and a score pass cost. **The answer is: yes — the low-level logit vector exposes the full vocabulary (ceiling 256 on the test model), G=20 is achievable, and the expectation over the softmax is a real scalar distinct from the argmax. Throughput was measured but is non-representative (synthetic model).**

## Stack

D21 originally pinned the proposer to Apple Silicon + MLX. The execution environment is x86_64 Linux without MLX, so — by human direction — the stack was swapped to **llama.cpp** via `llama-cpp-python` (dep-vetted at `docs/decisions/dep-vet-llama-cpp-python.md`). The io-boundary Provider (M1) keeps the specific engine a swap behind the interface, so this choice does not change the plan's architecture.

## Question

**B2.a — top-k exposure.** D19 computes `proposed_score` as the expectation over the distribution of scoring-token logits on a single-token letter scale at G=20. That needs at least 20 ranked logprobs at the scoring position. **Result:** llama.cpp exposes them two ways, and they differ sharply — see the finding below.

**Capacity.** Decode throughput for a hunt pass (long generation) and a score pass (single token). **Result:** measured, but on a synthetic model, so flagged `throughput_representative: false`. A production model's rate must be measured on a production model.

## Method

Real HuggingFace models are unreachable — the agent proxy allows only `pypi.org` and `files.pythonhosted.org`, and every model host returns 403. So the spike runs against a **synthetic seeded random-weight tiny llama-arch GGUF** built by `build_tiny_gguf.py` (256-token byte vocab, 64-dim, 2 layers). This is legitimate for M0's two questions: top-k exposure is a property of the runtime API, and decode rate is a property of model size and hardware — neither depends on weight values. Only the scores are meaningless, and M0 scores nothing.

Reproduce:

    python3 docs/experiments/9020-logprob-capability/build_tiny_gguf.py   # writes /home/user/models/tiny-llama-random.gguf
    python3 docs/experiments/9020-logprob-capability/run.py \
        --model /home/user/models/tiny-llama-random.gguf \
        --model-id tiny-llama-random --synthetic --quantization F32 \
        --n-ctx 4096 --hunt-tokens 256 --samples 3

With a real GGUF, drop `--synthetic` and pass `--model-id`/`--model-hash`/`--quantization` for the pinned production model; then `throughput_representative` becomes true and the capacity numbers can feed Q4.

## Key finding (feeds M2 directly)

llama.cpp exposes logprobs by two paths and **only the low-level one is usable for D19**:

- **High-level** `create_completion(logprobs=N)` — requires `logits_all=True`, then caps below N and returns a distribution-dependent count (requested 20 → 12; requested 256 → 129). It cannot reliably deliver G=20 distinct entries.
- **Low-level** `Llama.scores` (with `logits_all=True`) — exposes the full logit vector (256 = vocab). This is the path D19's per-dimension expectation must be computed from.

Recorded as a Decision Log entry in the plan; it constrains M2's implementation.

## Conclusion

`output.json` (schema_version 2) is committed and `tests/test_logprob_capability.py` passes against it. `topk_available: true`, `topk_ceiling: 256`, `g_used: 20`, `expectation_demo.differs_from_argmax: true`. B2.a is resolved for llama.cpp; D19 is computable. The one carry-forward is throughput: re-measure on a production model before trusting the capacity arithmetic (Q4). The artifact is not hand-authored — the acceptance test rejects a future-dated `measured_at` and requires the producing stack's identity.
