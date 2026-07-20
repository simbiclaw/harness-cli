# 9004 Execution Prompt

Hand this to a fresh Claude Code session.

## Execution Notes (lessons from 2026-07-20 run)

### Mistake 1: worktree isolation for sequential agents

**Don't use `isolation: 'worktree'` for sequential dependent agents. It's obviously wrong.**

A worktree is an isolated checkout. A sequential pipeline means M2 consumes M1's output,
M3 consumes M2's, and so on. Putting each agent in its own worktree makes it impossible
for M2 to see M1's code — they literally start from different filesystem states. This is
not a subtle tradeoff. It's a category error.

When it happened: the orchestrator had to manually copy files out of four separate
worktrees, reconcile independently-written versions of the same files, fix API mismatches,
and re-run all verification. Double the work.

Do this instead — no isolation, sequential await:
```
const m1 = await agent(M1_PROMPT)
const m2 = await agent(M2_PROMPT)
const m3 = await agent(M3_PROMPT)
const m4 = await agent(M4_PROMPT)
```
Each agent commits before returning. The next agent sees the commit.

### Mistake 2: reporting "E2E pass" without running S0 or S1

M4 was checked off on 2026-07-20 based on:
- S2-S4 running on hardcoded strings, not real ASR output
- Claude never invoked for extraction (S1) or naming (S3)
- No `.structural.json` ever produced from real WAV

46 unit tests passing does NOT mean the pipeline works end-to-end. The acceptance
gate requires real audio in, real manifests out, with Claude in the loop.

### Mistake 3: scripts in project root instead of skill directory

