"""CalendarBackend — abstract base for calendar read/create.

Concrete backends:
- AppleCalendarBackend (macOS, AppleScript)
- CalDAVCalendarBackend (RFC 4791, works with iCloud, Google Calendar
  via CalDAV bridge, Fastmail, Posteo, Nextcloud, Radicale, Baikal,
  ...)

Future backend slots: Google Calendar API, Microsoft Graph
(server/integrations/calendar/google.py / microsoft.py) — both
optional, both behind config flags.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CalendarEvent:
    """Normalised event envelope. `start` / `end` are local-time ISO strings.

    Backend-specific extra fields (recurrence, attendees, response
    state, ...) are intentionally not exposed in Phase 5; the
    Interactive Layer's prompt budget can't carry them and the model
    rarely needs them. Add them per-backend in later phases when a
    skill needs them.
    """

    id: str
    summary: str
    calendar: str
    start: str
    end: str
    location: str
    all_day: bool


class CalendarBackendError(Exception):
    """Calendar operation failed for a backend-specific reason."""


class CalendarPermissionError(CalendarBackendError):
    """Permission required (macOS automation prompt; CalDAV 401; ...)."""


class CalendarBackend(ABC):
    id: str
    name: str

    @abstractmethod
    async def is_available(self) -> bool: ...

    @abstractmethod
    async def events_in_range(
        self, start: datetime, end: datetime
    ) -> list[CalendarEvent]: ...

    @abstractmethod
    async def list_calendars(self) -> list[str]: ...

    @abstractmethod
    async def create(
        self,
        *,
        calendar_name: str,
        summary: str,
        start: datetime,
        end: datetime,
        location: str = "",
    ) -> str:
        """Create an event. Returns the new event's identifier."""

    async def aclose(self) -> None:
        return None
