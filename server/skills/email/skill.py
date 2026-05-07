"""email skill — read recent unread mail / send a plain-text message.

Mode-based; both modes route through `context.integrations.email`,
which the user's config picks (Apple Mail or IMAP). The skill itself
doesn't know or care which backend is active — that decision lives
in the IntegrationsRouter.
"""

from __future__ import annotations

from server.integrations.email import EmailBackendError, EmailPermissionError
from server.skills.base import Skill, SkillContext, SkillError, SkillInput, SkillResult


MAX_RECENT_LIMIT = 50


class EmailSkill(Skill):
    name = "email"

    async def execute(
        self, payload: SkillInput, context: SkillContext
    ) -> SkillResult:
        if context.integrations is None:
            raise SkillError(
                "email skill called without an integrations router; this is "
                "a server wiring bug, not a user error."
            )
        backend = context.integrations.email
        mode = payload.get("mode")
        try:
            if mode == "recent":
                return await self._recent(payload, backend)
            if mode == "send":
                return await self._send(payload, backend)
        except EmailPermissionError as e:
            raise SkillError(str(e)) from e
        except EmailBackendError as e:
            raise SkillError(f"{backend.name}: {e}") from e
        raise SkillError(
            f"unknown email mode: {mode!r}; expected 'recent' or 'send'"
        )

    async def _recent(self, payload: SkillInput, backend) -> SkillResult:  # noqa: ANN001
        limit = int(payload.get("limit") or 10)
        limit = max(1, min(MAX_RECENT_LIMIT, limit))
        msgs = await backend.recent_unread(limit=limit)
        out = [
            {
                "id": m.id,
                "subject": m.subject,
                "sender": m.sender,
                "received": m.received,
                "read": m.read,
            }
            for m in msgs
        ]
        return SkillResult(
            output={
                "mode": "recent",
                "messages": out,
                "count": len(out),
                "backend": backend.id,
            },
            summary=f"{len(out)} unread message(s) via {backend.name}.",
        )

    async def _send(self, payload: SkillInput, backend) -> SkillResult:  # noqa: ANN001
        to = (payload.get("to") or "").strip()
        subject = payload.get("subject") or ""
        body = payload.get("body") or ""
        if not to:
            raise SkillError("send requires `to` (recipient address)")
        if not body.strip():
            raise SkillError("send requires `body` (message content)")
        await backend.send(to=to, subject=subject, body=body)
        return SkillResult(
            output={
                "mode": "send",
                "result": f"sent to {to}",
                "backend": backend.id,
            },
            summary=f"Sent message to {to} via {backend.name}.",
            verification={
                "to": to,
                "subject": subject,
                "body_chars": len(body),
                "backend": backend.id,
            },
        )
