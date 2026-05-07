"""Apple Mail.app email backend.

Drives the user's installed Mail.app via AppleScript. First call from
a fresh install triggers macOS's automation prompt; thereafter calls
return immediately. No credentials required — the user already
configured their accounts in Mail.app.
"""

from __future__ import annotations

import sys

from server.integrations._macos import (
    FIELD_SEP,
    AppleScriptError,
    PermissionDeniedError,
    quote,
    run_script,
    split_records,
)
from server.integrations.email.base import (
    EmailBackend,
    EmailBackendError,
    EmailMessage,
    EmailPermissionError,
)


_RECENT_UNREAD_TEMPLATE = """
on run
    set sep to "{sep}"
    set out to ""
    set lim to {limit}
    set count_so_far to 0
    tell application "Mail"
        try
            set msgs to (messages of inbox whose read status is false)
        on error
            return ""
        end try
        repeat with msg in msgs
            if count_so_far is greater than or equal to lim then
                exit repeat
            end if
            try
                set mid to (id of msg) as text
                set msub to (subject of msg) as text
                set msender to (sender of msg) as text
                set mrec to (date received of msg) as «class isot» as string
            on error
                set mid to "?"
                set msub to "(unparseable)"
                set msender to "?"
                set mrec to "?"
            end try
            set out to out & mid & sep & msub & sep & msender & sep & mrec & sep & "false"
            set out to out & linefeed
            set count_so_far to count_so_far + 1
        end repeat
    end tell
    return out
end run
"""


_SEND_TEMPLATE = """
tell application "Mail"
    set newMessage to make new outgoing message with properties {{subject:{subject}, content:{body}, visible:false}}
    tell newMessage
        make new to recipient at end of to recipients with properties {{address:{recipient}}}
    end tell
    send newMessage
    return "sent"
end tell
"""


class AppleMailBackend(EmailBackend):
    id = "apple_mail"
    name = "Apple Mail.app"

    async def is_available(self) -> bool:
        # macOS-only; we don't try to actually invoke Mail in the probe
        # because that would trigger the automation prompt at startup.
        # Skill calls give the user a clear permission error if denied.
        return sys.platform == "darwin"

    async def recent_unread(self, *, limit: int) -> list[EmailMessage]:
        if limit <= 0:
            return []
        script = _RECENT_UNREAD_TEMPLATE.format(sep=FIELD_SEP, limit=limit)
        try:
            stdout = await run_script(script, permission_app="Mail")
        except PermissionDeniedError as e:
            raise EmailPermissionError(str(e)) from e
        except AppleScriptError as e:
            raise EmailBackendError(str(e)) from e

        out: list[EmailMessage] = []
        for fields in split_records(stdout):
            if len(fields) < 5:
                continue
            mid, subject, sender, received, read_str = fields[:5]
            out.append(
                EmailMessage(
                    id=mid,
                    subject=subject,
                    sender=sender,
                    received=received,
                    read=(read_str.strip().lower() == "true"),
                )
            )
        return out

    async def send(self, *, to: str, subject: str, body: str) -> None:
        if not to.strip():
            raise EmailBackendError("`to` must be a non-empty email address")
        script = _SEND_TEMPLATE.format(
            subject=quote(subject),
            body=quote(body),
            recipient=quote(to.strip()),
        )
        try:
            result = await run_script(script, permission_app="Mail")
        except PermissionDeniedError as e:
            raise EmailPermissionError(str(e)) from e
        except AppleScriptError as e:
            raise EmailBackendError(str(e)) from e

        if "sent" not in result.lower():
            raise EmailBackendError(
                "Mail.app reported no error but did not confirm send."
            )
