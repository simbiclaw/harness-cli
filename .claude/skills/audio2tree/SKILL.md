---
name: audio2tree
description: Populate an INTENTS tree from raw call audio. Pipeline: S0 (ASR via structural-transcription) → S1 (Request extraction) → S2 (clustering) → S3 (routing + naming) → S4 (manifest population). Use this skill when the user says "audio2tree" or wants to go from support-call WAVs to a structured INTENTS hierarchy. Trigger especially when the deliverable is a populated MANIFEST.yaml or INTENTS/ tree, not just a transcript or single-request extraction. Each stage is a separate script; this skill orchestrates them.
---

# audio2tree Pipeline

Convert raw support-call audio recordings into a structured INTENTS tree. The pipeline runs in five stages (S0–S4), each consuming the output of the previous stage.

At the end, you have `intent_manifest.json` files populating the INTENTS tree with discovered intents, cluster centroids, and routing information.

## When the pipeline makes sense

You already have a batch of WAV files from support calls and you want to turn them into a structured, multi-level intent taxonomy — not just a single transcript or one-off extraction. The pipeline discovers clusters of customer Requests, names them contrastively, routes them through dual-channel matching, and writes them into the INTENTS tree format.

## Pipeline overview

| Stage | Name | What it does | Script |
|---|---|---|---|
| **S0** | ASR + structural transcription | Transcribe each WAV to `.structural.json` (speaker-labeled, time-aligned) | `structural-transcription` skill |
| **S1** | Request extraction | Read `.structural.json`, filter customer turns, build extraction prompts, produce `{audio_id, request_text, source_segment_ids}` | `scripts/audio2tree_pipeline.py` — uses `scripts/request_extractor.py` |
| **S2** | Embedding + clustering | Embed Requests via Ollama `bge-m3` (1024-d), k-means clustering (silhouette-optimal k), build contrastive naming prompts (5 in-cluster + 5 contrastive samples) | `scripts/cluster.py` |
| **S3** | Dual-channel routing | Cosine-match each Request against L2 description anchors. S_max >= 0.60 → matched channel; S_max < 0.60 → deviation channel. Collision detection freezes near-duplicate L2 anchors (cosine > 0.7) | `scripts/routing.py` |
| **S4** | Manifest population | Write `intent_manifest.json → bottom_up` sections for L2/L3 nodes. Never touches `top_down`. Reports deviation rate on stdout | `scripts/manifest_writer.py` |

## Prerequisites

- **Python 3.10+** with deps: numpy, scikit-learn, requests
- **Ollama** running locally with `bge-m3` model pulled (for S2 embedding and S3 routing)
- **structural-transcription skill** for S0 — see `.claude/skills/structural-transcription/SKILL.md`
- **audio-server** running with `--preload` if doing ASR (S0)

For S1 alone (Request extraction only), no Ollama or audio-server is needed — it works on already-transcribed `.structural.json` files.

## Workflow

### Full pipeline (all 5 stages)

```bash
# S0: Transcribe each WAV (run in parallel for throughput)
for f in /path/to/calls/*.wav; do
  out="/path/to/transcripts/$(basename "$f" .wav).structural.json"
  python .claude/skills/structural-transcription/scripts/pipeline.py \
    --input "$f" --output "$out" &
done
wait

# S1-S4: Run the full audio2tree pipeline
python scripts/audio2tree_pipeline.py \
  --input-dir /path/to/transcripts \
  --output-intents /path/to/INTENTS \
  --l1 "法人数字证书业务" \
  --run-all
```

### S1 standalone (Request extraction only)

If you already have `.structural.json` files, skip S0:

```bash
python scripts/audio2tree_pipeline.py \
  --input-dir /path/to/transcripts \
  --output-file /path/to/requests.json
```

### S0 details: ASR via structural-transcription

The structural-transcription skill handles speaker diarization (pyannote), ASR (Qwen3-ASR or Parakeet TDT), and prosodic feature extraction. Each WAV produces one `.structural.json` file.

Key points:
- Mono files: diarization identifies speakers via pyannote segmentation 3.0
- Stereo files: per-channel mode with no diarization; channel label maps to speaker
- See `.claude/skills/structural-transcription/SKILL.md` for detailed invocation, error handling, and feature flags

### S1 details: Request extraction

The pipeline reads each `.structural.json` and:

1. Identifies customer turns — filters `turns` where `speaker` is `"customer"` (or mapped through `speakers[].label`)
2. Concatenates customer turn text into a single block
3. Builds an extraction prompt using `build_extraction_prompt()` from `scripts.request_extractor`
4. Claude reads the prompt and extracts one Request per call: one Chinese sentence, 8-80 characters

The output of S1 is a JSON array where each entry has:

```json
{
  "audio_id": "call_001",
  "request_text": "客户咨询数字证书延期流程和费用",
  "source_segment_ids": [1, 3, 5],
  "prompt": "你是客服意图分析助手..."
}
```

### S2 details: Embedding + clustering

1. Each Request text is embedded via Ollama `bge-m3` → 1024-d vectors
2. K-means partitions Requests into clusters (k auto-selected via silhouette heuristic; min 2)
3. For each cluster, a contrastive naming prompt is built:
   - 5 in-cluster samples (closest to centroid)
   - 5 contrastive samples from the nearest neighboring cluster
4. Claude reads each prompt and names the cluster with a distinctive Chinese name (2-8 characters)
5. Names are validated: rejected if generic (其他咨询, 综合问题, 其他, 其他业务)

