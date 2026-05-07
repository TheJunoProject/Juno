"""IntegrationsRouter unit tests — backend selection + selected_ids."""

from __future__ import annotations

from server.config import (
    CalendarIntegrationConfig,
    EmailIntegrationConfig,
    IntegrationsConfig,
    MessagesIntegrationConfig,
    SystemIntegrationConfig,
)
from server.integrations import IntegrationsRouter


def test_default_selection_picks_apple_backends() -> None:
    router = IntegrationsRouter(IntegrationsConfig())
    assert router.email.id == "apple_mail"
    assert router.calendar.id == "apple_calendar"
    assert router.messages.id == "apple_messages"
    assert router.system.id == "macos"


def test_imap_backend_selectable_via_config() -> None:
    cfg = IntegrationsConfig(
        email=EmailIntegrationConfig(backend="imap"),
        calendar=CalendarIntegrationConfig(backend="caldav"),
        messages=MessagesIntegrationConfig(),
        system=SystemIntegrationConfig(),
    )
    router = IntegrationsRouter(cfg)
    assert router.email.id == "imap"
    assert router.calendar.id == "caldav"


def test_selected_ids_reflects_config() -> None:
    cfg = IntegrationsConfig(
        email=EmailIntegrationConfig(backend="imap"),
    )
    router = IntegrationsRouter(cfg)
    assert router.selected_ids() == {
        "email": "imap",
        "calendar": "apple_calendar",
        "messages": "apple_messages",
        "system": "macos",
    }


def test_all_backends_constructed() -> None:
    """Every known backend should be in the router's `all_*` map even
    when only one is selected — /api/health exposes them all."""
    router = IntegrationsRouter(IntegrationsConfig())
    assert set(router.all_email().keys()) == {"apple_mail", "imap"}
    assert set(router.all_calendar().keys()) == {"apple_calendar", "caldav"}
    assert set(router.all_messages().keys()) == {"apple_messages"}
    assert set(router.all_system().keys()) == {"macos"}
