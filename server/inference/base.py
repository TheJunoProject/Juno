"""Provider-agnostic inference interface.

Every model call in Juno — agentic, interactive, background, skill-internal —
goes through an `InferenceProvider`. Providers are interchangeable plugins;
adding a new one (Anthropic, Google, OpenAI-compatible, ...) means dropping a
new class under `server/inference/providers/` and wiring it into the router.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# Closed enum of routable task types. Used by the router to look up which
# provider should handle a given request. Adding a new task type means adding
# a routing entry to TaskRoutingConfig as well.
TaskType = Literal[
    "conversational",
    "agentic_reasoning",
    "intent_classification",
    "background_summarization",
    "complex_tasks",
]

# Adds "tool" to the conversational role set so we can echo tool results
# back into the model's context as proper tool messages (per Ollama /
# OpenAI tool-call convention).
Role = Literal["system", "user", "assistant", "tool"]


class ToolCall(BaseModel):
    """One model-emitted tool call in a single assistant turn."""

    model_config = ConfigDict(extra="forbid")

    # Provider-emitted call id when present (some backends use it to
    # correlate result messages back to the originating call). Synthesised
    # from the call index when the provider doesn't send one.
    id: str
    name: str
    # Parsed arguments object. Providers that emit tool calls as JSON
    # strings are parsed into a dict by the provider adapter before this
    # model is constructed.
    arguments: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role
    # Text content. Empty string is valid for assistant turns whose only
    # output is a tool call.
    content: str = ""
    # Populated on assistant turns when the model called tools.
    tool_calls: list[ToolCall] = Field(default_factory=list)
    # Set on `role="tool"` messages: the call id this result corresponds
    # to, and the tool name (echoed for clarity / model-side disambiguation).
    tool_call_id: str | None = None
    name: str | None = None


class Tool(BaseModel):
    """Tool definition passed to the model.

    Mirrors the OpenAI / Ollama function-tool shape. The Agentic Layer
    derives one of these from each registered Skill's manifest.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    # JSON Schema for the input. Providers send this verbatim to the
    # model, so it must conform to JSON Schema draft 7 (the de facto
    # standard tool-calling backends accept).
    parameters: dict[str, Any]


class InferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[Message]
    task_type: TaskType
    # If set, overrides the provider's configured default model.
    model: str | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    # Tools the model may call. Empty = no tool calling for this request.
    # Providers that don't support tool calls ignore this field; the
    # router's task_routing should keep tool-using tasks pointed at
    # tool-capable models.
    tools: list[Tool] = Field(default_factory=list)
    # When True the model is told to produce a JSON object as its only
    # output. Used by the intent classifier and other structured calls.
    response_format_json: bool = False


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
    # Populated when the model emitted tool calls instead of (or in
    # addition to) free text. Empty list when no tools were called.
    tool_calls: list[ToolCall] = Field(default_factory=list)


class InferenceChunk(BaseModel):
    """One incremental piece of a streaming response.

    `delta` is the new token(s) since the previous chunk. `done=True` marks
    the final chunk and may carry the final `usage` numbers and any
    accumulated tool calls (Ollama emits tool_calls only on the final
    `done=true` frame, not progressively).
    """

    model_config = ConfigDict(extra="forbid")

    delta: str = ""
    model: str
    provider: str
    done: bool = False
    usage: TokenUsage | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


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
