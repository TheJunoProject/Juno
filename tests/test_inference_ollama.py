"""Ollama provider tests.

The live "real Ollama" test runs only when JUNO_TEST_OLLAMA=1 is set, so the
suite stays green on machines without Ollama installed. The mocked tests
exercise the same code paths against a fake transport.
"""

from __future__ import annotations

import json
import os

import httpx
import pytest

from server.config.schema import OllamaProviderConfig
from server.inference.base import InferenceRequest, Message
from server.inference.providers.ollama import OllamaProvider


def _provider_with_transport(transport: httpx.MockTransport) -> OllamaProvider:
    cfg = OllamaProviderConfig()
    p = OllamaProvider(cfg)
    # Swap the live AsyncClient for one wired to the mock transport so the
    # provider speaks to a fake Ollama with the same code path it would use
    # against the real server.
    p._client = httpx.AsyncClient(transport=transport, timeout=5.0)
    return p


async def test_is_available_true_on_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": []})

    p = _provider_with_transport(httpx.MockTransport(handler))
    try:
        assert await p.is_available() is True
    finally:
        await p.aclose()


async def test_is_available_false_on_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    p = _provider_with_transport(httpx.MockTransport(handler))
    try:
        assert await p.is_available() is False
    finally:
        await p.aclose()


async def test_complete_returns_content_and_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "qwen2.5:7b"
        assert body["stream"] is False
        return httpx.Response(
            200,
            json={
                "model": "qwen2.5:7b",
                "message": {"role": "assistant", "content": "Hello!"},
                "prompt_eval_count": 10,
                "eval_count": 5,
            },
        )

    p = _provider_with_transport(httpx.MockTransport(handler))
    try:
        resp = await p.complete(
            InferenceRequest(
                messages=[Message(role="user", content="hi")],
                task_type="conversational",
            )
        )
        assert resp.content == "Hello!"
        assert resp.provider == "ollama"
        assert resp.model == "qwen2.5:7b"
        assert resp.usage.prompt_tokens == 10
        assert resp.usage.completion_tokens == 5
        assert resp.usage.total_tokens == 15
    finally:
        await p.aclose()


async def test_stream_yields_chunks_and_terminates_on_done() -> None:
    chunks = [
        {"model": "qwen2.5:7b", "message": {"content": "Hel"}, "done": False},
        {"model": "qwen2.5:7b", "message": {"content": "lo"}, "done": False},
        {
            "model": "qwen2.5:7b",
            "message": {"content": "!"},
            "done": True,
            "prompt_eval_count": 3,
            "eval_count": 2,
        },
    ]
    body = ("\n".join(json.dumps(c) for c in chunks) + "\n").encode("utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(200, content=body)

    p = _provider_with_transport(httpx.MockTransport(handler))
    try:
        deltas: list[str] = []
        saw_done = False
        async for chunk in p.stream(
            InferenceRequest(
                messages=[Message(role="user", content="hi")],
                task_type="conversational",
            )
        ):
            if chunk.delta:
                deltas.append(chunk.delta)
            if chunk.done:
                saw_done = True
                assert chunk.usage is not None
                assert chunk.usage.total_tokens == 5
        assert "".join(deltas) == "Hello!"
        assert saw_done is True
    finally:
        await p.aclose()


@pytest.mark.skipif(
    os.environ.get("JUNO_TEST_OLLAMA") != "1",
    reason="Set JUNO_TEST_OLLAMA=1 to run live Ollama integration test.",
)
async def test_live_ollama_says_hello() -> None:
    """End-to-end: real Ollama, real model, simple greeting."""
    p = OllamaProvider(OllamaProviderConfig())
    try:
        assert await p.is_available(), "Ollama must be running for this test."
        resp = await p.complete(
            InferenceRequest(
                messages=[Message(role="user", content="Say hello in one word.")],
                task_type="conversational",
                temperature=0.0,
            )
        )
        assert resp.content.strip() != ""
    finally:
        await p.aclose()
