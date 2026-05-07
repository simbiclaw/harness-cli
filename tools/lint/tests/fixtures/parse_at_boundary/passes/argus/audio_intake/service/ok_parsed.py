"""Cross-domain call with pydantic validation at boundary — must pass."""

from pydantic import BaseModel


class AudioFrame(BaseModel):
    data: bytes


def process(frame: AudioFrame) -> None:
    pass


# Call is made with a parsed model instance
frame = AudioFrame.model_validate({"data": b"hello"})
process(frame)
