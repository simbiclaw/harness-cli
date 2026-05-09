# Acoustic Feature Definitions

This file explains what each feature in the `acoustic` block measures and why Conversation Distillation might care. Implementation details live in `scripts/acoustic_features.py`; this file is for the reader trying to understand the output, not modify the code.

## Why these features at all?

A pure ASR transcript loses everything about *how* something was said: emotional tone, hesitation, emphasis, certainty. Conversation Distillation produces atomic claims, and a claim's confidence and provenance often depend on prosodic context. The acoustic block is small (a few dozen floats per segment) but lets the next layer reason about hedge-versus-assertion, frustration, surprise, and other signals that are illegible from text alone.

We chose the smallest set of well-understood features that telephony-grade speech research consistently finds informative. We did not add raw spectrograms or learned embeddings — those are large, opaque, and not what this layer is for.

---

## F0 (fundamental frequency / pitch)

Computed by `librosa.pyin`. Reported only over voiced frames; `voiced_frames_pct` says how much of the segment was actually pitched.

| Statistic | What it tells us |
|---|---|
| `mean_hz` | Speaker's average pitch in this segment. Compare across segments from the same speaker to detect emotional shifts. |
| `std_hz` | Pitch variability. Low std = monotone (boredom, formal register, scripted reading); high std = expressive, animated, distressed. |
| `range_hz` | `max - min`. Robust complement to std. |
| `voiced_frames_pct` | Trustworthiness gate. Below 30%, ignore the F0 stats — the segment was mostly unvoiced (whispers, fricatives, silence). |

**F0 floor 60 Hz, ceiling 500 Hz** by default — covers male, female, and excited / pediatric voices. Tighten if your population is narrower (e.g., adult male call center): a tighter range gives cleaner pyin output.

## Intensity (RMS in dBFS)

Computed by `librosa.feature.rms` over 25 ms windows with 10 ms hops, converted to decibels.

| Statistic | What it tells us |
|---|---|
| `mean_db` | Overall loudness of the segment in dBFS (negative; closer to 0 is louder). |
| `std_db` | Within-segment dynamic range — emphasis pattern. |
| `max_db` | Peak. Useful for detecting raised voices when paired with high std_db. |

**Important**: not normalized across the call. Absolute values depend on the recording's gain. Compare segments to other segments in the same recording, not to a hardcoded threshold.

## Speaking rate

| Statistic | What it tells us |
|---|---|
| `words_per_sec` | From the ASR transcript divided by segment duration. Standard rate measure when ASR is reliable. |
| `syllables_per_sec_est` | Voiced-onset count / duration. Independent of ASR. Useful when ASR is empty or wrong (hot for filler-heavy turns: "uhhh", "umm"). |
| `duration_sec` | Convenience copy of segment duration. |

Typical ranges for adult conversational speech: 2–4 words/sec, 4–7 syllables/sec. Sustained values outside these bounds suggest stress, over-rehearsed delivery, or ASR/pipeline issues.

## Voice quality (Praat via parselmouth)

These three measures are sensitive to the recording medium — telephony codecs degrade them. Treat as relative indicators within a call, not as cross-recording absolutes.

### `jitter_local`

Cycle-to-cycle variation in pitch period. Higher values = less regular vocal-fold vibration. Elevated jitter correlates with vocal fatigue, emotional arousal, and certain pathologies. Normal speech: < 0.02 (i.e., < 2%). Above 0.04 in a calm telephony call is unusual.

### `shimmer_local_db`

Cycle-to-cycle variation in amplitude, in dB. Like jitter but for loudness. Higher = breathier, more variable. Normal speech: < 1.0 dB.

### `hnr_db`

Harmonics-to-Noise Ratio. Ratio of periodic (voicing) to aperiodic (noise) energy in dB. Higher = clearer voicing. Telephony speech typically falls in 10–25 dB. Below 5 dB suggests serious noise, distortion, or non-speech being analyzed.

These three together are a coarse proxy for **voice clarity / strain**. They are not a clinical diagnostic — Praat's algorithms assume sustained vowels, and conversational speech violates that assumption. Use them to flag outliers, not to grade voices.

## Spectral (only with `--features all`)

| Statistic | What it tells us |
|---|---|
| `centroid_hz.mean/std` | Center of mass of the spectrum. Higher = brighter / sibilant; lower = warmer / muffled. |
| `rolloff_hz.mean/std` | Frequency below which 85% of spectral energy lies. Robustness check on centroid. |
| `mfcc.means/stds` | First 13 MFCCs. General-purpose audio fingerprint; useful for downstream models that want a numeric speech representation. |

This block is large (32 floats). Conversation Distillation rarely needs it — disabled by default. Turn on when downstream consumers explicitly ask for spectral features, e.g. for clustering acoustic events across many calls.

## NaN, in detail

A feature can be NaN for two distinct reasons:

1. **Computation failed** — Praat threw on a degenerate input, pyin found no voiced frames, the segment was empty. The pipeline catches these and writes NaN rather than letting one bad segment kill the run.
2. **Feature was not computed** — older runs with a smaller `feature_set` produced JSON without the field at all. That is *missing*, not NaN.

Downstream consumers should distinguish these cases:
- Field absent → "this version of the pipeline did not measure this; consult `config.feature_set`."
- Field present but NaN → "measured, but the segment did not support the measurement; treat as missing for that segment specifically."

## Things deliberately not measured

- **Emotion classification labels** (happy/sad/angry/etc.). These are model outputs, not features. They belong downstream of structural transcription, in a separate analysis layer.
- **Speaker traits** (age, gender). Out of scope; if downstream needs them, run dedicated classifiers on segment audio with the segment time intervals.
- **Word-level timestamps**. The structural transcription is segment-aligned, not word-aligned. Word alignment is available via the speech-swift forced aligner (`audio align`) but is not part of this pipeline. If a downstream consumer needs it, run forced alignment as a separate step keyed by `audio.id`.
- **Source separation** for overlapping speech. We report `stats.speech_overlap_sec` so consumers know overlap exists; reconstructing what each speaker said during overlap is a different problem.

The discipline here matters: Structural Transcription is a thin layer that organizes raw audio into a structured-but-low-interpretation surface. Anything that requires a model to make a judgment ("this person sounds frustrated") belongs to the next layer, not this one.
