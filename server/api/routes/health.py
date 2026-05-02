"""Health endpoint. Reflects per-provider availability."""

from __future__ import annotations

from fastapi import APIRouter, Request

from server.api.models import HealthResponse, ProviderHealth
from server.config.schema import OllamaProviderConfig
from server.inference import InferenceRouter

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    inference_router: InferenceRouter = request.app.state.inference_router
    providers: dict[str, ProviderHealth] = {}
    for pid, provider in inference_router.all_providers().items():
        available = await provider.is_available()
        # Phase 1 only knows how to expose Ollama's configured model. Other
        # providers will plug in their own "default model" surface here.
        model = None
        if pid == "ollama":
            cfg: OllamaProviderConfig = (
                request.app.state.config.inference.providers.ollama
            )
            model = cfg.default_model
        providers[pid] = ProviderHealth(available=available, model=model)
    return HealthResponse(status="ok", providers=providers)
