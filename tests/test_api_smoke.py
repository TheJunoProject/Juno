"""API smoke tests using FastAPI's TestClient + a stubbed inference router.

These verify the wiring (routes, error handling, app lifespan) without
needing a real Ollama running.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from fastapi.testclient import TestClient

from server.api.app import create_app
from server.config import load_config
from server.inference.base import (
    InferenceChunk,
    InferenceProvider,
    InferenceRequest,
    InferenceResponse,
    TokenUsage,
)


class StubProvider(InferenceProvider):
    id = "ollama"
    name = "stub"

    def __init__(self, *, available: bool = True) -> None:
        self._available = available

    async def is_available(self) -> bool:
        return self._available

    async def complete(self, request: InferenceRequest) -> InferenceResponse:
        last = request.messages[-1].content
        return InferenceResponse(
            content=f"echo: {last}",
            model="stub-model",
            provider=self.id,
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

    async def stream(
        self, request: InferenceRequest
    ) -> AsyncIterator[InferenceChunk]:
        for piece in ["echo:", " ", request.messages[-1].content]:
            yield InferenceChunk(delta=piece, model="stub-model", provider=self.id)
        yield InferenceChunk(model="stub-model", provider=self.id, done=True)


def _stub_app(tmp_path: Path, *, available: bool = True):
    cfg_path = tmp_path / "config.yaml"
    config = load_config(cfg_path)
    app = create_app(config, reports_dir=tmp_path / "reports")

    # Patch the router's registered ollama provider with a stub once the
    # lifespan has constructed it. TestClient uses the lifespan context, so
    # we hook in via the dependency-free `app.state` after entering the
    # context manager.
    return app, cfg_path


def test_health_reports_provider_state(tmp_path: Path) -> None:
    app, _ = _stub_app(tmp_path)
    with TestClient(app) as client:
        # Replace the live ollama provider with our stub.
        app.state.inference_router._providers["ollama"] = StubProvider(available=True)
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["providers"]["ollama"]["available"] is True
        assert body["providers"]["ollama"]["model"] == "qwen2.5:7b"


def test_health_when_provider_unavailable(tmp_path: Path) -> None:
    app, _ = _stub_app(tmp_path)
    with TestClient(app) as client:
        app.state.inference_router._providers["ollama"] = StubProvider(available=False)
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["providers"]["ollama"]["available"] is False


def test_chat_returns_response_and_session_id(tmp_path: Path) -> None:
    app, _ = _stub_app(tmp_path)
    with TestClient(app) as client:
        app.state.inference_router._providers["ollama"] = StubProvider()
        r = client.post("/api/chat", json={"message": "hello"})
        assert r.status_code == 200
        body = r.json()
        assert body["response"] == "echo: hello"
        assert body["provider"] == "ollama"
        assert body["model"] == "stub-model"
        assert body["session_id"]


def test_chat_websocket_streams_chunks(tmp_path: Path) -> None:
    app, _ = _stub_app(tmp_path)
    with TestClient(app) as client:
        app.state.inference_router._providers["ollama"] = StubProvider()
        with client.websocket_connect("/api/chat/stream") as ws:
            ws.send_json({"message": "hello", "session_id": None})
            collected: list[str] = []
            saw_intent = False
            done_seen = False
            for _ in range(20):
                frame = ws.receive_json()
                if frame.get("event") == "intent":
                    saw_intent = True
                    continue
                if frame.get("done"):
                    done_seen = True
                    break
                if "delta" in frame:
                    collected.append(frame["delta"])
            assert saw_intent, "Phase 4 wire format must lead with an intent frame"
            assert done_seen
            assert "".join(collected) == "echo: hello"


def test_chat_validation_rejects_empty_message(tmp_path: Path) -> None:
    app, _ = _stub_app(tmp_path)
    with TestClient(app) as client:
        app.state.inference_router._providers["ollama"] = StubProvider()
        r = client.post("/api/chat", json={"message": ""})
        assert r.status_code == 422
