"""macOS clipboard skill — pbcopy / pbpaste.

Linux companion + Tauri runtime is Phase 6. For now, on non-macOS the
skill returns a clear error so the model knows not to use it.

Implementation uses subprocess directly rather than pulling in
pyperclip — pyperclip's behaviour on macOS already shells out to
pbcopy/pbpaste, and stdlib gives us better error reporting.
"""

from __future__ import annotations

import asyncio
import sys

from server.skills.base import Skill, SkillContext, SkillError, SkillInput, SkillResult


MAX_WRITE_BYTES = 1_000_000  # 1 MB — guards against the model dumping huge text


class ClipboardSkill(Skill):
    name = "clipboard"

    async def execute(
        self, payload: SkillInput, context: SkillContext
    ) -> SkillResult:
        if sys.platform != "darwin":
            raise SkillError(
                "clipboard skill is macOS-only in Phase 4. "
                "Linux support lands with the Linux companion (Phase 6+)."
            )
        mode = payload.get("mode")
        if mode == "read":
            text = await _pbpaste()
            return SkillResult(
                output={"mode": "read", "text": text, "bytes": len(text.encode("utf-8"))},
                summary=f"Read {len(text)} chars from clipboard.",
            )
        if mode == "write":
            text = payload.get("text")
            if not isinstance(text, str):
                raise SkillError("clipboard write requires `text` as a string")
            if len(text.encode("utf-8")) > MAX_WRITE_BYTES:
                raise SkillError(
                    f"clipboard write exceeds {MAX_WRITE_BYTES} bytes; refuse to flood"
                )
            await _pbcopy(text)
            return SkillResult(
                output={"mode": "write", "text": text, "bytes": len(text.encode("utf-8"))},
                summary=f"Wrote {len(text)} chars to clipboard.",
                verification={"bytes": len(text.encode("utf-8"))},
            )
        raise SkillError(f"unknown mode: {mode!r}; expected 'read' or 'write'")


async def _pbpaste() -> str:
    proc = await asyncio.create_subprocess_exec(
        "pbpaste",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise SkillError(
            f"pbpaste failed (rc={proc.returncode}): {stderr.decode().strip()}"
        )
    return stdout.decode("utf-8", errors="replace")


async def _pbcopy(text: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        "pbcopy",
        stdin=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate(input=text.encode("utf-8"))
    if proc.returncode != 0:
        raise SkillError(
            f"pbcopy failed (rc={proc.returncode}): {stderr.decode().strip()}"
        )
