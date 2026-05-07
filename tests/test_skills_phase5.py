"""Phase 5 skill tests against fake integration backends.

The fakes record every call so tests assert both the outward result
the agent sees AND the side effect the backend would have produced.
Nothing here touches real Mail / Calendar / Messages / Apple Events.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from server.config import JunoConfig
from server.config.paths import resolve_paths
from server.inference import InferenceRouter
from server.integrations.calendar.base import CalendarEvent
from server.integrations.email.base import EmailMessage
from server.integrations.messages.base import Message
from server.scheduler import EventBus
from server.skills import SkillContext, SkillError
from server.skills.calendar.skill import CalendarSkill
from server.skills.email.skill import EmailSkill
from server.skills.messages.skill import MessagesSkill
from server.skills.system.skill import SystemSkill
from tests._fakes import (
    FakeCalendarBackend,
    FakeEmailBackend,
    FakeMessagesBackend,
    FakeSystemBackend,
    fake_router_for_config,
)


def _ctx(tmp_path: Path) -> SkillContext:
    config = JunoConfig()
    config.paths.base = str(tmp_path / "juno")
    paths = resolve_paths(config.paths)
    paths.ensure()
    inference = InferenceRouter(config.inference)
    return SkillContext(
        config=config,
        paths=paths,
        inference=inference,
        bus=EventBus(),
        sandbox_dir=paths.base / "skill-data",
        integrations=fake_router_for_config(config),
    )


def _put_email_backend(ctx: SkillContext, fake: FakeEmailBackend) -> None:
    """Hot-swap the email backend on the test router."""
    router = ctx.integrations
    router._email[router._config.email.backend] = fake  # type: ignore[reportPrivateUsage]


def _put_calendar_backend(ctx: SkillContext, fake: FakeCalendarBackend) -> None:
    router = ctx.integrations
    router._calendar[router._config.calendar.backend] = fake  # type: ignore[reportPrivateUsage]


def _put_messages_backend(ctx: SkillContext, fake: FakeMessagesBackend) -> None:
    router = ctx.integrations
    router._messages[router._config.messages.backend] = fake  # type: ignore[reportPrivateUsage]


def _put_system_backend(ctx: SkillContext, fake: FakeSystemBackend) -> None:
    router = ctx.integrations
    router._system[router._config.system.backend] = fake  # type: ignore[reportPrivateUsage]


# ---- email skill -------------------------------------------------------


async def test_email_recent_returns_normalised_messages(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    fake = FakeEmailBackend(
        messages=[
            EmailMessage(
                id="m1",
                subject="Lunch?",
                sender="Sam <sam@example.com>",
                received="2026-05-05T12:00:00",
                read=False,
            ),
        ]
    )
    _put_email_backend(ctx, fake)
    out = await EmailSkill().execute({"mode": "recent", "limit": 5}, ctx)
    assert out.output["count"] == 1
    assert out.output["messages"][0]["subject"] == "Lunch?"
    assert out.output["backend"] == "fake_email"
    await ctx.inference.aclose()


async def test_email_send_records_call(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    fake = FakeEmailBackend()
    _put_email_backend(ctx, fake)
    out = await EmailSkill().execute(
        {
            "mode": "send",
            "to": "sam@example.com",
            "subject": "Re: Lunch?",
            "body": "Sounds good.",
        },
        ctx,
    )
    assert out.output["result"].startswith("sent to")
    assert fake.sent == [
        {"to": "sam@example.com", "subject": "Re: Lunch?", "body": "Sounds good."}
    ]
    await ctx.inference.aclose()


async def test_email_send_rejects_missing_to(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    _put_email_backend(ctx, FakeEmailBackend())
    with pytest.raises(SkillError):
        await EmailSkill().execute({"mode": "send", "body": "hi"}, ctx)
    await ctx.inference.aclose()


# ---- calendar skill ----------------------------------------------------


async def test_calendar_today_returns_events(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
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
    _put_calendar_backend(ctx, fake)
    out = await CalendarSkill().execute({"mode": "today"}, ctx)
    assert out.output["events"][0]["summary"] == "Standup"
    assert out.output["backend"] == "fake_calendar"
    await ctx.inference.aclose()


async def test_calendar_create_records_call(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    fake = FakeCalendarBackend()
    _put_calendar_backend(ctx, fake)
    out = await CalendarSkill().execute(
        {
            "mode": "create",
            "calendar": "Personal",
            "summary": "Lunch with Sam",
            "start": "2026-05-15T13:00:00",
            "end": "2026-05-15T14:00:00",
            "location": "Pearl Street",
        },
        ctx,
    )
    assert out.output["uid"] == "fake-uid-123"
    assert fake.created[0]["summary"] == "Lunch with Sam"
    await ctx.inference.aclose()


async def test_calendar_create_picks_first_calendar_when_unspecified(
    tmp_path: Path,
) -> None:
    ctx = _ctx(tmp_path)
    fake = FakeCalendarBackend()
    _put_calendar_backend(ctx, fake)
    out = await CalendarSkill().execute(
        {
            "mode": "create",
            "summary": "X",
            "start": "2026-05-15T13:00:00",
            "end": "2026-05-15T14:00:00",
        },
        ctx,
    )
    # Fake returns ["Test"] from list_calendars.
    assert fake.created[0]["calendar"] == "Test"
    await ctx.inference.aclose()


async def test_calendar_create_rejects_inverted_range(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    _put_calendar_backend(ctx, FakeCalendarBackend())
    with pytest.raises(SkillError):
        await CalendarSkill().execute(
            {
                "mode": "create",
                "summary": "x",
                "calendar": "Test",
                "start": "2026-05-15T14:00:00",
                "end": "2026-05-15T13:00:00",
            },
            ctx,
        )
    await ctx.inference.aclose()


# ---- messages skill ----------------------------------------------------


async def test_messages_recent_returns_inbound(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    fake = FakeMessagesBackend(
        messages=[
            Message(
                sender="+15551234567",
                text="running 5 late",
                received_at="2026-05-06T08:55:00",
                chat="",
            )
        ]
    )
    _put_messages_backend(ctx, fake)
    out = await MessagesSkill().execute({"mode": "recent"}, ctx)
    assert out.output["count"] == 1
    assert out.output["messages"][0]["text"] == "running 5 late"
    await ctx.inference.aclose()


async def test_messages_send_records_call(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    fake = FakeMessagesBackend()
    _put_messages_backend(ctx, fake)
    await MessagesSkill().execute(
        {"mode": "send", "to": "+15551234567", "body": "ok see you soon"}, ctx
    )
    assert fake.sent == [{"to": "+15551234567", "body": "ok see you soon"}]
    await ctx.inference.aclose()


# ---- system skill ------------------------------------------------------


async def test_system_apps_list(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    _put_system_backend(ctx, FakeSystemBackend())
    out = await SystemSkill().execute({"mode": "apps_list"}, ctx)
    assert "AppOne" in out.output["result"]
    await ctx.inference.aclose()


async def test_system_app_launch_records_call(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    fake = FakeSystemBackend()
    _put_system_backend(ctx, fake)
    await SystemSkill().execute({"mode": "app_launch", "app": "Safari"}, ctx)
    assert fake.launched == ["Safari"]
    await ctx.inference.aclose()


async def test_system_volume_set_clamps_invalid(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    fake = FakeSystemBackend()
    _put_system_backend(ctx, fake)
    with pytest.raises(SkillError):
        await SystemSkill().execute(
            {"mode": "volume_set", "volume": "not-a-number"}, ctx
        )
    await ctx.inference.aclose()


async def test_system_screenshot_writes_file(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    fake = FakeSystemBackend()
    _put_system_backend(ctx, fake)
    out = await SystemSkill().execute({"mode": "screenshot"}, ctx)
    target = Path(out.output["result"])
    assert target.is_file()
    assert target.stat().st_size > 0
    await ctx.inference.aclose()
