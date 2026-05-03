"""Messages job — Phase 3 stub.

See the email stub for rationale. Real implementation in Phase 5 will
read iMessage / SMS via AppleScript and produce `messages.md`.
"""

from __future__ import annotations

from server.agents.background.jobs.base import BackgroundJob, JobResult


PLACEHOLDER_BODY = """\
## Status

Phase 3 placeholder. The real messages job lands in Phase 5 (iMessage
+ SMS via AppleScript on macOS).

## Planned schema (Phase 5)

```
## Unread

- <contact> · <relative-time>  — <one-line preview>
  ...

## Threads waiting on a reply from you

- <contact> · <relative-time>  — <what they last said>
  ...

## Recent activity (24h)

- <contact> · <message count>  — <theme>
  ...
```
"""


class MessagesStubJob(BackgroundJob):
    name = "messages"

    async def run(self) -> JobResult:
        return JobResult(
            report_filename="messages.md",
            report_body=self.report_header("Messages") + "\n" + PLACEHOLDER_BODY,
        )
