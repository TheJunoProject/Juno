"""Messages digest job.

Reads recent inbound iMessage / SMS via `context.integrations.messages`
and writes `messages.md`. Apple Messages backend reads chat.db
directly — requires Full Disk Access.
"""

from __future__ import annotations

import logging

from server.agents.background.jobs.base import BackgroundJob, JobResult
from server.integrations.messages import (
    MessagesBackendError,
    MessagesPermissionError,
)

log = logging.getLogger(__name__)


DIGEST_LIMIT = 30


class MessagesJob(BackgroundJob):
    name = "messages"

    async def run(self) -> JobResult:
        header = self.report_header("Messages")
        if self.context.integrations is None:
            return JobResult(
                report_filename="messages.md",
                report_body=header
                + "\n## Status\n\n_Integrations router not wired._\n",
            )
        backend = self.context.integrations.messages
        try:
            messages = await backend.recent(limit=DIGEST_LIMIT)
        except MessagesPermissionError as e:
            return JobResult(
                report_filename="messages.md",
                report_body=header
                + f"\n## Status\n\n_Permission required ({backend.name})._\n\n"
                + str(e)
                + "\n",
            )
        except MessagesBackendError as e:
            log.warning("Messages job: %s error: %s", backend.name, e)
            return JobResult(
                report_filename="messages.md",
                report_body=header
                + f"\n## Status\n\n_{backend.name} error_: {e}\n",
            )

        if not messages:
            return JobResult(
                report_filename="messages.md",
                report_body=header
                + f"\n## Status\n\nNo recent inbound messages "
                f"({backend.name}).\n",
            )

        threads: dict[str, list] = {}
        for m in messages:
            key = m.chat or m.sender or "(unknown)"
            threads.setdefault(key, []).append(m)

        lines: list[str] = [
            header,
            f"\n_Source: {backend.name}_\n",
            f"\n## Recent inbound ({len(messages)})\n",
        ]
        for thread_key, items in threads.items():
            lines.append(f"\n### {thread_key}\n")
            for m in items:
                preview = m.text.replace("\n", " ").strip()
                if len(preview) > 200:
                    preview = preview[:197] + "..."
                lines.append(
                    f"- {m.received_at} · {m.sender or '?'}: {preview}"
                )
        return JobResult(
            report_filename="messages.md",
            report_body="\n".join(lines) + "\n",
        )
