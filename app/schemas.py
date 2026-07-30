"""Request/response models for the public API."""
from pydantic import BaseModel, Field


class SpeechRequest(BaseModel):
    """OpenAI-compatible request body for POST /v1/audio/speech."""
    model: str = "VietTTS"
    input: str
    voice: str = "vi_fe"
    response_format: str = "wav"
    # OpenAI-compatible: 1.0 = engine default (no client adjustment). For
    # VietTTS, the server still applies its own VIETTTS_TEMPO on top — so
    # speed=1.0 keeps the existing "slightly slower than raw" default, and
    # other values multiply against it (e.g. speed=1.2 = 20% faster than
    # default, speed=0.8 = 20% slower).
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
