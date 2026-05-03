"""Background job + runtime tests.

Heavy use of stub providers + httpx mock transport so nothing in here
needs the network or a real model.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from server.agents.background.jobs import (
    BackgroundJob,
    CalendarStubJob,
    EmailStubJob,
    JobContext,
    JobResult,
    MessagesStubJob,
    RSSJob,
)
from server.agents.background.runtime import BackgroundRuntime
from server.config import (
    BackgroundConfig,
    BackgroundJobsConfig,
    InferenceConfig,
    JunoConfig,
    OllamaProviderConfig,
    PathsConfig,
    ProvidersConfig,
    RSSJobConfig,
    StubJobConfig,
)
from server.inference import InferenceRouter
from server.inference.base import (
    InferenceChunk,
    InferenceProvider,
    InferenceRequest,
    InferenceResponse,
    TokenUsage,
)
from server.scheduler import EventBus, JunoScheduler


# ---- helpers -----------------------------------------------------------


class StubInference(InferenceProvider):
    id = "ollama"
    name = "stub"

    def __init__(self, summary: str = "Today's news at a glance.") -> None:
        self._summary = summary

    async def is_available(self) -> bool:
        return True

    async def complete(self, request: InferenceRequest) -> InferenceResponse:
        return InferenceResponse(
            content=self._summary,
            model="stub-model",
            provider=self.id,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    async def stream(
        self, request: InferenceRequest
    ) -> AsyncIterator[InferenceChunk]:
        yield InferenceChunk(
            delta=self._summary, model="stub-model", provider=self.id
        )
        yield InferenceChunk(model="stub-model", provider=self.id, done=True)


def _config_with_feeds(feeds: list[str], summarize: bool = True) -> JunoConfig:
    return JunoConfig(
        paths=PathsConfig(),
        inference=InferenceConfig(
            providers=ProvidersConfig(ollama=OllamaProviderConfig()),
        ),
        background=BackgroundConfig(
            enabled=True,
            persist_jobs=False,
            jobs=BackgroundJobsConfig(
                rss=RSSJobConfig(
                    feeds=feeds,
                    max_items_per_feed=3,
                    summarize=summarize,
                ),
                email=StubJobConfig(),
                calendar=StubJobConfig(),
                messages=StubJobConfig(),
            ),
        ),
    )


def _ctx(
    config: JunoConfig,
    reports_dir: Path,
    inference: InferenceRouter,
) -> JobContext:
    return JobContext(
        config=config,
        reports_dir=reports_dir,
        inference=inference,
        bus=EventBus(),
    )


# ---- stub jobs ---------------------------------------------------------


async def test_email_stub_writes_placeholder(tmp_path: Path) -> None:
    config = _config_with_feeds([])
    inference = InferenceRouter(config.inference)
    job = EmailStubJob(_ctx(config, tmp_path, inference))
    result = await job.run()
    assert result.report_filename == "email-digest.md"
    assert "Phase 3 placeholder" in result.report_body
    assert "email" in result.report_body.lower()
    await inference.aclose()


async def test_calendar_stub_writes_placeholder(tmp_path: Path) -> None:
    config = _config_with_feeds([])
    inference = InferenceRouter(config.inference)
    job = CalendarStubJob(_ctx(config, tmp_path, inference))
    result = await job.run()
    assert result.report_filename == "calendar.md"
    assert "Phase 3 placeholder" in result.report_body
    await inference.aclose()


async def test_messages_stub_writes_placeholder(tmp_path: Path) -> None:
    config = _config_with_feeds([])
    inference = InferenceRouter(config.inference)
    job = MessagesStubJob(_ctx(config, tmp_path, inference))
    result = await job.run()
    assert result.report_filename == "messages.md"
    assert "Phase 3 placeholder" in result.report_body
    await inference.aclose()


# ---- RSS job (with mock HTTP) ------------------------------------------


SAMPLE_RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Test Feed</title>
  <item>
    <title>First story</title>
    <link>https://example.com/1</link>
    <description>An &amp;lt;b&amp;gt;exciting&amp;lt;/b&amp;gt; thing happened.</description>
  </item>
  <item>
    <title>Second story</title>
    <link>https://example.com/2</link>
    <description>Another thing.</description>
  </item>
</channel></rss>
"""


def _mock_feed_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=SAMPLE_RSS)

    return httpx.MockTransport(handler)


