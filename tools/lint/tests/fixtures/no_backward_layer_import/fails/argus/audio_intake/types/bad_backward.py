"""Types layer (rank 0) importing from Service layer (rank 3) — forbidden backward dependency."""

from argus.audio_intake.service import process_audio  # noqa: F401
