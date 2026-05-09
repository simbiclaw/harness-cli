"""
audio-server HTTP client.

Wraps the speech-swift `audio-server` REST API. Endpoints documented at
https://soniqo.audio/api. The wrapper exists so the rest of the pipeline
deals in Python dicts and numpy arrays, not in HTTP details.

Endpoints used here:
  POST /transcribe    audio/wav body  → JSON {"text": "..."}
  POST /vad           audio/wav body  → JSON list of {"startTime", "endTime"}
  POST /diarize       audio/wav body  → JSON list of {"startTime", "endTime", "speakerId"}
  POST /embed-speaker audio/wav body  → JSON list of float (256-dim)

The server's JSON keys are camelCase (Swift Codable default). We preserve
that on the wire and rename to snake_case at the boundary so downstream
Python is idiomatic.
"""

from __future__ import annotations

import io
import time
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import requests
import soundfile as sf


@dataclass(frozen=True)
class Segment:
    start_sec: float
    end_sec: float

    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec


@dataclass(frozen=True)
class DiarizedSegment(Segment):
    speaker_id: int


class AudioServerClient:
    """
    Thin client. One instance per pipeline run; reuse the underlying
    requests.Session for HTTP keep-alive (matters when calling /transcribe
    dozens or hundreds of times per call recording).
    """

    def __init__(self, base_url: str, timeout_sec: float = 600.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.session = requests.Session()

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _samples_to_wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
        """
        Encode a float32/float64 mono array as a 16-bit PCM WAV in memory.
        audio-server accepts WAV at any reasonable rate and resamples internally
        to whatever each model needs.
        """
        if samples.ndim != 1:
            raise ValueError(
                f"Expected mono audio (1-D array); got shape {samples.shape}"
            )
        # soundfile writes the dtype-correct WAV; clip to avoid surprises with
        # peaks slightly over 1.0 from upstream processing.
        clipped = np.clip(samples, -1.0, 1.0).astype(np.float32, copy=False)
        buf = io.BytesIO()
        sf.write(buf, clipped, sample_rate, format="WAV", subtype="PCM_16")
        return buf.getvalue()

    def _post_audio(self, endpoint: str, samples: np.ndarray, sample_rate: int):
        """POST a WAV body and return parsed JSON. Raises on non-2xx."""
        url = f"{self.base_url}{endpoint}"
        body = self._samples_to_wav_bytes(samples, sample_rate)
        headers = {"Content-Type": "audio/wav"}
        resp = self.session.post(
            url, data=body, headers=headers, timeout=self.timeout_sec
        )
        if not resp.ok:
            # Surface a useful error: audio-server returns plain-text bodies on
            # 4xx/5xx that often name the missing model file.
            raise RuntimeError(
                f"{endpoint} returned HTTP {resp.status_code}: {resp.text[:500]}"
            )
        return resp.json()

    # ------------------------------------------------------------------ ping

    def ping(self) -> bool:
        """
        Best-effort liveness check. audio-server has no dedicated health
        endpoint, so we do an OPTIONS on / and accept any response that means
        the socket is open. Reliable signal that the process is up; says
        nothing about whether models are loaded.
        """
        try:
            resp = self.session.request(
                "OPTIONS", self.base_url + "/", timeout=2.0
            )
            return resp.status_code < 500
        except requests.RequestException:
            return False

    # ------------------------------------------------------------------ ASR

    def transcribe(self, samples: np.ndarray, sample_rate: int) -> str:
        """
        Run /transcribe over a mono audio slice. Returns the transcript text.
        Whatever the server's default ASR engine is (Qwen3-ASR-0.6B as of
        v0.0.2) is what runs.
        """
        result = self._post_audio("/transcribe", samples, sample_rate)
        text = result.get("text", "")
        if not isinstance(text, str):
            raise RuntimeError(
                f"/transcribe returned unexpected payload: {result!r}"
            )
        return text.strip()

    # ------------------------------------------------------------------ VAD

    def vad(self, samples: np.ndarray, sample_rate: int) -> list[Segment]:
        """
        Run /vad (offline pyannote VAD, 10s sliding windows). Returns speech
        segments in seconds. Empty list means no detected speech.
        """
        payload = self._post_audio("/vad", samples, sample_rate)
        return [
            Segment(
                start_sec=float(item["startTime"]),
                end_sec=float(item["endTime"]),
            )
            for item in payload
        ]

    # ------------------------------------------------------------------ diarize

    def diarize(
        self,
        samples: np.ndarray,
        sample_rate: int,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> list[DiarizedSegment]:
        """
        Run /diarize. The HTTP endpoint accepts the audio body but does not
        currently expose min/max-speakers as form parameters — those are CLI
        flags. If min_speakers / max_speakers are needed for the call,
        pipeline.py should fall back to invoking the `audio diarize` CLI
        instead. We accept the args here for API symmetry but do not pass
        them to the HTTP call; pipeline.py is responsible for routing.
        """
        del min_speakers, max_speakers  # not currently sent over HTTP
        payload = self._post_audio("/diarize", samples, sample_rate)
        return [
            DiarizedSegment(
                start_sec=float(item["startTime"]),
                end_sec=float(item["endTime"]),
                speaker_id=int(item["speakerId"]),
            )
            for item in payload
        ]

    # ------------------------------------------------------------------ embed

    def embed_speaker(
        self, samples: np.ndarray, sample_rate: int
    ) -> np.ndarray:
        """
        Run /embed-speaker. Returns a 256-dim L2-normalized float vector as
        a numpy array. Used for speaker stability checks across long segments
        (stable embedding within a turn → diarization is probably right).
        """
        payload = self._post_audio("/embed-speaker", samples, sample_rate)
        if not isinstance(payload, list):
            raise RuntimeError(
                f"/embed-speaker returned unexpected payload: {payload!r}"
            )
        vec = np.asarray(payload, dtype=np.float32)
        if vec.shape != (256,):
            raise RuntimeError(
                f"/embed-speaker returned vector of shape {vec.shape}, "
                "expected (256,)"
            )
        return vec


def wait_for_server(
    client: AudioServerClient,
    deadline_sec: float = 60.0,
    interval_sec: float = 1.0,
) -> bool:
    """
    Block until the server responds to ping(), or deadline expires.
    Returns True if reachable, False on timeout. Useful right after launching
    audio-server in start_server.sh.
    """
    start = time.monotonic()
    while time.monotonic() - start < deadline_sec:
        if client.ping():
            return True
        time.sleep(interval_sec)
    return False


__all__ = [
    "AudioServerClient",
    "Segment",
    "DiarizedSegment",
    "wait_for_server",
]
