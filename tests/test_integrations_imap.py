"""ImapEmailBackend tests — mocks imaplib + smtplib so no network IO."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from server.config import ImapConfig, SmtpConfig
from server.integrations.email import (
    EmailBackendError,
    EmailPermissionError,
)
from server.integrations.email.imap import ImapEmailBackend


def _imap_cfg(
    *, env_name: str = "JUNO_TEST_IMAP_PW", host: str = "imap.example.com"
) -> ImapConfig:
    return ImapConfig(
        host=host,
        port=993,
        username="user@example.com",
        password_env=env_name,
        use_ssl=True,
        mailbox="INBOX",
    )


def _smtp_cfg(
    *, env_name: str = "JUNO_TEST_SMTP_PW", host: str = "smtp.example.com"
) -> SmtpConfig:
    return SmtpConfig(
        host=host,
        port=587,
        username="user@example.com",
        password_env=env_name,
        use_ssl=False,
        use_starttls=True,
        from_address="user@example.com",
    )


# ---- availability ------------------------------------------------------


async def test_unavailable_when_no_password_in_env() -> None:
    cfg = _imap_cfg(env_name="JUNO_NEVER_SET_THIS_VAR_X")
    backend = ImapEmailBackend(cfg, _smtp_cfg())
    assert await backend.is_available() is False


async def test_unavailable_when_host_blank() -> None:
    cfg = _imap_cfg(host="")
    backend = ImapEmailBackend(cfg, _smtp_cfg())
    assert await backend.is_available() is False


async def test_available_with_env_password(monkeypatch) -> None:
    monkeypatch.setenv("JUNO_TEST_IMAP_PW_OK", "shh")
    cfg = _imap_cfg(env_name="JUNO_TEST_IMAP_PW_OK")
    backend = ImapEmailBackend(cfg, _smtp_cfg())
    assert await backend.is_available() is True


# ---- recent_unread -----------------------------------------------------


def _build_imap_mock(*, search_response, fetch_responses) -> MagicMock:
    mock = MagicMock()
    mock.login.return_value = ("OK", [b"LOGIN successful"])
    mock.select.return_value = ("OK", [b"OK"])
    mock.search.return_value = ("OK", [search_response])

    fetch_iter = iter(fetch_responses)

    def _fetch(_num, _spec):
        return next(fetch_iter)

    mock.fetch.side_effect = _fetch
    mock.logout.return_value = ("OK", [b"BYE"])
    return mock


async def test_recent_unread_empty_inbox(monkeypatch) -> None:
    monkeypatch.setenv("JUNO_TEST_IMAP_PW_OK2", "shh")
    cfg = _imap_cfg(env_name="JUNO_TEST_IMAP_PW_OK2")
    backend = ImapEmailBackend(cfg, _smtp_cfg())

    mock_imap = _build_imap_mock(search_response=b"", fetch_responses=[])
    with patch("imaplib.IMAP4_SSL", return_value=mock_imap):
        out = await backend.recent_unread(limit=10)
    assert out == []


async def test_recent_unread_parses_headers(monkeypatch) -> None:
    monkeypatch.setenv("JUNO_TEST_IMAP_PW_OK3", "shh")
    cfg = _imap_cfg(env_name="JUNO_TEST_IMAP_PW_OK3")
    backend = ImapEmailBackend(cfg, _smtp_cfg())

    headers = (
        b"Subject: Lunch?\r\n"
        b"From: Sam <sam@example.com>\r\n"
        b"Date: Mon, 5 May 2026 12:00:00 -0700\r\n"
        b"Message-ID: <abc-123@example.com>\r\n\r\n"
    )
    fetch_response = ("OK", [(b"1 (BODY[HEADER.FIELDS] {n}", headers), b")"])
    mock_imap = _build_imap_mock(
        search_response=b"1 2 3", fetch_responses=[fetch_response] * 3
    )
    with patch("imaplib.IMAP4_SSL", return_value=mock_imap):
        out = await backend.recent_unread(limit=2)
    assert len(out) == 2
    assert out[0].subject == "Lunch?"
    assert "Sam" in out[0].sender
    assert out[0].read is False
    assert "abc-123" in out[0].id


async def test_recent_unread_decodes_rfc2047_headers(monkeypatch) -> None:
    monkeypatch.setenv("JUNO_TEST_IMAP_PW_OK4", "shh")
    cfg = _imap_cfg(env_name="JUNO_TEST_IMAP_PW_OK4")
    backend = ImapEmailBackend(cfg, _smtp_cfg())

    headers = (
        b"Subject: =?utf-8?b?SGVsbG8gd29ybGQ=?=\r\n"
        b"From: =?utf-8?q?S=C3=A9bastien?= <s@example.com>\r\n"
        b"Date: Mon, 5 May 2026 12:00:00 -0700\r\n\r\n"
    )
    fetch_response = ("OK", [(b"1 (BODY[HEADER.FIELDS] {n}", headers), b")"])
    mock_imap = _build_imap_mock(
        search_response=b"1", fetch_responses=[fetch_response]
    )
    with patch("imaplib.IMAP4_SSL", return_value=mock_imap):
        out = await backend.recent_unread(limit=1)
    assert out[0].subject == "Hello world"
    assert "Sébastien" in out[0].sender


async def test_auth_failure_raises_permission_error(monkeypatch) -> None:
    import imaplib

    monkeypatch.setenv("JUNO_TEST_IMAP_PW_BAD", "wrong")
    cfg = _imap_cfg(env_name="JUNO_TEST_IMAP_PW_BAD")
    backend = ImapEmailBackend(cfg, _smtp_cfg())

    mock_imap = MagicMock()
    mock_imap.login.side_effect = imaplib.IMAP4.error("[AUTHENTICATIONFAILED] bad pw")
    mock_imap.logout.return_value = ("OK", [b"BYE"])
    with patch("imaplib.IMAP4_SSL", return_value=mock_imap):
        with pytest.raises(EmailPermissionError):
            await backend.recent_unread(limit=10)


async def test_no_password_raises_permission_error() -> None:
    cfg = _imap_cfg(env_name="JUNO_NEVER_SET_THIS_OTHER")
    backend = ImapEmailBackend(cfg, _smtp_cfg())
    if os.environ.get("JUNO_NEVER_SET_THIS_OTHER"):
        pytest.skip("test env shadowed our 'never set' var")
    with pytest.raises(EmailPermissionError) as exc:
        await backend.recent_unread(limit=10)
    assert "JUNO_NEVER_SET_THIS_OTHER" in str(exc.value)


# ---- send --------------------------------------------------------------


async def test_send_starttls_path(monkeypatch) -> None:
    monkeypatch.setenv("JUNO_TEST_SMTP_PW_OK", "shh")
    cfg_smtp = _smtp_cfg(env_name="JUNO_TEST_SMTP_PW_OK")
    backend = ImapEmailBackend(_imap_cfg(), cfg_smtp)

    mock_smtp = MagicMock()
    mock_smtp.ehlo.return_value = (250, b"OK")
    mock_smtp.starttls.return_value = (220, b"Ready to start TLS")
    mock_smtp.login.return_value = (235, b"Authentication successful")
    mock_smtp.send_message.return_value = {}
    mock_smtp.quit.return_value = (221, b"Bye")
    with patch("smtplib.SMTP", return_value=mock_smtp):
        await backend.send(
            to="dest@example.com", subject="hi", body="hello there"
        )
    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once_with("user@example.com", "shh")
    mock_smtp.send_message.assert_called_once()


async def test_send_without_smtp_host_raises_clean_error(monkeypatch) -> None:
    monkeypatch.setenv("JUNO_TEST_SMTP_PW_OK2", "shh")
    cfg_smtp = _smtp_cfg(host="", env_name="JUNO_TEST_SMTP_PW_OK2")
    backend = ImapEmailBackend(_imap_cfg(), cfg_smtp)
    with pytest.raises(EmailBackendError) as exc:
        await backend.send(to="d@example.com", subject="x", body="y")
    assert "SMTP" in str(exc.value)


async def test_send_auth_failure_raises_permission_error(monkeypatch) -> None:
    import smtplib

    monkeypatch.setenv("JUNO_TEST_SMTP_PW_BAD", "wrong")
    cfg_smtp = _smtp_cfg(env_name="JUNO_TEST_SMTP_PW_BAD")
    backend = ImapEmailBackend(_imap_cfg(), cfg_smtp)

    mock_smtp = MagicMock()
    mock_smtp.ehlo.return_value = (250, b"OK")
    mock_smtp.starttls.return_value = (220, b"OK")
    mock_smtp.login.side_effect = smtplib.SMTPAuthenticationError(
        535, b"5.7.8 Authentication failed"
    )
    mock_smtp.quit.return_value = (221, b"Bye")
    with patch("smtplib.SMTP", return_value=mock_smtp):
        with pytest.raises(EmailPermissionError):
            await backend.send(to="d@example.com", subject="x", body="y")
