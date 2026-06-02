#!/usr/bin/env python3
"""
MCP server for the speech-swift audio-server.

Wraps a remote audio-server HTTP API as MCP tools so Claude Code can
transcribe, VAD, diarize, and embed audio from the local filesystem.

Target: audio-server on another Mac Studio on the local network.
Configure the server URL via AUDIO_SERVER_URL env var (default: http://localhost:8080).

Usage:
    AUDIO_SERVER_URL=http://192.168.1.100:8080 python audio_server_mcp.py
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Optional

import httpx
import numpy as np
import soundfile as sf
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AUDIO_SERVER_URL = os.environ.get("AUDIO_SERVER_URL", "http://localhost:8080").rstrip("/")
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_TIMEOUT = 300.0  # seconds — transcription of long files can be slow

mcp = FastMCP("audio_server_mcp")

# ---------------------------------------------------------------------------
# Shared audio I/O helpers
# ---------------------------------------------------------------------------


def _load_audio(path: str, start_sec: float | None = None, end_sec: float | None = None) -> tuple[np.ndarray, int]:
    """Load an audio file (any format soundfile or ffmpeg supports). Optionally slice."""
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    try:
        samples, sr = sf.read(str(path_obj), dtype="float32", always_2d=False)
    except RuntimeError:
        # Fall back to ffmpeg for compressed formats (MP3, M4A, Opus, etc.)
        import subprocess
        import tempfile

        # Probe channels
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=channels", "-of", "csv=p=0", str(path_obj)],
            capture_output=True, check=True, text=True,
        )
        channels = int(probe.stdout.strip())

        cmd = [
            "ffmpeg", "-loglevel", "error", "-i", str(path_obj),
            "-f", "f32le", "-acodec", "pcm_f32le",
            "-ar", str(DEFAULT_SAMPLE_RATE), "-",
        ]
        proc = subprocess.run(cmd, capture_output=True, check=True)
        raw = np.frombuffer(proc.stdout, dtype=np.float32)
        if channels > 1:
            raw = raw.reshape(-1, channels)
        samples = raw
        sr = DEFAULT_SAMPLE_RATE

    # Convert to mono if multi-channel
    if samples.ndim == 2:
        samples = np.mean(samples, axis=1).astype(np.float32)

    # Slice if requested
    if start_sec is not None or end_sec is not None:
        start_idx = int((start_sec or 0) * sr)
        end_idx = int((end_sec or len(samples) / sr) * sr)
        start_idx = max(0, start_idx)
        end_idx = min(len(samples), end_idx)
        if end_idx <= start_idx:
            raise ValueError(f"Empty slice: start={start_sec}, end={end_sec}")
        samples = samples[start_idx:end_idx]

    return samples.astype(np.float32), sr


def _samples_to_wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    """Encode float32 mono array as 16-bit PCM WAV in memory."""
    if samples.ndim != 1:
        raise ValueError(f"Expected mono audio (1-D array); got shape {samples.shape}")
    clipped = np.clip(samples, -1.0, 1.0).astype(np.float32, copy=False)
    buf = io.BytesIO()
    sf.write(buf, clipped, sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


async def _post_audio(endpoint: str, samples: np.ndarray, sample_rate: int) -> dict | list:
    """POST WAV body to the remote audio-server endpoint, return parsed JSON."""
    url = f"{AUDIO_SERVER_URL}{endpoint}"
    body = _samples_to_wav_bytes(samples, sample_rate)
    headers = {"Content-Type": "audio/wav"}
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.post(url, content=body, headers=headers)
        if not resp.is_success:
            raise RuntimeError(
                f"{endpoint} returned HTTP {resp.status_code}: {resp.text[:500]}"
            )
        return resp.json()


def _handle_error(e: Exception) -> str:
    """Consistent error formatting."""
    if isinstance(e, FileNotFoundError):
        return f"Error: {e}"
    if isinstance(e, ValueError):
        return f"Error: {e}"
    if isinstance(e, httpx.HTTPStatusError):
        return f"Error: audio-server returned HTTP {e.response.status_code}"
    if isinstance(e, httpx.TimeoutException):
        return f"Error: audio-server request timed out after {DEFAULT_TIMEOUT}s"
    if isinstance(e, httpx.ConnectError):
        return f"Error: cannot connect to audio-server at {AUDIO_SERVER_URL}. Is it running?"
    if isinstance(e, RuntimeError):
        return f"Error: {e}"
    return f"Error: unexpected {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Pydantic input models
# ---------------------------------------------------------------------------


class TranscribeInput(BaseModel):
    """Input for audio transcription."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    audio_path: str = Field(
        ..., description="Path to the audio file to transcribe (WAV, MP3, M4A, FLAC, etc.)"
    )
    start_sec: Optional[float] = Field(
        default=None, description="Start time in seconds for segment slicing"
    )
    end_sec: Optional[float] = Field(
        default=None, description="End time in seconds for segment slicing"
    )


