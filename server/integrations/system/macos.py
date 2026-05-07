"""macOS system backend.

Apps via AppleScript / `open` CLI; volume via `set volume output volume`;
screenshot via `screencapture`. AppleScript is preferred over System
Events for app launch/quit because it gives clearer error codes than
the wrapper.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from server.integrations._macos import (
    AppleScriptError,
    PermissionDeniedError,
    quote,
    run_script,
)
from server.integrations.system.base import (
    SystemBackend,
    SystemBackendError,
    SystemPermissionError,
)


class MacosSystemBackend(SystemBackend):
    id = "macos"
    name = "macOS (AppleScript + screencapture)"

    async def is_available(self) -> bool:
        return sys.platform == "darwin"

    # ---- apps ----------------------------------------------------------

    async def apps_list(self) -> list[str]:
        script = (
            'tell application "System Events" to '
            'get name of every process whose visible is true'
        )
        try:
            out = await run_script(script, permission_app="System Events")
        except PermissionDeniedError as e:
            raise SystemPermissionError(str(e)) from e
        except AppleScriptError as e:
            raise SystemBackendError(str(e)) from e
        return [n.strip() for n in out.split(",") if n.strip()]

    async def app_launch(self, app: str) -> None:
        proc = await asyncio.create_subprocess_exec(
            "open", "-a", app,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            raise SystemBackendError(
                f"could not launch {app!r}: {err or 'unknown'}"
            )

    async def app_quit(self, app: str) -> None:
        script = f'tell application {quote(app)} to quit'
        try:
            await run_script(script, permission_app=app)
        except PermissionDeniedError as e:
            raise SystemPermissionError(str(e)) from e
        except AppleScriptError as e:
            raise SystemBackendError(str(e)) from e

    # ---- volume --------------------------------------------------------

    async def volume_set(self, level: int) -> None:
        if not 0 <= level <= 100:
            raise SystemBackendError("volume must be between 0 and 100")
        try:
            await run_script(f"set volume output volume {level}")
        except AppleScriptError as e:
            raise SystemBackendError(str(e)) from e

    # ---- screenshot ----------------------------------------------------

    async def screenshot(self, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        proc = await asyncio.create_subprocess_exec(
            "screencapture", "-x", "-T", "0", str(target),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0 or not target.exists():
            err = stderr.decode("utf-8", errors="replace").strip()
            raise SystemBackendError(
                f"screencapture failed (rc={proc.returncode}): "
                f"{err or 'no output. Check System Settings → Privacy & Security → Screen Recording for the program running Juno.'}"
            )
