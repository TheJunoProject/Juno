"""Sandboxing helper shared by the file_read / file_write skills.

Resolves a user-supplied path against the configured allow-list. Default
allow-list is `<paths.base>/skill-data/`; the user can extend it via
`skills.file_io.allowed_paths` (Phase 5+ may add UI controls).

Without sandboxing, an Agentic Layer slip could let the model overwrite
~/.ssh/config or read ~/.aws/credentials. The model never sees outside
the sandbox unless the operator explicitly opens it up.
"""

from __future__ import annotations

from pathlib import Path

from server.skills.base import SkillContext, SkillError


def allowed_roots(context: SkillContext) -> list[Path]:
    """Return the absolute, resolved set of directories the file skills
    may touch. Always at least the sandbox dir under paths.base."""
    roots: list[Path] = []
    sandbox = (context.paths.base / "skill-data").resolve()
    sandbox.mkdir(parents=True, exist_ok=True)
    roots.append(sandbox)
    # Per-skill allow-list will land in config in Phase 5+; for now the
    # sandbox is the only allowed root. Adding more is one config field.
    return roots


def resolve_safe(path_str: str, context: SkillContext) -> Path:
    """Resolve a path string against the allow-list.

    Rejects absolute paths outside any allowed root, paths with `..`
    that would escape, and non-string inputs.
    """
    if not isinstance(path_str, str) or not path_str:
        raise SkillError("path is required and must be a non-empty string")

    p = Path(path_str)
    if not p.is_absolute():
        # Resolve relative paths against the sandbox so the model can say
        # "notes.txt" and have it land in skill-data/notes.txt.
        p = (context.paths.base / "skill-data" / p)
    p = p.resolve()

    roots = [r.resolve() for r in allowed_roots(context)]
    if not any(_is_within(p, r) for r in roots):
        raise SkillError(
            f"path '{path_str}' is outside the allowed sandbox; "
            f"allowed roots: {', '.join(str(r) for r in roots)}"
        )
    return p


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True
