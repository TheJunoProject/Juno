"""Background API smoke tests against stub providers + fake integrations.

These NEVER touch real macOS apps — `install_fake_integrations` swaps
the live IntegrationsRouter backends for in-memory fakes before any
job runs.
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
from tests._fakes import install_fake_integrations


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
    config.paths.base = str(tmp_path / "juno")
    return create_app(config)


def _wire(app):  # noqa: ANN001
    """Common test wiring: stub chat provider + fake macOS integrations.

    Returns the fake-backend dict so individual tests can assert
    against `.sent`, `.created`, etc.
    """
    app.state.inference_router._providers["ollama"] = StubChat()
    return install_fake_integrations(app)


def test_list_jobs_returns_phase3_set(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        _wire(app)
        body = client.get("/api/background/jobs").json()
        names = {j["name"] for j in body["jobs"]}
        assert names == {"rss", "email", "calendar", "messages"}
        for j in body["jobs"]:
            assert j["report_filename"].endswith(".md")
            assert j["schedule"]


def test_run_email_job_writes_report(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        _wire(app)
        r = client.post("/api/background/jobs/email/run")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "email"
        assert body["last_run"]["success"] is True

        reports = client.get("/api/background/reports").json()
        assert any(r["name"] == "email-digest.md" for r in reports["reports"])

        report = client.get("/api/background/reports/email-digest.md").text
        # Empty fake inbox -> "Inbox is clear" report.
        assert "Inbox is clear" in report
        # The report MUST identify which backend produced it.
        assert "Fake email" in report


def test_run_unknown_job_returns_404(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        _wire(app)
        r = client.post("/api/background/jobs/nope/run")
        assert r.status_code == 404


def test_read_report_path_traversal_blocked(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        _wire(app)
        r = client.get("/api/background/reports/..%2Fconfig.yaml")
        assert r.status_code in {400, 404}
        assert "ollama" not in r.text


def test_events_stream_delivers_published_event(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        _wire(app)
        with client.websocket_connect("/api/events/stream") as ws:
            sub = ws.receive_json()
            assert sub == {"event": "subscribed", "topic": "interrupts"}

            async def publish():
                await app.state.event_bus.publish(
                    "interrupts", {"kind": "test", "msg": "hi"}
                )

            client.portal.call(publish)

            frame = ws.receive_json()
            assert frame["event"] == "interrupt"
            assert frame["payload"] == {"kind": "test", "msg": "hi"}


def test_health_includes_integrations_block(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        _wire(app)
        body = client.get("/api/health").json()
        assert "integrations" in body and body["integrations"] is not None
        intg = body["integrations"]
        for domain in ("email", "calendar", "messages", "system"):
            assert domain in intg
            # Each domain has at least one backend listed; one should be
            # selected.
            entries = intg[domain]
            assert any(v["selected"] for v in entries.values()), domain
