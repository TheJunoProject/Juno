"""Email job — Phase 3 stub.

Writes a placeholder `email-digest.md` describing the schema the real
implementation will follow. Real impl lands in Phase 5 (macOS system
integration) where it will read Mail.app via AppleScript or IMAP using
credentials from the macOS keychain (per the CLAUDE.md "Never store
credentials anywhere except the OS keychain" rule).

Shipping this stub now serves three purposes:
- Proves the scheduler-triggers-job-writes-report pipeline end-to-end.
- Pins the `email-digest.md` filename and section structure so the
  Interactive Layer's Phase 4 just-in-time loading can target it.
- Gives the user a clearly-marked "this isn't real yet" report rather
  than a 404 in the reports directory.
"""

from __future__ import annotations

from server.agents.background.jobs.base import BackgroundJob, JobResult


PLACEHOLDER_BODY = """\
## Status

This report is a Phase 3 placeholder. The real email digest job lands
in Phase 5 (macOS system integration). Until then, the file exists so
the Interactive Layer's report-loading path is exercised end-to-end.

## Planned schema (Phase 5)

```
## Unread

- <sender> · <subject> · <relative-time>  — <one-sentence summary>
  ...

## Urgent (flagged for proactive interrupt)

- <sender> · <subject>  — <reason this is urgent>
  ...

## Threads waiting on you

- <sender> · <subject> · <last-touched>  — <what they're asking>
  ...
```

The Phase 5 implementation will read from Mail.app (via AppleScript) or
IMAP (with credentials in the macOS keychain), summarise via the
inference layer at `task_type=background_summarization`, and publish
"urgent" matches to the EventBus interrupt topic.
"""


class EmailStubJob(BackgroundJob):
    name = "email"

    async def run(self) -> JobResult:
        return JobResult(
            report_filename="email-digest.md",
            report_body=self.report_header("Email digest") + "\n" + PLACEHOLDER_BODY,
        )
