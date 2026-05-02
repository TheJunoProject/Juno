"""Interactive Layer.

Phase 1 surface area: receive a text message, build a prompt that includes
the system persona + any available context reports + the session history,
hand it to the inference router, return the response.

Designed to be extended (not rewritten) in later phases:
- Phase 2 adds STT / TTS by wrapping `handle_text` in audio I/O at the API
  boundary; this layer keeps speaking text in and text out.
- Phase 3 adds context reports — already loaded here, the Background Layer
  just starts populating the directory.
- Phase 4 adds intent classification: a routing step before the inference
  call decides whether to answer directly (current path) or dispatch to the
  Agentic Layer.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path

from server.agents.interactive.prompts import JUNO_SYSTEM_PROMPT
from server.agents.interactive.sessions import SessionStore
from server.inference import (
    InferenceChunk,
    InferenceRequest,
    InferenceResponse,
    InferenceRouter,
    Message,
)
from server.memory.reports import load_reports, render_reports_block

log = logging.getLogger(__name__)


class InteractiveLayer:
    def __init__(
        self,
        router: InferenceRouter,
        *,
        reports_dir: Path,
        sessions: SessionStore | None = None,
    ) -> None:
        self._router = router
        self._reports_dir = reports_dir
        self._sessions = sessions or SessionStore()

    def new_session_id(self) -> str:
        return self._sessions.new_session_id()

    async def handle_text(
        self,
        message: str,
        *,
        session_id: str | None = None,
    ) -> tuple[InferenceResponse, str]:
        """Process one text turn and return (response, session_id)."""
        sid = session_id or self.new_session_id()
        request = self._build_request(message, sid)
        response = await self._router.complete(request)
        self._sessions.append(
            sid,
            [
                Message(role="user", content=message),
                Message(role="assistant", content=response.content),
            ],
        )
        return response, sid

    async def stream_text(
        self,
        message: str,
        *,
        session_id: str | None = None,
    ) -> AsyncIterator[tuple[InferenceChunk, str]]:
        """Stream one text turn. Yields (chunk, session_id) per chunk.

        On completion, the assistant's full reply is committed to session
        history just like the non-streaming path.
        """
        sid = session_id or self.new_session_id()
        request = self._build_request(message, sid)
        collected: list[str] = []
        async for chunk in self._router.stream(request):
            if chunk.delta:
                collected.append(chunk.delta)
            yield chunk, sid

        self._sessions.append(
            sid,
            [
                Message(role="user", content=message),
                Message(role="assistant", content="".join(collected)),
            ],
        )

    def _build_request(self, message: str, session_id: str) -> InferenceRequest:
        messages: list[Message] = [
            Message(role="system", content=self._build_system_prompt())
        ]
        messages.extend(self._sessions.get(session_id))
        messages.append(Message(role="user", content=message))
        return InferenceRequest(messages=messages, task_type="conversational")

    def _build_system_prompt(self) -> str:
        # Reports are loaded fresh per turn so newly written reports take
        # effect on the next user message without a restart.
        reports = load_reports(self._reports_dir)
        if not reports:
            return JUNO_SYSTEM_PROMPT
        return f"{JUNO_SYSTEM_PROMPT}\n\n{render_reports_block(reports)}"
