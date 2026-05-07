"""EmailBackend — abstract base for email read/send.

Concrete backends:
- AppleMailBackend (macOS, AppleScript)
- ImapEmailBackend (IMAP/SMTP, works with any provider that supports
  the standard — Gmail, iCloud Mail, Outlook, Fastmail, Posteo,
  self-hosted Dovecot, etc.)

The skill and background job code talks to this interface only; they
never know which backend is wired. Adding a Microsoft Graph or Gmail
API backend in a future phase is one new file under this package.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class EmailMessage:
    """Normalised email envelope returned to callers.

    `id` is opaque — its meaning depends on the backend (Mail.app
    message id; IMAP UID with mailbox prefix; Graph message id).
    Used only for "I've seen this one" deduplication, not for
    cross-backend correlation.
    """

    id: str
    subject: str
    sender: str  # full address ("Alice <alice@example.com>")
    received: str  # ISO-ish; backend-dependent precision
    read: bool


class EmailBackendError(Exception):
    """Email operation failed for a backend-specific reason."""


class EmailPermissionError(EmailBackendError):
    """Permission required.

    Carries a user-actionable string (where to grant access / which
    env var to set / etc.). Skills surface this verbatim — never
    rephrase it.
    """


class EmailBackend(ABC):
    id: str
    """Short identifier matching the config value (`apple_mail`, `imap`)."""
    name: str
    """Human-readable label shown in /api/health."""

    @abstractmethod
    async def is_available(self) -> bool:
        """Quick probe: can this backend run right now?

        Must not raise — return False on any configuration / network /
        permission failure.
        """

    @abstractmethod
    async def recent_unread(self, *, limit: int) -> list[EmailMessage]: ...

    @abstractmethod
    async def send(self, *, to: str, subject: str, body: str) -> None: ...

    async def aclose(self) -> None:
        """Release any held resources (sockets, file handles, ...)."""
        return None
