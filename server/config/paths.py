"""Resolve the canonical on-disk paths Juno uses for user state.

The config carries a `paths.base` field; this module turns it into
absolute, mkdir'd directories. Callers throughout the server should
use `JunoPaths` rather than reaching into the config directly so the
layout decision lives in one place.

Default layout (paths.base = ~/.juno):

    ~/.juno/
      config.yaml          (managed by server/config/loader.py)
      memory/
        reports/           (Background Layer writes, Interactive reads)
        conversations/     (Phase 7)
        knowledge/         (Phase 7)
      voices/              (Piper voice models the user downloads)
      scheduler.db         (APScheduler SQLAlchemy jobstore)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from server.config.schema import PathsConfig


@dataclass(frozen=True)
class JunoPaths:
    base: Path
    reports_dir: Path
    conversations_dir: Path
    knowledge_dir: Path
    voices_dir: Path
    scheduler_db: Path

    def ensure(self) -> None:
        """Create all directories. Idempotent."""
        for d in (
            self.base,
            self.reports_dir,
            self.conversations_dir,
            self.knowledge_dir,
            self.voices_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)


def resolve_paths(config: PathsConfig) -> JunoPaths:
    base = (
        Path(config.base).expanduser().resolve()
        if config.base
        else (Path.home() / ".juno").resolve()
    )
    memory = base / "memory"
    return JunoPaths(
        base=base,
        reports_dir=memory / "reports",
        conversations_dir=memory / "conversations",
        knowledge_dir=memory / "knowledge",
        voices_dir=base / "voices",
        scheduler_db=base / "scheduler.db",
    )
