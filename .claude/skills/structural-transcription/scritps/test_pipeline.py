"""
Tests for the structural transcription pipeline.

Run from the skill's scritps/ directory:
    python -m pytest test_pipeline.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure we can import the pipeline module
sys.path.insert(0, str(Path(__file__).parent))

from pipeline import load_audio, TARGET_SAMPLE_RATE


# ---------------------------------------------------------------------------
# Sample files — all G.723.1, 8000 Hz, mono
# ---------------------------------------------------------------------------

SAMPLE_DIR = Path.home() / "workspace/best-practice/3audio-engineering/origin_calls"
SAMPLE_FILES = sorted(SAMPLE_DIR.glob("[0-9]*.wav"))

# ---------------------------------------------------------------------------
# load_audio() — G.723.1 codec support
# ---------------------------------------------------------------------------


class TestLoadAudioG7231:
    """load_audio() must decode G.723.1 WAV via ffmpeg fallback."""

    @pytest.mark.parametrize("wav_path", SAMPLE_FILES)
    def test_decodes_g7231_without_error(self, wav_path: Path):
        """G.723.1 files should load without raising."""
        audio = load_audio(wav_path)
        assert audio is not None

    @pytest.mark.parametrize("wav_path", SAMPLE_FILES)
    def test_resamples_to_target_rate(self, wav_path: Path):
        """Output sample rate must be the pipeline target (16000 Hz)."""
        audio = load_audio(wav_path)
        assert audio.sample_rate == TARGET_SAMPLE_RATE

    @pytest.mark.parametrize("wav_path", SAMPLE_FILES)
    def test_output_is_mono(self, wav_path: Path):
        """Mono input must produce mono output (1-D array)."""
        audio = load_audio(wav_path)
        assert audio.samples.ndim == 1
        assert audio.channels == 1

    @pytest.mark.parametrize("wav_path", SAMPLE_FILES)
    def test_duration_matches_ffprobe(self, wav_path: Path):
        """Duration should be within 0.5s of ffprobe-reported duration."""
        import subprocess
        import json

        audio = load_audio(wav_path)

        # Get expected duration from ffprobe
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(wav_path)],
            capture_output=True, check=True, text=True,
        )
        expected = float(json.loads(result.stdout)["format"]["duration"])

        assert abs(audio.duration_sec - expected) < 0.5, (
            f"Duration mismatch: pipeline={audio.duration_sec:.2f}s, "
            f"ffprobe={expected:.2f}s"
        )

    def test_load_audio_rejects_missing_file(self):
        """Non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_audio(Path("/nonexistent/audio.wav"))
