"""Inference router.

Owns the live set of provider instances and dispatches each `InferenceRequest`
to the right one based on its `task_type`.

Phase 1 keeps the routing simple: a config-driven lookup, plus optional
fallback to a second provider after `escalation_attempts` failures. The plan
in CLAUDE.md is to evolve this into a small classifier that also weighs cost
policy, provider health, and per-task overrides — but the call surface stays
the same so callers don't have to change when that lands.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from server.config.schema import InferenceConfig
from server.inference.base import (
    InferenceChunk,
    InferenceProvider,
    InferenceProviderError,
    InferenceRequest,
    InferenceResponse,
    TaskType,
)
from server.inference.providers.ollama import OllamaProvider

log = logging.getLogger(__name__)


class InferenceRouter:
    def __init__(self, config: InferenceConfig) -> None:
        self._config = config
        self._providers: dict[str, InferenceProvider] = {}
        self._build_providers()

    def _build_providers(self) -> None:
        # Phase 1 only ships the Ollama provider. New providers added here
        # keyed by their `id`; everything else (router lookup, fallback) keeps
        # working unchanged.
        self._providers["ollama"] = OllamaProvider(self._config.providers.ollama)

    def get_provider(self, provider_id: str) -> InferenceProvider:
        if provider_id not in self._providers:
            raise KeyError(f"No inference provider registered for '{provider_id}'")
        return self._providers[provider_id]

    def provider_for_task(self, task_type: TaskType) -> InferenceProvider:
        provider_id: str = getattr(self._config.task_routing, task_type)
        return self.get_provider(provider_id)

    def all_providers(self) -> dict[str, InferenceProvider]:
        return dict(self._providers)

    async def complete(self, request: InferenceRequest) -> InferenceResponse:
        primary = self.provider_for_task(request.task_type)
        attempts = max(1, self._config.escalation_attempts)
        last_error: InferenceProviderError | None = None

        for attempt in range(1, attempts + 1):
            try:
                return await primary.complete(request)
            except InferenceProviderError as e:
                last_error = e
                log.warning(
                    "Provider %s failed on attempt %d/%d for task %s: %s",
                    primary.id,
                    attempt,
                    attempts,
                    request.task_type,
                    e,
                )

        fallback_id = self._config.fallback_provider
        if fallback_id and fallback_id in self._providers:
            log.info("Escalating to fallback provider %s", fallback_id)
            return await self._providers[fallback_id].complete(request)

        assert last_error is not None
        raise last_error

    async def stream(
        self, request: InferenceRequest
    ) -> AsyncIterator[InferenceChunk]:
        # Streaming intentionally does not retry: by the time the first chunk
        # has been forwarded to the client, switching providers mid-stream
        # would produce a corrupt response. Failures bubble to the caller.
        primary = self.provider_for_task(request.task_type)
        async for chunk in primary.stream(request):
            yield chunk

    async def aclose(self) -> None:
        for p in self._providers.values():
            await p.aclose()
