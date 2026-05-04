"""Intent classifier tests using a stub provider."""

from __future__ import annotations

from collections.abc import AsyncIterator

from server.agents.interactive.classifier import IntentClassifier
from server.config import JunoConfig
from server.inference import InferenceRouter
from server.inference.base import (
    InferenceChunk,
    InferenceProvider,
    InferenceRequest,
    InferenceResponse,
    TokenUsage,
)
from server.skills import SkillRegistry
from server.skills.base import Skill, SkillContext, SkillResult
from server.skills.manifest import SkillManifest


class _Replier(InferenceProvider):
    id = "ollama"
    name = "stub"

    def __init__(self, content: str) -> None:
        self._content = content

    async def is_available(self) -> bool:
        return True

    async def complete(self, request: InferenceRequest) -> InferenceResponse:
        return InferenceResponse(
            content=self._content,
            model="m",
            provider=self.id,
            usage=TokenUsage(),
        )

    async def stream(
        self, request: InferenceRequest
    ) -> AsyncIterator[InferenceChunk]:
        yield InferenceChunk(model="m", provider=self.id, done=True)


class _Echo(Skill):
    name = "web_search"

    async def execute(self, payload, context: SkillContext) -> SkillResult:
        return SkillResult(output={})


def _classifier_with(content: str) -> IntentClassifier:
    config = JunoConfig()
    router = InferenceRouter(config.inference)
    router._providers["ollama"] = _Replier(content)
    registry = SkillRegistry()
    registry.register(
        _Echo(),
        SkillManifest(
            name="web_search",
            description="search",
            when_to_use="when",
        ),
    )
    return IntentClassifier(router=router, skills=registry)


async def test_classifier_parses_well_formed_json() -> None:
    classifier = _classifier_with(
        '{"path": "agentic", "skills": ["web_search"], '
        '"reports": ["news"], "rationale": "needs live search"}'
    )
    decision = await classifier.classify(
        "What's the weather right now?",
        available_reports=["news", "calendar"],
    )
    assert decision.path == "agentic"
    assert decision.skills == ["web_search"]
    assert decision.reports == ["news"]


async def test_classifier_filters_unknown_skills_and_reports() -> None:
    classifier = _classifier_with(
        '{"path": "agentic", "skills": ["bogus_skill", "web_search"], '
        '"reports": ["bogus_report", "news"], "rationale": ""}'
    )
    decision = await classifier.classify(
        "anything",
        available_reports=["news"],
    )
    assert decision.skills == ["web_search"]
    assert decision.reports == ["news"]


async def test_classifier_rejects_invalid_path_to_default() -> None:
    classifier = _classifier_with(
        '{"path": "lolwut", "skills": [], "reports": [], "rationale": "oops"}'
    )
    decision = await classifier.classify("hi", available_reports=[])
    # Invalid path -> safe default of "direct".
    assert decision.path == "direct"


async def test_classifier_handles_markdown_fenced_json() -> None:
    classifier = _classifier_with(
        '```json\n{"path": "direct", "skills": [], "reports": [], "rationale": "small talk"}\n```'
    )
    decision = await classifier.classify("hello", available_reports=[])
    assert decision.path == "direct"


async def test_classifier_handles_garbage_with_default() -> None:
    classifier = _classifier_with("not json at all")
    decision = await classifier.classify("hi", available_reports=["news"])
    # Garbage -> safe default; reports list is empty (never load when in doubt).
    assert decision.path == "direct"
    assert decision.reports == []
