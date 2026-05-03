"""Background API smoke tests against a stub inference provider."""

from __future__ import annotations

import asyncio
import json
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


class StubChat(InferenceProvider):
    id = "ollama"
    name = "stub"

    async def is_available(self) -> bool:
        return True

    async def complete(self, request: InferenceRequest) -> InferenceResponse:
        return InferenceResponse(
            content="ok",
            model="stub",
            provider=self.id,
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

    async def stream(
        self, request: InferenceRequest
    ) -> AsyncIterator[InferenceChunk]:
        yield InferenceChunk(delta="ok", model="stub", provider=self.id)
        yield InferenceChunk(model="stub", provider=self.id, done=True)


def _app(tmp_path: Path):
    """Build a TestClient app with paths rooted in tmp_path."""
    cfg_path = tmp_path / "config.yaml"
    config = load_config(cfg_path)
    # Override paths.base so reports/scheduler db live in tmp_path.
    config.paths.base = str(tmp_path / "juno")
    return create_app(config)


def test_list_jobs_returns_phase3_set(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        app.state.inference_router._providers["ollama"] = StubChat()
        body = client.get("/api/background/jobs").json()
        names = {j["name"] for j in body["jobs"]}
        assert names == {"rss", "email", "calendar", "messages"}
        for j in body["jobs"]:
            assert j["report_filename"].endswith(".md")
            assert j["schedule"]


def test_run_stub_job_writes_report(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        app.state.inference_router._providers["ollama"] = StubChat()
        r = client.post("/api/background/jobs/email/run")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "email"
        assert body["last_run"]["success"] is True

        reports = client.get("/api/background/reports").json()
        assert any(r["name"] == "email-digest.md" for r in reports["reports"])

        body = client.get("/api/background/reports/email-digest.md").text
        assert "Phase 3 placeholder" in body


def test_run_unknown_job_returns_404(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        app.state.inference_router._providers["ollama"] = StubChat()
        r = client.post("/api/background/jobs/nope/run")
        assert r.status_code == 404


def test_read_report_path_traversal_blocked(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        app.state.inference_router._providers["ollama"] = StubChat()
        r = client.get("/api/background/reports/..%2Fconfig.yaml")
        # Either the in-route guard (400) or Starlette URL normalization
        # rejecting the route (404) is acceptable — both prove the
        # traversal cannot reach a file outside reports_dir.
        assert r.status_code in {400, 404}
        # And the actual config.yaml above the reports dir must not have
        # been served.
        assert "ollama" not in r.text


def test_events_stream_delivers_published_event(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        app.state.inference_router._providers["ollama"] = StubChat()
        with client.websocket_connect("/api/events/stream") as ws:
            sub = ws.receive_json()
            assert sub == {"event": "subscribed", "topic": "interrupts"}

            # Publish an interrupt from the test side. asyncio.run-on-loop:
            # TestClient runs the app on its own loop, so use it.
            async def publish():
                await app.state.event_bus.publish(
                    "interrupts", {"kind": "test", "msg": "hi"}
                )

            # Use the underlying anyio portal that TestClient owns.
            client.portal.call(publish)

            frame = ws.receive_json()
            assert frame["event"] == "interrupt"
            assert frame["payload"] == {"kind": "test", "msg": "hi"}