class VADInput(BaseModel):
    """Input for voice activity detection."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    audio_path: str = Field(
        ..., description="Path to the audio file for VAD"
    )
    start_sec: Optional[float] = Field(
        default=None, description="Start time in seconds for segment slicing"
    )
    end_sec: Optional[float] = Field(
        default=None, description="End time in seconds for segment slicing"
    )


class DiarizeInput(BaseModel):
    """Input for speaker diarization."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    audio_path: str = Field(
        ..., description="Path to the audio file for diarization"
    )
    start_sec: Optional[float] = Field(
        default=None, description="Start time in seconds for segment slicing"
    )
    end_sec: Optional[float] = Field(
        default=None, description="End time in seconds for segment slicing"
    )


class EmbedSpeakerInput(BaseModel):
    """Input for speaker embedding."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    audio_path: str = Field(
        ..., description="Path to the audio file for speaker embedding"
    )
    start_sec: Optional[float] = Field(
        default=None, description="Start time in seconds for segment slicing"
    )
    end_sec: Optional[float] = Field(
        default=None, description="End time in seconds for segment slicing"
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="audio_transcribe",
    annotations={
        "title": "Transcribe Audio",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def audio_transcribe(params: TranscribeInput) -> str:
    """Transcribe speech in an audio file to text via the remote audio-server.

    Sends a WAV-encoded audio slice to the /transcribe endpoint. Supports
    optional segment slicing to transcribe only a portion of the file.

    Args:
        params (TranscribeInput): Validated input containing:
            - audio_path (str): Path to the audio file
            - start_sec (Optional[float]): Slice start time in seconds
            - end_sec (Optional[float]): Slice end time in seconds

    Returns:
        str: The transcribed text, or an error message.
    """
    import json

    try:
        samples, sr = _load_audio(params.audio_path, params.start_sec, params.end_sec)
        duration = len(samples) / sr
        result = await _post_audio("/transcribe", samples, sr)
        text = result.get("text", "") if isinstance(result, dict) else ""
        return json.dumps({
            "text": str(text).strip(),
            "duration_sec": round(duration, 3),
            "sample_rate": sr,
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="audio_vad",
    annotations={
        "title": "Voice Activity Detection",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def audio_vad(params: VADInput) -> str:
    """Detect speech segments in an audio file via the remote audio-server.

    Sends a WAV-encoded audio slice to the /vad endpoint. Returns a list of
    speech segments with start and end times.

    Args:
        params (VADInput): Validated input containing:
            - audio_path (str): Path to the audio file
            - start_sec (Optional[float]): Slice start time in seconds
            - end_sec (Optional[float]): Slice end time in seconds

    Returns:
        str: JSON list of speech segments with startTime, endTime, and duration.
    """
    import json

    try:
        samples, sr = _load_audio(params.audio_path, params.start_sec, params.end_sec)
        result = await _post_audio("/vad", samples, sr)
        segments = []
        for item in result if isinstance(result, list) else []:
            start = float(item.get("startTime", 0))
            end = float(item.get("endTime", 0))
            segments.append({
                "startTime": start,
                "endTime": end,
                "duration": round(end - start, 3),
            })
        return json.dumps({
            "segments": segments,
            "count": len(segments),
            "total_speech_sec": round(sum(s["duration"] for s in segments), 3),
        }, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="audio_diarize",
    annotations={
        "title": "Speaker Diarization",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def audio_diarize(params: DiarizeInput) -> str:
    """Identify speakers in an audio file via the remote audio-server.

    Sends a WAV-encoded audio slice to the /diarize endpoint. Returns a list
    of segments with speaker IDs, grouped by speaker.

    Args:
        params (DiarizeInput): Validated input containing:
            - audio_path (str): Path to the audio file
            - start_sec (Optional[float]): Slice start time in seconds
            - end_sec (Optional[float]): Slice end time in seconds

    Returns:
        str: JSON with per-speaker segments and summary statistics.
    """
    import json

    try:
        samples, sr = _load_audio(params.audio_path, params.start_sec, params.end_sec)
        result = await _post_audio("/diarize", samples, sr)

        by_speaker: dict[int, list[dict]] = {}
        for item in result if isinstance(result, list) else []:
            sid = int(item.get("speakerId", 0))
            start = float(item.get("startTime", 0))
            end = float(item.get("endTime", 0))
            seg = {"startTime": start, "endTime": end, "duration": round(end - start, 3)}
            by_speaker.setdefault(sid, []).append(seg)

        speakers = []
        for sid in sorted(by_speaker):
            segs = by_speaker[sid]
            speakers.append({
                "speakerId": sid,
                "label": f"S{sid}",
                "segments": segs,
                "total_speech_sec": round(sum(s["duration"] for s in segs), 3),
                "num_segments": len(segs),
            })

        return json.dumps({
            "speakers": speakers,
            "num_speakers": len(speakers),
            "total_segments": sum(s["num_segments"] for s in speakers),
        }, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="audio_embed_speaker",
    annotations={
        "title": "Speaker Embedding",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def audio_embed_speaker(params: EmbedSpeakerInput) -> str:
    """Get a 256-dim speaker embedding vector from an audio slice.

    Sends a WAV-encoded audio slice to the /embed-speaker endpoint. Returns an
    L2-normalized embedding vector useful for speaker similarity comparisons.

    Args:
        params (EmbedSpeakerInput): Validated input containing:
            - audio_path (str): Path to the audio file
            - start_sec (Optional[float]): Slice start time in seconds
            - end_sec (Optional[float]): Slice end time in seconds

    Returns:
        str: JSON with the 256-dim embedding vector and its L2 norm.
    """
    import json

    try:
        samples, sr = _load_audio(params.audio_path, params.start_sec, params.end_sec)
        result = await _post_audio("/embed-speaker", samples, sr)
        if isinstance(result, list):
            vec = [float(v) for v in result]
            norm = sum(v * v for v in vec) ** 0.5
            return json.dumps({
                "embedding": vec,
                "dimensions": len(vec),
                "l2_norm": round(norm, 6),
            }, indent=2)
        return f"Error: unexpected response format from /embed-speaker"
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="audio_ping",
    annotations={
        "title": "Check Audio Server Health",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def audio_ping() -> str:
    """Check if the remote audio-server is reachable.

    Sends an OPTIONS request to the audio-server root URL. Returns the server
    status and response time.

    Returns:
        str: JSON with reachable status, server URL, and latency.
    """
    import json
    import time

    try:
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.request("OPTIONS", AUDIO_SERVER_URL + "/")
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            return json.dumps({
                "reachable": resp.status_code < 500,
                "server_url": AUDIO_SERVER_URL,
                "status_code": resp.status_code,
                "latency_ms": latency_ms,
            }, indent=2)
    except httpx.ConnectError:
        return json.dumps({
            "reachable": False,
            "server_url": AUDIO_SERVER_URL,
            "error": "Connection refused — is the audio-server running?",
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "reachable": False,
            "server_url": AUDIO_SERVER_URL,
            "error": str(e),
        }, indent=2)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
