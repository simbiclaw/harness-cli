# 9004 Execution Prompt

Hand this to a fresh Claude Code session.

---

```
ultracode: build the audio2tree skill.

## What audio2tree is

A Claude Code skill (.claude/skills/audio2tree/SKILL.md + scripts/) that takes raw call audio as input and populates the INTENTS tree as output. The pipeline:

  S0: ASR → .structural.json (reuse .claude/skills/structural-transcription/)
  S1: Extract one Request per call — one Chinese sentence capturing the customer's core need
  S2: Embed Requests (Ollama bge-m3, localhost:11434), cluster (k-means), dual-channel route
      to L2 descriptions from intent_manifest.json
  S3: Name clusters (contrastive prompt), populate intent_manifest.json → bottom_up section

## How to build it

Execute 9004 Phase A (M0 is done). One independent subagent per milestone, in order.
Subagents read the full milestone spec in docs/exec-plans/active/9004-skill-prototype-cli-production.md.

For each milestone, the subagent MUST follow TDD:
  1. Write the test FIRST — a .py file that fails because the feature doesn't exist yet (RED)
  2. Run `python -m pytest <test_file> -v` — confirm it FAILS
  3. Write only enough code to make the test pass (GREEN)
  4. Run `python -m pytest <test_file> -v` — confirm it PASSES
  5. Flip the milestone checkbox in the exec-plan
  6. Commit: test(m<n>): ... / Plan: ... / Decision: test-first

Never write code before the test. Never commit code that doesn't pass.

## M1 — Request Extraction

Input: raw WAV files from /Users/prometheus/workspace/best-practice/3audio-engineering/origin_calls/
       (use the first 5: 1.wav through 5.wav)

What to build: SKILL.md scaffold + extraction logic. Reuse .claude/skills/structural-transcription/
for S0 (ASR). For S1, use scripts/request_extractor.py (already has build_extraction_prompt and
parse_request_response). The skill reads the .structural.json, extracts customer turns, builds the
extraction prompt, and outputs one Request per call.

Test: call the skill on 5 real audio files. Assert: 5 valid Requests produced — each is one Chinese
sentence, 8-80 chars, no agent dialogue markers, maps to an audio_id. The existing 11 tests in
tests/test_m1_request_extraction.py must stay GREEN.

## M2 — Clustering + Contrastive Naming

Input: Requests from M1.

What to build: clustering logic + naming. Reuse scripts/cluster.py (already has run_clustering,
build_naming_prompt, validate_cluster_name, select_contrastive_samples). Embed with Ollama
bge-m3 at localhost:11434. K-means with silhouette-optimal k. Contrastive prompt: 5 in-cluster
samples + 5 contrastive samples from nearest neighboring cluster. Claude names each cluster.
Validate names are non-generic (not "其他咨询", "综合问题").

Test: cluster 5 Requests into >= 2 clusters, verify contrastive prompt has <同类> and <对比>
sections, reject generic names. Existing 5 tests in tests/test_m2_cluster_naming.py must stay GREEN.

## M3 — Dual-Channel Routing

Input: Requests + clusters from M2, L2 descriptions from INTENTS intent_manifest.json files.

What to build: routing logic. Cosine-match each Request against L2 description anchors (embedded
via Ollama bge-m3). S_max >= 0.60 → matched channel (assign to that L2). S_max < 0.60 →
deviation channel (flag for auto-discovery). Collision detection: if two L2 descriptions have
cosine > 0.7, freeze the newer anchor. Report deviation rate on stdout.

Test: a Request semantically close to an L2 description is matched. A Request semantically
distant from all L2s enters the deviation pool. Near-duplicate L2 descriptions trigger freeze.

## M4 — Manifest Population + E2E

Input: all M1-M3 outputs.

What to build: write intent_manifest.json → bottom_up section for L2/L3 nodes. Never touch
top_down. Wire M1→M2→M3→M4 into a single skill invocation: /audio2tree cluster.

E2E Test: run the full skill on the 5 real audio files. Assert:
  - exit 0
  - At least one intent_manifest.json has populated bottom_up section
  - All cluster names are non-generic Chinese
  - top_down sections are untouched
  - Deviation rate is reported on stdout

## Context

Real audio: /Users/prometheus/workspace/best-practice/3audio-engineering/origin_calls/ (10 WAV files, 8kHz mono)
Real transcripts: INTENTS/_demo/call_001.txt through call_005.txt (manual transcriptions)
Fixture: tests/fixtures/demo_calls.json (5 calls, speaker-labeled JSON)
Ollama: bge-m3 running at localhost:11434 (1024-d embeddings)

Design docs (read as needed, do NOT modify):
  docs/exec-plans/active/9004-skill-prototype-cli-production.md — the plan
  docs/references/audio2tree-pipeline-design.md — design patterns (prompt templates, manifest schemas, algorithms)
  docs/superpowers/specs/2026-07-19-clio-to-audio2tree-design.md — product spec (WHAT, constraints, acceptance criteria)
  docs/superpowers/specs/2026-07-19-clio-to-audio2tree-design-decision.md — decision log
  docs/superpowers/specs/2026-07-20-clio-to-audio2tree-decisions-round-2.md — round 2 decisions

Existing code (reuse, do NOT rewrite):
  scripts/request_extractor.py — build_extraction_prompt, parse_request_response
  scripts/cluster.py — run_clustering, build_naming_prompt, validate_cluster_name, select_contrastive_samples
  .claude/skills/structural-transcription/ — S0 ASR pipeline
  tests/test_m1_request_extraction.py — 11 tests (GREEN)
  tests/test_m2_cluster_naming.py — 5 tests (GREEN)
  tests/fixtures/demo_calls.json — 5-call fixture
  INTENTS/AGENTS.md — routing protocol

/goal don't stop until the audio2tree skill exists, M1-M4 are checked off,
`python -m pytest` exits 0, and running the skill on the 5 real audio files
populates INTENTS with manifest files that have valid bottom_up sections.
```
