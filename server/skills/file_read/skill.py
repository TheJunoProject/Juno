"""file_read skill — read a sandboxed text file."""

from __future__ import annotations

from server.skills._file_sandbox import resolve_safe
from server.skills.base import Skill, SkillContext, SkillError, SkillInput, SkillResult

DEFAULT_MAX_BYTES = 200_000


class FileReadSkill(Skill):
    name = "file_read"

    async def execute(
        self, payload: SkillInput, context: SkillContext
    ) -> SkillResult:
        path = resolve_safe(payload.get("path", ""), context)
        if not path.exists():
            raise SkillError(f"file not found: {path}")
        if not path.is_file():
            raise SkillError(f"not a regular file: {path}")
        max_bytes = int(payload.get("max_bytes") or DEFAULT_MAX_BYTES)
        size = path.stat().st_size
        try:
            data = path.read_bytes()
        except OSError as e:
            raise SkillError(f"could not read {path}: {e}") from e

        truncated = False
        if len(data) > max_bytes:
            data = data[:max_bytes]
            truncated = True

        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError:
            # Binary or unknown-encoding files: surface a clear error
            # rather than handing the model a base64 dump that pretends
            # to be text.
            raise SkillError(
                f"file {path} is not valid UTF-8; binary read is not supported."
            ) from None

        if truncated:
            content += f"\n\n…(truncated at {max_bytes} bytes; full size {size})\n"
        return SkillResult(
            output={
                "path": str(path),
                "content": content,
                "truncated": truncated,
                "size_bytes": size,
            },
            summary=f"Read {len(data)} of {size} bytes from {path}.",
        )
