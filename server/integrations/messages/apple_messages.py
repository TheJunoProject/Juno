"""Apple Messages backend.

Reads recent inbound messages from `~/Library/Messages/chat.db` (the
only reliable way to access unread state — Messages.app's AppleScript
dictionary doesn't expose it). Sends via AppleScript through
Messages.app.

Permissions required:
- Reading chat.db: Full Disk Access for the program running Juno.
- Sending: standard automation permission for Messages.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from server.integrations._macos import (
    AppleScriptError,
    PermissionDeniedError,
    quote,
    run_script,
)
from server.integrations.messages.base import (
    Message,
    MessagesBackend,
    MessagesBackendError,
    MessagesPermissionError,
)


# Mac epoch: 2001-01-01 UTC. message.date in chat.db is nanoseconds since.
_MAC_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)


def _chat_db_path() -> Path:
    return Path.home() / "Library" / "Messages" / "chat.db"


_RECENT_QUERY = """
SELECT
    handle.id        AS sender,
    message.text     AS body,
    message.date     AS mac_ns,
    chat.display_name AS chat_name
FROM message
LEFT JOIN handle ON message.handle_id = handle.ROWID
LEFT JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
LEFT JOIN chat ON chat_message_join.chat_id = chat.ROWID
WHERE message.is_from_me = 0
  AND message.text IS NOT NULL
  AND TRIM(message.text) != ''
ORDER BY message.date DESC
LIMIT ?
"""


_SEND_TEMPLATE = """
tell application "Messages"
    try
        set targetService to 1st service whose service type = iMessage
    on error
        set targetService to first service
    end try
    set targetBuddy to buddy {recipient} of targetService
    send {body} to targetBuddy
    return "sent"
end tell
"""


class AppleMessagesBackend(MessagesBackend):
    id = "apple_messages"
    name = "Apple Messages.app"

    async def is_available(self) -> bool:
        return sys.platform == "darwin"

    async def recent(self, *, limit: int) -> list[Message]:
        if limit <= 0:
            return []
        db_path = _chat_db_path()
        if not db_path.exists():
            return []
        uri = f"file:{db_path}?mode=ro"
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=2.0)
        except sqlite3.OperationalError as e:
            raise MessagesPermissionError(
                "Could not open ~/Library/Messages/chat.db. Grant Full "
                "Disk Access to the program running Juno: System "
                "Settings → Privacy & Security → Full Disk Access."
            ) from e

        try:
            rows = conn.execute(_RECENT_QUERY, (limit,)).fetchall()
        finally:
            conn.close()

        out: list[Message] = []
        for sender, body, mac_ns, chat_name in rows:
            ts = ""
            if mac_ns is not None:
                seconds_since_mac = (
                    mac_ns / 1_000_000_000
                    if mac_ns > 1_000_000_000_000
                    else mac_ns
                )
                try:
                    received = _MAC_EPOCH + timedelta(seconds=seconds_since_mac)
                    ts = received.astimezone().isoformat(timespec="seconds")
                except (OverflowError, OSError):
                    ts = ""
            out.append(
                Message(
                    sender=sender or "",
                    text=(body or "").strip(),
                    received_at=ts,
                    chat=chat_name or "",
                )
            )
        return out

    async def send(self, *, to: str, body: str) -> None:
        if not to.strip():
            raise MessagesBackendError("`to` must be a non-empty handle")
        if not body.strip():
            raise MessagesBackendError("`body` must be a non-empty message")
        script = _SEND_TEMPLATE.format(
            recipient=quote(to.strip()),
            body=quote(body),
        )
        try:
            result = await run_script(script, permission_app="Messages")
        except PermissionDeniedError as e:
            raise MessagesPermissionError(str(e)) from e
        except AppleScriptError as e:
            raise MessagesBackendError(str(e)) from e

        if "sent" not in result.lower():
            raise MessagesBackendError(
                "Messages.app reported no error but did not confirm send."
            )
