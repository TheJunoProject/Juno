"""Ollama inference provider.

Talks to a local Ollama server over its HTTP API. We use httpx directly rather
than the `ollama` Python client so we have full control over the streaming
parser and don't pick up an extra heavy dependency.

Ollama's chat endpoint:
  POST /api/chat
  body: {"model": str, "messages": [...], "tools": [...], "format": ...,
         "stream": bool, "options": {...}}
  - stream=False: returns a single JSON object with `message.content` and
                  optional `message.tool_calls`.
  - stream=True:  returns newline-delimited JSON, one object per chunk;
                  text chunks contain `message.content`; the final
                  `done=true` frame carries any `message.tool_calls`
                  (Ollama does not stream tool calls progressively).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx

from server.config.schema import OllamaProviderConfig
from server.inference.base import (
    InferenceChunk,
    InferenceProvider,
    InferenceProviderError,
    InferenceRequest,
    InferenceResponse,
    Message,
    TokenUsage,
    ToolCall,
)


class OllamaProvider(InferenceProvider):
    id = "ollama"
    name = "Ollama (local)"

    def __init__(self, config: OllamaProviderConfig) -> None:
        self._config = config
        # str() on HttpUrl gives the canonical form with trailing slash.
        # rstrip keeps URL-joining predictable below.
        self._base_url = str(config.base_url).rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.request_timeout_seconds),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def is_available(self) -> bool:
        try:
            r = await self._client.get(f"{self._base_url}/api/tags", timeout=5.0)
            return r.status_code == 200
        except (httpx.HTTPError, OSError):
            return False

    async def complete(self, request: InferenceRequest) -> InferenceResponse:
        model = request.model or self._config.default_model
        payload = self._build_payload(request, model, stream=False)
        try:
            r = await self._client.post(f"{self._base_url}/api/chat", json=payload)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise InferenceProviderError(
                f"Ollama request failed: {e}"
            ) from e

        data = r.json()
        message = data.get("message", {}) or {}
        return InferenceResponse(
            content=message.get("content", "") or "",
            model=data.get("model", model),
            provider=self.id,
            usage=_usage_from_ollama(data),
            tool_calls=_tool_calls_from_ollama(message.get("tool_calls")),
        )

    async def stream(
        self, request: InferenceRequest
    ) -> AsyncIterator[InferenceChunk]:
        model = request.model or self._config.default_model
        payload = self._build_payload(request, model, stream=True)

        try:
            async with self._client.stream(
                "POST", f"{self._base_url}/api/chat", json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        # Ollama only emits well-formed JSON lines; a malformed
                        # one means a network truncation. Skip and let the
                        # final `done` flag terminate the stream cleanly.
                        continue

                    message = chunk.get("message", {}) or {}
                    delta = message.get("content", "") or ""
                    done = bool(chunk.get("done", False))
                    yield InferenceChunk(
                        delta=delta,
                        model=chunk.get("model", model),
                        provider=self.id,
                        done=done,
                        usage=_usage_from_ollama(chunk) if done else None,
                        # Tool calls only arrive on the final frame.
                        tool_calls=(
                            _tool_calls_from_ollama(message.get("tool_calls"))
                            if done
                            else []
                        ),
                    )
        except httpx.HTTPError as e:
            raise InferenceProviderError(
                f"Ollama stream failed: {e}"
            ) from e

    def _build_payload(
        self,
        request: InferenceRequest,
        model: str,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        options: dict[str, Any] = {"temperature": request.temperature}
        if request.max_tokens is not None:
            # Ollama uses `num_predict` for the max-tokens equivalent.
            options["num_predict"] = request.max_tokens
        payload: dict[str, Any] = {
            "model": model,
            "messages": [_message_to_ollama(m) for m in request.messages],
            "stream": stream,
            "options": options,
        }
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in request.tools
            ]
        if request.response_format_json:
            # Ollama's `format: "json"` constrains output to valid JSON.
            # Use sparingly — combined with tool calls it can confuse some
            # models; the agentic loop never sets both at once.
            payload["format"] = "json"
        return payload


def _usage_from_ollama(data: dict[str, Any]) -> TokenUsage:
    """Pull token counts out of an Ollama response/chunk if present."""
    prompt = data.get("prompt_eval_count")
    completion = data.get("eval_count")
    total = None
    if isinstance(prompt, int) and isinstance(completion, int):
        total = prompt + completion
    return TokenUsage(
        prompt_tokens=prompt if isinstance(prompt, int) else None,
        completion_tokens=completion if isinstance(completion, int) else None,
        total_tokens=total,
    )


def _tool_calls_from_ollama(raw: Any) -> list[ToolCall]:
    """Normalise Ollama's tool_calls field into our ToolCall list.

    Ollama's shape: `[{"function": {"name": str, "arguments": dict}}]`.
    Some models (and some Ollama versions) emit `arguments` as a JSON
    string instead of an object — handle both. Synthesises a stable id
    when the provider doesn't supply one.
    """
    if not raw:
        return []
    out: list[ToolCall] = []
    for i, raw_call in enumerate(raw):
        fn = (raw_call or {}).get("function") or {}
        name = fn.get("name")
        if not name:
            continue
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                # Skip malformed argument blobs — better than crashing the
                # whole agentic turn.
                args = {}
        if not isinstance(args, dict):
            args = {}
        call_id = raw_call.get("id") or f"call_{i}_{uuid.uuid4().hex[:8]}"
        out.append(ToolCall(id=str(call_id), name=name, arguments=args))
    return out


def _message_to_ollama(m: Message) -> dict[str, Any]:
    """Render our Message into the dict shape Ollama expects.

    Ollama accepts the same role + content shape as OpenAI; tool messages
    use `role="tool"` + a `content` payload (Ollama is lenient about the
    `tool_call_id` / `name` fields and ignores them when present).
    """
    out: dict[str, Any] = {"role": m.role, "content": m.content}
    if m.tool_calls:
        out["tool_calls"] = [
            {
                "function": {
                    "name": tc.name,
                    "arguments": tc.arguments,
                }
            }
            for tc in m.tool_calls
        ]
    if m.tool_call_id is not None:
        out["tool_call_id"] = m.tool_call_id
    if m.name is not None:
        out["name"] = m.name
    return out
