"""Voice router.

Mirrors `server/inference/router.py` for STT + TTS. Owns the live
provider instances picked by config and exposes a thin call surface
(`transcribe`, `synthesize`) so callers don't have to know which
backend is wired up.
"""

from __future__ import annotations

import logging

from server.config.schema import VoiceConfig
from server.voice.base import (
    STTProvider,
    STTRequest,
    STTResponse,
    TTSProvider,
    TTSRequest,
    TTSResponse,
)
from server.voice.providers.stt_stub import StubSTT
from server.voice.providers.stt_whisper import WhisperSTT
from server.voice.providers.tts_piper import PiperTTS
from server.voice.providers.tts_stub import StubTTS

log = logging.getLogger(__name__)


class VoiceRouter:
    def __init__(self, config: VoiceConfig) -> None:
        self._config = config

        # All providers are constructed up front (cheap — they don't load
        # models in __init__). The active one is selected by config; the
        # others sit idle in case the user toggles the config and reloads.
        self._stt_providers: dict[str, STTProvider] = {
            "stub": StubSTT(),
            "whisper": WhisperSTT(config.stt.whisper),
        }
        self._tts_providers: dict[str, TTSProvider] = {
            "stub": StubTTS(),
            "piper": PiperTTS(config.tts.piper),
        }

    @property
    def stt(self) -> STTProvider:
        return self._stt_providers[self._config.stt.provider]

    @property
    def tts(self) -> TTSProvider:
        return self._tts_providers[self._config.tts.provider]

    def all_stt_providers(self) -> dict[str, STTProvider]:
        return dict(self._stt_providers)

    def all_tts_providers(self) -> dict[str, TTSProvider]:
        return dict(self._tts_providers)

    async def transcribe(self, request: STTRequest) -> STTResponse:
        return await self.stt.transcribe(request)

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        return await self.tts.synthesize(request)

    async def aclose(self) -> None:
        for p in self._stt_providers.values():
            await p.aclose()
        for p in self._tts_providers.values():
            await p.aclose()
