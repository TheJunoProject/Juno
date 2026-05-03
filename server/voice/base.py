"""Provider-agnostic STT and TTS interfaces.

Mirrors `server/inference/base.py`: every voice call goes through one of
these provider interfaces; adding a new backend (Kokoro for TTS,
whisper.cpp for STT, etc.) is a new file under `providers/` plus one
router-registration line.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field


class STTRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    # Raw WAV bytes. Other container formats may be accepted by some
    # providers but the canonical input is WAV.
    audio: bytes
    # ISO 639-1 language code (e.g. "en"). None = autodetect.
    language: str | None = None


class STTResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    language: str | None = None
    duration_seconds: float | None = None
    provider: str
    model: str | None = None


class TTSRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    # Provider-specific voice identifier. None = provider default.
    voice: str | None = None


class TTSResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    # WAV bytes, ready to play or hand to the companion.
    audio: bytes
    sample_rate: int
    channels: int = 1
    duration_seconds: float
    provider: str
    voice: str | None = None


class STTProviderError(Exception):
    """Transcription failed."""


class TTSProviderError(Exception):
    """Synthesis failed."""


class STTProvider(ABC):
    id: str
    name: str

    @abstractmethod
    async def is_available(self) -> bool: ...

    @abstractmethod
    async def transcribe(self, request: STTRequest) -> STTResponse: ...

    async def aclose(self) -> None:
        return None


class TTSProvider(ABC):
    id: str
    name: str

    @abstractmethod
    async def is_available(self) -> bool: ...

    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> TTSResponse: ...

    async def aclose(self) -> None:
        return None
