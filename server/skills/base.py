"""Skill abstract base.

Every skill subclasses `Skill` and ships a `skill.json` manifest in its
package directory. The Agentic Layer calls skills only via the
registry; it never imports the skill class directly.

Skills never call models themselves — if a skill needs inference, it
goes through the inference router on the SkillContext. This keeps
provider routing decisions centralised and means a "summarise this
file" skill (Phase 5+) automatically benefits from cloud escalation
config.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from server.config import JunoConfig
from server.config.paths import JunoPaths
from server.inference import InferenceRouter
from server.scheduler import EventBus

if False:  # pragma: no cover -- typing-only to avoid import cycle
    from server.integrations import IntegrationsRouter

log = logging.getLogger(__name__)


SkillInput = dict[str, Any]
SkillOutput = dict[str, Any]


@dataclass
class SkillContext:
    """Shared resources every skill receives at execution time."""

    config: JunoConfig
    paths: JunoPaths
    inference: InferenceRouter
    bus: EventBus
    # Per-call sandbox dir under <paths.base>/skill-data/. Skills should
    # write transient artefacts here, not anywhere else on disk.
    sandbox_dir: Path
    # The active backend per integration domain (email / calendar /
    # messages / system). Optional so unit tests can construct a
    # SkillContext without spinning up real backends.
    integrations: "IntegrationsRouter | None" = None


@dataclass
class SkillResult:
    """What a skill returns. The output dict is JSON-serialisable.

    `summary` is a short human-readable line the Agentic Layer can show
    in its trace stream. `verification` is post-action state per the
    "verification is the highest-leverage thing" principle in
    docs/agent-architecture.md §8 — for skills that take action,
    populate it with what actually changed.
    """

    output: SkillOutput
    summary: str = ""
    verification: dict[str, Any] | None = None


class SkillError(Exception):
    """Skill execution failed. Carries a user-visible message."""


class Skill(ABC):
    """Stable interface every skill plugin implements."""

    name: str
    """Short identifier matching the manifest's `name` field. Must be
    valid as an OpenAI / Ollama tool name (alphanumeric + underscores)."""

    @abstractmethod
    async def execute(
        self, payload: SkillInput, context: SkillContext
    ) -> SkillResult:
        """Run the skill against `payload`, return a typed result.

        Raises `SkillError` for any user-visible failure. Unhandled
        exceptions get caught by the Agentic Layer and wrapped — but
        prefer raising `SkillError` with a clean message.
        """
