"""
Acoustic feature extraction for structural transcription.

Two libraries do the work:
  - librosa  → F0 (pyin), RMS intensity, spectral centroid, rolloff, MFCC
  - parselmouth → Praat-grade jitter, shimmer, HNR, intensity

Why both: librosa's pyin is a robust, well-tested F0 tracker. parselmouth
exposes Praat's voice-quality measures, which librosa does not implement
faithfully. Using each library for what it's good at avoids re-implementing
algorithms that are already correct elsewhere.

All features are computed per-segment. The caller slices audio first and
hands us a mono float32 array. We do not handle silence-trimming here —
segments come from VAD/diarization and are assumed to contain speech.
"""

from __future__ import annotations

from typing import Literal

import numpy as np


FeatureSet = Literal[
    "none",
    "prosody",
    "prosody+rate",
    "prosody+rate+voice",
    "all",
]


# Defaults are chosen for telephony-grade speech (8–16 kHz effective bandwidth).
# F0 floor of 60 Hz catches male voices; ceiling of 500 Hz catches children
# and excited speech. Tighten the range if your population is narrower.
F0_FLOOR_HZ = 60.0
F0_CEILING_HZ = 500.0
PYIN_FRAME_LENGTH = 2048
PYIN_HOP_LENGTH = 256


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract_features(
    samples: np.ndarray,
    sample_rate: int,
    feature_set: FeatureSet,
    text: str | None = None,
) -> dict | None:
    """
    Extract the feature subset specified by `feature_set`.

    `text` is only used to compute speaking rate (words / segment_duration)
    when the rate sub-feature is enabled. If text is None, rate is omitted.

    Returns a nested dict matching the schema's `acoustic` block, or None
    when feature_set == "none".
    """
    if feature_set == "none":
        return None

    if samples.size == 0:
        # Defensive: degenerate empty segment. Return a structurally-valid
        # block with NaNs so downstream JSON loaders don't crash on missing
        # keys.
        return _empty_feature_block(feature_set)

    out: dict = {}

    # Prosody (always present except for "none")
    out["f0"] = _f0_stats(samples, sample_rate)
    out["intensity"] = _intensity_stats(samples, sample_rate)

    if feature_set in ("prosody+rate", "prosody+rate+voice", "all"):
        out["speaking_rate"] = _speaking_rate(samples, sample_rate, text)

    if feature_set in ("prosody+rate+voice", "all"):
        out["voice_quality"] = _voice_quality(samples, sample_rate)

    if feature_set == "all":
        out["spectral"] = _spectral_features(samples, sample_rate)

    return out


# ---------------------------------------------------------------------------
# Individual feature blocks
# ---------------------------------------------------------------------------


def _f0_stats(samples: np.ndarray, sample_rate: int) -> dict:
    """
    F0 (fundamental frequency / pitch) statistics, computed only over voiced
    frames. We report `voiced_frames_pct` so the consumer can decide whether
    to trust the F0 numbers — segments dominated by unvoiced consonants or
    silence will have low voiced percentage and unreliable means.
    """
    import librosa

    f0, voiced_flag, _voiced_prob = librosa.pyin(
        samples,
        fmin=F0_FLOOR_HZ,
        fmax=F0_CEILING_HZ,
        sr=sample_rate,
        frame_length=PYIN_FRAME_LENGTH,
        hop_length=PYIN_HOP_LENGTH,
    )

    voiced = f0[~np.isnan(f0)]
    total_frames = len(f0)
    voiced_pct = float(len(voiced) / total_frames * 100.0) if total_frames else 0.0

    if voiced.size == 0:
        return {
            "mean_hz": float("nan"),
            "std_hz": float("nan"),
            "min_hz": float("nan"),
            "max_hz": float("nan"),
            "range_hz": float("nan"),
            "voiced_frames_pct": voiced_pct,
        }

    return {
        "mean_hz": float(np.mean(voiced)),
        "std_hz": float(np.std(voiced)),
        "min_hz": float(np.min(voiced)),
        "max_hz": float(np.max(voiced)),
        "range_hz": float(np.max(voiced) - np.min(voiced)),
        "voiced_frames_pct": voiced_pct,
    }


