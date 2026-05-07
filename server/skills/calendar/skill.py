"""calendar skill — list today / list calendars / create event.

Mode-based; routes through `context.integrations.calendar`. Date
inputs are parsed as naive local-time ISO 8601 (matching the
Calendar.app interpretation; CalDAV backend converts to UTC for
transport).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from server.integrations.calendar import (
    CalendarBackendError,
    CalendarPermissionError,
)
from server.skills.base import Skill, SkillContext, SkillError, SkillInput, SkillResult


class CalendarSkill(Skill):
    name = "calendar"

    async def execute(
        self, payload: SkillInput, context: SkillContext
    ) -> SkillResult:
        if context.integrations is None:
            raise SkillError(
                "calendar skill called without an integrations router; "
                "this is a server wiring bug."
            )
        backend = context.integrations.calendar
        mode = payload.get("mode")
        try:
            if mode == "today":
                return await self._today(backend)
            if mode == "list_calendars":
                return await self._list_calendars(backend)
            if mode == "create":
                return await self._create(payload, backend)
        except CalendarPermissionError as e:
            raise SkillError(str(e)) from e
        except CalendarBackendError as e:
            raise SkillError(f"{backend.name}: {e}") from e
        raise SkillError(
            f"unknown calendar mode: {mode!r}; expected 'today', "
            "'list_calendars', or 'create'"
        )

    async def _today(self, backend) -> SkillResult:  # noqa: ANN001
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        events = await backend.events_in_range(today, today + timedelta(days=1))
        out = [
            {
                "id": e.id,
                "summary": e.summary,
                "calendar": e.calendar,
                "start": e.start,
                "end": e.end,
                "location": e.location,
                "all_day": e.all_day,
            }
            for e in events
        ]
        return SkillResult(
            output={"mode": "today", "events": out, "backend": backend.id},
            summary=f"{len(out)} event(s) today via {backend.name}.",
        )

    async def _list_calendars(self, backend) -> SkillResult:  # noqa: ANN001
        names = await backend.list_calendars()
        return SkillResult(
            output={
                "mode": "list_calendars",
                "calendars": names,
                "backend": backend.id,
            },
            summary=f"{len(names)} calendar(s) via {backend.name}.",
        )

    async def _create(self, payload: SkillInput, backend) -> SkillResult:  # noqa: ANN001
        summary = (payload.get("summary") or "").strip()
        if not summary:
            raise SkillError("create requires `summary` (event title)")
        start = _parse_iso_local(payload.get("start"), field="start")
        end = _parse_iso_local(payload.get("end"), field="end")
        if start >= end:
            raise SkillError("`start` must be before `end`")

        calendar = (payload.get("calendar") or "").strip()
        if not calendar:
            cals = await backend.list_calendars()
            if not cals:
                raise SkillError(
                    "No calendars available; create one in Calendar.app or "
                    "your CalDAV provider first."
                )
            calendar = cals[0]

        location = payload.get("location") or ""
        uid = await backend.create(
            calendar_name=calendar,
            summary=summary,
            start=start,
            end=end,
            location=location,
        )
        return SkillResult(
            output={
                "mode": "create",
                "uid": uid,
                "result": "created",
                "backend": backend.id,
            },
            summary=(
                f"Created '{summary}' on {calendar} ({backend.name}) "
                f"from {start.isoformat(timespec='minutes')} to "
                f"{end.isoformat(timespec='minutes')}."
            ),
            verification={
                "uid": uid,
                "calendar": calendar,
                "summary": summary,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "backend": backend.id,
            },
        )


def _parse_iso_local(value, *, field: str) -> datetime:  # noqa: ANN001
    """Parse an ISO 8601 datetime as local time.

    Accepts both 'YYYY-MM-DDTHH:MM:SS' and 'YYYY-MM-DD HH:MM:SS'.
    Strips trailing 'Z' / timezone offsets — Apple Calendar is
    local-time only and treating a UTC-suffixed value as UTC would
    silently shift the event. (The CalDAV backend re-localises before
    transport.)
    """
    if not isinstance(value, str) or not value.strip():
        raise SkillError(f"`{field}` is required as an ISO 8601 datetime string")
    raw = value.strip().replace(" ", "T")
    if raw.endswith("Z"):
        raw = raw[:-1]
    if "+" in raw[10:]:
        raw = raw[: raw.rfind("+")]
    elif "-" in raw[10:]:
        raw = raw[: raw.rfind("-")]
    try:
        return datetime.fromisoformat(raw)
    except ValueError as e:
        raise SkillError(
            f"`{field}`: could not parse {value!r} as ISO 8601 local datetime: {e}"
        ) from e
