"""Calendar agenda job.

Reads today + tomorrow events via `context.integrations.calendar`
(Apple Calendar or CalDAV) and writes `calendar.md`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from server.agents.background.jobs.base import BackgroundJob, JobResult
from server.integrations.calendar import (
    CalendarBackendError,
    CalendarPermissionError,
)

log = logging.getLogger(__name__)


class CalendarJob(BackgroundJob):
    name = "calendar"

    async def run(self) -> JobResult:
        header = self.report_header("Calendar")
        if self.context.integrations is None:
            return JobResult(
                report_filename="calendar.md",
                report_body=header
                + "\n## Status\n\n_Integrations router not wired._\n",
            )
        backend = self.context.integrations.calendar
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            today_events = await backend.events_in_range(
                today, today + timedelta(days=1)
            )
            tomorrow_events = await backend.events_in_range(
                today + timedelta(days=1), today + timedelta(days=2)
            )
        except CalendarPermissionError as e:
            return JobResult(
                report_filename="calendar.md",
                report_body=header
                + f"\n## Status\n\n_Permission required ({backend.name})._\n\n"
                + str(e)
                + "\n",
            )
        except CalendarBackendError as e:
            log.warning("Calendar job: %s error: %s", backend.name, e)
            return JobResult(
                report_filename="calendar.md",
                report_body=header
                + f"\n## Status\n\n_{backend.name} error_: {e}\n",
            )

        lines: list[str] = [header, f"\n_Source: {backend.name}_\n"]
        lines.append(f"\n## Today ({today.strftime('%A, %d %B %Y')})\n")
        if today_events:
            for e in today_events:
                lines.append(_format_event(e))
        else:
            lines.append("_Nothing on the calendar today._")

        tomorrow = today + timedelta(days=1)
        lines.append(f"\n## Tomorrow ({tomorrow.strftime('%A, %d %B %Y')})\n")
        if tomorrow_events:
            for e in tomorrow_events:
                lines.append(_format_event(e))
        else:
            lines.append("_Nothing on the calendar tomorrow._")

        return JobResult(
            report_filename="calendar.md",
            report_body="\n".join(lines) + "\n",
        )


def _format_event(e) -> str:  # noqa: ANN001
    when = (
        f"{_short_time(e.start)}-{_short_time(e.end)}"
        if not e.all_day
        else "all day"
    )
    parts = [f"- {when} · {e.summary or '(no title)'}", f"· {e.calendar}"]
    if e.location:
        parts.append(f"· {e.location}")
    return " ".join(parts)


def _short_time(iso_or_close: str) -> str:
    if len(iso_or_close) >= 16 and iso_or_close[10] == "T":
        return iso_or_close[11:16]
    return iso_or_close