Per the [skills spec](https://docs.anthropic.com/en/docs/claude-code/skills), a skill's
scripts belong in `.claude/skills/<name>/scripts/`, not in a project-level `scripts/`
directory. Putting them in the wrong place and then fixing it required updating 30+
hardcoded import paths across 8 files.

### Mistake 4: S3 routing is a no-op placeholder

`batch_route()` in `routing.py` walks the INTENTS tree but never calls Ollama for
embeddings, never computes cosine similarity, and returns every request as `channel:
"deviation"`. The real routing functions (`route_request`, `route_batch`) exist and
are tested, but the pipeline doesn't call them.

### Known code gaps as of 2026-07-20

1. **`audio2tree_pipeline.py` cannot read `.structural.json`** — only reads `.txt` demo
   files (`load_demo_transcripts`) or fixture JSON (`load_demo_calls`). Needs a
   `load_structural_json(dir)` function.
2. **`routing.py::batch_route()` is a no-op** — always returns deviation. Pipeline
   needs to call `route_batch()` with real Ollama embeddings instead.
3. **SKILL.md references `--output-file`, `--l2`, `--k`, `--run-s2`** — none of these
   exist in the actual argparse. Either add them or remove from docs.

### Prerequisites before running

```bash
# 1. audio-server must be running (for S0 ASR)
audio-server --port 8080 --preload &
# OR verify CLI backend: which speech

# 2. Ollama must be running with bge-m3 (for S2/S3)
curl http://localhost:11434/api/tags | grep bge-m3

# 3. Python deps
python -c "import numpy, sklearn, librosa, soundfile, parselmouth, requests"
```

### Concrete execution steps (S0→S4)

```bash
# S0: Transcribe 5 WAVs to .structural.json
mkdir -p /tmp/transcripts
for i in 1 2 3 4 5; do
  python .claude/skills/structural-transcription/scritps/pipeline.py \
    --backend cli \
    --input /Users/prometheus/workspace/best-practice/3audio-engineering/origin_calls/$i.wav \
    --output /tmp/transcripts/$i.structural.json &
done
wait

# S1: Claude extracts one Request per call from .structural.json
# (Claude reads each .structural.json, filters customer turns, writes one Chinese sentence)
# Output: {audio_id, request_text, source_segment_ids} per call

# S2: Embed + cluster the extracted Requests (Ollama bge-m3)
# S3: Dual-channel routing — cosine match Requests to L2 description anchors
# S4: Write intent_manifest.json files to INTENTS tree

python .claude/skills/audio2tree/scripts/audio2tree_pipeline.py \
  --input-dir /tmp/transcripts \
  --output-intents INTENTS \
  --l1 "法人数字证书业务" \
  --run-all
```

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

Input: all M1-M3 outputs plus the 5 real WAV files.

What to build: write intent_manifest.json → bottom_up section for L2/L3 nodes. Never touch
top_down. Wire M1→M2→M3→M4 into a single skill invocation: /audio2tree cluster.

## E2E Acceptance Gate — input and minimum output

### Input (mandatory — no substitutions allowed)

5 real WAV files from:
  /Users/prometheus/workspace/best-practice/3audio-engineering/origin_calls/1.wav
  …through 5.wav

Pipeline MUST start at S0 (ASR) on these WAVs. Do not skip S0. Do not substitute
hand-transcribed .txt files or fixture JSON for the ASR output.

### Minimum output files

After a successful run, the following files MUST exist on disk:

1. Five `.structural.json` files — one per input WAV, produced by S0 structural-transcription.
   These are intermediate artifacts consumed by S1.

2. `INTENTS/<L1>/<L2>/intent_manifest.json` — one per discovered L2 cluster.
   At minimum, 1 file if all 5 calls land in the same cluster; normally >= 2.
   Each manifest MUST have these fields non-empty and valid:

   | Field | Requirement |
   |---|---|
   | `intent_id` | non-null, kebab-case string |
   | `title` | non-generic Chinese (2–8 chars, not "其他咨询", "综合问题", "其他", "其他业务") |
   | `description` | Chinese sentence describing the cluster's scope, with contrastive boundary |
   | `source` | `"audio2tree"` (deviation) or `"both"` (matched, if L2 anchors existed) |
   | `bottom_up.channel` | `"matched"` or `"deviation"` |
   | `bottom_up.request_count` | integer > 0 |
   | `bottom_up.cluster_centroid` | 1024-d float array |
   | `bottom_up.representative_requests` | non-empty list of Chinese Request strings |
   | `bottom_up.clustering_run_id` | non-empty string |
   | `top_down` | preserved exactly as-is if manifest existed; `{}` if new |
   | `calibration_status` | `"calibrated"` (matched) or `"needs_manual"` (deviation) |
   | `last_updated_by` | `"audio_to_tree"` |

3. Standard output MUST include deviation rate as a percentage.

### Things that are NOT sufficient

- Using hand-transcribed .txt files instead of ASR output from real WAVs
- Using hardcoded Request strings instead of Claude extracting them from transcripts
- Machine-generated placeholder names like "偏差聚类-0" instead of Claude-named clusters
- Running only S2-S4 and calling it "end-to-end"

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
  .claude/skills/audio2tree/scripts/request_extractor.py — build_extraction_prompt, parse_request_response
  .claude/skills/audio2tree/scripts/cluster.py — run_clustering, build_naming_prompt, validate_cluster_name, select_contrastive_samples
  .claude/skills/audio2tree/scripts/routing.py — extract_l2_descriptions, detect_collisions, route_request, route_batch (batch_route is a NO-OP — fix it)
  .claude/skills/audio2tree/scripts/manifest_writer.py — write_l2_manifest, read_manifest, merge_manifest, populate_manifests
  .claude/skills/audio2tree/scripts/audio2tree_pipeline.py — pipeline orchestrator (CANNOT read .structural.json — fix it)
  .claude/skills/structural-transcription/ — S0 ASR pipeline
  tests/test_m1_request_extraction.py — 11 tests (GREEN)
  tests/test_m2_cluster_naming.py — 5 tests (GREEN)
  tests/test_m3_routing.py — 16 tests (GREEN)
  tests/test_m4_manifest.py — 6 tests (GREEN)
  tests/test_m4_e2e.py — 8 tests (GREEN)
  tests/fixtures/demo_calls.json — 5-call fixture
  INTENTS/AGENTS.md — routing protocol

/goal don't stop until the audio2tree skill exists, M1-M4 are checked off,
`python -m pytest` exits 0, and running the skill on the 5 real audio files
populates INTENTS with manifest files that have valid bottom_up sections.
```
