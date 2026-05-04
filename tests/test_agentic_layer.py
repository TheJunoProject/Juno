"""Agentic Layer loop tests against stub providers + stub skills."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from server.agents.agentic import AgenticLayer, AgenticTask
from server.config import JunoConfig
from server.config.paths import resolve_paths
from server.inference import InferenceRouter
from server.inference.base import (
    InferenceChunk,
    InferenceProvider,
    InferenceRequest,
    InferenceResponse,
    TokenUsage,
    ToolCall,
)
from server.scheduler import EventBus
from server.skills import (
    Skill,
    SkillContext,
    SkillError,
    SkillRegistry,
    SkillResult,
)
from server.skills.manifest import SkillManifest


class _ScriptedProvider(InferenceProvider):
    """Inference provider that returns a queued list of responses."""

    id = "ollama"
    name = "scripted"

    def __init__(self, responses: list[InferenceResponse]) -> None:
        self._queue = list(responses)

    async def is_available(self) -> bool:
        return True

    async def complete(self, request: InferenceRequest) -> InferenceResponse:
        if not self._queue:
            raise AssertionError(
                "scripted provider exhausted — agentic loop is calling more "
                "times than expected"
            )
        return self._queue.pop(0)

    async def stream(
        self, request: InferenceRequest
    ) -> AsyncIterator[InferenceChunk]:
        # Not used in agentic tests — agentic uses complete().
        yield InferenceChunk(model="x", provider=self.id, done=True)


class _EchoSkill(Skill):
    """A skill that just echoes its input. Used to verify dispatch."""

    name = "echo"

    async def execute(self, payload, context: SkillContext) -> SkillResult:
        return SkillResult(
            output={"echoed": payload}, summary=f"echo({payload})"
        )


class _BrokenSkill(Skill):
    """Always raises — used to verify error handling."""

    name = "broken"

    async def execute(self, payload, context: SkillContext) -> SkillResult:
        raise SkillError("intentional failure")


def _registry_with(*skills: Skill) -> SkillRegistry:
    r = SkillRegistry()
    for s in skills:
        m = SkillManifest(
            name=s.name,
            description=f"{s.name} test skill",
            when_to_use="In tests.",
        )
        r.register(s, m)
    return r


def _layer(
    tmp_path: Path, *, responses: list[InferenceResponse], skills: SkillRegistry
) -> AgenticLayer:
    config = JunoConfig()
    config.paths.base = str(tmp_path / "juno")
    paths = resolve_paths(config.paths)
    paths.ensure()
    inference = InferenceRouter(config.inference)
    inference._providers["ollama"] = _ScriptedProvider(responses)
    return AgenticLayer(
        config=config,
        paths=paths,
        inference=inference,
        skills=skills,
        bus=EventBus(),
    )


# ---- non-streaming path ----------------------------------------------


async def test_agentic_returns_final_text_with_no_tool_calls(tmp_path: Path) -> None:
    """Model emits a final text on the first turn -> loop exits cleanly."""
    layer = _layer(
        tmp_path,
        responses=[
            InferenceResponse(
                content="The answer is 42.",
                model="m",
                provider="ollama",
                usage=TokenUsage(),
                tool_calls=[],
            )
        ],
        skills=_registry_with(_EchoSkill()),
    )
    result = await layer.run(AgenticTask(instruction="What is the answer?"))
    assert result.success is True
    assert result.final_text == "The answer is 42."
    assert result.tool_calls_made == 0


async def test_agentic_dispatches_tool_call_then_finishes(tmp_path: Path) -> None:
    """First turn -> tool call. Second turn -> final text using tool output."""
    layer = _layer(
        tmp_path,
        responses=[
            InferenceResponse(
                content="",
                model="m",
                provider="ollama",
                usage=TokenUsage(),
                tool_calls=[
                    ToolCall(id="c1", name="echo", arguments={"x": "hi"})
                ],
            ),
            InferenceResponse(
                content="The echo returned hi.",
                model="m",
                provider="ollama",
                usage=TokenUsage(),
                tool_calls=[],
            ),
        ],
        skills=_registry_with(_EchoSkill()),
    )
    events = []
    async for ev in layer.stream(AgenticTask(instruction="echo hi")):
        events.append(ev.type)

    assert "tool_call" in events
    assert "tool_result" in events
    assert events[-1] == "final"


async def test_agentic_surfaces_skill_errors_to_model(tmp_path: Path) -> None:
    """A failing skill produces a tool_result with ok=False; the loop
    continues so the model can recover and produce a final answer."""
    layer = _layer(
        tmp_path,
        responses=[
            InferenceResponse(
                content="",
                model="m",
                provider="ollama",
                usage=TokenUsage(),
                tool_calls=[
                    ToolCall(id="c1", name="broken", arguments={})
                ],
            ),
            InferenceResponse(
                content="That tool failed; here's the best I can do.",
                model="m",
                provider="ollama",
                usage=TokenUsage(),
                tool_calls=[],
            ),
        ],
        skills=_registry_with(_BrokenSkill()),
    )
    events = [ev async for ev in layer.stream(AgenticTask(instruction="x"))]
    tool_results = [ev for ev in events if ev.type == "tool_result"]
    assert tool_results and tool_results[0].payload["ok"] is False
    assert tool_results[0].payload["error"] == "intentional failure"
    final = [ev for ev in events if ev.type == "final"]
    assert final and "failed" in final[0].payload["text"].lower()


async def test_agentic_iteration_cap_emits_error(tmp_path: Path) -> None:
    """If the model never emits a final, the loop bails after max_iterations."""
    # 3 turns, all of which call echo and never produce a final.
    responses = [
        InferenceResponse(
            content="",
            model="m",
            provider="ollama",
            usage=TokenUsage(),
            tool_calls=[ToolCall(id=f"c{i}", name="echo", arguments={"i": i})],
        )
        for i in range(3)
    ]
    layer = _layer(
        tmp_path, responses=responses, skills=_registry_with(_EchoSkill())
    )
    events = [
        ev
        async for ev in layer.stream(
            AgenticTask(instruction="loop forever", max_iterations=3)
        )
    ]
    assert events[-1].type == "error"
    assert "iterations" in events[-1].payload["detail"].lower()


async def test_agentic_parallel_tool_calls_in_one_turn(tmp_path: Path) -> None:
    """Multiple tool calls in a single assistant turn run concurrently."""
    layer = _layer(
        tmp_path,
        responses=[
            InferenceResponse(
                content="",
                model="m",
                provider="ollama",
                usage=TokenUsage(),
                tool_calls=[
                    ToolCall(id="a", name="echo", arguments={"k": 1}),
                    ToolCall(id="b", name="echo", arguments={"k": 2}),
                ],
            ),
            InferenceResponse(
                content="Done.",
                model="m",
                provider="ollama",
                usage=TokenUsage(),
                tool_calls=[],
            ),
        ],
        skills=_registry_with(_EchoSkill()),
    )
    events = [ev async for ev in layer.stream(AgenticTask(instruction="parallel"))]
    tool_calls = [ev for ev in events if ev.type == "tool_call"]
    tool_results = [ev for ev in events if ev.type == "tool_result"]
    assert len(tool_calls) == 2
    assert len(tool_results) == 2
    assert events[-1].type == "final"
