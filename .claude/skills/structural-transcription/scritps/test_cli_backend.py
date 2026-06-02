"""
Tests for the CLI backend that wraps `audio` CLI as an alternative to
the HTTP AudioServerClient. Follows TDD: these must fail (no implementation yet).
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))

SAMPLE_DIR = Path.home() / "workspace/best-practice/3audio-engineering/origin_calls"
SAMPLE_FILE = sorted(SAMPLE_DIR.glob("[0-9]*.wav"))[0]  # shortest: 1.wav


# ---------------------------------------------------------------------------
# Helper: decode a G.723.1 WAV into raw PCM samples (same as pipeline does)
# ---------------------------------------------------------------------------

def _load_pcm_mono(path: Path, target_sr: int = 16000) -> tuple[np.ndarray, int]:
    """Decode via ffmpeg to 16kHz mono f32."""
    import tempfile
    import soundfile as sf

    # ffmpeg decodes G.723.1 → PCM WAV
    cmd = [
        "ffmpeg", "-loglevel", "error", "-i", str(path),
        "-f", "wav", "-acodec", "pcm_s16le", "-ar", str(target_sr),
        "-ac", "1", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    # Write to temp file for soundfile to read
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tf.write(proc.stdout)
        tmp_path = tf.name
    try:
        samples, sr = sf.read(tmp_path, dtype="float32")
        return samples, sr
    finally:
        Path(tmp_path).unlink()


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pcm_samples():
    """Decoded PCM samples from the first G.723.1 file."""
    samples, sr = _load_pcm_mono(SAMPLE_FILE)
    return samples, sr


# ---------------------------------------------------------------------------
# Tests — these must FAIL initially (no CLIAudioBackend exists)
# ---------------------------------------------------------------------------

class TestCLIBackendSmoke:
    """Minimal smoke tests: can we import and instantiate the backend."""

    def test_can_import_cli_backend(self):
        """CLIAudioBackend should be importable from the pipeline module."""
        from pipeline import CLIAudioBackend  # noqa: F401

    def test_can_instantiate_with_defaults(self):
        """Default constructor should work (no audio-server URL needed)."""
        from pipeline import CLIAudioBackend

        backend = CLIAudioBackend()
        assert backend is not None


class TestCLIBackendTranscribe:
    """ASR via `audio transcribe`."""

    def test_transcribe_returns_string(self, pcm_samples):
        """transcribe() should return a non-empty string for real speech."""
        from pipeline import CLIAudioBackend

        backend = CLIAudioBackend()
        samples, sr = pcm_samples
        text = backend.transcribe(samples, sr)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_transcribe_silence_returns_empty(self):
        """Silence should return empty or very short string."""
        from pipeline import CLIAudioBackend

        backend = CLIAudioBackend()
        silence = np.zeros(16000, dtype=np.float32)  # 1 second
        text = backend.transcribe(silence, 16000)
        # silence should produce little to no output
        assert len(text.strip()) < 10, f"Expected near-empty, got: {text!r}"


class TestCLIBackendVAD:
    """VAD via `audio vad`."""

    def test_vad_returns_segments(self, pcm_samples):
        """VAD should return a list of segments with start_sec/end_sec."""
        from pipeline import CLIAudioBackend

        backend = CLIAudioBackend()
        samples, sr = pcm_samples
        segments = backend.vad(samples, sr)
        assert isinstance(segments, list)
        assert len(segments) > 0
        for seg in segments:
            assert hasattr(seg, "start_sec")
            assert hasattr(seg, "end_sec")
            assert seg.end_sec > seg.start_sec

    def test_vad_silence_returns_empty(self):
        """Silence should produce no segments."""
        from pipeline import CLIAudioBackend

        backend = CLIAudioBackend()
        silence = np.zeros(16000, dtype=np.float32)  # 1 second
        segments = backend.vad(silence, 16000)
        assert segments == []


class TestCLIBackendDiarize:
    """Diarization via `audio diarize`."""

    def test_diarize_returns_segments_with_speaker(self, pcm_samples):
        """Diarize should return segments with speaker_id."""
        from pipeline import CLIAudioBackend

        backend = CLIAudioBackend()
        samples, sr = pcm_samples
        segments = backend.diarize(samples, sr)
        assert isinstance(segments, list)
        assert len(segments) > 0
        speaker_ids = set()
        for seg in segments:
            assert hasattr(seg, "speaker_id")
            assert hasattr(seg, "start_sec")
            assert hasattr(seg, "end_sec")
            speaker_ids.add(seg.speaker_id)
        # A real support call should have at least 1 speaker
        assert len(speaker_ids) >= 1
