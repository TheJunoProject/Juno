"""messages skill — read recent inbound / send via the configured backend.

Mode-based; routes through `context.integrations.messages`. Only the
Apple Messages backend ships in Phase 5 (per CLAUDE.md hard rules
against third-party messaging integrations), but the abstraction
makes adding a signal-cli or Linux iMessage proxy backend a one-file
change.
"""

from __future__ import annotations

from server.integrations.messages import (
    MessagesBackendError,
    MessagesPermissionError,
)
from server.skills.base import Skill, SkillContext, SkillError, SkillInput, SkillResult


MAX_RECENT_LIMIT = 100


class MessagesSkill(Skill):
    name = "messages"

    async def execute(
        self, payload: SkillInput, context: SkillContext
    ) -> SkillResult:
        if context.integrations is None:
            raise SkillError(
                "messages skill called without an integrations router; "
                "this is a server wiring bug."
            )
        backend = context.integrations.messages
        mode = payload.get("mode")
        try:
            if mode == "recent":
                return await self._recent(payload, backend)
            if mode == "send":
                return await self._send(payload, backend)
        except MessagesPermissionError as e:
            raise SkillError(str(e)) from e
        except MessagesBackendError as e:
            raise SkillError(f"{backend.name}: {e}") from e
        raise SkillError(
            f"unknown messages mode: {mode!r}; expected 'recent' or 'send'"
        )

    async def _recent(self, payload: SkillInput, backend) -> SkillResult:  # noqa: ANN001
        limit = int(payload.get("limit") or 20)
        limit = max(1, min(MAX_RECENT_LIMIT, limit))
        msgs = await backend.recent(limit=limit)
        out = [
            {
                "sender": m.sender,
                "text": m.text,
                "received_at": m.received_at,
                "chat": m.chat,
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
            summary=f"{len(out)} recent inbound message(s) via {backend.name}.",
        )

    async def _send(self, payload: SkillInput, backend) -> SkillResult:  # noqa: ANN001
        to = (payload.get("to") or "").strip()
        body = payload.get("body") or ""
        if not to:
            raise SkillError("send requires `to` (phone number / handle)")
        if not body.strip():
            raise SkillError("send requires `body` (message text)")
        await backend.send(to=to, body=body)
        return SkillResult(
            output={
                "mode": "send",
                "result": f"sent to {to}",
                "backend": backend.id,
            },
            summary=f"Sent message to {to} via {backend.name}.",
            verification={"to": to, "body_chars": len(body), "backend": backend.id},
        )
