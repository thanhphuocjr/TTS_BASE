"""Request/response models for the public API."""
from typing import Optional
from pydantic import BaseModel, Field


class SpeechRequest(BaseModel):
    """OpenAI-compatible request body for POST /v1/audio/speech."""
    model: str = "VietTTS"
    input: str
    voice: str = "north"
    response_format: str = "wav"
    # OpenAI-compatible: 1.0 = engine default (no client adjustment). For
    # VietTTS, the server still applies its own VIETTTS_TEMPO on top — so
    # speed=1.0 keeps the existing "slightly slower than raw" default, and
    # other values multiply against it (e.g. speed=1.2 = 20% faster than
    # default, speed=0.8 = 20% slower).
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    # Optional generic pause in seconds (fallback for both ":" and "..." if specific pause is not set)
    pause_seconds: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    # Optional pause in seconds injected after colon (":")
    colon_pause_seconds: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    # Optional pause in seconds injected between segments separated by "..."
    ellipsis_pause_seconds: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    # Optional diffusion steps override
    num_step: Optional[int] = Field(default=None, ge=4, le=100)

