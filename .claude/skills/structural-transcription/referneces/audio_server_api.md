# audio-server HTTP API — endpoints used by this skill

The pipeline talks to `audio-server` from speech-swift over HTTP. Full upstream documentation lives at https://soniqo.audio/api. This file is a cheat-sheet for the four endpoints the structural-transcription pipeline actually depends on.

All endpoints accept `audio/wav` request bodies. JSON keys on the wire are camelCase (Swift `Encodable` default). The Python client renames to snake_case at the boundary; values below are shown as the server emits them.

## `POST /transcribe`

ASR, defaults to Qwen3-ASR-0.6B (52 languages, MLX). Returns the transcript text only — no per-word timestamps.

**Request**
```
POST /transcribe
Content-Type: audio/wav
<wav body>
```

**Response**
```json
{ "text": "Thanks for calling support, this is Sam." }
```

**Notes**
- Engine selection is not exposed as an HTTP parameter. To use Parakeet TDT (faster on EU languages, runs on Neural Engine), invoke the `audio` CLI directly.
- Long inputs (~>30s) can silently truncate. The pipeline chunks segments above `--max-segment-sec` (default 25s) before sending here.

## `POST /vad`

Pyannote offline VAD. Used in the stereo per-channel branch of the pipeline; not used in mono mode (where `/diarize` does VAD as a side-effect).

**Response**
```json
[
  { "startTime": 0.42, "endTime": 3.87 },
  { "startTime": 5.10, "endTime": 7.95 }
]
```

Empty list = no speech detected.

## `POST /diarize`

Pyannote segmentation 3.0 + WeSpeaker embeddings + GMM-BIC clustering. Returns speaker-labeled segments.

**Response**
```json
[
  { "startTime": 0.42, "endTime": 3.87, "speakerId": 0 },
  { "startTime": 4.20, "endTime": 6.50, "speakerId": 1 },
  { "startTime": 7.10, "endTime": 9.80, "speakerId": 0 }
]
```

`speakerId` is 0-indexed and stable within one diarization run, but not across files.

**Notes**
- The HTTP endpoint does not currently expose `min_speakers` / `max_speakers`. Those are CLI flags only. If the call is known-2-speaker and pyannote is over-segmenting into 3+, drop to the CLI: `audio diarize call.wav --min-speakers 2 --max-speakers 2 --json`.
- Up to 3 concurrent speakers supported by the underlying pyannote model. For meetings with more, expect degraded accuracy.

## `POST /embed-speaker`

WeSpeaker ResNet34 256-dim L2-normalized speaker embedding. Not directly used by the structural-transcription pipeline today, but available for future enrollment/identification extensions.

**Response**
```json
[0.012, -0.034, 0.221, ..., 0.087]   // length 256
```

## Endpoints intentionally not used

The pipeline does **not** call:
- `/speak` — TTS, not relevant to transcription.
- `/respond` — speech-to-speech (PersonaPlex).
- `/enhance` — DeepFilterNet3 noise suppression. Useful for noisy calls but the pipeline does not pre-denoise by default. To pre-denoise, run `audio denoise raw.wav --output clean.wav` before invoking the pipeline; pass the cleaned file as `--input`.

## Liveness

There is no dedicated health endpoint. The Python client does an `OPTIONS /` and accepts any response < 500 as "socket reachable". `scripts/check_server.py` goes further: it sends a 2-second test tone to each endpoint and verifies the response shape. Run it after any `brew upgrade speech` or first-time setup.
