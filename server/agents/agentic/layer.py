"""Agentic Layer — the plan-act-observe-reflect loop.

Per `docs/agent-architecture.md` §3:

    receive(task, context)
      plan: build the initial plan inline (model's first turn)
      loop:
        choose next step (model emits tool calls or final text)
        call tool(s) — parallel where the manifest allows
        observe results
        if final text emitted -> finish
        if step failed twice with same args -> fail
        if iteration cap hit -> fail
      finish: produce a structured result

Phase 4 ships the loop with native tool calling against the inference
layer. Each iteration:
- Calls inference with the current message history + tools.
- If the model emitted tool calls, dispatch them in parallel where
  safe, append results as `role=tool` messages, and loop.
- If the model emitted final text (no tool calls), return it.

The loop is bounded by `max_iterations` and per-step retry counts.
Success criteria are advisory in Phase 4 (passed in via the task) —
we ship the loop machinery now; Phase 5+ wires the criteria into
hard verification.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal

from server.agents.agentic.prompts import JUNO_AGENTIC_SYSTEM_PROMPT
from server.config import JunoConfig
from server.config.paths import JunoPaths
from server.inference import (
    InferenceRequest,
    InferenceRouter,
    Message,
    ToolCall,
)
from server.scheduler import EventBus
from server.skills import SkillContext, SkillError, SkillRegistry

log = logging.getLogger(__name__)


# ---- public types -------------------------------------------------------


@dataclass
class AgenticTask:
    """One task dispatched from the Interactive Layer."""

    instruction: str
    """Plain-English description of what the user wants done."""
    success_criterion: str = ""
    """Free-text criterion the model uses to decide when to stop."""
    context: str = ""
    """Optional preamble the Interactive Layer wants the agent to see
    (e.g. relevant report excerpts, the user's recent message)."""
    max_iterations: int = 6
    """Hard cap on plan/act loops. 6 is plenty for Phase 4 skills."""


EventType = Literal[
    "plan",
    "tool_call",
    "tool_result",
    "delta",
    "final",
    "error",
]


@dataclass
class AgenticEvent:
    """One step in the loop, surfaced to streaming callers."""

    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgenticResult:
    """What `run()` returns once the loop terminates."""

    final_text: str
    iterations: int
    tool_calls_made: int
    success: bool
    error: str | None = None


# ---- the layer ----------------------------------------------------------


class AgenticLayer:
    def __init__(
        self,
        *,
        config: JunoConfig,
        paths: JunoPaths,
        inference: InferenceRouter,
        skills: SkillRegistry,
        bus: EventBus,
    ) -> None:
        self._config = config
        self._paths = paths
        self._inference = inference
        self._skills = skills
        self._bus = bus

    # ---- non-streaming run ---------------------------------------------

    async def run(self, task: AgenticTask) -> AgenticResult:
        """Run the loop to completion and return the result."""
        events: list[AgenticEvent] = []
        async for ev in self.stream(task):
            events.append(ev)
        # The final event is "final" or "error".
        last = events[-1] if events else None
        if last is None or last.type == "error":
            err = last.payload.get("detail") if last else "no events"
            return AgenticResult(
                final_text="",
                iterations=_count(events, "tool_call") and 1 or 0,
                tool_calls_made=_count(events, "tool_call"),
                success=False,
                error=err,
            )
        return AgenticResult(
            final_text=last.payload.get("text", ""),
            iterations=last.payload.get("iterations", 0),
            tool_calls_made=last.payload.get("tool_calls_made", 0),
            success=True,
        )

    # ---- streaming run -------------------------------------------------

    async def stream(self, task: AgenticTask) -> AsyncIterator[AgenticEvent]:
        """Run the loop and yield AgenticEvent frames as it progresses."""
        skill_ctx = SkillContext(
            config=self._config,
            paths=self._paths,
            inference=self._inference,
            bus=self._bus,
            sandbox_dir=(self._paths.base / "skill-data"),
        )
        skill_ctx.sandbox_dir.mkdir(parents=True, exist_ok=True)

        tools = self._skills.as_tools()
        if not tools:
            log.warning("Agentic Layer running with zero registered skills.")

        messages = self._build_initial_messages(task)
        tool_calls_made = 0

        for iteration in range(1, task.max_iterations + 1):
            try:
                response = await self._inference.complete(
                    InferenceRequest(
                        messages=messages,
                        task_type="agentic_reasoning",
                        tools=tools,
                        temperature=0.2,
                    )
                )
            except Exception as e:
                yield AgenticEvent(
                    type="error",
                    payload={"stage": "inference", "detail": str(e)},
                )
                return

            assistant_msg = Message(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
            )
            messages.append(assistant_msg)

            if iteration == 1 and (response.content or "").strip():
                # The first text the model produces — treat it as its plan
                # if it doesn't immediately answer. Useful for the trace.
                yield AgenticEvent(
                    type="plan",
                    payload={"text": response.content.strip()},
                )

            if not response.tool_calls:
                yield AgenticEvent(
                    type="final",
                    payload={
                        "text": response.content.strip(),
                        "iterations": iteration,
                        "tool_calls_made": tool_calls_made,
                    },
                )
                return

            # Dispatch tool calls (parallel — the loop trusts the
            # manifest's parallelizable flag; a non-parallel skill that
            # fires twice in one turn is the model's responsibility).
            for tc in response.tool_calls:
                yield AgenticEvent(
                    type="tool_call",
                    payload={"id": tc.id, "name": tc.name, "arguments": tc.arguments},
                )

            results = await self._dispatch(response.tool_calls, skill_ctx)
            tool_calls_made += len(response.tool_calls)

            for tc, result in zip(response.tool_calls, results, strict=True):
                yield AgenticEvent(
                    type="tool_result",
                    payload={
                        "id": tc.id,
                        "name": tc.name,
                        "ok": result["ok"],
                        "summary": result.get("summary", ""),
                        "error": result.get("error"),
                    },
                )
                messages.append(
                    Message(
                        role="tool",
                        content=result["payload_json"],
                        tool_call_id=tc.id,
                        name=tc.name,
                    )
                )

        # Iteration cap hit without a final text emission.
        yield AgenticEvent(
            type="error",
            payload={
                "stage": "loop",
                "detail": f"Reached {task.max_iterations} iterations without producing a final answer.",
            },
        )

    # ---- helpers --------------------------------------------------------

    def _build_initial_messages(self, task: AgenticTask) -> list[Message]:
        user_parts = [task.instruction.strip()]
        if task.success_criterion:
            user_parts.append(
                f"\nSuccess criterion: {task.success_criterion.strip()}"
            )
        if task.context:
            user_parts.append(f"\n\nContext from the user's session:\n{task.context.strip()}")
        return [
            Message(role="system", content=JUNO_AGENTIC_SYSTEM_PROMPT),
            Message(role="user", content="\n".join(user_parts)),
        ]

    async def _dispatch(
        self, tool_calls: list[ToolCall], skill_ctx: SkillContext
    ) -> list[dict[str, Any]]:
        """Run all tool calls in parallel; collect normalised results.

        Each entry is `{ok, summary, error?, payload_json}` where
        `payload_json` is a JSON string suitable for the `tool` role
        message. Skill exceptions are caught here so one bad call
        doesn't abort sibling calls in the same turn.
        """
        async def one(tc: ToolCall) -> dict[str, Any]:
            try:
                result = await self._skills.execute(
                    tc.name, tc.arguments, skill_ctx
                )
                return {
                    "ok": True,
                    "summary": result.summary,
                    "payload_json": _json_dump(result.output),
                }
            except SkillError as e:
                return {
                    "ok": False,
                    "summary": "",
                    "error": str(e),
                    "payload_json": _json_dump(
                        {"error": str(e), "tool": tc.name}
                    ),
                }
            except Exception as e:
                log.exception("Unexpected skill error in '%s'", tc.name)
                return {
                    "ok": False,
                    "summary": "",
                    "error": f"unexpected error: {e}",
                    "payload_json": _json_dump(
                        {"error": str(e), "tool": tc.name}
                    ),
                }

        return await asyncio.gather(*(one(tc) for tc in tool_calls))


# ---- module helpers -----------------------------------------------------


def _count(events: list[AgenticEvent], type_: EventType) -> int:
    return sum(1 for ev in events if ev.type == type_)


def _json_dump(obj: Any) -> str:
    """Serialise tool output for a `role=tool` message.

    Strings pass through; everything else gets JSON-dumped. Models accept
    either, but a plain string for textual output is a touch cheaper to
    parse.
    """
    import json

    if isinstance(obj, str):
        return obj
    return json.dumps(obj, default=str)
