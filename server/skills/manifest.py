"""Skill manifest schema.

Mirrors the JSON shape documented in CLAUDE.md and
`docs/agent-architecture.md` §7. Loaded from `skill.json` files at
discovery time.

The Agentic Layer derives the model-facing tool definition from the
manifest's `description`, `when_to_use`, and `input` schema. Examples
and `when_not_to_use` exist for prompt-engineering tweaks; they are
not blasted into the model context on every turn.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SkillExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: dict[str, Any]
    output: dict[str, Any] | str


class SkillManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    when_to_use: str = Field(min_length=1)
    when_not_to_use: str = ""
    parallelizable: bool = False
    # JSON Schema fragment for the input. Per CLAUDE.md the manifest can
    # use a compact `{"type": ..., "required": ...}` form *or* a full
    # JSON Schema; we accept either and the registry normalises to a real
    # JSON Schema before handing to the model.
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    examples: list[SkillExample] = Field(default_factory=list)

    def to_json_schema(self) -> dict[str, Any]:
        """Convert the compact manifest input into a JSON Schema object.

        Compact form:
            "input": {
              "query":       {"type": "string", "required": true},
              "max_results": {"type": "number", "required": false, "default": 5}
            }
        Becomes:
            {"type": "object",
             "properties": {"query": {"type": "string"}, ...},
             "required": ["query"]}

        Full JSON Schema form (manifest already has "type": "object") is
        passed through unchanged.
        """
        if self.input.get("type") == "object":
            return dict(self.input)

        properties: dict[str, Any] = {}
        required: list[str] = []
        for field_name, spec in self.input.items():
            if not isinstance(spec, dict):
                continue
            sub: dict[str, Any] = {}
            for k, v in spec.items():
                if k == "required":
                    if v:
                        required.append(field_name)
                    continue
                sub[k] = v
            properties[field_name] = sub
        schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }
        if required:
            schema["required"] = required
        return schema
