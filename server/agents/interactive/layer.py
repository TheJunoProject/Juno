"""Interactive Layer.

Phase 4 surface area:
- Receive a text message.
- Optionally run an intent classifier to pick Path A vs Path B.
- Path A: load just the reports the classifier flagged + the persona
  prompt, single inference call, return.
- Path B: dispatch to the Agentic Layer; stream its events through to
  the API caller.
- Either way: maintain in-process session history so multi-turn works.

The layer stays text-in / text-out. The voice pipeline (Phase 2) wraps
this at the API boundary; STT / TTS never live inside the layer.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from server.agents.agentic import AgenticEvent, AgenticLayer, AgenticTask
from server.agents.interactive.classifier import IntentClassifier, IntentDecision
from server.agents.interactive.prompts import (
    JUNO_INTERACTIVE_SYSTEM_PROMPT,
    now_context_block,
    wrap_context,
)
from server.agents.interactive.sessions import SessionStore
from server.inference import (
    InferenceChunk,
    InferenceRequest,
    InferenceResponse,
    InferenceRouter,
    Message,
)
from server.memory.reports import (
    ContextReport,
    load_reports,
    render_reports_block,
)

log = logging.getLogger(__name__)


@dataclass
class InteractiveTurnEvent:
    """A single piece of progress emitted by `stream_turn`.

    Two flavours:
    - kind="delta": `text` carries an incremental token chunk for the
      direct-conversational path (Path A) or the final-text from the
      agentic path (Path B).
    - kind in {"plan", "tool_call", "tool_result", "intent"}: agentic /
      classifier metadata frames the API forwards to the client.
    """

    kind: str  # delta | intent | plan | tool_call | tool_result | done | error
    text: str = ""
    payload: dict | None = None
    session_id: str = ""


class InteractiveLayer:
    def __init__(
        self,
        router: InferenceRouter,
        *,
        reports_dir: Path,
        sessions: SessionStore | None = None,
        agentic: AgenticLayer | None = None,
        classifier: IntentClassifier | None = None,
    ) -> None:
        self._router = router
        self._reports_dir = reports_dir
        self._sessions = sessions or SessionStore()
        self._agentic = agentic
        self._classifier = classifier

    def new_session_id(self) -> str:
        return self._sessions.new_session_id()

    # ---- Phase 1 surface (kept for callers that don't want streaming) --

    async def handle_text(
        self,
        message: str,
        *,
        session_id: str | None = None,
    ) -> tuple[InferenceResponse, str]:
        """Process one text turn and return (response, session_id).

        Always uses the direct path. Voice turn callers should keep using
        this — voice + agentic streaming together is Phase 5+ work.
        """
        sid = session_id or self.new_session_id()
        decision = await self._classify_or_default(message)
        request = self._build_request(message, sid, decision=decision)
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
        """Stream one direct-path turn (Path A only).

        Phase 4 introduces `stream_turn` for the full intent-aware
        streaming surface (Path A or Path B). This method is kept as the
        Phase 1 chat-streaming endpoint for backwards compatibility and
        for callers that explicitly want a token stream of conversational
        text only.
        """
        sid = session_id or self.new_session_id()
        decision = await self._classify_or_default(message)
        request = self._build_request(message, sid, decision=decision)
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

    # ---- Phase 4 unified streaming surface ------------------------------

    async def stream_turn(
        self,
        message: str,
        *,
        session_id: str | None = None,
    ) -> AsyncIterator[InteractiveTurnEvent]:
        """Run one turn end-to-end and yield typed events.

        - Always emits an `intent` event first.
        - For direct path: streams `delta` events, then a `done` event.
        - For agentic path: streams `plan` / `tool_call` / `tool_result`
          events from the Agentic Layer, then a single `delta` carrying
          the agent's final text, then a `done` event.
        - On any failure: emits an `error` event and stops.
        """
        sid = session_id or self.new_session_id()
        decision = await self._classify_or_default(message)
        yield InteractiveTurnEvent(
            kind="intent",
            payload={
                "path": decision.path,
                "skills": decision.skills,
                "reports": decision.reports,
                "rationale": decision.rationale,
            },
            session_id=sid,
        )

        if decision.path == "agentic" and self._agentic is not None:
            async for ev in self._run_agentic(message, sid, decision):
                yield ev
            return

        # Direct path — token stream from the conversational model.
        request = self._build_request(message, sid, decision=decision)
        collected: list[str] = []
        try:
            async for chunk in self._router.stream(request):
                if chunk.delta:
                    collected.append(chunk.delta)
                    yield InteractiveTurnEvent(
                        kind="delta", text=chunk.delta, session_id=sid
                    )
        except Exception as e:
            yield InteractiveTurnEvent(
                kind="error", payload={"detail": str(e)}, session_id=sid
            )
            return
        final_text = "".join(collected)
        self._sessions.append(
            sid,
            [
                Message(role="user", content=message),
                Message(role="assistant", content=final_text),
            ],
        )
        yield InteractiveTurnEvent(kind="done", session_id=sid)

    # ---- internals ------------------------------------------------------

    async def _run_agentic(
        self,
        message: str,
        sid: str,
        decision: IntentDecision,
    ) -> AsyncIterator[InteractiveTurnEvent]:
        assert self._agentic is not None
        # Agentic context is the same just-loaded reports the direct path
        # would have seen, so the agent has the same situational
        # awareness as a direct answer would.
        reports = self._select_reports(decision)
        context_text = render_reports_block(reports)
        task = AgenticTask(
            instruction=message,
            success_criterion="Produce a concise final answer to the user's request.",
            context=context_text,
        )

        final_text = ""
        try:
            async for ev in self._agentic.stream(task):
                if ev.type == "plan":
                    yield InteractiveTurnEvent(
                        kind="plan", payload=dict(ev.payload), session_id=sid
                    )
                elif ev.type == "tool_call":
                    yield InteractiveTurnEvent(
                        kind="tool_call",
                        payload=dict(ev.payload),
                        session_id=sid,
                    )
                elif ev.type == "tool_result":
                    yield InteractiveTurnEvent(
                        kind="tool_result",
                        payload=dict(ev.payload),
                        session_id=sid,
                    )
                elif ev.type == "final":
                    final_text = ev.payload.get("text", "")
                    if final_text:
                        yield InteractiveTurnEvent(
                            kind="delta", text=final_text, session_id=sid
                        )
                elif ev.type == "error":
                    yield InteractiveTurnEvent(
                        kind="error", payload=dict(ev.payload), session_id=sid
                    )
                    return
        except Exception as e:
            yield InteractiveTurnEvent(
                kind="error", payload={"detail": str(e)}, session_id=sid
            )
            return

        self._sessions.append(
            sid,
            [
                Message(role="user", content=message),
                Message(role="assistant", content=final_text),
            ],
        )
        yield InteractiveTurnEvent(kind="done", session_id=sid)

    async def _classify_or_default(self, message: str) -> IntentDecision:
        """Run the classifier when wired; otherwise behave like Phase 3
        (direct path, load whatever reports exist)."""
        if self._classifier is None:
            return IntentDecision(
                path="direct",
                skills=[],
                reports=[r.name for r in load_reports(self._reports_dir)],
                rationale="no classifier wired",
            )
        available = [r.name for r in load_reports(self._reports_dir)]
        return await self._classifier.classify(
            message, available_reports=available
        )

    def _select_reports(self, decision: IntentDecision) -> list[ContextReport]:
        """Filter the reports on disk down to those the classifier flagged
        as relevant. Empty `decision.reports` means inject none."""
        if not decision.reports:
            return []
        wanted = set(decision.reports)
        return [
            r for r in load_reports(self._reports_dir) if r.name in wanted
        ]

    def _build_request(
        self,
        message: str,
        session_id: str,
        *,
        decision: IntentDecision,
    ) -> InferenceRequest:
        messages: list[Message] = [
            Message(role="system", content=self._build_system_prompt(decision))
        ]
        messages.extend(self._sessions.get(session_id))
        messages.append(Message(role="user", content=message))
        return InferenceRequest(messages=messages, task_type="conversational")

    def _build_system_prompt(self, decision: IntentDecision) -> str:
        sections: list[str] = [now_context_block()]
        reports = self._select_reports(decision)
        reports_block = render_reports_block(reports)
        if reports_block:
            sections.append(reports_block)
        dynamic = "\n\n".join(sections)
        return JUNO_INTERACTIVE_SYSTEM_PROMPT + wrap_context(dynamic)
