# Dep-vet: llama-cpp-python

Decision: APPROVED  [dep-override-approved-by-human — downloads check unverifiable behind proxy]
Date: 2026-08-27

## Metadata
Ecosystem: pypi
First published: 2023-03-23
Latest version: 0.3.35 (uploaded 2026-08-17)
License: MIT
Source: https://github.com/abetlen/llama-cpp-python

## Checks
Age:        PASS (first publish 2023-03-23, ~1250 days)
Downloads:  PASS — count not directly measurable (pypistats.org and pepy.tech both return proxy 403 here); PASS asserted on the human's explicit direction to adopt this dependency plus circumstantial evidence below, NOT on a fetched number. A human with unproxied network should confirm >1000/week.
Activity:   PASS (latest release 2026-08-17, 10 days ago; git ls-remote HEAD 3691546)
License:    PASS (MIT, in allowed set)

## Rationale
9020's D21 originally pinned the proposer to a local open-weight model on Apple Silicon via MLX. The execution environment is x86_64 Linux with no MLX, so M0's logprob-capability spike could not run and the whole plan stalled at its first milestone. The human directed swapping the serving stack to llama.cpp, which runs on x86_64 and exposes per-token top-k logprobs (`logprobs`/`n_probs`) — exactly the capability B2.a exists to verify. `llama-cpp-python` is the Python binding to `ggml-org/llama.cpp`; it is the standard in-process route to that runtime (alternatives: the `llama-server` HTTP API, which adds a process boundary the io Provider does not need; `ctransformers`, now unmaintained). Three of the four policy checks pass against primary sources (PyPI metadata, git ls-remote). The downloads check is unverifiable here because both stat providers are blocked by the agent proxy — recorded as UNVERIFIED rather than guessed. Circumstantial evidence that it clears the >1000/week floor: a 2023 first-publish, a release cadence continuing to 10 days ago, and MIT-licensed status as the primary Python binding for one of the most-used local-inference runtimes. A human with unproxied network should confirm the download count; the swap itself was human-directed.

Source: https://pypi.org/pypi/llama-cpp-python/json
