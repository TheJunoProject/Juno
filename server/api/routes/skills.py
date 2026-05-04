"""Skills API — currently just listing manifests."""

from __future__ import annotations

from fastapi import APIRouter, Request

from server.api.models import SkillManifestWire, SkillsListResponse
from server.skills import SkillRegistry

router = APIRouter(prefix="/skills")


@router.get("", response_model=SkillsListResponse)
async def list_skills(request: Request) -> SkillsListResponse:
    registry: SkillRegistry | None = getattr(
        request.app.state, "skill_registry", None
    )
    if registry is None:
        return SkillsListResponse(skills=[])
    out = []
    for m in registry.manifests():
        out.append(
            SkillManifestWire(
                name=m.name,
                description=m.description,
                when_to_use=m.when_to_use,
                when_not_to_use=m.when_not_to_use,
                parallelizable=m.parallelizable,
                input=m.input,
                output=m.output,
            )
        )
    return SkillsListResponse(skills=out)
