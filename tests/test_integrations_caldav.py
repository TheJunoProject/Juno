"""CalDAVCalendarBackend tests — graceful behaviour without the dep."""

from __future__ import annotations

from datetime import datetime

import pytest

from server.config import CalDAVConfig
from server.integrations.calendar import (
    CalendarBackendError,
    CalendarPermissionError,
)
from server.integrations.calendar.caldav import (
    CalDAVCalendarBackend,
    _try_import_caldav,
)


def _cfg(**over) -> CalDAVConfig:
    base = dict(
        url="https://caldav.example.com/",
        username="user@example.com",
        password_env="JUNO_NEVER_SET_FOR_CALDAV_TESTS",
    )
    base.update(over)
    return CalDAVConfig(**base)


# ---- availability ------------------------------------------------------


async def test_unavailable_when_caldav_not_installed() -> None:
    backend = CalDAVCalendarBackend(_cfg())
    if _try_import_caldav() is None:
        assert await backend.is_available() is False


async def test_unavailable_when_url_blank() -> None:
    backend = CalDAVCalendarBackend(_cfg(url=""))
    assert await backend.is_available() is False


async def test_unavailable_when_password_env_unset() -> None:
    backend = CalDAVCalendarBackend(_cfg())
    # Password env intentionally unset.
    assert await backend.is_available() is False


# ---- error surface when dep is missing --------------------------------


@pytest.mark.skipif(
    _try_import_caldav() is not None,
    reason="caldav installed; skipping the missing-dep error test.",
)
async def test_methods_raise_clear_error_when_dep_missing(monkeypatch) -> None:
    backend = CalDAVCalendarBackend(_cfg())
    monkeypatch.setenv("JUNO_NEVER_SET_FOR_CALDAV_TESTS", "shh")
    with pytest.raises(CalendarBackendError) as exc:
        await backend.events_in_range(
            datetime(2026, 5, 6, 0, 0), datetime(2026, 5, 7, 0, 0)
        )
    assert "caldav" in str(exc.value).lower()


# ---- error surface when password env unset ----------------------------


@pytest.mark.skipif(
    _try_import_caldav() is None,
    reason="caldav not installed; the password check happens after import.",
)
async def test_methods_raise_permission_error_when_password_unset() -> None:
    backend = CalDAVCalendarBackend(_cfg())
    with pytest.raises(CalendarPermissionError):
        await backend.events_in_range(
            datetime(2026, 5, 6, 0, 0), datetime(2026, 5, 7, 0, 0)
        )
