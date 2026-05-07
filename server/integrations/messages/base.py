"""MessagesBackend — abstract base for direct-message read/send.

Concrete backends:
- AppleMessagesBackend (macOS, AppleScript + chat.db read)

CLAUDE.md prohibits third-party messaging integrations
(WhatsApp / Telegram / Discord / Slack). The base interface exists
because future cross-platform options *that don't violate that rule*
do exist — e.g. signal-cli for Signal, or a Linux iMessage proxy.
Adding one would be a new file under this package; nothing else
changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Message:
    sender: str  # phone number / handle / email; "" when unknown
    text: str
    received_at: str  # local-time ISO; "" when not parseable
    chat: str  # display name of the chat (group name or "")


class MessagesBackendError(Exception):
    """Direct-message operation failed."""


class MessagesPermissionError(MessagesBackendError):
    """Permission required (Full Disk Access for chat.db, etc.)."""


class MessagesBackend(ABC):
    id: str
    name: str

    @abstractmethod
    async def is_available(self) -> bool: ...

    @abstractmethod
    async def recent(self, *, limit: int) -> list[Message]: ...

    @abstractmethod
    async def send(self, *, to: str, body: str) -> None: ...

    async def aclose(self) -> None:
        return None
