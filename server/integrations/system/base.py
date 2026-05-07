"""SystemBackend — abstract base for system control (apps, volume, screenshot).

Concrete backends:
- MacosSystemBackend (AppleScript + screencapture)

A `LinuxSystemBackend` slot is reserved here for the Phase 6+ Linux
companion (xdotool / wmctrl / pactl / scrot / grim+slurp etc.).
That work is out of scope today.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class SystemBackendError(Exception):
    """System operation failed."""


class SystemPermissionError(SystemBackendError):
    """Permission required (System Events, Screen Recording, ...)."""


class SystemBackend(ABC):
    id: str
    name: str

    @abstractmethod
    async def is_available(self) -> bool: ...

    @abstractmethod
    async def apps_list(self) -> list[str]: ...

    @abstractmethod
    async def app_launch(self, app: str) -> None: ...

    @abstractmethod
    async def app_quit(self, app: str) -> None: ...

    @abstractmethod
    async def volume_set(self, level: int) -> None: ...

    @abstractmethod
    async def screenshot(self, target: Path) -> None:
        """Capture the full screen to `target`. Caller picks the path."""

    async def aclose(self) -> None:
        return None