def _intensity_stats(samples: np.ndarray, sample_rate: int) -> dict:
    """
    Frame-level RMS, converted to dBFS. We do not normalize across the call
    here — that's a downstream concern. Reporting raw dBFS keeps the value
    comparable to other tools that consume the same WAV.
    """
    import librosa

    # 25 ms windows, 10 ms hop — standard for prosodic intensity tracks
    frame_length = max(1, int(0.025 * sample_rate))
    hop_length = max(1, int(0.010 * sample_rate))
    rms = librosa.feature.rms(
        y=samples, frame_length=frame_length, hop_length=hop_length
    )[0]

    # Avoid log(0) on perfectly silent frames
    rms_safe = np.maximum(rms, 1e-10)
    db = 20.0 * np.log10(rms_safe)

    return {
        "mean_db": float(np.mean(db)),
        "std_db": float(np.std(db)),
        "min_db": float(np.min(db)),
        "max_db": float(np.max(db)),
    }


def _speaking_rate(
    samples: np.ndarray, sample_rate: int, text: str | None
) -> dict:
    """
    Words per second from the ASR transcript, plus a syllable-rate estimate
    from voiced-frame counts as a model-independent fallback.
    """
    duration_sec = len(samples) / sample_rate
    words_per_sec = float("nan")
    if text is not None and duration_sec > 0:
        word_count = len([w for w in text.split() if w.strip()])
        words_per_sec = float(word_count / duration_sec)

    # Crude syllable proxy: count voiced-frame onsets. Useful as a sanity
    # check when ASR is missing or wrong (e.g., on filler-heavy turns).
    syll_per_sec = _voiced_onset_rate(samples, sample_rate)

    return {
        "words_per_sec": words_per_sec,
        "syllables_per_sec_est": syll_per_sec,
        "duration_sec": duration_sec,
    }


def _voiced_onset_rate(samples: np.ndarray, sample_rate: int) -> float:
    """Estimate syllabic rate by counting voiced→voiced runs in the F0 track."""
    import librosa

    _, voiced_flag, _ = librosa.pyin(
        samples,
        fmin=F0_FLOOR_HZ,
        fmax=F0_CEILING_HZ,
        sr=sample_rate,
        frame_length=PYIN_FRAME_LENGTH,
        hop_length=PYIN_HOP_LENGTH,
    )
    if voiced_flag is None or len(voiced_flag) == 0:
        return float("nan")

    # Count rising edges in the boolean voiced track
    arr = np.asarray(voiced_flag, dtype=bool)
    edges = np.diff(arr.astype(np.int8))
    onsets = int(np.sum(edges == 1))
    duration_sec = len(samples) / sample_rate
    return float(onsets / duration_sec) if duration_sec > 0 else float("nan")


