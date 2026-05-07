"""Apple Calendar.app calendar backend.

Drives Calendar.app via AppleScript. Date handling is locale-safe
(builds dates by component instead of parsing locale strings).
"""

from __future__ import annotations

import sys
from datetime import datetime

from server.integrations._macos import (
    FIELD_SEP,
    AppleScriptError,
    PermissionDeniedError,
    quote,
    run_script,
    split_records,
)
from server.integrations.calendar.base import (
    CalendarBackend,
    CalendarBackendError,
    CalendarEvent,
    CalendarPermissionError,
)


def _date_setup_lines(varname: str, dt: datetime) -> str:
    """AppleScript snippet that builds a `date` value by component."""
    return (
        f'set {varname} to current date\n'
        f'set year of {varname} to {dt.year}\n'
        f'set month of {varname} to {dt.month}\n'
        f'set day of {varname} to {dt.day}\n'
        f'set hours of {varname} to {dt.hour}\n'
        f'set minutes of {varname} to {dt.minute}\n'
        f'set seconds of {varname} to {dt.second}\n'
    )


_RANGE_TEMPLATE = """
on run
    set sep to "{sep}"
    {start_setup}
    {end_setup}
    set out to ""
    tell application "Calendar"
        repeat with cal in calendars
            set calName to (name of cal) as text
            try
                set theEvents to (events of cal whose start date is greater than or equal to startDate and start date is less than endDate)
            on error
                set theEvents to {{}}
            end try
            repeat with ev in theEvents
                try
                    set evid to (uid of ev) as text
                    set summ to (summary of ev) as text
                    set sd to (start date of ev) as «class isot» as string
                    set ed to (end date of ev) as «class isot» as string
                    set loc to ""
                    try
                        set loc to (location of ev) as text
                    end try
                    set ad to (allday event of ev) as text
                on error
                    set evid to "?"
                    set summ to "(unparseable)"
                    set sd to "?"
                    set ed to "?"
                    set loc to ""
                    set ad to "false"
                end try
                set out to out & evid & sep & summ & sep & calName & sep & sd & sep & ed & sep & loc & sep & ad
                set out to out & linefeed
            end repeat
        end repeat
    end tell
    return out
end run
"""

_LIST_CALENDARS = """
tell application "Calendar"
    set out to ""
    repeat with cal in calendars
        set out to out & (name of cal) as text & linefeed
    end repeat
    return out
end tell
"""

_CREATE_TEMPLATE = """
on run
    {start_setup}
    {end_setup}
    tell application "Calendar"
        tell calendar {calendar_name}
            set newEvent to make new event with properties {{summary:{summary}, start date:startDate, end date:endDate, location:{location}}}
            return (uid of newEvent) as text
        end tell
    end tell
end run
"""


class AppleCalendarBackend(CalendarBackend):
    id = "apple_calendar"
    name = "Apple Calendar.app"

    async def is_available(self) -> bool:
        return sys.platform == "darwin"

    async def events_in_range(
        self, start: datetime, end: datetime
    ) -> list[CalendarEvent]:
        script = _RANGE_TEMPLATE.format(
            sep=FIELD_SEP,
            start_setup=_date_setup_lines("startDate", start),
            end_setup=_date_setup_lines("endDate", end),
        )
        try:
            stdout = await run_script(
                script, permission_app="Calendar", timeout=60.0
            )
        except PermissionDeniedError as e:
            raise CalendarPermissionError(str(e)) from e
        except AppleScriptError as e:
            raise CalendarBackendError(str(e)) from e

        out: list[CalendarEvent] = []
        for fields in split_records(stdout):
            if len(fields) < 7:
                continue
            evid, summ, cal, sd, ed, loc, ad = fields[:7]
            out.append(
                CalendarEvent(
                    id=evid,
                    summary=summ,
                    calendar=cal,
                    start=sd,
                    end=ed,
                    location=loc,
                    all_day=(ad.strip().lower() == "true"),
                )
            )
        return out

    async def list_calendars(self) -> list[str]:
        try:
            stdout = await run_script(_LIST_CALENDARS, permission_app="Calendar")
        except PermissionDeniedError as e:
            raise CalendarPermissionError(str(e)) from e
        except AppleScriptError as e:
            raise CalendarBackendError(str(e)) from e
        return [line.strip() for line in stdout.splitlines() if line.strip()]

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
        script = _CREATE_TEMPLATE.format(
            calendar_name=quote(calendar_name),
            summary=quote(summary),
            location=quote(location),
            start_setup=_date_setup_lines("startDate", start),
            end_setup=_date_setup_lines("endDate", end),
        )
        try:
            return (
                await run_script(script, permission_app="Calendar", timeout=30.0)
            ).strip()
        except PermissionDeniedError as e:
            raise CalendarPermissionError(str(e)) from e
        except AppleScriptError as e:
            raise CalendarBackendError(str(e)) from e
