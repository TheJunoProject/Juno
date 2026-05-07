"""Email digest job.

Reads recent unread mail via `context.integrations.email` (Apple Mail
or IMAP — the user's config picks) and writes `email-digest.md`.

We deliberately don't run an LLM summary on every cycle — raw items
the model can quote from are more useful than a paraphrased digest,
and avoid burning tokens every 15 minutes. The Interactive Layer's
just-in-time loading picks up `email-digest.md` when the classifier
flags an email intent.

When the configured backend reports a permission problem (macOS
prompt denied, IMAP password env var unset, ...), the job writes a
clearly-marked permissions-required report instead of crashing the
runtime.
"""

from __future__ import annotations

import logging

from server.agents.background.jobs.base import BackgroundJob, JobResult
from server.integrations.email import EmailBackendError, EmailPermissionError

log = logging.getLogger(__name__)


# How many unread to surface per cycle.
DIGEST_LIMIT = 20


class EmailJob(BackgroundJob):
    name = "email"

    async def run(self) -> JobResult:
        header = self.report_header("Email digest")
        if self.context.integrations is None:
            return JobResult(
                report_filename="email-digest.md",
                report_body=header
                + "\n## Status\n\n_Integrations router not wired into the "
                "background runtime; this is a server bug._\n",
            )
        backend = self.context.integrations.email

        try:
            messages = await backend.recent_unread(limit=DIGEST_LIMIT)
        except EmailPermissionError as e:
            return JobResult(
                report_filename="email-digest.md",
                report_body=header
                + f"\n## Status\n\n_Permission required ({backend.name})._\n\n"
                + str(e)
                + "\n",
            )
        except EmailBackendError as e:
            log.warning("Email digest job: backend error (%s): %s", backend.name, e)
            return JobResult(
                report_filename="email-digest.md",
                report_body=header
                + f"\n## Status\n\n_{backend.name} error_: {e}\n",
            )

        if not messages:
            return JobResult(
                report_filename="email-digest.md",
                report_body=header
                + f"\n## Status\n\nInbox is clear — no unread messages "
                f"({backend.name}).\n",
            )

        lines = [
            header,
            f"\n_Source: {backend.name}_\n",
            f"\n## Unread ({len(messages)})\n",
        ]
        for m in messages:
            lines.append(
                f"- {m.received} · {m.sender or 'Unknown'} · "
                f"{m.subject or '(no subject)'}"
            )
        return JobResult(
            report_filename="email-digest.md",
            report_body="\n".join(lines) + "\n",
        )
