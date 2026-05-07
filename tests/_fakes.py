"""Fakes shared by Phase 5 tests.

Anything that talks to macOS (Mail / Calendar / Messages / System
Events) MUST go through these — running a real AppleScript in a test
will trigger automation prompts on the dev's machine and may hit
their real inbox / calendar.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from server.integrations.calendar.base import (
    CalendarBackend,
    CalendarEvent,
)
from server.integrations.email.base import EmailBackend, EmailMessage
from server.integrations.messages.base import (
    Message,
    MessagesBackend,
)
from server.integrations.router import IntegrationsRouter
from server.integrations.system.base import SystemBackend


class FakeEmailBackend(EmailBackend):
    id = "fake_email"
    name = "Fake email"

    def __init__(self, messages: list[EmailMessage] | None = None) -> None:
        self._messages = messages or []
        self.sent: list[dict] = []

    async def is_available(self) -> bool:
        return True

    async def recent_unread(self, *, limit: int) -> list[EmailMessage]:
        return list(self._messages[:limit])

    async def send(self, *, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})


class FakeCalendarBackend(CalendarBackend):
    id = "fake_calendar"
    name = "Fake calendar"

    def __init__(self, events: list[CalendarEvent] | None = None) -> None:
        self._events = events or []
        self.created: list[dict] = []

    async def is_available(self) -> bool:
        return True

    async def events_in_range(
        self, start: datetime, end: datetime
    ) -> list[CalendarEvent]:
        return list(self._events)

    async def list_calendars(self) -> list[str]:
        return ["Test"]

    async def create(
        self,
        *,
        calendar_name: str,
        summary: str,
        start: datetime,
        end: datetime,
        location: str = "",
    ) -> str:
        self.created.append(
            {
                "calendar": calendar_name,
                "summary": summary,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "location": location,
            }
        )
        return "fake-uid-123"


class FakeMessagesBackend(MessagesBackend):
    id = "fake_messages"
    name = "Fake messages"

    def __init__(self, messages: list[Message] | None = None) -> None:
        self._messages = messages or []
        self.sent: list[dict] = []

    async def is_available(self) -> bool:
        return True

    async def recent(self, *, limit: int) -> list[Message]:
        return list(self._messages[:limit])

    async def send(self, *, to: str, body: str) -> None:
        self.sent.append({"to": to, "body": body})


class FakeSystemBackend(SystemBackend):
    id = "fake_system"
    name = "Fake system"

    def __init__(self) -> None:
        self.launched: list[str] = []
        self.quit: list[str] = []
        self.volumes: list[int] = []
        self.screenshots: list[Path] = []

    async def is_available(self) -> bool:
        return True

    async def apps_list(self) -> list[str]:
        return ["AppOne", "AppTwo"]

    async def app_launch(self, app: str) -> None:
        self.launched.append(app)

    async def app_quit(self, app: str) -> None:
        self.quit.append(app)

    async def volume_set(self, level: int) -> None:
        self.volumes.append(level)

    async def screenshot(self, target: Path) -> None:
        self.screenshots.append(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Write a tiny file so callers that stat() it succeed.
        target.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)


def install_fake_integrations(app) -> dict[str, object]:  # noqa: ANN001
    """Replace the live IntegrationsRouter on `app.state` with one whose
    selected backends are fakes. Returns the fake instances so tests
    can assert against `.sent`, `.created`, etc.
    """
    fakes = {
        "email": FakeEmailBackend(),
        "calendar": FakeCalendarBackend(),
        "messages": FakeMessagesBackend(),
        "system": FakeSystemBackend(),
    }
    router: IntegrationsRouter = app.state.integrations_router
    router._email[router._config.email.backend] = fakes["email"]  # type: ignore[reportPrivateUsage]
    router._calendar[router._config.calendar.backend] = fakes["calendar"]  # type: ignore[reportPrivateUsage]
    router._messages[router._config.messages.backend] = fakes["messages"]  # type: ignore[reportPrivateUsage]
    router._system[router._config.system.backend] = fakes["system"]  # type: ignore[reportPrivateUsage]
    return fakes


def fake_router_for_config(config) -> IntegrationsRouter:  # noqa: ANN001
    """Standalone IntegrationsRouter for tests that don't construct an
    app — wires fake backends as the active selection."""
    router = IntegrationsRouter(config.integrations)
    router._email[router._config.email.backend] = FakeEmailBackend()  # type: ignore[reportPrivateUsage]
    router._calendar[router._config.calendar.backend] = FakeCalendarBackend()  # type: ignore[reportPrivateUsage]
    router._messages[router._config.messages.backend] = FakeMessagesBackend()  # type: ignore[reportPrivateUsage]
    router._system[router._config.system.backend] = FakeSystemBackend()  # type: ignore[reportPrivateUsage]
    return router
