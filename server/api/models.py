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


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str
    session_id: str
    model: str
    provider: str


class ProviderHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    model: str | None = None


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    providers: dict[str, ProviderHealth]


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: str
    detail: str | None = None
