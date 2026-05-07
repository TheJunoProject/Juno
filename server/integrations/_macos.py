"""Shared AppleScript runner used by every `apple_*` backend.

Single chokepoint for `osascript` execution + safe string quoting +
permission-error wrapping. Other macOS-specific backends live one
level deeper under their domain (server/integrations/email/apple_mail.py
etc.) and pull these helpers from here.

This file used to live at `server/macos/applescript.py`; it moved
during the Phase 5 refactor that introduced the cross-platform
backend abstraction.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass

log = logging.getLogger(__name__)


DEFAULT_TIMEOUT = 30.0


class AppleScriptError(Exception):
    """AppleScript execution failed (non-zero exit, malformed output, etc.)."""

    def __init__(
        self,
        message: str,
        *,
        exit_code: int | None = None,
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr = stderr


class PermissionDeniedError(AppleScriptError):
    """macOS denied the automation request.

    Carries a user-actionable message pointing at System Settings.
    Skills surface this verbatim.
    """

    def __init__(self, app_name: str, *, exit_code: int | None = None) -> None:
        super().__init__(
            (
                f"macOS denied automation access to {app_name}. "
                f"Open System Settings → Privacy & Security → Automation, "
                f"and turn on the entry for the program running Juno "
                f"(Terminal, your IDE, or the `juno` CLI), with "
                f"{app_name} ticked underneath it."
            ),
            exit_code=exit_code,
        )
        self.app_name = app_name


@dataclass
class _OsascriptResult:
    stdout: str
    stderr: str
    exit_code: int


def quote(s: str) -> str:
    """Render a Python string as a safe AppleScript string literal.

    Wraps in double quotes and escapes backslash, double quote, and
    newline. Any user-controlled value (model tool argument, file
    path, message body, ...) MUST pass through this function before
    being concatenated into a script.
    """
    if s is None:
        return '""'
    escaped = (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "")
    )
    return f'"{escaped}"'


async def run_script(
    script: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    permission_app: str | None = None,
) -> str:
    """Execute an AppleScript via osascript and return stdout.

    Raises:
      AppleScriptError on any failure (non-zero exit, timeout).
      PermissionDeniedError on the standard macOS automation-denied
      exit code when `permission_app` is set.
    """
    if sys.platform != "darwin":
        raise AppleScriptError(
            "AppleScript is macOS-only. This integration runs only on Darwin."
        )

    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as e:
        raise AppleScriptError(f"osascript not found: {e}") from e

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError as e:
        proc.kill()
        await proc.wait()
        raise AppleScriptError(
            f"AppleScript timed out after {timeout}s."
        ) from e

    out_text = stdout.decode("utf-8", errors="replace").rstrip("\n")
    err_text = stderr.decode("utf-8", errors="replace").strip()
    rc = proc.returncode or 0

    if rc != 0:
        # `errAEEventNotPermitted` = -1743. Recognise both numeric and
        # human-readable forms.
        if permission_app is not None and (
            rc == 1
            and (
                "-1743" in err_text
                or "not allowed assistive access" in err_text.lower()
                or "is not allowed to send" in err_text.lower()
                or "not authorized" in err_text.lower()
                or "doesn't have permission" in err_text.lower()
            )
        ):
            raise PermissionDeniedError(permission_app, exit_code=rc)
        log.warning(
            "AppleScript failed (rc=%d): %s | script first 120 chars: %r",
            rc,
            err_text[:300],
            script[:120],
        )
        raise AppleScriptError(
            f"osascript exited {rc}: {err_text or '(no stderr)'}",
            exit_code=rc,
            stderr=err_text,
        )

    return out_text


# Field separator used by `apple_*` backends that emit fielded records
# from AppleScript. `@@@` is extremely unlikely to appear inside
# subjects, names, or message bodies, and avoids the AppleScript-record
# parsing nightmare. Scripts that emit this format produce one record
# per line of output.
RECORD_SEP = "|||"
FIELD_SEP = "@@@"


def split_records(stdout: str) -> list[list[str]]:
    """Parse `osascript` stdout into a list of fielded records."""
    records: list[list[str]] = []
    for line in stdout.splitlines():
        line = line.rstrip("\r")
        if not line.strip():
            continue
        records.append(line.split(FIELD_SEP))
    return records