def _voice_quality(samples: np.ndarray, sample_rate: int) -> dict:
    """
    Praat-grade voice quality measures via parselmouth.

    jitter (local): cycle-to-cycle variation in pitch period.
    shimmer (local, dB): cycle-to-cycle variation in amplitude.
    HNR (Harmonics-to-Noise Ratio): voicing quality / breathiness signal.

    These require sustained voiced regions. On unvoiced or noisy segments
    Praat may fail or return NaN — we catch that and report NaN explicitly
    rather than crash.
    """
    try:
        import parselmouth
    except ImportError:
        return _nan_voice_block()

    try:
        sound = parselmouth.Sound(samples.astype(np.float64), sample_rate)
        point_process = parselmouth.praat.call(
            sound, "To PointProcess (periodic, cc)", F0_FLOOR_HZ, F0_CEILING_HZ
        )

        jitter_local = parselmouth.praat.call(
            point_process,
            "Get jitter (local)",
            0.0, 0.0, 0.0001, 0.02, 1.3,
        )

        shimmer_local_db = parselmouth.praat.call(
            [sound, point_process],
            "Get shimmer (local_dB)",
            0.0, 0.0, 0.0001, 0.02, 1.3, 1.6,
        )

        harmonicity = parselmouth.praat.call(
            sound, "To Harmonicity (cc)", 0.01, F0_FLOOR_HZ, 0.1, 1.0
        )
        hnr_db = parselmouth.praat.call(
            harmonicity, "Get mean", 0.0, 0.0
        )

        return {
            "jitter_local": _safe_float(jitter_local),
            "shimmer_local_db": _safe_float(shimmer_local_db),
            "hnr_db": _safe_float(hnr_db),
        }
    except Exception:
        # Praat throws on degenerate inputs (very short, all-unvoiced, etc.).
        # NaN-fill rather than letting one bad segment kill the run.
        return _nan_voice_block()


def _spectral_features(samples: np.ndarray, sample_rate: int) -> dict:
    """
    Spectral centroid + rolloff + first-13 MFCCs (means + stds).
    Included only with --features all; large and rarely needed for
    Conversation Distillation.
    """
    import librosa

    centroid = librosa.feature.spectral_centroid(
        y=samples, sr=sample_rate
    )[0]
    rolloff = librosa.feature.spectral_rolloff(
        y=samples, sr=sample_rate, roll_percent=0.85
    )[0]
    mfcc = librosa.feature.mfcc(y=samples, sr=sample_rate, n_mfcc=13)

    return {
        "centroid_hz": {
            "mean": float(np.mean(centroid)),
            "std": float(np.std(centroid)),
        },
        "rolloff_hz": {
            "mean": float(np.mean(rolloff)),
            "std": float(np.std(rolloff)),
        },
        "mfcc": {
            "means": [float(x) for x in np.mean(mfcc, axis=1)],
            "stds": [float(x) for x in np.std(mfcc, axis=1)],
        },
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_float(value) -> float:
    """parselmouth sometimes returns numpy scalars or NaN-like sentinels."""
    try:
        f = float(value)
        if np.isnan(f) or np.isinf(f):
            return float("nan")
        return f
    except (TypeError, ValueError):
        return float("nan")


def _nan_voice_block() -> dict:
    return {
        "jitter_local": float("nan"),
        "shimmer_local_db": float("nan"),
        "hnr_db": float("nan"),
    }


def _empty_feature_block(feature_set: FeatureSet) -> dict:
    """Schema-shaped block of NaNs for degenerate empty segments."""
    out: dict = {
        "f0": {
            "mean_hz": float("nan"),
            "std_hz": float("nan"),
            "min_hz": float("nan"),
            "max_hz": float("nan"),
            "range_hz": float("nan"),
            "voiced_frames_pct": 0.0,
        },
        "intensity": {
            "mean_db": float("nan"),
            "std_db": float("nan"),
            "min_db": float("nan"),
            "max_db": float("nan"),
        },
    }
    if feature_set in ("prosody+rate", "prosody+rate+voice", "all"):
        out["speaking_rate"] = {
            "words_per_sec": float("nan"),
            "syllables_per_sec_est": float("nan"),
            "duration_sec": 0.0,
        }
    if feature_set in ("prosody+rate+voice", "all"):
        out["voice_quality"] = _nan_voice_block()
    if feature_set == "all":
        out["spectral"] = {
            "centroid_hz": {"mean": float("nan"), "std": float("nan")},
            "rolloff_hz": {"mean": float("nan"), "std": float("nan")},
            "mfcc": {"means": [float("nan")] * 13, "stds": [float("nan")] * 13},
        }
    return out


__all__ = ["extract_features", "FeatureSet"]
