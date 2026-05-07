"""system skill — apps_list / app_launch / app_quit / volume_set / screenshot.

Mode-based; routes through `context.integrations.system`. Only the
macOS backend ships in Phase 5 — the abstraction reserves a clean slot
for a Linux backend (xdotool / wmctrl / pactl / grim+slurp) when the
Linux companion lands in Phase 6+.
"""

from __future__ import annotations

from datetime import datetime

from server.integrations.system import SystemBackendError, SystemPermissionError
from server.skills.base import Skill, SkillContext, SkillError, SkillInput, SkillResult


class SystemSkill(Skill):
    name = "system"

    async def execute(
        self, payload: SkillInput, context: SkillContext
    ) -> SkillResult:
        if context.integrations is None:
            raise SkillError(
                "system skill called without an integrations router; this "
                "is a server wiring bug."
            )
        backend = context.integrations.system
        mode = payload.get("mode")
        try:
            if mode == "apps_list":
                names = await backend.apps_list()
                return SkillResult(
                    output={
                        "mode": "apps_list",
                        "result": ", ".join(names),
                        "backend": backend.id,
                    },
                    summary=f"{len(names)} visible app(s).",
                )
            if mode == "app_launch":
                app = (payload.get("app") or "").strip()
                if not app:
                    raise SkillError("app_launch requires `app`")
                await backend.app_launch(app)
                return SkillResult(
                    output={
                        "mode": "app_launch",
                        "result": f"launched {app}",
                        "backend": backend.id,
                    },
                    summary=f"launched {app}",
                    verification={"app": app},
                )
            if mode == "app_quit":
                app = (payload.get("app") or "").strip()
                if not app:
                    raise SkillError("app_quit requires `app`")
                await backend.app_quit(app)
                return SkillResult(
                    output={
                        "mode": "app_quit",
                        "result": f"quit {app}",
                        "backend": backend.id,
                    },
                    summary=f"asked {app} to quit",
                )
            if mode == "volume_set":
                level = payload.get("volume")
                if not isinstance(level, int):
                    try:
                        level = int(level)
                    except (TypeError, ValueError) as e:
                        raise SkillError(
                            "volume_set requires `volume` as an integer 0..100"
                        ) from e
                await backend.volume_set(level)
                return SkillResult(
                    output={
                        "mode": "volume_set",
                        "result": f"set to {level}",
                        "backend": backend.id,
                    },
                    summary=f"system volume set to {level}",
                    verification={"volume": level},
                )
            if mode == "screenshot":
                ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                target = context.sandbox_dir / f"screenshot-{ts}.png"
                await backend.screenshot(target)
                return SkillResult(
                    output={
                        "mode": "screenshot",
                        "result": str(target),
                        "backend": backend.id,
                    },
                    summary=f"screenshot saved to {target}",
                    verification={
                        "path": str(target),
                        "size_bytes": target.stat().st_size,
                    },
                )
        except SystemPermissionError as e:
            raise SkillError(str(e)) from e
        except SystemBackendError as e:
            raise SkillError(f"{backend.name}: {e}") from e
        raise SkillError(
            f"unknown system mode: {mode!r}; expected one of "
            "apps_list / app_launch / app_quit / volume_set / screenshot"
        )
