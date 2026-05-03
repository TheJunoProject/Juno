"""Calendar job — Phase 3 stub.

See the email stub for rationale. Real implementation in Phase 5 will
read EventKit (via a small Swift helper) and write a daily agenda
summary into `calendar.md`.
"""

from __future__ import annotations

from server.agents.background.jobs.base import BackgroundJob, JobResult


PLACEHOLDER_BODY = """\
## Status

Phase 3 placeholder. The real calendar job lands in Phase 5 with
EventKit integration via a Swift helper.

## Planned schema (Phase 5)

```
## Today (<date>)

- HH:MM-HH:MM · <event title>  — <attendees, location>
  ...

## Tomorrow (<date>)

- HH:MM-HH:MM · <event title>
  ...

## This week (overview)

- <day-of-week>: <count> meetings, <total-hours>
  ...
```

Free / busy gaps and conflicts will be surfaced explicitly so the
Interactive Layer can answer "when am I free this afternoon?" without
re-reading the whole report.
"""


class CalendarStubJob(BackgroundJob):
    name = "calendar"

    async def run(self) -> JobResult:
        return JobResult(
            report_filename="calendar.md",
            report_body=self.report_header("Calendar") + "\n" + PLACEHOLDER_BODY,
        )
