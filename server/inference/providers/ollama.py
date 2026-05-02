"""Ollama inference provider.

Talks to a local Ollama server over its HTTP API. We use httpx directly rather
than the `ollama` Python client so we have full control over the streaming
parser and don't pick up an extra heavy dependency.

Ollama's chat endpoint:
  POST /api/chat
  body: {"model": str, "messages": [...], "stream": bool, "options": {...}}
  - stream=False: returns a single JSON object with `message.content`.
  - stream=True:  returns newline-delimited JSON, one object per chunk,
                  each with `message.content` (a delta) and `done` bool.
"""

from __future__ import annotations

import json
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
    TokenUsage,
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
        return InferenceResponse(
            content=data.get("message", {}).get("content", ""),
            model=data.get("model", model),
            provider=self.id,
            usage=_usage_from_ollama(data),
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

                    delta = chunk.get("message", {}).get("content", "")
                    done = bool(chunk.get("done", False))
                    yield InferenceChunk(
                        delta=delta,
                        model=chunk.get("model", model),
                        provider=self.id,
                        done=done,
                        usage=_usage_from_ollama(chunk) if done else None,
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
        return {
            "model": model,
            "messages": [m.model_dump() for m in request.messages],
            "stream": stream,
            "options": options,
        }


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
