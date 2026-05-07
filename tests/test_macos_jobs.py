"""Phase 5 background job tests (email / calendar / messages).

All three exercise the runtime against fake backends that record
calls + return canned data. None of them touch the user's actual
Mail / Calendar / Messages.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from server.agents.background.jobs.calendar import CalendarJob
from server.agents.background.jobs.email import EmailJob
from server.agents.background.jobs.messages import MessagesJob
from server.agents.background.jobs.base import JobContext
from server.config import JunoConfig
from server.config.paths import resolve_paths
from server.inference import InferenceRouter
from server.integrations.calendar.base import CalendarEvent
from server.integrations.email.base import (
    EmailMessage,
    EmailPermissionError,
)
from server.integrations.messages.base import Message
from server.scheduler import EventBus
from tests._fakes import (
    FakeCalendarBackend,
    FakeEmailBackend,
    FakeMessagesBackend,
    fake_router_for_config,
)


def _ctx(tmp_path: Path):
    config = JunoConfig()
    config.paths.base = str(tmp_path / "juno")
    paths = resolve_paths(config.paths)
    paths.ensure()
    inference = InferenceRouter(config.inference)
    integrations = fake_router_for_config(config)
    ctx = JobContext(
        config=config,
        reports_dir=paths.reports_dir,
        inference=inference,
        bus=EventBus(),
        integrations=integrations,
    )
    return ctx, integrations, inference


# ---- email job --------------------------------------------------------


async def test_email_job_renders_unread_list(tmp_path: Path) -> None:
    ctx, integrations, inference = _ctx(tmp_path)
    fake = FakeEmailBackend(
        messages=[
            EmailMessage(
                id="m1",
                subject="Lunch?",
                sender="Sam <sam@example.com>",
                received="2026-05-05T12:00:00",
                read=False,
            )
        ]
    )
    integrations._email[integrations._config.email.backend] = fake  # type: ignore[reportPrivateUsage]
    job = EmailJob(ctx)
    result = await job.run()
    assert result.report_filename == "email-digest.md"
    body = result.report_body
    assert "Lunch?" in body
    assert "Sam" in body
    assert "Fake email" in body
    await inference.aclose()


async def test_email_job_renders_inbox_clear_on_empty(tmp_path: Path) -> None:
    ctx, integrations, inference = _ctx(tmp_path)
    integrations._email[integrations._config.email.backend] = FakeEmailBackend()  # type: ignore[reportPrivateUsage]
    result = await EmailJob(ctx).run()
    assert "Inbox is clear" in result.report_body
    await inference.aclose()


async def test_email_job_handles_permission_error(tmp_path: Path) -> None:
    ctx, integrations, inference = _ctx(tmp_path)

    class BoomEmail(FakeEmailBackend):
        async def recent_unread(self, *, limit: int):
            raise EmailPermissionError("permission required (test)")

    integrations._email[integrations._config.email.backend] = BoomEmail()  # type: ignore[reportPrivateUsage]
    result = await EmailJob(ctx).run()
    assert "Permission required" in result.report_body
    assert "permission required (test)" in result.report_body
    await inference.aclose()


# ---- calendar job -----------------------------------------------------


async def test_calendar_job_renders_today_and_tomorrow(tmp_path: Path) -> None:
    ctx, integrations, inference = _ctx(tmp_path)
    fake = FakeCalendarBackend(
        events=[
            CalendarEvent(
                id="e1",
                summary="Standup",
                calendar="Work",
                start="2026-05-06T10:00:00",
                end="2026-05-06T10:15:00",
                location="",
                all_day=False,
            )
        ]
    )
    integrations._calendar[integrations._config.calendar.backend] = fake  # type: ignore[reportPrivateUsage]
    result = await CalendarJob(ctx).run()
    body = result.report_body
    assert "Standup" in body
    assert "## Today" in body
    assert "## Tomorrow" in body
    assert "Fake calendar" in body
    await inference.aclose()


# ---- messages job -----------------------------------------------------


async def test_messages_job_groups_by_thread(tmp_path: Path) -> None:
    ctx, integrations, inference = _ctx(tmp_path)
    fake = FakeMessagesBackend(
        messages=[
            Message(
                sender="+15551234567",
                text="running 5 late",
                received_at="2026-05-06T08:55:00",
                chat="",
            ),
            Message(
                sender="+15551234567",
                text="actually 10",
                received_at="2026-05-06T08:57:00",
                chat="",
            ),
        ]
    )
    integrations._messages[integrations._config.messages.backend] = fake  # type: ignore[reportPrivateUsage]
    result = await MessagesJob(ctx).run()
    body = result.report_body
    assert "running 5 late" in body
    assert "actually 10" in body
    assert "Fake messages" in body
    # Both messages share a thread key (sender), so should appear under
    # one ### section.
    assert body.count("### +15551234567") == 1
    await inference.aclose()
