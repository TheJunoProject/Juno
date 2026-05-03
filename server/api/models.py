"""Wire-format Pydantic models for the local API.

Kept separate from the internal `InferenceRequest` / `InferenceResponse`
types so that the public API can evolve independently of the agent
internals.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)
    session_id: str | None = None


class TokenUsageWire(BaseModel):
    """Token usage as exposed on the API. Mirrors `inference.base.TokenUsage`
    but lives in the API models so internal type changes don't accidentally
    leak to clients."""

    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str
    session_id: str
    model: str
    provider: str
    usage: TokenUsageWire = Field(default_factory=TokenUsageWire)


class ProviderHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    model: str | None = None


class VoiceProviderHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    selected: bool
    detail: str | None = None


class VoiceHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stt: dict[str, VoiceProviderHealth]
    tts: dict[str, VoiceProviderHealth]


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    providers: dict[str, ProviderHealth]
    voice: VoiceHealth | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: str
    detail: str | None = None


# ---- Voice endpoints ----------------------------------------------------


class TranscribeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    language: str | None = None
    duration_seconds: float | None = None
    provider: str
    model: str | None = None


class SynthesizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    voice: str | None = None


class VoiceTurnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transcript: str
    response: str
    session_id: str
    chat_model: str
    chat_provider: str
    stt_provider: str
    tts_provider: str
    audio_base64: str
    audio_sample_rate: int
    audio_duration_seconds: float


class WakeWordConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    keyword: str
    sensitivity: float
    model: str | None


# ---- Background layer ---------------------------------------------------


class JobLastRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    started_at: str
    duration_seconds: float
    success: bool
    error: str | None = None


class JobInfoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    schedule: str | None
    next_run: str | None
    report_filename: str
    last_run: JobLastRun | None = None


class JobsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jobs: list[JobInfoResponse]


class ReportInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    size_bytes: int
    modified_at: str


class ReportsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reports: list[ReportInfo]
