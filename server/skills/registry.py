"""Skill registry — discovers, loads, and exposes skill instances.

Discovery walks every package under `server/skills/` looking for a
`skill.json` manifest. The matching Python class is loaded from the
package's `skill.py` module; the registry expects exactly one
`Skill` subclass per package.

The registry holds singleton instances of each skill — skills should
keep their constructors cheap (no IO, no model loads). Heavy state
goes inside `execute()` or behind a lazy property.
"""

from __future__ import annotations

import importlib
import inspect
import json
import logging
from pathlib import Path

from pydantic import ValidationError

from server.inference import Tool
from server.skills.base import Skill, SkillContext, SkillError, SkillResult
from server.skills.manifest import SkillManifest

log = logging.getLogger(__name__)


class SkillRegistryError(Exception):
    pass


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}
        self._manifests: dict[str, SkillManifest] = {}

    # ---- discovery / loading -------------------------------------------

    def register(self, skill: Skill, manifest: SkillManifest) -> None:
        if skill.name != manifest.name:
            raise SkillRegistryError(
                f"Skill class name '{skill.name}' does not match manifest "
                f"'{manifest.name}'"
            )
        if skill.name in self._skills:
            raise SkillRegistryError(f"Skill '{skill.name}' already registered")
        self._skills[skill.name] = skill
        self._manifests[skill.name] = manifest
        log.debug("Registered skill '%s'", skill.name)

    def discover(self, skills_root: Path | None = None) -> None:
        """Scan a directory for skill packages and register each one.

        A skill package is any subdirectory of `skills_root` containing a
        `skill.json`. The matching Python module is imported as
        `server.skills.<package_name>.skill`.
        """
        root = skills_root or _default_skills_root()
        if not root.is_dir():
            log.warning("Skills root %s does not exist; no skills discovered.", root)
            return
        for pkg_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            manifest_path = pkg_dir / "skill.json"
            if not manifest_path.is_file():
                continue
            try:
                self._load_package(pkg_dir, manifest_path)
            except SkillRegistryError as e:
                log.error("Skipping skill at %s: %s", pkg_dir, e)
            except Exception as e:
                log.exception("Unexpected failure loading skill at %s: %s", pkg_dir, e)

    def _load_package(self, pkg_dir: Path, manifest_path: Path) -> None:
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = SkillManifest.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            raise SkillRegistryError(f"Invalid manifest {manifest_path}: {e}") from e

        module_name = f"server.skills.{pkg_dir.name}.skill"
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            raise SkillRegistryError(
                f"Could not import {module_name} for skill '{manifest.name}': {e}"
            ) from e

        skill_cls: type[Skill] | None = None
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is Skill:
                continue
            if issubclass(obj, Skill) and obj.__module__ == module.__name__:
                skill_cls = obj
                break
        if skill_cls is None:
            raise SkillRegistryError(
                f"No Skill subclass found in {module_name}"
            )

        self.register(skill_cls(), manifest)

    # ---- introspection -------------------------------------------------

    def names(self) -> list[str]:
        return sorted(self._skills.keys())

    def manifest(self, name: str) -> SkillManifest:
        if name not in self._manifests:
            raise KeyError(name)
        return self._manifests[name]

    def manifests(self) -> list[SkillManifest]:
        return [self._manifests[n] for n in self.names()]

    def as_tools(self) -> list[Tool]:
        """Render every skill as a Tool definition for the inference layer."""
        return [
            Tool(
                name=m.name,
                description=_compose_tool_description(m),
                parameters=m.to_json_schema(),
            )
            for m in self.manifests()
        ]

    # ---- execution ------------------------------------------------------

    async def execute(
        self,
        name: str,
        payload: dict,
        context: SkillContext,
    ) -> SkillResult:
        if name not in self._skills:
            raise SkillError(f"No such skill: {name}")
        skill = self._skills[name]
        return await skill.execute(payload, context)


def _compose_tool_description(m: SkillManifest) -> str:
    """Build the description text the model sees for this tool.

    Combines `description` + `when_to_use` + (optionally) `when_not_to_use`.
    Per the agentic-design research, this string is the highest-leverage
    text in the manifest — the model uses it to decide whether to call.
    """
    parts = [m.description.strip()]
    if m.when_to_use:
        parts.append(f"Use when: {m.when_to_use.strip()}")
    if m.when_not_to_use:
        parts.append(f"Do not use when: {m.when_not_to_use.strip()}")
    return " ".join(parts)


def _default_skills_root() -> Path:
    """Repo-relative skills root: `server/skills/`."""
    return Path(__file__).resolve().parent
