"""Provider-agnostic inference interface.

Every model call in Juno — agentic, interactive, background, skill-internal —
goes through an `InferenceProvider`. Providers are interchangeable plugins;
adding a new one (Anthropic, Google, OpenAI-compatible, ...) means dropping a
new class under `server/inference/providers/` and wiring it into the router.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# Closed enum of routable task types. Used by the router to look up which
# provider should handle a given request. Adding a new task type means adding
# a routing entry to TaskRoutingConfig as well.
TaskType = Literal[
    "conversational",
    "agentic_reasoning",
    "background_summarization",
    "complex_tasks",
]

Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role
    content: str


class InferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[Message]
    task_type: TaskType
    # If set, overrides the provider's configured default model.
    model: str | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class InferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    model: str
    provider: str
    usage: TokenUsage = Field(default_factory=TokenUsage)


class InferenceChunk(BaseModel):
    """One incremental piece of a streaming response.

    `delta` is the new token(s) since the previous chunk. `done=True` marks
    the final chunk and may carry the final `usage` numbers.
    """

    model_config = ConfigDict(extra="forbid")

    delta: str = ""
    model: str
    provider: str
    done: bool = False
    usage: TokenUsage | None = None


class InferenceProviderError(Exception):
    """Raised when a provider fails to handle a request.

    The router uses this to decide whether to escalate to a fallback provider.
    """


class InferenceProvider(ABC):
    """Stable interface every provider plugin implements.

    Providers should be cheap to construct (constructor reads config, opens
    no network connections). Network work belongs in `complete` / `stream` /
    `is_available`.
    """

    id: str
    name: str

    @abstractmethod
    async def is_available(self) -> bool:
        """Quick health check. Must not raise — returns False on any failure."""

    @abstractmethod
    async def complete(self, request: InferenceRequest) -> InferenceResponse:
        """Single non-streaming completion."""

    @abstractmethod
    def stream(self, request: InferenceRequest) -> AsyncIterator[InferenceChunk]:
        """Stream a completion as incremental chunks.

        Implementations must actually stream — they may not buffer the full
        response and yield it as a single chunk.
        """

    async def aclose(self) -> None:
        """Release any held resources (HTTP clients, sockets, ...).

        Default is a no-op. Providers that hold connections override this.
        """
        return None
