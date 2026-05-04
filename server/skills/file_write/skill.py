"""file_write skill — write a sandboxed text file.

Atomic write (tmp -> rename) so a crash mid-write never leaves a
half-readable file. Refuses to overwrite by default.
"""

from __future__ import annotations

from server.skills._file_sandbox import resolve_safe
from server.skills.base import Skill, SkillContext, SkillError, SkillInput, SkillResult


class FileWriteSkill(Skill):
    name = "file_write"

    async def execute(
        self, payload: SkillInput, context: SkillContext
    ) -> SkillResult:
        path = resolve_safe(payload.get("path", ""), context)
        content = payload.get("content")
        if not isinstance(content, str):
            raise SkillError("file_write requires `content` as a UTF-8 string")
        overwrite = bool(payload.get("overwrite", False))

        existed = path.exists()
        if existed and not overwrite:
            raise SkillError(
                f"file {path} already exists; pass overwrite=true to replace it"
            )

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(path)
        except OSError as e:
            # Try to clean up the tmp file on failure; ignore secondary
            # errors so the user sees the original cause.
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise SkillError(f"could not write {path}: {e}") from e

        size = path.stat().st_size
        return SkillResult(
            output={"path": str(path), "size_bytes": size, "created": not existed},
            summary=(
                f"{'Created' if not existed else 'Overwrote'} {path} "
                f"({size} bytes)."
            ),
            verification={"path": str(path), "size_bytes": size},
        )
