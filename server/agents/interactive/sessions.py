"""In-process session memory.

Phase 1 keeps short conversational history in memory only — restarts wipe
sessions. Conversation persistence and vector retrieval land in Phase 7.
"""

from __future__ import annotations

import uuid
from collections import OrderedDict
from collections.abc import Iterable

from server.inference.base import Message


class SessionStore:
    """Bounded LRU of session_id -> message history."""

    def __init__(self, *, max_sessions: int = 256, max_messages: int = 40) -> None:
        self._max_sessions = max_sessions
        self._max_messages = max_messages
        self._sessions: OrderedDict[str, list[Message]] = OrderedDict()

    def new_session_id(self) -> str:
        return uuid.uuid4().hex

    def get(self, session_id: str) -> list[Message]:
        if session_id not in self._sessions:
            return []
        # Touch for LRU.
        self._sessions.move_to_end(session_id)
        return list(self._sessions[session_id])

    def append(self, session_id: str, messages: Iterable[Message]) -> None:
        history = self._sessions.get(session_id, [])
        history.extend(messages)
        # Cap per-session history to keep prompts bounded.
        if len(history) > self._max_messages:
            history = history[-self._max_messages :]
        self._sessions[session_id] = history
        self._sessions.move_to_end(session_id)
        # Cap session count to avoid unbounded growth on a long-running server.
        while len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)
