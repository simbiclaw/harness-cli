# Structural Transcription Output Schema (v1.0)

The pipeline produces one JSON document per input audio file. This document is the contract between Structural Transcription and downstream Conversation Distillation. It is segment-centric: the unit of analysis is a speech segment, and everything else (turns, pauses, speaker totals) is derived from segments.

## Top-level shape

```json
{
  "schema_version": "1.0",
  "audio": { ... },
  "config": { ... },
  "speakers": [ ... ],
  "segments": [ ... ],
  "turns": [ ... ],
  "between_turn_pauses": [ ... ],
  "stats": { ... }
}
```

`schema_version` is a string and must be checked by every downstream consumer. Breaking changes bump the major version. Adding new optional fields within an `acoustic` block does not bump the version.

## `audio`

Identifies and describes the recording.

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable ID derived from file content (SHA-256 prefix) by default, or whatever the caller passed via `--audio-id`. Use this as a primary key for downstream caching. |
| `path` | string | Filesystem path the pipeline read. Informational only. |
| `duration_sec` | float | Audio duration after resampling. |
| `sample_rate` | int | Always 16000 in v1.0 (the pipeline normalizes). |
| `channels` | int | Original channel count of the input file. |
| `channel_mode` | string | One of `mono`, `stereo_per_channel`. Tells consumers how speaker labels were assigned. |

## `config`

Records the pipeline configuration so a downstream consumer can detect when results came from an outdated setup.

| Field | Type | Notes |
|---|---|---|
| `asr_engine` | string | Name + version of the ASR backend. Currently `qwen3-asr-0.6b`. |
| `diarizer` | string \| null | `pyannote-segmentation-3.0` for mono mode; `null` for stereo per-channel (no diarization runs). |
| `vad` | string | `pyannote-via-diarize` (mono — VAD is a side-effect of diarization) or `pyannote` (stereo — separate /vad call per channel). |
| `feature_set` | string | One of `none`, `prosody`, `prosody+rate`, `prosody+rate+voice`, `all`. |

## `speakers`

One entry per distinct speaker. The `id` is a synthetic label (`S0`, `S1`, ...) — channel role labels go in `label`.

| Field | Type | Notes |
|---|---|---|
| `id` | string | `"S0"`, `"S1"`, ... — primary key for `segments[].speaker` and `turns[].speaker`. |
| `label` | string \| null | Human-meaningful role like `"agent"` or `"customer"`. Set only in stereo per-channel mode. |
| `channel` | int \| null | 0 or 1 in stereo per-channel mode; `null` in mono. |
| `total_speech_sec` | float | Sum of segment durations for this speaker. |
| `wpm_mean` | float \| null | Mean words per minute across this speaker's segments. `null` if total_speech_sec is 0. |
| `num_segments` | int | Count of segments attributed to this speaker. |

## `segments`

The core array. One entry per speech segment from VAD/diarization, in chronological order.

| Field | Type | Notes |
|---|---|---|
| `id` | int | 0-indexed position in `segments`. Used as the primary key. |
| `speaker` | string | References `speakers[].id`. |
| `channel` | int \| null | Source channel in stereo mode; `null` in mono. |
| `start_sec` | float | Segment start, rounded to 3 decimals. |
| `end_sec` | float | Segment end. |
| `duration_sec` | float | Convenience: `end_sec - start_sec`. |
| `text` | string | ASR transcript for this segment. May be empty when ASR returned nothing for a short or noisy segment. |
| `acoustic` | object \| null | See below. `null` only when `feature_set == "none"`. |

### `segments[].acoustic`

Structure depends on which feature set was selected. Fields are NaN when extraction failed for that segment (very short, all-unvoiced, etc.) — JSON encodes NaN as the literal `NaN` (Python's `allow_nan=True`). Downstream consumers MUST handle NaN.

#### `f0` (always present unless feature_set == "none")

```json
"f0": {
  "mean_hz": 132.5,
  "std_hz": 18.2,
  "min_hz": 88.4,
  "max_hz": 198.1,
  "range_hz": 109.7,
  "voiced_frames_pct": 81.3
}
```

`voiced_frames_pct` is the fraction of analysis frames where pyin found a pitch. Below 30% the F0 stats are unreliable — Conversation Distillation should treat them as missing rather than zero.

#### `intensity` (always)

```json
"intensity": {
  "mean_db": -22.4,
  "std_db": 4.1,
  "min_db": -41.0,
  "max_db": -12.8
}
```

dBFS — values are negative. Not normalized across the call; absolute level depends on the recording's gain.

#### `speaking_rate` (when feature_set is `prosody+rate` or richer)

```json
"speaking_rate": {
  "words_per_sec": 2.7,
  "syllables_per_sec_est": 4.1,
  "duration_sec": 3.57
}
```

`syllables_per_sec_est` is a model-free fallback (counts voiced-frame onsets). If words_per_sec is NaN but syllables_per_sec_est is sensible, the segment had speech but ASR returned empty.

#### `voice_quality` (when feature_set is `prosody+rate+voice` or `all`)

```json
"voice_quality": {
  "jitter_local": 0.018,
  "shimmer_local_db": 0.42,
  "hnr_db": 14.6
}
```

Praat measures via parselmouth. `hnr_db` (Harmonics-to-Noise Ratio) typically falls in the 10–25 dB range for clear telephony speech; lower values suggest noise, breathiness, or distortion.

#### `spectral` (only when feature_set == "all")

```json
"spectral": {
  "centroid_hz": { "mean": 1840.0, "std": 480.5 },
  "rolloff_hz":  { "mean": 3920.5, "std": 720.1 },
  "mfcc": { "means": [13 floats], "stds": [13 floats] }
}
```

## `turns`

Consecutive same-speaker segments collapsed into turns. A turn boundary occurs when the next segment's speaker changes.

```json
"turns": [
  { "speaker": "S0", "start_sec": 1.24, "end_sec": 8.50, "segment_ids": [0, 1] },
  { "speaker": "S1", "start_sec": 9.34, "end_sec": 12.10, "segment_ids": [2] }
]
```

`segment_ids` references `segments[].id` (which is positional, so the IDs are sorted by chronological order within the call).

## `between_turn_pauses`

Gap between the end of one turn and the start of the next. Signed — negative durations mean the next turn started before the previous ended (interruption / overlap).

```json
"between_turn_pauses": [
  { "after_segment": 1, "duration_sec": 0.84 },
  { "after_segment": 2, "duration_sec": -0.31 }
]
```

`after_segment` is the segment id of the **last** segment in the preceding turn. There are always `len(turns) - 1` entries.

## `stats`

Call-level summaries.

| Field | Type | Notes |
|---|---|---|
| `num_segments` | int | Length of `segments`. |
| `num_speakers` | int | Distinct speaker count. |
| `total_speech_sec` | float | Sum of all segment durations (may exceed `audio.duration_sec` in stereo mode if both channels speak simultaneously). |
| `total_silence_sec` | float | `max(0, audio.duration_sec - total_speech_sec)`. |
| `speech_overlap_sec` | float | Total time when more than one speaker was talking. Useful as an interruption signal. |

## NaN handling

NaN appears wherever a feature could not be computed. The pipeline writes Python's literal `NaN` token, which is invalid in strict JSON but accepted by all major parsers (Python's `json.loads`, JavaScript's `JSON.parse` with leniency, Rust's `serde_json` with the `arbitrary_precision` feature, etc.). If a downstream consumer needs strict JSON, post-process to replace `NaN` with `null` — but doing so loses the distinction between "not measured" (this version of the pipeline did not produce this field) and "measured but failed" (NaN). Conversation Distillation cares about that distinction.
