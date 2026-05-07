"""CalDAV calendar backend.

Universal calendar backend — works with iCloud Calendar, Google
Calendar (via the CalDAV bridge), Fastmail, Posteo, Nextcloud,
Radicale, Baikal, Apple's macOS Server, and any other CalDAV
endpoint (RFC 4791).

Optional dep: install via `pip install -e '.[calendar]'`. When the
`caldav` package isn't installed, `is_available()` returns False
and method calls raise a clear "install the extra" error rather
than crashing the server.

Credentials come from env vars in Phase 5
(`password_env: JUNO_CALDAV_PASSWORD`).
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from server.config.schema import CalDAVConfig
from server.integrations.calendar.base import (
    CalendarBackend,
    CalendarBackendError,
    CalendarEvent,
    CalendarPermissionError,
)

log = logging.getLogger(__name__)


def _try_import_caldav():
    try:
        import caldav  # type: ignore[import-not-found]

        return caldav
    except ImportError:
        return None


class CalDAVCalendarBackend(CalendarBackend):
    id = "caldav"
    name = "CalDAV"

    def __init__(self, config: CalDAVConfig) -> None:
        self._config = config
        self._lib = _try_import_caldav()

    async def is_available(self) -> bool:
        if self._lib is None:
            return False
        if not self._config.url or not self._config.username:
            return False
        return self._resolve_password() is not None

    # ---- read ----------------------------------------------------------

    async def events_in_range(
        self, start: datetime, end: datetime
    ) -> list[CalendarEvent]:
        client = await asyncio.to_thread(self._connect)
        try:
            principal = await asyncio.to_thread(client.principal)
            calendars = await asyncio.to_thread(principal.calendars)
            out: list[CalendarEvent] = []
            for cal in calendars:
                cal_name = _safe_str(getattr(cal, "name", "") or "")
                events = await asyncio.to_thread(
                    cal.search,
                    start=_to_utc(start),
                    end=_to_utc(end),
                    event=True,
                    expand=True,
                )
                for ev in events:
                    parsed = _event_to_envelope(ev, cal_name)
                    if parsed is not None:
                        out.append(parsed)
            return out
        except Exception as e:  # noqa: BLE001 -- caldav uses many exception types
            self._reraise(e)
            raise  # unreachable but keeps type-checkers happy

    async def list_calendars(self) -> list[str]:
        client = await asyncio.to_thread(self._connect)
        try:
            principal = await asyncio.to_thread(client.principal)
            calendars = await asyncio.to_thread(principal.calendars)
            return [_safe_str(getattr(c, "name", "") or "") for c in calendars]
        except Exception as e:  # noqa: BLE001
            self._reraise(e)
            raise

    async def create(
        self,
        *,
        calendar_name: str,
        summary: str,
        start: datetime,
        end: datetime,
        location: str = "",
    ) -> str:
        if start >= end:
            raise CalendarBackendError("`start` must be before `end`")

        client = await asyncio.to_thread(self._connect)
        try:
            principal = await asyncio.to_thread(client.principal)
            calendars = await asyncio.to_thread(principal.calendars)
            target = next(
                (c for c in calendars if _safe_str(getattr(c, "name", "")) == calendar_name),
                None,
            )
            if target is None:
                raise CalendarBackendError(
                    f"CalDAV server has no calendar named {calendar_name!r}; "
                    f"available: {[_safe_str(getattr(c, 'name', '')) for c in calendars]}"
                )

            ical = _build_ical(
                summary=summary,
                start=start,
                end=end,
                location=location,
            )
            ev = await asyncio.to_thread(target.save_event, ical)
            return _safe_str(getattr(ev, "url", "") or "") or _safe_str(
                getattr(ev, "id", "")
            )
        except CalendarBackendError:
            raise
        except Exception as e:  # noqa: BLE001
            self._reraise(e)
            raise

    # ---- helpers --------------------------------------------------------

    def _connect(self) -> Any:
        if self._lib is None:
            raise CalendarBackendError(
                "caldav package is not installed. Run "
                "`pip install -e '.[calendar]'` to enable CalDAV support."
            )
        password = self._resolve_password()
        if password is None:
            raise CalendarPermissionError(
                f"CalDAV password not set. Export the env var "
                f"`{self._config.password_env}` and restart Juno."
            )
        return self._lib.DAVClient(
            url=self._config.url,
            username=self._config.username,
            password=password,
        )

    def _resolve_password(self) -> str | None:
        env_name = self._config.password_env
        if not env_name:
            return None
        return os.environ.get(env_name, "").strip() or None

    @staticmethod
    def _reraise(e: BaseException) -> None:
        msg = str(e)
        low = msg.lower()
        if "401" in low or "unauthor" in low or "forbidden" in low or "403" in low:
            raise CalendarPermissionError(
                f"CalDAV authentication failed: {msg}"
            ) from e
        raise CalendarBackendError(f"CalDAV error: {msg}") from e


# ---- iCal helpers -------------------------------------------------------


def _build_ical(
    *,
    summary: str,
    start: datetime,
    end: datetime,
    location: str,
) -> str:
    """Hand-built minimal iCalendar VEVENT.

    We don't pull in the `vobject` library that `caldav` re-exports —
    a hand-built VEVENT is small enough to maintain and avoids a
    second optional dep. CalDAV servers only validate the bits used
    here.
    """
    import uuid

    def _ical_dt(dt: datetime) -> str:
        return _to_utc(dt).strftime("%Y%m%dT%H%M%SZ")

    uid = f"juno-{uuid.uuid4().hex}@juno.local"
    now_z = _ical_dt(datetime.now(timezone.utc))
    parts = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Juno//EN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now_z}",
        f"DTSTART:{_ical_dt(start)}",
        f"DTEND:{_ical_dt(end)}",
        f"SUMMARY:{_ical_escape(summary)}",
    ]
    if location:
        parts.append(f"LOCATION:{_ical_escape(location)}")
    parts.extend(["END:VEVENT", "END:VCALENDAR"])
    return "\r\n".join(parts) + "\r\n"


def _ical_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", r"\;")
        .replace(",", r"\,")
        .replace("\n", r"\n")
    )


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        # Treat naive datetimes as local — that matches the rest of the
        # calendar contract (`AppleCalendarBackend` uses local-time too).
        return dt.astimezone(timezone.utc)
    return dt.astimezone(timezone.utc)


def _safe_str(v: Any) -> str:
    try:
        return str(v).strip()
    except Exception:  # noqa: BLE001
        return ""


def _event_to_envelope(ev: Any, calendar_name: str) -> CalendarEvent | None:
    """Pull a CalendarEvent out of a caldav `Event` object's iCal data."""
    try:
        ical = ev.icalendar_instance  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return None

    try:
        # An ical document may carry multiple VEVENT components; pick
        # the first one that has DTSTART (a recurring event expanded by
        # `expand=True` produces one VEVENT per occurrence).
        for component in ical.walk():
            if getattr(component, "name", "") != "VEVENT":
                continue
            summary = _safe_str(component.get("SUMMARY", ""))
            location = _safe_str(component.get("LOCATION", ""))
            uid = _safe_str(component.get("UID", "")) or _safe_str(
                getattr(ev, "url", "")
            )
            start = component.get("DTSTART")
            end = component.get("DTEND")
            if start is None:
                continue
            start_iso, all_day = _ical_dt_to_iso(start)
            end_iso, _ = _ical_dt_to_iso(end) if end is not None else (
                start_iso,
                False,
            )
            return CalendarEvent(
                id=uid,
                summary=summary,
                calendar=calendar_name,
                start=start_iso,
                end=end_iso,
                location=location,
                all_day=all_day,
            )
    except Exception as e:  # noqa: BLE001
        log.debug("Skipping unparseable CalDAV event: %s", e)
        return None
    return None


def _ical_dt_to_iso(prop: Any) -> tuple[str, bool]:
    """Convert an icalendar DATE / DATE-TIME property to (iso_str, all_day)."""
    val = getattr(prop, "dt", prop)
    if isinstance(val, datetime):
        # Render in local time for parity with AppleCalendarBackend.
        local = val.astimezone() if val.tzinfo else val.astimezone()
        return local.isoformat(timespec="seconds"), False
    # `date` (no time) → all-day event.
    return f"{val}T00:00:00", True
