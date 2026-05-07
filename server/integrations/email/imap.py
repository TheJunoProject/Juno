"""IMAP/SMTP email backend.

Universal email backend — works with Gmail (via app password),
iCloud Mail, Outlook, Fastmail, Posteo, ProtonMail Bridge, Tutanota
Bridge, self-hosted Dovecot, and any other server speaking IMAP4rev1
+ SMTP. No third-party dependencies — pure stdlib (`imaplib`,
`smtplib`, `email`).

Credentials come from environment variables in Phase 5
(`password_env: JUNO_IMAP_PASSWORD`). macOS Keychain integration is
deferred to Phase 6 — same config field will accept
`password_keychain: <account>` then.

Blocking IMAP/SMTP runs on a worker thread (`asyncio.to_thread`) so
it doesn't stall the FastAPI event loop. The connection is opened
fresh per call rather than pooled — keeps the code simple and the
common case (one IMAP call every 15 minutes from the background job)
doesn't need pooling.
"""

from __future__ import annotations

import asyncio
import email
import imaplib
import logging
import os
import smtplib
import ssl
from email.header import decode_header
from email.message import EmailMessage as StdLibEmailMessage
from email.utils import parseaddr, parsedate_to_datetime

from server.config.schema import ImapConfig, SmtpConfig
from server.integrations.email.base import (
    EmailBackend,
    EmailBackendError,
    EmailMessage,
    EmailPermissionError,
)

log = logging.getLogger(__name__)


