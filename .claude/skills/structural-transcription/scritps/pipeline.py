#!/usr/bin/env python3
"""
Structural transcription pipeline orchestrator.

Reads an audio file, runs the speech-swift / audio-server pipeline, and
writes a single structural transcription JSON document. See SKILL.md for
the high-level architecture and references/output_schema.md for the
output contract.

Usage:
    python pipeline.py --input call.wav --output call.structural.json

The script is intentionally linear and well-commented. The agent invoking
it should rarely need to edit it — knobs are exposed as CLI flags. If a
new failure mode shows up that isn't covered here, prefer adding a flag
over teaching the orchestrator new tricks inline.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

# When running as a script from the skill's scripts/ directory, sibling
# imports work directly. When imported as a package, fall back to absolute.
try:
    from server_client import (
        AudioServerClient,
        DiarizedSegment,
        Segment,
        wait_for_server,
    )
    from acoustic_features import extract_features, FeatureSet
except ImportError:  # pragma: no cover
    from .server_client import (  # type: ignore
        AudioServerClient,
        DiarizedSegment,
        Segment,
        wait_for_server,
    )
    from .acoustic_features import extract_features, FeatureSet  # type: ignore


SCHEMA_VERSION = "1.0"
TARGET_SAMPLE_RATE = 16000  # speech-swift normalizes internally; we standardize here too
MAX_SEGMENT_SEC_DEFAULT = 25.0  # ASR truncation guard


# ---------------------------------------------------------------------------
# CLI backend — wraps the `audio` CLI as an alternative to audio-server HTTP
# ---------------------------------------------------------------------------


class CLIAudioBackend:
    """
    Drop-in replacement for AudioServerClient that shells out to the
    `speech` CLI instead of an HTTP server. Same interface: transcribe(),
    vad(), diarize() accept numpy arrays and return the same types.
    """

    def __init__(
        self,
        audio_bin: str = "speech",
        model: str | None = None,
    ):
        self.audio_bin = audio_bin
        self.model = model

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _samples_to_temp_wav(samples: np.ndarray, sample_rate: int) -> str:
        import tempfile
        import os

        clipped = np.clip(samples, -1.0, 1.0).astype(np.float32, copy=False)
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            sf.write(path, clipped, sample_rate, format="WAV", subtype="PCM_16")
        except Exception:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise
        return path

    @staticmethod
    def _parse_vad_line(line: str) -> tuple[float, float] | None:
        """Parse '[2.46s - 2.95s] (0.49s)' → (2.46, 2.95)."""
        import re

        m = re.match(r"\[\s*([\d.]+)s\s*-\s*([\d.]+)s\]", line)
        if m:
            return float(m.group(1)), float(m.group(2))
        return None

    @staticmethod
    def _parse_diarize_line(line: str) -> tuple[int, float, float] | None:
        """Parse 'Speaker 0: [2.44s - 2.99s] (0.54s)' → (0, 2.44, 2.99)."""
        import re

        m = re.match(
            r"Speaker\s+(\d+):\s*\[\s*([\d.]+)s\s*-\s*([\d.]+)s\]", line
        )
        if m:
            return int(m.group(1)), float(m.group(2)), float(m.group(3))
        return None

    def _run(self, args: list[str]) -> str:
        """Run `speech` CLI with given args, return combined stdout+stderr."""
        import subprocess

        cmd = [self.audio_bin] + args
        if self.model and args[0] == "transcribe":
            cmd += ["--model", self.model]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        # Model loading goes to stdout; diagnostics to stderr. Combine.
        combined = proc.stdout + "\n" + proc.stderr
        if proc.returncode != 0:
            raise RuntimeError(
                f"speech {' '.join(args)} failed (rc={proc.returncode}): "
                f"{combined[:500]}"
            )
        return combined

    # ------------------------------------------------------------------ ASR

    def transcribe(self, samples: np.ndarray, sample_rate: int) -> str:
        path = self._samples_to_temp_wav(samples, sample_rate)
        try:
            output = self._run(["transcribe", path])
            for line in output.splitlines():
                line = line.strip()
                if line.startswith("Result:"):
                    return line.removeprefix("Result:").strip()
            return ""
        finally:
            Path(path).unlink(missing_ok=True)

    # ------------------------------------------------------------------ VAD

    def vad(self, samples: np.ndarray, sample_rate: int) -> list[Segment]:
        path = self._samples_to_temp_wav(samples, sample_rate)
        try:
            output = self._run(["vad", path])
            segments: list[Segment] = []
            for line in output.splitlines():
                parsed = self._parse_vad_line(line.strip())
                if parsed:
                    segments.append(Segment(start_sec=parsed[0], end_sec=parsed[1]))
            return segments
        finally:
            Path(path).unlink(missing_ok=True)

    # ------------------------------------------------------------------ diarize

    def diarize(self, samples: np.ndarray, sample_rate: int) -> list[DiarizedSegment]:
        path = self._samples_to_temp_wav(samples, sample_rate)
        try:
            output = self._run(["diarize", path])
            segments: list[DiarizedSegment] = []
            for line in output.splitlines():
                parsed = self._parse_diarize_line(line.strip())
                if parsed:
                    segments.append(DiarizedSegment(
                        speaker_id=parsed[0],
                        start_sec=parsed[1],
                        end_sec=parsed[2],
                    ))
            return segments
        finally:
            Path(path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Audio loading / channel inspection
# ---------------------------------------------------------------------------


@dataclass
class LoadedAudio:
    samples: np.ndarray  # shape (N,) for mono or (N, C) for multichannel
    sample_rate: int
    channels: int
    path: Path

    @property
    def duration_sec(self) -> float:
        return self.samples.shape[0] / self.sample_rate


def load_audio(path: Path, target_sample_rate: int = TARGET_SAMPLE_RATE) -> LoadedAudio:
    """
    Load any soundfile-supported format. For MP3/M4A/Opus, soundfile may
    fail; fall back to ffmpeg via subprocess. We resample to the target rate
    here so all downstream HTTP calls deal with one rate.
    """
    if not path.exists():
        raise FileNotFoundError(f"Input audio not found: {path}")

    try:
        samples, sr = sf.read(str(path), dtype="float32", always_2d=False)
    except RuntimeError as e:
        # soundfile (libsndfile) only handles PCM WAV and a handful of
        # compressed formats. ffmpeg is the universal fallback decoder for
        # everything else — MSG723, ADPCM, μ-law, MP3, M4A, Opus, etc.
        try:
            samples, sr = _decode_via_ffmpeg(path)
        except Exception as ffmpeg_err:
            raise RuntimeError(
                f"Failed to read {path} with both soundfile and ffmpeg. "
                f"soundfile: {e}. ffmpeg: {ffmpeg_err}"
            ) from e

    if sr != target_sample_rate:
        samples = _resample(samples, sr, target_sample_rate)
        sr = target_sample_rate

    channels = 1 if samples.ndim == 1 else samples.shape[1]
    return LoadedAudio(samples=samples, sample_rate=sr, channels=channels, path=path)


def _decode_via_ffmpeg(path: Path) -> tuple[np.ndarray, int]:
    """Decode arbitrary audio via ffmpeg → 32-bit float WAV in memory."""
    import subprocess

    cmd = [
        "ffmpeg", "-loglevel", "error", "-i", str(path),
        "-f", "f32le", "-acodec", "pcm_f32le",
        "-ar", str(TARGET_SAMPLE_RATE), "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    raw = np.frombuffer(proc.stdout, dtype=np.float32)
    # ffmpeg interleaves channels; we don't yet know the channel count.
    # Probe with a quick second pass to read metadata.
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=channels", "-of", "csv=p=0", str(path)],
        capture_output=True, check=True, text=True,
    )
    channels = int(probe.stdout.strip())
    if channels > 1:
        raw = raw.reshape(-1, channels)
    return raw, TARGET_SAMPLE_RATE


def _resample(samples: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    """Resample using librosa (high-quality kaiser_best)."""
    import librosa

    if samples.ndim == 1:
        return librosa.resample(samples, orig_sr=src_sr, target_sr=dst_sr)
    # Multichannel: resample each channel independently
    resampled = [
        librosa.resample(samples[:, c], orig_sr=src_sr, target_sr=dst_sr)
        for c in range(samples.shape[1])
    ]
    return np.stack(resampled, axis=1)


def to_mono(samples: np.ndarray) -> np.ndarray:
    """Equal-weight downmix to mono."""
    if samples.ndim == 1:
        return samples
    return np.mean(samples, axis=1).astype(np.float32, copy=False)


# ---------------------------------------------------------------------------
# Segment slicing + length guarding
# ---------------------------------------------------------------------------


def slice_audio(samples: np.ndarray, sr: int, start_sec: float, end_sec: float) -> np.ndarray:
    start_idx = max(0, int(start_sec * sr))
    end_idx = min(len(samples), int(end_sec * sr))
    if end_idx <= start_idx:
        return np.zeros(0, dtype=np.float32)
    return samples[start_idx:end_idx]


def chunk_long_segment(
    start_sec: float,
    end_sec: float,
    max_segment_sec: float,
    overlap_sec: float = 0.5,
) -> list[tuple[float, float]]:
    """
    Split a too-long segment into overlapping chunks. ASR text is later
    re-joined with overlap deduplication. Returns list of (start, end).
    """
    duration = end_sec - start_sec
    if duration <= max_segment_sec:
        return [(start_sec, end_sec)]
    chunks: list[tuple[float, float]] = []
    cursor = start_sec
    step = max_segment_sec - overlap_sec
    while cursor < end_sec:
        chunk_end = min(cursor + max_segment_sec, end_sec)
        chunks.append((cursor, chunk_end))
        if chunk_end >= end_sec:
            break
        cursor += step
    return chunks


def fuzzy_join_chunks(chunk_texts: list[str]) -> str:
    """
    Join chunk transcripts, removing the trailing N words of one chunk if
    they appear at the start of the next. N is small (3) since 0.5s overlap
    typically captures 1–3 words. Imperfect but adequate; downstream
    Conversation Distillation is robust to short duplications.
    """
    if not chunk_texts:
        return ""
    if len(chunk_texts) == 1:
        return chunk_texts[0].strip()

    joined = chunk_texts[0].strip()
    for nxt in chunk_texts[1:]:
        nxt = nxt.strip()
        if not nxt:
            continue
        prev_words = joined.split()
        nxt_words = nxt.split()
        max_overlap = min(3, len(prev_words), len(nxt_words))
        cut = 0
        for k in range(max_overlap, 0, -1):
            tail = [w.lower().strip(".,!?") for w in prev_words[-k:]]
            head = [w.lower().strip(".,!?") for w in nxt_words[:k]]
            if tail == head:
                cut = k
                break
        joined = joined + " " + " ".join(nxt_words[cut:])
    return joined


# ---------------------------------------------------------------------------
# Per-segment work: ASR + acoustic features in parallel
# ---------------------------------------------------------------------------


@dataclass
class SegmentResult:
    speaker_id: int  # 0-indexed; we map to "S0"/"S1" at output
    speaker_label: str | None
    channel: int | None
    start_sec: float
    end_sec: float
    text: str
    acoustic: dict | None = None


def run_asr_for_segment(
    client: AudioServerClient,
    samples: np.ndarray,
    sr: int,
    start_sec: float,
    end_sec: float,
    max_segment_sec: float,
) -> str:
    """ASR over one segment, with chunking if it exceeds max_segment_sec."""
    chunks = chunk_long_segment(start_sec, end_sec, max_segment_sec)
    texts: list[str] = []
    for c_start, c_end in chunks:
        slice_samples = slice_audio(samples, sr, c_start, c_end)
        if slice_samples.size == 0:
            continue
        texts.append(client.transcribe(slice_samples, sr))
    return fuzzy_join_chunks(texts)


def process_segment(
    client: AudioServerClient,
    full_samples: np.ndarray,  # mono channel array
    sr: int,
    speaker_id: int,
    speaker_label: str | None,
    channel: int | None,
    start_sec: float,
    end_sec: float,
    feature_set: FeatureSet,
    max_segment_sec: float,
    asr_executor: cf.ThreadPoolExecutor,
    feature_executor: cf.ThreadPoolExecutor,
) -> SegmentResult:
    """
    Submit ASR and feature extraction concurrently for one segment, wait
    for both, and return the merged result. Both branches independently
    operate on the same audio slice so we materialize the slice once.
    """
    slice_samples = slice_audio(full_samples, sr, start_sec, end_sec)

    asr_future = asr_executor.submit(
        run_asr_for_segment,
        client, full_samples, sr, start_sec, end_sec, max_segment_sec,
    )
    feature_future = feature_executor.submit(
        extract_features, slice_samples, sr, feature_set, None,
    )

    text = asr_future.result()
    acoustic = feature_future.result()

    # speaking_rate.words_per_sec needs the ASR text, so backfill if present
    if acoustic is not None and "speaking_rate" in acoustic and text:
        word_count = len([w for w in text.split() if w.strip()])
        duration = end_sec - start_sec
        if duration > 0:
            acoustic["speaking_rate"]["words_per_sec"] = float(word_count / duration)

    return SegmentResult(
        speaker_id=speaker_id,
        speaker_label=speaker_label,
        channel=channel,
        start_sec=start_sec,
        end_sec=end_sec,
        text=text,
        acoustic=acoustic,
    )


# ---------------------------------------------------------------------------
# Branch A: mono → diarize
# ---------------------------------------------------------------------------


def process_mono(
    client: AudioServerClient,
    audio: LoadedAudio,
    feature_set: FeatureSet,
    max_segment_sec: float,
    asr_executor: cf.ThreadPoolExecutor,
    feature_executor: cf.ThreadPoolExecutor,
) -> tuple[list[SegmentResult], int]:
    """Run /diarize then per-segment ASR + features. Returns (segments, num_speakers)."""
    mono_samples = to_mono(audio.samples)
    diarized = client.diarize(mono_samples, audio.sample_rate)

    if not diarized:
        return [], 0

    results: list[SegmentResult] = []
    for seg in diarized:
        results.append(
            process_segment(
                client=client,
                full_samples=mono_samples,
                sr=audio.sample_rate,
                speaker_id=seg.speaker_id,
                speaker_label=None,
                channel=None,
                start_sec=seg.start_sec,
                end_sec=seg.end_sec,
                feature_set=feature_set,
                max_segment_sec=max_segment_sec,
                asr_executor=asr_executor,
                feature_executor=feature_executor,
            )
        )

    num_speakers = len({r.speaker_id for r in results})
    return results, num_speakers


# ---------------------------------------------------------------------------
# Branch B: stereo → per-channel VAD
# ---------------------------------------------------------------------------


def process_stereo_per_channel(
    client: AudioServerClient,
    audio: LoadedAudio,
    label_l: str,
    label_r: str,
    feature_set: FeatureSet,
    max_segment_sec: float,
    asr_executor: cf.ThreadPoolExecutor,
    feature_executor: cf.ThreadPoolExecutor,
) -> tuple[list[SegmentResult], int]:
    """
    Each channel is treated as one speaker. Run /vad per channel; channel
    index becomes the speaker id (0=L, 1=R).
    """
    if audio.samples.ndim != 2 or audio.samples.shape[1] < 2:
        raise ValueError(
            f"Stereo per-channel mode requires 2+ channels; got shape {audio.samples.shape}"
        )

    channel_labels = [label_l, label_r]
    results: list[SegmentResult] = []

    for ch in range(min(2, audio.samples.shape[1])):
        ch_samples = np.ascontiguousarray(audio.samples[:, ch])
        speech_segs = client.vad(ch_samples, audio.sample_rate)
        for seg in speech_segs:
            results.append(
                process_segment(
                    client=client,
                    full_samples=ch_samples,
                    sr=audio.sample_rate,
                    speaker_id=ch,
                    speaker_label=channel_labels[ch],
                    channel=ch,
                    start_sec=seg.start_sec,
                    end_sec=seg.end_sec,
                    feature_set=feature_set,
                    max_segment_sec=max_segment_sec,
                    asr_executor=asr_executor,
                    feature_executor=feature_executor,
                )
            )

    # Sort by start time so the document reads in chronological order
    results.sort(key=lambda r: (r.start_sec, r.channel or 0))
    num_speakers = len({r.speaker_id for r in results})
    return results, num_speakers


# ---------------------------------------------------------------------------
# Merge: turns, between-turn pauses, speaker totals, document
# ---------------------------------------------------------------------------


def build_speakers_block(
    results: list[SegmentResult], channel_mode: str
) -> list[dict]:
    """One entry per distinct speaker_id, with totals."""
    by_speaker: dict[int, list[SegmentResult]] = {}
    for r in results:
        by_speaker.setdefault(r.speaker_id, []).append(r)

    blocks: list[dict] = []
    for sid in sorted(by_speaker.keys()):
        segs = by_speaker[sid]
        total_speech = sum(r.end_sec - r.start_sec for r in segs)
        total_words = sum(
            len([w for w in r.text.split() if w.strip()]) for r in segs
        )
        wpm_mean = (total_words / total_speech * 60.0) if total_speech > 0 else float("nan")

        # Channel only meaningful in stereo per-channel mode
        ch = segs[0].channel if channel_mode == "stereo_per_channel" else None
        label = segs[0].speaker_label

        blocks.append({
            "id": f"S{sid}",
            "label": label,
            "channel": ch,
            "total_speech_sec": round(total_speech, 3),
            "wpm_mean": round(wpm_mean, 2) if not math.isnan(wpm_mean) else None,
            "num_segments": len(segs),
        })
    return blocks


def build_turns(results: list[SegmentResult]) -> list[dict]:
    """
    Group consecutive same-speaker segments into turns. A turn ends when the
    next segment's speaker differs. Used by Conversation Distillation to
    reason about exchanges rather than individual utterances.
    """
    if not results:
        return []
    sorted_results = sorted(results, key=lambda r: r.start_sec)
    turns: list[dict] = []
    current_speaker = sorted_results[0].speaker_id
    current_segs: list[int] = [0]
    current_start = sorted_results[0].start_sec
    current_end = sorted_results[0].end_sec

    for idx in range(1, len(sorted_results)):
        r = sorted_results[idx]
        if r.speaker_id == current_speaker:
            current_segs.append(idx)
            current_end = max(current_end, r.end_sec)
        else:
            turns.append({
                "speaker": f"S{current_speaker}",
                "start_sec": round(current_start, 3),
                "end_sec": round(current_end, 3),
                "segment_ids": current_segs,
            })
            current_speaker = r.speaker_id
            current_segs = [idx]
            current_start = r.start_sec
            current_end = r.end_sec

    turns.append({
        "speaker": f"S{current_speaker}",
        "start_sec": round(current_start, 3),
        "end_sec": round(current_end, 3),
        "segment_ids": current_segs,
    })
    return turns


def build_between_turn_pauses(
    results: list[SegmentResult], turns: list[dict]
) -> list[dict]:
    """
    Pauses between consecutive turns, indexed by the segment id that ends
    each turn. Pauses can be negative when speakers overlap (interruptions);
    we emit them as-is so consumers can detect interruption.
    """
    if len(turns) < 2:
        return []
    pauses: list[dict] = []
    for i in range(len(turns) - 1):
        prev_turn = turns[i]
        next_turn = turns[i + 1]
        last_seg_id = prev_turn["segment_ids"][-1]
        gap = next_turn["start_sec"] - prev_turn["end_sec"]
        pauses.append({
            "after_segment": last_seg_id,
            "duration_sec": round(gap, 3),  # negative = overlap
        })
    return pauses


def compute_overlap_seconds(results: list[SegmentResult]) -> float:
    """Total overlapping speech across all speakers (interruptions)."""
    if len(results) < 2:
        return 0.0
    intervals = sorted(
        [(r.start_sec, r.end_sec, r.speaker_id) for r in results],
        key=lambda t: t[0],
    )
    overlap = 0.0
    for i, (s1, e1, sp1) in enumerate(intervals):
        for s2, e2, sp2 in intervals[i + 1:]:
            if s2 >= e1:
                break  # sorted by start; no further overlap possible
            if sp1 == sp2:
                continue  # same speaker = not interruption overlap
            overlap += max(0.0, min(e1, e2) - s2)
    return round(overlap, 3)


def build_document(
    results: list[SegmentResult],
    audio: LoadedAudio,
    channel_mode: str,
    audio_id: str,
    feature_set: FeatureSet,
) -> dict:
    """Assemble the full structural transcription document."""
    speakers = build_speakers_block(results, channel_mode)
    turns = build_turns(results)
    pauses = build_between_turn_pauses(results, turns)

    segments_json: list[dict] = []
    for idx, r in enumerate(sorted(results, key=lambda x: x.start_sec)):
        segments_json.append({
            "id": idx,
            "speaker": f"S{r.speaker_id}",
            "channel": r.channel,
            "start_sec": round(r.start_sec, 3),
            "end_sec": round(r.end_sec, 3),
            "duration_sec": round(r.end_sec - r.start_sec, 3),
            "text": r.text,
            "acoustic": r.acoustic,
        })

    total_speech = sum(r.end_sec - r.start_sec for r in results)
    total_silence = max(0.0, audio.duration_sec - total_speech)
    overlap_sec = compute_overlap_seconds(results)

    return {
        "schema_version": SCHEMA_VERSION,
        "audio": {
            "id": audio_id,
            "path": str(audio.path),
            "duration_sec": round(audio.duration_sec, 3),
            "sample_rate": audio.sample_rate,
            "channels": audio.channels,
            "channel_mode": channel_mode,
        },
        "config": {
            "asr_engine": "qwen3-asr-0.6b",  # current /transcribe default
            "diarizer": "pyannote-segmentation-3.0" if channel_mode == "mono" else None,
            "vad": "pyannote" if channel_mode == "stereo_per_channel" else "pyannote-via-diarize",
            "feature_set": feature_set,
        },
        "speakers": speakers,
        "segments": segments_json,
        "turns": turns,
        "between_turn_pauses": pauses,
        "stats": {
            "num_segments": len(results),
            "num_speakers": len({r.speaker_id for r in results}),
            "total_speech_sec": round(total_speech, 3),
            "total_silence_sec": round(total_silence, 3),
            "speech_overlap_sec": overlap_sec,
        },
    }


# ---------------------------------------------------------------------------
# Channel mode resolution
# ---------------------------------------------------------------------------


def resolve_channel_mode(audio: LoadedAudio, requested: str) -> str:
    """
    `auto`     → stereo file → stereo_per_channel; mono file → mono
    `mono-mix` → always downmix and diarize (returned as 'mono')
    `per-channel` → always per-channel (returned as 'stereo_per_channel');
                    error if input is mono
    """
    if requested == "mono-mix":
        return "mono"
    if requested == "per-channel":
        if audio.channels < 2:
            raise ValueError(
                "Channel mode 'per-channel' requires stereo input; "
                f"got mono ({audio.path})"
            )
        return "stereo_per_channel"
    # auto
    return "stereo_per_channel" if audio.channels >= 2 else "mono"


# ---------------------------------------------------------------------------
# Audio ID
# ---------------------------------------------------------------------------


def compute_audio_id(path: Path) -> str:
    """
    Deterministic ID from file content. Lets downstream Conversation
    Distillation cache results across pipeline reruns of the same file.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return f"call_{h.hexdigest()[:16]}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Convert a support-call recording into structural transcription JSON."
    )
    p.add_argument("--input", "-i", required=True, type=Path,
                   help="Path to audio file (WAV/FLAC always; MP3/M4A/Opus if ffmpeg installed)")
    p.add_argument("--output", "-o", required=True, type=Path,
                   help="Path to write the structural transcription JSON")
    p.add_argument("--backend", choices=["http", "cli"], default="cli",
                   help="Backend: 'http' (audio-server) or 'cli' (speech CLI). Default: cli.")
    p.add_argument("--model",
                   help="ASR model path or HuggingFace ID (CLI backend only)")
    p.add_argument("--server", default="http://localhost:8080",
                   help="audio-server base URL (HTTP backend only, default: http://localhost:8080)")
    p.add_argument("--channel-mode",
                   choices=["auto", "mono-mix", "per-channel"],
                   default="auto",
                   help="Channel handling. 'auto' picks per-channel for stereo, mono for mono.")
    p.add_argument("--label-l", default="agent",
                   help="Label for left channel in stereo per-channel mode (default: agent)")
    p.add_argument("--label-r", default="customer",
                   help="Label for right channel in stereo per-channel mode (default: customer)")
    p.add_argument("--features",
                   choices=["none", "prosody", "prosody+rate",
                            "prosody+rate+voice", "all"],
                   default="prosody+rate+voice",
                   help="Acoustic feature subset (default: prosody+rate+voice)")
    p.add_argument("--max-segment-sec", type=float, default=MAX_SEGMENT_SEC_DEFAULT,
                   help="Chunk segments longer than this for ASR (default: 25s)")
    p.add_argument("--asr-concurrency", type=int, default=4,
                   help="Concurrent /transcribe HTTP calls (default: 4)")
    p.add_argument("--feature-concurrency", type=int, default=2,
                   help="Concurrent acoustic feature extractions (default: 2; Praat is single-threaded per analysis)")
    p.add_argument("--audio-id",
                   help="Override the auto-computed audio_id (default: SHA-256 prefix of file)")
    p.add_argument("--server-deadline-sec", type=float, default=60.0,
                   help="How long to wait for audio-server to become reachable (default: 60s)")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    print(f"[pipeline] loading {args.input}", file=sys.stderr)
    audio = load_audio(args.input)
    channel_mode = resolve_channel_mode(audio, args.channel_mode)
    print(
        f"[pipeline] channels={audio.channels}, duration={audio.duration_sec:.1f}s, "
        f"channel_mode={channel_mode}",
        file=sys.stderr,
    )

    audio_id = args.audio_id or compute_audio_id(args.input)
    print(f"[pipeline] audio_id={audio_id}", file=sys.stderr)

    if args.backend == "cli":
        client = CLIAudioBackend(model=args.model)
        print(f"[pipeline] using CLI backend (speech {args.model or 'default model'})",
              file=sys.stderr)
    else:
        client = AudioServerClient(args.server)
        print(f"[pipeline] waiting for audio-server at {args.server}", file=sys.stderr)
        if not wait_for_server(client, deadline_sec=args.server_deadline_sec):
            print(
                f"[pipeline] ERROR: audio-server at {args.server} not reachable "
                f"after {args.server_deadline_sec}s. Run scripts/start_server.sh "
                "or scripts/check_server.py for diagnostics.",
                file=sys.stderr,
            )
            return 2

    t0 = time.monotonic()
    asr_executor = cf.ThreadPoolExecutor(max_workers=args.asr_concurrency)
    feature_executor = cf.ThreadPoolExecutor(max_workers=args.feature_concurrency)
    try:
        if channel_mode == "stereo_per_channel":
            results, _ = process_stereo_per_channel(
                client, audio, args.label_l, args.label_r,
                args.features, args.max_segment_sec,
                asr_executor, feature_executor,
            )
        else:  # mono channel_mode (input may have been stereo and was downmixed)
            # process_mono calls to_mono() internally, so passing the original
            # multichannel audio is fine. We deliberately keep audio.channels
            # at the original value so the output document records what the
            # input file actually was, not what we processed.
            results, _ = process_mono(
                client, audio, args.features, args.max_segment_sec,
                asr_executor, feature_executor,
            )
    finally:
        asr_executor.shutdown(wait=True)
        feature_executor.shutdown(wait=True)

    elapsed = time.monotonic() - t0
    print(
        f"[pipeline] processed {len(results)} segments in {elapsed:.1f}s "
        f"(rtf={elapsed / max(audio.duration_sec, 0.001):.3f})",
        file=sys.stderr,
    )

    document = build_document(
        results, audio, channel_mode, audio_id, args.features
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(document, f, indent=2, ensure_ascii=False, allow_nan=True)
    print(f"[pipeline] wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
