"""Integration layer.

Each domain (email, calendar, messages, system) ships:

    server/integrations/<domain>/
        base.py            <Domain>Backend ABC + shared types
        <backend>.py       one file per concrete implementation
                           (apple_*, imap, caldav, ...)

`server/integrations/router.py` is the single chokepoint that picks
the active backend per domain from the user's config. Skills and
background jobs always go through the router; they never import
backend implementations directly. This is the same pattern Juno uses
for inference and voice providers.
"""

from server.integrations.router import IntegrationsRouter

__all__ = ["IntegrationsRouter"]
