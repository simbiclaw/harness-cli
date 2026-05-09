---
name: structural-transcription
description: Convert raw support-call audio recordings (WAV/MP3/FLAC, mono or stereo) into structural transcription JSON — text aligned with speaker, time, and acoustic features (pitch, intensity, voice quality, pause structure) — using soniqo/speech-swift's audio-server HTTP API plus librosa/parselmouth for prosodic features. Use this skill whenever the user mentions transcribing call recordings, support calls, customer-service audio, conversation analysis, building input for downstream Conversation Distillation or claim extraction, or producing speaker-labeled time-aligned transcripts. Also trigger when the user mentions speech-swift, audio-server, soniqo, pyannote diarization, or wants prosody / F0 / jitter / shimmer features alongside ASR output. Apply this skill even if the user only describes the deliverable (e.g., "turn this call into a structured transcript") without naming the underlying tools.
---

# Structural Transcription Pipeline

Produce **structural transcription** from raw support-call audio: text aligned with speaker, time, and acoustic features. The output is consumed by downstream Conversation Distillation, which deconstructs the transcript into atomic claims. There is no human reader of this layer — the consumer is the platform itself.

## What this skill produces

A single JSON document conforming to `references/output_schema.md`. The schema is segment-centric: each segment has a speaker, a time interval, ASR text, and an `acoustic` block of prosodic features. Top-level metadata (audio properties, speaker totals, turn structure, between-turn pauses) lets the next layer reason about call dynamics without re-reading the audio.

The output is deterministic given the same input, audio-server build, and feature config. Pin the schema version (`schema_version` field) so downstream consumers can detect breaking changes.

## When the diagram simplifies

The conceptual pipeline is `audio → VAD → Diarisation → ASR → Acoustic Features → merge`. In practice, two collapses happen and one branching happens:

1. **Mono path: VAD and Diarisation merge.** `audio-server`'s `/diarize` endpoint runs pyannote segmentation 3.0, which performs frame-level voice activity detection as part of producing speaker-labeled segments. Calling `/vad` separately on a mono file is redundant — `/diarize` already returns gated, speaker-attributed intervals. The script reflects this; do not call `/vad` ahead of `/diarize` "to be safe."
2. **Stereo path: Diarisation drops out.** When the recording is stereo with one speaker per channel (typical for split-recorded support calls — agent on L, customer on R), the channel **is** the speaker label. Run `/vad` per channel to gate silence and skip diarization entirely. This is more accurate than diarizing a downmix because there is no risk of speaker confusion.
3. **Acoustic features run in parallel with ASR**, not after it. The pipeline.py orchestrator dispatches ASR and feature extraction concurrently per segment, then joins.

The skill does not paper over these collapses with extra HTTP calls. Both fidelity to the speech-swift implementation and end-to-end latency benefit from honoring them.

## Prerequisites

The user's machine must have:

- **speech-swift installed** (Apple Silicon, macOS 14+, native ARM Homebrew at `/opt/homebrew`):
  ```bash
  brew tap soniqo/speech https://github.com/soniqo/speech-swift
  brew install speech
  ```
- **audio-server running** (preferably with `--preload` so model weights are warm):
  ```bash
  audio-server --port 8080 --preload
  ```
  The skill bundles `scripts/start_server.sh` which launches it as a background process and waits for `/transcribe` to respond.
- **Python 3.10+** with the deps in `requirements.txt` (numpy, soundfile, librosa, praat-parselmouth, requests). Acoustic features are computed in-process; speech-swift handles the HTTP heavy lifting.
- **ffmpeg** if input is MP3/M4A/Opus (skill normalizes to 16 kHz mono WAV per channel before sending to audio-server).

If any prerequisite is missing, run `python scripts/check_server.py` first — it diagnoses missing endpoints, wrong sample rates, and whether `--preload` was set.

## Workflow

The orchestrator is `scripts/pipeline.py`. The agent's job is to invoke it correctly, inspect the output, and adjust knobs when results disappoint — not to reimplement the pipeline.

### Standard invocation

```bash
python scripts/pipeline.py \
  --input /path/to/call.wav \
  --output /path/to/call.structural.json \
  --server http://localhost:8080
```

Defaults: auto channel detection, Qwen3-ASR for transcription, full acoustic feature set, schema version 1.0.

### Choosing the ASR engine

The `/transcribe` endpoint defaults to Qwen3-ASR-0.6B (52 languages, MLX). For European-language support calls the Parakeet TDT engine is faster (CoreML on the Neural Engine, frees the GPU for concurrent workloads) — but `audio-server` only exposes engine choice for `/speak`, not `/transcribe`. To use Parakeet for ASR, two options:

- Start `audio-server` with the engine override env var if the build supports it (check `audio-server --help`).
- Or shell out to the `audio` CLI directly per segment (`scripts/pipeline.py --asr-backend cli`), which accepts `--engine parakeet`. This loses HTTP connection pooling but is the only fully supported way today.

Default to HTTP unless the user asks for speed and is on a 25-EU-language call.

### Stereo per-channel mode

The pipeline auto-detects stereo and falls through to the per-channel branch. Override:

```bash
# Force per-channel even on a downmixed file (rare; will produce one speaker)
python scripts/pipeline.py --channel-mode per-channel ...

# Force diarization on a stereo file (e.g., when channels weren't split-recorded)
python scripts/pipeline.py --channel-mode mono-mix ...
```

