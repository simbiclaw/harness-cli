# Alignment with Clio (Tamkin et al., 2024)

This subagent's pipeline is informed by Clio, Anthropic's privacy-preserving system for analysing real-world AI use (arXiv:2412.13678). Clio's pattern — extract → embed → cluster → describe → hierarchise — is the right shape for transforming a corpus of conversations into a navigable hierarchy. This document records what we reuse and what we deliberately depart from.

## What we reuse

### The five-stage pipeline shape

Clio runs: extract facets → embed → k-means cluster → LLM-describe clusters → build multi-level hierarchy via combined k-means + prompting. Conversation Distillation runs: extract claims → de-contextualise → embed → assign-or-discover cluster → LLM-name new clusters → build 2-to-3 level tree.

The shapes are isomorphic. Both rely on embeddings to find semantic neighbours that string-matching would miss; both use the LLM for the parts (cluster naming, hierarchy reasoning) where structural similarity isn't the right signal.

### LLM-generated cluster titles and summaries

Clio prompts a model with sample conversations from each cluster and asks for a descriptive title plus a one-line summary, with explicit instructions to omit private information. This subagent does the same for new L3 leaves: read 5 exemplar claims, propose a title and summary. The instruction surface in `references/extraction_rules.md` carries forward Clio's emphasis on specific, descriptive titles over generic ones ("Requirements for evidence of system failure during late filing", not "Filing questions").

### Hierarchy via embed-cluster-then-prompt

Clio builds its hierarchy by first clustering at the leaf level and then using a model to group those leaves into mid-level themes (Appendix G.7 of the paper). The subagent does the same on tree construction: leaf centroids cluster into L2 themes, L2 centroids cluster into L1 categories, with the LLM naming each level.

### Bottom-up over top-down

Clio's design principle is "bottom-up pattern discovery" — surface what's in the data, don't impose a predefined taxonomy. The subagent's L1 categories emerge from the corpus, not from a fixed business glossary. (Exception: an organisation that already has a stable canonical L1 list can pin them in `state/protocol_config.json` and require new L1 proposals to reconcile against the existing list.)

## What we deliberately depart from

### Privacy posture

Clio's most distinctive design choice is privacy-by-construction: cluster aggregation thresholds, omission of private information at summary time, cluster auditing that drops anything containing identifiable details. **Conversation Distillation makes the opposite trade-off**: claims preserve specific entities ("the U-Key driver", "form 8-K", "the customer's order placed 2026-04-23") because de-contextualisation requires it.

This is appropriate because the consumer is the platform itself, not human analysts browsing aggregated patterns. The intents tree feeds an automated calibration layer, not a public Clio-style dashboard. **An organisation deploying this subagent must take on the privacy responsibility separately** — typical mitigations include scoping claim retention windows, encrypting `claim_library.jsonl`, redacting PII fields before the input structural transcriptions are written, or running this subagent only over already-anonymised transcripts. None of those are this subagent's job, but consumers should be aware that the output is *not* a privacy-preserving artifact in Clio's sense.

### Atomic claims, not conversation summaries

Clio extracts one summary per conversation. The subagent extracts one claim per proposition, multiple per turn, multiple turns per call. This finer granularity is necessary because the downstream consumer wants to ask "what did customers ask for, what did agents commit to, what was contested" — questions that operate below conversation level.

The cost: more LLM calls per call (extraction is per-segment, not per-conversation), more storage (claim library grows ~5–20× faster than a Clio-style summary library), more entries to cluster.

### Stability across regenerations

Clio re-clusters from scratch on each run. That's fine for "what are people doing this month" trend analysis, where cluster identities don't need to persist. The subagent's intents tree is a calibration target. Calibration requires identity stability (`L3.compliance_reporting.annual_report.late_filing_evidence` must mean the same thing across runs).

The stability protocol in `references/stability_protocol.md` is the engineering response to that requirement: incremental cluster assignment with thresholds, gated discovery, human-approved refactoring. This is the largest single departure from Clio.

### Source citations

Clio's privacy design specifically severs the link from cluster summaries back to the originating conversations — that's a feature there. Claims here are source-cited (back to specific `audio_id` + `segment_ids`) because verifiability is required: a downstream consumer disputing a claim must be able to trace it to the segment that grounded it. This couples the claim library tightly to the structural transcription corpus; if the source transcripts are deleted, citations dangle.

### No 2D map or interactive viewer

Clio's interface (zoomable map, colour-by-facet) is an analyst tool. The subagent has no UI; its consumer is automated. We don't compute UMAP projections, don't render coordinates, don't ship a viewer. If a human wants to browse the tree, they read the JSON.

### Concern scoring, abuse detection, classifier monitoring

Clio uses concern scores to find safety classifier false-positives and false-negatives, and to detect coordinated abuse. None of this applies to a private support-call corpus. The subagent does not score claims for harm, does not flag suspicious patterns, does not run any kind of classifier-comparison analysis. Those are out of scope.

## Things we adopt with modifications

### Synthetic evaluation

Clio validates its accuracy against a 19,476-conversation synthetic dataset with known topic distribution (94% reconstruction accuracy). The subagent has no equivalent eval bundled today, but the recommended pattern is similar: generate synthetic structural transcriptions with controlled intent distributions, run distillation, compare the produced tree against the ground-truth distribution. This is left as future work; when undertaken, follow Clio's methodology closely.

### Embedding model

Clio uses a text embedding model (the paper doesn't pin a specific one in the public material; their internal choice is presumably an Anthropic-internal embedder). The subagent defaults to a public sentence-transformer (`BAAI/bge-base-en-v1.5`) so the pipeline works offline. The embedding model is configurable; matching Clio's choice is a tradeoff between recall on edge cases and reproducibility for downstream consumers.

## What the paper does that we punted on

- **Cross-lingual analysis** — Clio includes language as a facet and analyses cross-language differences in usage. The subagent currently treats language as a per-segment property surfaced from the structural transcription but does not segregate clusters by language. A bilingual call produces claims in both languages and they cluster across language boundaries by embedding similarity, which is sometimes wrong (the same intent in English and Japanese may not be embedded close enough). Future work: optionally bucket by language at the L1 level.
- **Coordinated-abuse detection at the cluster level** — n/a for this domain.
- **Public methodology disclosure** — Clio's value comes partly from publishing methodology and findings. This subagent's outputs are operational, not for publication.

## Citation discipline

When a downstream consumer asks "why is this leaf shaped this way?", the answer is `references/stability_protocol.md` plus the audit log for that node. When they ask "where did the pipeline shape come from?", the answer is this document plus the Clio paper. Always refer back to the paper rather than restating its findings as if they were original to this subagent — the techniques are theirs; the application and the stability protocol are the additions here.