See `scripts/cluster.py` for the API: `embed()`, `run_clustering()`, `build_naming_prompt()`, `validate_cluster_name()`, `select_contrastive_samples()`.

### S3 details: Dual-channel routing

The routing protocol (see `INTENTS/AGENTS.md`):

1. Extract L2 descriptions from existing `intent_manifest.json` files
2. Embed each L2 description via Ollama `bge-m3`
3. For each Request embedding, compute cosine similarity against all L2 description anchors
4. **Matched channel** (S_max >= 0.60): assign Request to that L2
5. **Deviation channel** (S_max < 0.60): flag Request for auto-discovery
6. **Collision detection**: if two L2 descriptions have pairwise cosine > 0.7, freeze the newer anchor

Deviation rate = |D_deviation| / |D_total| — reported on stdout after every run.

See `scripts/routing.py` for the API: `extract_l2_descriptions()`, `detect_collisions()`, `route_request()`, `route_batch()`.

### S4 details: Manifest population

Writes `intent_manifest.json → bottom_up` sections for L2/L3 nodes. **Never touches `top_down`.**

Manifest shapes:
- **L2 Matched**: `source: "both"`, `bottom_up.channel: "matched"`, match_confidence, request_count, cluster_centroid
- **L2 Deviation**: `source: "audio2tree"`, `bottom_up.channel: "deviation"`, `status: "pending_review"`, `top_down: {}`
- **L3**: `source: "audio2tree"`, `parent_intent_id`, `bottom_up` with channel and request_count

Merge rules:
- Manifest exists → update only `bottom_up`, `last_updated`, `last_updated_by`, `calibration_status`
- Manifest doesn't exist (deviation) → create with `source: "audio2tree"`, `status: "pending_review"`
- L3 manifests are always created by audio2tree

See `scripts/manifest_writer.py` for the API and `docs/references/audio2tree-pipeline-design.md` §5 for exact JSON shapes.

## Invocation

```bash
# Full pipeline — cluster Requests from a directory of .structural.json files
/audio2tree cluster --input-dir /path/to/transcripts --l1 "法人数字证书业务"
```

### Arguments for `/audio2tree`

| Argument | Required | Stage | Description |
|---|---|---|---|
| `--input-dir` | Yes | S0/S1 | Directory with `.structural.json` files (S1 onwards) or `.wav` files (S0) |
| `--output-file` | No | S1 | Path to write the extracted Requests JSON. Default: `requests.json` in input-dir |
| `--output-intents` | No | S4 | Path to INTENTS root directory. Default: `INTENTS/` |
| `--l1` | Yes (full pipeline) | S3 | L1 business domain name, e.g. `"法人数字证书业务"` |
| `--l2` | No | S3 | L2 intent name override (default: auto-detect) |
| `--k` | No | S2 | Number of clusters (default: auto via silhouette heuristic) |
| `--run-all` | No | All | Run full S1-S4 pipeline in one invocation |
| `--run-s2` | No | S2 | Run S1+S2 (extraction + clustering) |

## File format: `.structural.json`

Each `.structural.json` produced by S0 follows a segment-centric schema. For M1 the relevant fields are:

```json
{
  "audio": { "id": "call_001" },
  "speakers": [ { "id": "S0", "label": "agent" }, { "id": "S1", "label": "customer" } ],
  "turns": [
    { "speaker": "S0", "segment_ids": [0, 1], "text": "您好,电话已接通。" },
    { "speaker": "S1", "segment_ids": [2, 3], "text": "你好,我想咨询..." }
  ]
}
```

Some sources (like the fixture in `tests/fixtures/demo_calls.json`) use a simplified format where `speaker` is already `"agent"` / `"customer"`:

```json
{
  "audio_id": "call_001",
  "turns": [
    { "speaker": "agent", "text": "您好,电话已接通。" },
    { "speaker": "customer", "text": "你好,我想咨询..." }
  ]
}
```

The pipeline handles both.

## Failure modes and remediation

### No `.structural.json` files found
Run S0 first on your WAV files. The structural-transcription skill produces one `.structural.json` per input.

### No customer turns in a transcript
Some calls have only agent speech (voicemail, wrong number). The pipeline logs the `audio_id` and skips it.

### Ollama not running
S2 and S3 require Ollama at `localhost:11434` with `bge-m3` pulled. Start Ollama and verify: `curl http://localhost:11434/api/tags`.

### No L2 descriptions found (S3)
If the INTENTS tree has no `intent_manifest.json` files with L2 descriptions, all Requests go to the deviation channel. This is correct behavior for a cold start.

### Extraction prompt too long
If a customer speaks many turns, `build_extraction_prompt` concatenates all text. For very long calls, consider summarizing before extraction.

## Directory layout

```
.claude/skills/audio2tree/
├── SKILL.md                  (this file)
├── references/               (future: schemas, examples)
└── scripts/                  (future: audio2tree-specific scripts)
```

Shared scripts live at `scripts/`:
- `scripts/audio2tree_pipeline.py` — pipeline orchestrator (S1-S4)
- `scripts/request_extractor.py` — extraction prompt builder + response parser
- `scripts/cluster.py` — embedding, k-means, contrastive naming prompts
- `scripts/routing.py` — dual-channel routing + collision detection
- `scripts/manifest_writer.py` — intent_manifest.json writer

## When to extend this skill

The pipeline is intentionally five stages. Extensions worth treating as separate skills:

- **Real-time / streaming** — live audio ingestion during an active call
- **Cross-lingual INTENTS** — Requests in multiple languages; translation step before clustering
- **Manual override UI** — human-in-the-loop for cluster naming or routing decisions