@pytest.fixture
def patch_httpx(monkeypatch):
    """Replace httpx.AsyncClient with one wired to a mock transport so the
    RSS job never touches the network."""
    transport = _mock_feed_transport()
    real_init = httpx.AsyncClient.__init__

    def fake_init(self, *args, **kwargs):
        kwargs.pop("timeout", None)
        kwargs.pop("follow_redirects", None)
        kwargs.pop("headers", None)
        real_init(self, transport=transport, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", fake_init)
    yield


async def test_rss_job_without_summary_lists_titles(
    tmp_path: Path, patch_httpx
) -> None:
    config = _config_with_feeds(
        ["https://example.com/feed.xml"], summarize=False
    )
    inference = InferenceRouter(config.inference)
    job = RSSJob(_ctx(config, tmp_path, inference))
    result = await job.run()
    assert result.report_filename == "news.md"
    assert "First story" in result.report_body
    assert "https://example.com/1" in result.report_body
    # No summary section when summarize=False.
    assert "## Summary" not in result.report_body
    await inference.aclose()


async def test_rss_job_with_summary_calls_inference(
    tmp_path: Path, patch_httpx
) -> None:
    config = _config_with_feeds(
        ["https://example.com/feed.xml"], summarize=True
    )
    inference = InferenceRouter(config.inference)
    # Swap the provider for our stub so we don't hit Ollama.
    inference._providers["ollama"] = StubInference(
        summary="The day's stories were quiet."
    )
    job = RSSJob(_ctx(config, tmp_path, inference))
    result = await job.run()
    assert "## Summary" in result.report_body
    assert "The day's stories were quiet." in result.report_body
    # Raw items list still present for verification.
    assert "First story" in result.report_body
    await inference.aclose()


async def test_rss_job_with_failing_summariser_falls_back_to_titles(
    tmp_path: Path, patch_httpx
) -> None:
    """A summariser failure must not break the whole job."""

    class ExplodingInference(InferenceProvider):
        id = "ollama"
        name = "boom"

        async def is_available(self) -> bool:
            return True

        async def complete(self, request):  # noqa: ANN001
            raise RuntimeError("model exploded")

        async def stream(self, request):  # noqa: ANN001
            raise RuntimeError("model exploded")
            yield  # pragma: no cover  (unreachable, satisfies async-gen typing)

    config = _config_with_feeds(
        ["https://example.com/feed.xml"], summarize=True
    )
    inference = InferenceRouter(config.inference)
    inference._providers["ollama"] = ExplodingInference()
    job = RSSJob(_ctx(config, tmp_path, inference))
    result = await job.run()
    assert "Summariser unavailable" in result.report_body
    assert "First story" in result.report_body
    await inference.aclose()


# ---- BackgroundRuntime end-to-end --------------------------------------


async def test_runtime_writes_report_to_disk(
    tmp_path: Path, patch_httpx
) -> None:
    config = _config_with_feeds(
        ["https://example.com/feed.xml"], summarize=False
    )
    inference = InferenceRouter(config.inference)
    bus = EventBus()
    scheduler = JunoScheduler(persist_db_path=None)
    scheduler.start()
    try:
        runtime = BackgroundRuntime(
            config,
            reports_dir=tmp_path / "reports",
            inference=inference,
            bus=bus,
            scheduler=scheduler,
        )
        runtime.register_default_jobs()

        # Manual trigger, no waiting for cron.
        await runtime.run_now("rss")
        report = (tmp_path / "reports" / "news.md").read_text()
        assert "First story" in report

        jobs = runtime.list_jobs()
        names = {j["name"] for j in jobs}
        assert names == {"rss", "email", "calendar", "messages"}
        rss_info = next(j for j in jobs if j["name"] == "rss")
        assert rss_info["last_run"]["success"] is True

        reports = runtime.list_reports()
        assert any(r["name"] == "news.md" for r in reports)
    finally:
        scheduler.shutdown()
        await inference.aclose()


async def test_runtime_records_failed_run(tmp_path: Path) -> None:
    """A job that throws records success=False but doesn't crash the runtime."""
    config = _config_with_feeds([], summarize=False)
    inference = InferenceRouter(config.inference)
    bus = EventBus()
    scheduler = JunoScheduler(persist_db_path=None)
    scheduler.start()
    try:
        runtime = BackgroundRuntime(
            config,
            reports_dir=tmp_path / "reports",
            inference=inference,
            bus=bus,
            scheduler=scheduler,
        )

        class BoomJob(BackgroundJob):
            name = "boom"

            async def run(self) -> JobResult:
                raise RuntimeError("kaboom")

        # Hand-register so we don't need to add the boom job to config.
        runtime._register(  # type: ignore[reportPrivateUsage]
            BoomJob(_ctx(config, tmp_path / "reports", inference)),
            "0 0 1 1 *",
        )
        await runtime.run_now("boom")
        jobs = runtime.list_jobs()
        boom = next(j for j in jobs if j["name"] == "boom")
        assert boom["last_run"]["success"] is False
        assert "kaboom" in boom["last_run"]["error"]
    finally:
        scheduler.shutdown()
        await inference.aclose()