Channel labels are configurable: `--label-l agent --label-r customer` (defaults). Channel labels are written to `speakers[].label`, not to `speakers[].id` — the `id` stays as `S0`/`S1` so downstream code doesn't have to special-case English support-call vocabulary.

### Acoustic feature subsets

Full feature extraction adds 200–400ms per segment on a Mac Studio. To skip subsets:

- `--features prosody` — F0 (librosa.pyin) and intensity (RMS dB) only. Fastest.
- `--features prosody+rate` — adds speaking rate (words / segment duration).
- `--features prosody+rate+voice` — adds parselmouth jitter, shimmer, HNR. Default.
- `--features all` — adds spectral centroid, spectral rolloff, MFCC means/stds. Largest output.
- `--features none` — skip the parallel branch entirely. Useful for debugging the ASR + diarization path in isolation.

See `references/feature_definitions.md` for what each feature is and why it's included.

### Output

A single JSON file. Always write to a file, never stdout — these documents grow large (megabytes for an hour-long call) and stdout corruption is a real failure mode in long-running pipelines.

If `--output -` is passed, the script writes to stderr-prefixed stdout but emits a warning. Prefer files.

## Failure modes and remediation

### audio-server is not reachable
`scripts/check_server.py` is the diagnostic. If it reports `connection refused`, the server isn't running — start it via `scripts/start_server.sh`. If it reports specific endpoints missing (e.g., `/diarize` 404s), the user's `audio-server` is older than v0.0.2; recommend `brew upgrade speech`.

### Diarization invents speakers
Pyannote's GMM-BIC step is not always right on noisy support-call audio. Symptoms: 4+ speakers detected on a 2-person call, or very short fragmentary segments attributed to a phantom third speaker. Mitigations in priority order:

1. Constrain speaker count: `--min-speakers 2 --max-speakers 2` (or whatever's known).
2. Pre-denoise: `audio denoise call.wav --output call.clean.wav` (DeepFilterNet3) before piping into the pipeline. Improves diarization meaningfully on calls with hold music or background office noise.
3. If the recording is actually stereo, force per-channel mode — diarization isn't needed.

### ASR returns truncated text on long segments
Qwen3-ASR has an internal context limit. Segments over ~30s can be truncated silently. The pipeline.py orchestrator chunks segments longer than 25s with 0.5s overlap and concatenates, deduplicating overlap with a fuzzy join. If you see truncation despite this, the chunker is being defeated by very fast speech — drop `--max-segment-sec` to 15.

### librosa F0 estimates are noisy
`librosa.pyin` returns NaN for unvoiced frames. The feature extractor reports the **voiced-only** mean / std and a `voiced_frames_pct` so downstream consumers can see how much of the segment was actually pitched. If `voiced_frames_pct < 30%`, treat F0 stats as unreliable and prefer parselmouth's intensity track for that segment instead. This is documented in the schema; do not silently smooth over it.

### Acoustic features take longer than ASR
On long calls, parselmouth's voice-quality measures (jitter, shimmer, HNR) dominate runtime. They run in a thread pool but Praat is single-threaded per analysis. If wallclock is tight and voice quality is not needed downstream, drop to `--features prosody+rate`.

## Output schema

See `references/output_schema.md` for the full spec. The shape at a glance:

```json
{
  "schema_version": "1.0",
  "audio": { "id": "...", "duration_sec": 642.3, "channels": 2, "channel_mode": "stereo_per_channel" },
  "speakers": [ { "id": "S0", "label": "agent", "channel": 0, "total_speech_sec": 312.4 } ],
  "segments": [ { "id": 0, "speaker": "S0", "start_sec": 1.24, "end_sec": 4.81, "text": "...", "acoustic": { ... } } ],
  "turns": [ { "speaker": "S0", "start_sec": 1.24, "end_sec": 4.81, "segment_ids": [0, 1] } ],
  "between_turn_pauses": [ { "after_segment": 5, "duration_sec": 0.84 } ],
  "stats": { "total_speech_sec": 564.2, "speech_overlap_sec": 4.3 }
}
```

A real example is in `assets/example_output.json` — agents debugging schema questions should open it rather than re-deriving from the spec.

## Directory layout

```
structural-transcription/
├── SKILL.md                  (this file)
├── requirements.txt          (Python deps)
├── scripts/
│   ├── pipeline.py           (main orchestrator)
│   ├── server_client.py      (HTTP client for audio-server)
│   ├── acoustic_features.py  (librosa + parselmouth feature extraction)
│   ├── check_server.py       (preflight diagnostic)
│   └── start_server.sh       (launch + wait for audio-server)
├── references/
│   ├── output_schema.md      (the structural transcription JSON schema)
│   ├── audio_server_api.md   (cheat-sheet of HTTP endpoints used)
│   └── feature_definitions.md (what each acoustic feature is and why)
└── assets/
    └── example_output.json   (canonical example for reference)
```

## When to extend this skill

The pipeline is intentionally narrow: WAV/MP3 input, JSON output, speech-swift on the back end. Extensions worth treating as separate skills rather than parameter additions:

- **Streaming / incremental transcription** — speech-swift has Parakeet-Streaming and Nemotron-Streaming for live audio. The structural-transcription contract is batch and offline; a live version is a different shape (events, not a document).
- **Cross-lingual translation** — Qwen3-ASR's `language` parameter does ASR in source language; translation is a separate downstream step.
- **Speaker enrollment / identification** — assigning known speakers (e.g., "agent_42") to S0/S1 requires `/embed-speaker` against an enrollment library. Useful but out of scope here.

The skill should not absorb these — they each warrant their own contract and tests.
