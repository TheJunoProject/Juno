"""Health endpoint. Reflects per-provider availability for both the
inference layer and the voice layer."""

from __future__ import annotations

from fastapi import APIRouter, Request

from server.api.models import (
    HealthResponse,
    ProviderHealth,
    VoiceHealth,
    VoiceProviderHealth,
)
from server.config.schema import OllamaProviderConfig, VoiceConfig
from server.inference import InferenceRouter
from server.voice import VoiceRouter

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    inference_router: InferenceRouter = request.app.state.inference_router
    providers: dict[str, ProviderHealth] = {}
    for pid, provider in inference_router.all_providers().items():
        available = await provider.is_available()
        # Phase 1 only exposes Ollama's configured model surface here.
        # Other providers will plug in their own "default model" surface.
        model = None
        if pid == "ollama":
            cfg: OllamaProviderConfig = (
                request.app.state.config.inference.providers.ollama
            )
            model = cfg.default_model
        providers[pid] = ProviderHealth(available=available, model=model)

    voice_router: VoiceRouter | None = getattr(
        request.app.state, "voice_router", None
    )
    voice_health: VoiceHealth | None = None
    if voice_router is not None:
        voice_cfg: VoiceConfig = request.app.state.config.voice
        stt: dict[str, VoiceProviderHealth] = {}
        for pid, provider in voice_router.all_stt_providers().items():
            stt[pid] = VoiceProviderHealth(
                available=await provider.is_available(),
                selected=(pid == voice_cfg.stt.provider),
            )
        tts: dict[str, VoiceProviderHealth] = {}
        for pid, provider in voice_router.all_tts_providers().items():
            tts[pid] = VoiceProviderHealth(
                available=await provider.is_available(),
                selected=(pid == voice_cfg.tts.provider),
            )
        voice_health = VoiceHealth(stt=stt, tts=tts)

    return HealthResponse(status="ok", providers=providers, voice=voice_health)