class ImapEmailBackend(EmailBackend):
    id = "imap"
    name = "IMAP / SMTP"

    def __init__(
        self,
        imap: ImapConfig,
        smtp: SmtpConfig | None,
    ) -> None:
        self._imap = imap
        self._smtp = smtp

    # ---- availability --------------------------------------------------

    async def is_available(self) -> bool:
        # We consider the backend "available" iff host + username + a
        # password resolution path are all set. We deliberately do NOT
        # open a real connection in is_available() — that would force a
        # network round trip on every /api/health probe.
        if not self._imap.host or not self._imap.username:
            return False
        return self._resolve_password(self._imap) is not None

    # ---- read ----------------------------------------------------------

    async def recent_unread(self, *, limit: int) -> list[EmailMessage]:
        if limit <= 0:
            return []
        password = self._resolve_password(self._imap)
        if password is None:
            raise EmailPermissionError(
                f"IMAP password not set. Export the env var "
                f"`{self._imap.password_env}` and restart Juno, or change "
                f"voice.email.imap.password_env to a different name."
            )

        try:
            return await asyncio.to_thread(
                self._fetch_unread_blocking, password, limit
            )
        except imaplib.IMAP4.error as e:
            # imaplib raises bare IMAP4.error for both auth failures and
            # protocol errors. Treat auth-style failures as a permission
            # problem so the skill surfaces the right "go fix your
            # credentials" message.
            msg = str(e).lower()
            if "auth" in msg or "login" in msg or "invalid" in msg:
                raise EmailPermissionError(
                    f"IMAP authentication failed for {self._imap.username} "
                    f"at {self._imap.host}: {e}"
                ) from e
            raise EmailBackendError(f"IMAP error: {e}") from e
        except OSError as e:
            raise EmailBackendError(
                f"could not reach {self._imap.host}:{self._imap.port}: {e}"
            ) from e

    def _fetch_unread_blocking(
        self, password: str, limit: int
    ) -> list[EmailMessage]:
        cls = imaplib.IMAP4_SSL if self._imap.use_ssl else imaplib.IMAP4
        client: imaplib.IMAP4 = cls(
            host=self._imap.host,
            port=self._imap.port,
            timeout=30,
        )
        try:
            client.login(self._imap.username, password)
            client.select(self._imap.mailbox, readonly=True)
            typ, data = client.search(None, "UNSEEN")
            if typ != "OK" or not data or not data[0]:
                return []
            msg_nums = data[0].split()
            # Newest-first: IMAP returns sequence numbers in ascending
            # order; reversed() gives us most-recent-first.
            picked = list(reversed(msg_nums))[:limit]

            out: list[EmailMessage] = []
            for num in picked:
                typ, parts = client.fetch(
                    num, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE MESSAGE-ID)])"
                )
                if typ != "OK" or not parts:
                    continue
                # parts[0] is a tuple ((b'1 (BODY[...]', b'<headers>'),
                # b')'). The actual headers are in parts[0][1].
                first = parts[0]
                if not isinstance(first, tuple) or len(first) < 2:
                    continue
                raw_headers = first[1]
                if not isinstance(raw_headers, (bytes, bytearray)):
                    continue
                msg = email.message_from_bytes(bytes(raw_headers))
                subject = _decode_header(msg.get("Subject", ""))
                from_raw = _decode_header(msg.get("From", ""))
                # Keep the full "Name <addr>" form for display; that's
                # what Mail.app's `sender` returns too.
                date_iso = ""
                date_raw = msg.get("Date")
                if date_raw:
                    try:
                        date_iso = parsedate_to_datetime(date_raw).isoformat(
                            timespec="seconds"
                        )
                    except (TypeError, ValueError):
                        date_iso = date_raw
                # Stable id: prefer Message-ID; fall back to mailbox-
                # qualified UID-equivalent.
                mid = (
                    _decode_header(msg.get("Message-ID", ""))
                    or f"{self._imap.mailbox}#{num.decode()}"
                )
                out.append(
                    EmailMessage(
                        id=mid,
                        subject=subject,
                        sender=from_raw,
                        received=date_iso,
                        read=False,  # we filtered UNSEEN
                    )
                )
            return out
        finally:
            try:
                client.logout()
            except Exception:  # noqa: BLE001 -- best-effort cleanup
                pass

    # ---- send ----------------------------------------------------------

    async def send(self, *, to: str, subject: str, body: str) -> None:
        if not to.strip():
            raise EmailBackendError("`to` must be a non-empty email address")
        if self._smtp is None or not self._smtp.host:
            raise EmailBackendError(
                "SMTP is not configured (integrations.email.smtp.host empty); "
                "cannot send mail."
            )
        password = self._resolve_password(self._smtp)
        if password is None:
            raise EmailPermissionError(
                f"SMTP password not set. Export the env var "
                f"`{self._smtp.password_env}` and restart Juno."
            )

        # Build the message in the calling thread — pure CPU work.
        msg = StdLibEmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._smtp.from_address or self._smtp.username
        msg["To"] = to
        msg.set_content(body)

        try:
            await asyncio.to_thread(self._send_blocking, msg, password)
        except smtplib.SMTPAuthenticationError as e:
            raise EmailPermissionError(
                f"SMTP authentication failed for {self._smtp.username} "
                f"at {self._smtp.host}: {e}"
            ) from e
        except (smtplib.SMTPException, OSError) as e:
            raise EmailBackendError(f"SMTP send failed: {e}") from e

    def _send_blocking(self, msg: StdLibEmailMessage, password: str) -> None:
        assert self._smtp is not None  # guarded above
        ctx = ssl.create_default_context()
        if self._smtp.use_ssl:
            client = smtplib.SMTP_SSL(
                host=self._smtp.host,
                port=self._smtp.port,
                context=ctx,
                timeout=30,
            )
        else:
            client = smtplib.SMTP(
                host=self._smtp.host,
                port=self._smtp.port,
                timeout=30,
            )
        try:
            client.ehlo()
            if self._smtp.use_starttls and not self._smtp.use_ssl:
                client.starttls(context=ctx)
                client.ehlo()
            client.login(self._smtp.username, password)
            client.send_message(msg)
        finally:
            try:
                client.quit()
            except Exception:  # noqa: BLE001 -- best-effort cleanup
                pass

    # ---- helpers --------------------------------------------------------

    @staticmethod
    def _resolve_password(cfg: "ImapConfig | SmtpConfig") -> str | None:
        """Read the password from the env var named in `cfg.password_env`.

        Returns None when the env var is unset or empty. The skill
        translates None into a `EmailPermissionError` with the env-var
        name in the user-facing message.
        """
        env_name = getattr(cfg, "password_env", "")
        if not env_name:
            return None
        value = os.environ.get(env_name, "").strip()
        return value or None


def _decode_header(value: str) -> str:
    """Decode RFC 2047 encoded-word headers (`=?utf-8?b?...?=`)."""
    if not value:
        return ""
    parts: list[str] = []
    for chunk, charset in decode_header(value):
        if isinstance(chunk, bytes):
            try:
                parts.append(chunk.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                parts.append(chunk.decode("utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts).strip()


# parseaddr re-exported in case future skills want to extract just the
# email part. Kept here so the import path is stable.
_ = parseaddr
