"""Typed config schema. Validated against the YAML at every server start."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


# Restricting providers to known IDs makes typos in the config a validation
# error instead of a confusing runtime "no such provider" failure.
ProviderId = Literal["ollama"]


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


class JunoConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    server: ServerConfig = Field(default_factory=ServerConfig)
    inference: InferenceConfig = Field(default_factory=InferenceConfig)
