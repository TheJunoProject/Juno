"""SkillRegistry tests."""

from __future__ import annotations

import pytest

from server.skills import SkillRegistry
from server.skills.base import Skill, SkillContext, SkillResult
from server.skills.manifest import SkillManifest
from server.skills.registry import SkillRegistryError


class _DummySkill(Skill):
    name = "dummy"

    async def execute(self, payload, context: SkillContext) -> SkillResult:
        return SkillResult(output={"echo": payload}, summary="dummy ran")


def _manifest(name: str = "dummy") -> SkillManifest:
    return SkillManifest(
        name=name,
        description="A dummy skill for tests.",
        when_to_use="In tests.",
        input={"x": {"type": "string", "required": True}},
    )


def test_register_and_list() -> None:
    r = SkillRegistry()
    r.register(_DummySkill(), _manifest())
    assert r.names() == ["dummy"]
    assert r.manifest("dummy").name == "dummy"


def test_double_register_rejected() -> None:
    r = SkillRegistry()
    r.register(_DummySkill(), _manifest())
    with pytest.raises(SkillRegistryError):
        r.register(_DummySkill(), _manifest())


def test_name_mismatch_rejected() -> None:
    class Mismatched(Skill):
        name = "totally_different"

        async def execute(self, payload, context):
            return SkillResult(output={})

    r = SkillRegistry()
    with pytest.raises(SkillRegistryError):
        r.register(Mismatched(), _manifest("dummy"))


def test_as_tools_includes_when_to_use_in_description() -> None:
    r = SkillRegistry()
    r.register(_DummySkill(), _manifest())
    tools = r.as_tools()
    assert len(tools) == 1
    assert tools[0].name == "dummy"
    assert "Use when:" in tools[0].description
    assert "type" in tools[0].parameters
    assert tools[0].parameters["type"] == "object"


def test_compact_input_form_becomes_json_schema() -> None:
    m = SkillManifest(
        name="t",
        description="t",
        when_to_use="t",
        input={
            "query": {"type": "string", "required": True},
            "max_results": {"type": "integer", "required": False, "default": 5},
        },
    )
    schema = m.to_json_schema()
    assert schema["type"] == "object"
    assert schema["required"] == ["query"]
    assert "query" in schema["properties"]
    # required:true must NOT survive into the per-property block.
    assert "required" not in schema["properties"]["query"]
    assert schema["properties"]["max_results"]["default"] == 5


def test_full_json_schema_passes_through() -> None:
    m = SkillManifest(
        name="t",
        description="t",
        when_to_use="t",
        input={
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        },
    )
    schema = m.to_json_schema()
    assert schema["properties"]["q"]["type"] == "string"
    assert schema["required"] == ["q"]


def test_discover_loads_phase4_skills() -> None:
    """The default discover() picks up the four skills shipped in Phase 4."""
    r = SkillRegistry()
    r.discover()
    names = set(r.names())
    assert {"web_search", "file_read", "file_write", "clipboard"}.issubset(names)
    # Every loaded manifest should have the structural fields.
    for m in r.manifests():
        assert m.description.strip()
        assert m.when_to_use.strip()
