"""IntegrationsRouter — picks the active backend per integration domain.

Same pattern as `InferenceRouter` and `VoiceRouter`. Constructs every
known backend up front (cheap — backends don't open IO in __init__)
and exposes `router.email`, `router.calendar`, `router.messages`,
`router.system` accessors that return the configured one.

Adding a new backend:
  1. Drop a file under `server/integrations/<domain>/<name>.py`
     implementing the domain's `*Backend` ABC.
  2. Add its id to the `*BackendId` Literal in `server/config/schema.py`.
  3. Add a one-line entry to `_build_*` below.
"""

from __future__ import annotations

import logging

from server.config.schema import IntegrationsConfig
from server.integrations.calendar.apple_calendar import AppleCalendarBackend
from server.integrations.calendar.base import CalendarBackend
from server.integrations.calendar.caldav import CalDAVCalendarBackend
from server.integrations.email.apple_mail import AppleMailBackend
from server.integrations.email.base import EmailBackend
from server.integrations.email.imap import ImapEmailBackend
from server.integrations.messages.apple_messages import AppleMessagesBackend
from server.integrations.messages.base import MessagesBackend
from server.integrations.system.base import SystemBackend
from server.integrations.system.macos import MacosSystemBackend

log = logging.getLogger(__name__)


class IntegrationsRouter:
    def __init__(self, config: IntegrationsConfig) -> None:
        self._config = config

        self._email: dict[str, EmailBackend] = {
            "apple_mail": AppleMailBackend(),
            "imap": ImapEmailBackend(config.email.imap, config.email.smtp),
        }
        self._calendar: dict[str, CalendarBackend] = {
            "apple_calendar": AppleCalendarBackend(),
            "caldav": CalDAVCalendarBackend(config.calendar.caldav),
        }
        self._messages: dict[str, MessagesBackend] = {
            "apple_messages": AppleMessagesBackend(),
        }
        self._system: dict[str, SystemBackend] = {
            "macos": MacosSystemBackend(),
        }

    # ---- selected (active) ---------------------------------------------

    @property
    def email(self) -> EmailBackend:
        return self._email[self._config.email.backend]

    @property
    def calendar(self) -> CalendarBackend:
        return self._calendar[self._config.calendar.backend]

    @property
    def messages(self) -> MessagesBackend:
        return self._messages[self._config.messages.backend]

    @property
    def system(self) -> SystemBackend:
        return self._system[self._config.system.backend]

    # ---- introspection (used by /api/health) ---------------------------

    def all_email(self) -> dict[str, EmailBackend]:
        return dict(self._email)

    def all_calendar(self) -> dict[str, CalendarBackend]:
        return dict(self._calendar)

    def all_messages(self) -> dict[str, MessagesBackend]:
        return dict(self._messages)

    def all_system(self) -> dict[str, SystemBackend]:
        return dict(self._system)

    def selected_ids(self) -> dict[str, str]:
        return {
            "email": self._config.email.backend,
            "calendar": self._config.calendar.backend,
            "messages": self._config.messages.backend,
            "system": self._config.system.backend,
        }

    # ---- lifecycle -----------------------------------------------------

    async def aclose(self) -> None:
        for group in (
            self._email,
            self._calendar,
            self._messages,
            self._system,
        ):
            for backend in group.values():
                await backend.aclose()
