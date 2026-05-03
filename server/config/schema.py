"""Typed config schema. Validated against the YAML at every server start."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


# Restricting providers to known IDs makes typos in the config a validation
# error instead of a confusing runtime "no such provider" failure.
ProviderId = Literal["ollama"]

# Voice providers — `stub` is the always-available default that doesn't
# require any model downloads. Real providers are gated behind the
# optional `[voice]` install extra.
STTProviderId = Literal["stub", "whisper"]
TTSProviderId = Literal["stub", "piper"]
STTLocation = Literal["server", "client"]


class ServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)


class OllamaProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: HttpUrl = HttpUrl("http://localhost:11434")
    default_model: str = "qwen2.5:7b"
    request_timeout_seconds: float = Field(default=120.0, gt=0)


class ProvidersConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ollama: OllamaProviderConfig = Field(default_factory=OllamaProviderConfig)


class TaskRoutingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversational: ProviderId = "ollama"
    agentic_reasoning: ProviderId = "ollama"
    background_summarization: ProviderId = "ollama"
    complex_tasks: ProviderId = "ollama"


class InferenceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_provider: ProviderId = "ollama"
    fallback_provider: ProviderId | None = None
    escalation_attempts: int = Field(default=2, ge=0)
    task_routing: TaskRoutingConfig = Field(default_factory=TaskRoutingConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)

    @field_validator("fallback_provider")
    @classmethod
    def _fallback_must_differ(cls, v: ProviderId | None, info):  # noqa: ANN001
        # A fallback that points at the same provider as the default is almost
        # always a config mistake — flag it now rather than at request time.
        default = info.data.get("default_provider")
        if v is not None and v == default:
            raise ValueError(
                "fallback_provider must differ from default_provider "
                f"(both are '{v}')"
            )
        return v


class WhisperConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Model size accepted by faster-whisper. "base" / "small" / "medium" /
    # "large-v3" are the common choices. Smaller is faster but less accurate.
    model_size: str = "base"
    # Compute precision. "int8" is the safe CPU default; use "float16" or
    # "int8_float16" on GPU. Runtime checks the device on first call.
    compute_type: str = "int8"
    # Where faster-whisper caches downloaded model weights. Null = library
    # default (~/.cache/huggingface).
    download_root: str | None = None
    # Hint when null = autodetect from audio.
    default_language: str | None = None


class PiperConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Path to a Piper .onnx voice model. Null = stub falls back to silence.
    # Get models from https://github.com/rhasspy/piper/blob/master/VOICES.md.
    model_path: str | None = None
    # Optional explicit speaker id when the model has multiple voices.
    speaker_id: int | None = None


class STTConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: STTProviderId = "stub"
    # Where transcription runs. Today only `server` is implemented; the
    # `client` value is reserved so the companion can opt into running
    # whisper.cpp locally and sending text instead of audio in the future.
    location: STTLocation = "server"
    whisper: WhisperConfig = Field(default_factory=WhisperConfig)


class TTSConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: TTSProviderId = "stub"
    piper: PiperConfig = Field(default_factory=PiperConfig)


class WakeWordConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    # Spoken trigger phrase. The companion's openWakeWord stack listens for
    # this. Server-side this value is purely informational; the companion
    # fetches it via GET /api/voice/wakeword.
    keyword: str = "juno"
    # Detection threshold, 0.0–1.0. Higher = fewer false triggers, more
    # missed wake words.
    sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
    # openWakeWord model identifier. Null = companion picks its default.
    model: str | None = None


class VoiceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stt: STTConfig = Field(default_factory=STTConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    wakeword: WakeWordConfig = Field(default_factory=WakeWordConfig)


class JunoConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    server: ServerConfig = Field(default_factory=ServerConfig)
    inference: InferenceConfig = Field(default_factory=InferenceConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
