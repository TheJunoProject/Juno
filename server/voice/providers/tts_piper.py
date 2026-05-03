"""Piper TTS provider.

Optional. Requires `pip install -e '.[voice]'` and a downloaded Piper
voice model (`.onnx` + `.onnx.json` pair) — see
https://github.com/rhasspy/piper/blob/master/VOICES.md.

Like the Whisper provider, lazy import + lazy model load: the server
boots cleanly when piper-tts isn't installed, just with
`is_available() == False`.
"""

from __future__ import annotations

import asyncio
import io
import logging
import wave
from pathlib import Path
from typing import TYPE_CHECKING, Any

from server.config.schema import PiperConfig
from server.voice.base import (
    TTSProvider,
    TTSProviderError,
    TTSRequest,
    TTSResponse,
)

if TYPE_CHECKING:
    pass  # piper-tts has no usable type stubs; treat as Any at runtime

log = logging.getLogger(__name__)


def _try_import_piper():
    try:
        from piper.voice import PiperVoice  # type: ignore[import-not-found]

        return PiperVoice
    except ImportError:
        return None


class PiperTTS(TTSProvider):
    id = "piper"
    name = "Piper TTS"

    def __init__(self, config: PiperConfig) -> None:
        self._config = config
        self._voice: Any | None = None
        self._voice_cls = _try_import_piper()

    async def is_available(self) -> bool:
        if self._voice_cls is None:
            return False
        if self._config.model_path is None:
            return False
        return Path(self._config.model_path).is_file()

    async def _ensure_voice(self) -> Any:
        if self._voice_cls is None:
            raise TTSProviderError(
                "piper-tts is not installed. Run "
                "`pip install -e '.[voice]'` to enable Piper synthesis."
            )
        if self._config.model_path is None:
            raise TTSProviderError(
                "voice.tts.piper.model_path is not set. Download a Piper "
                "voice model (.onnx) and set the path in your config."
            )
        if self._voice is None:
            path = self._config.model_path
            log.info("Loading Piper voice model %s…", path)
            self._voice = await asyncio.to_thread(self._voice_cls.load, path)
            log.info("Piper voice model ready.")
        return self._voice

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        voice = await self._ensure_voice()

        def synth() -> tuple[bytes, int]:
            buf = io.BytesIO()
            # Piper writes raw PCM samples through a `wave` writer it
            # configures itself with the model's native sample rate.
            with wave.open(buf, "wb") as wf:
                voice.synthesize(
                    request.text,
                    wf,
                    speaker_id=self._config.speaker_id,
                )
                sr = wf.getframerate()
            return buf.getvalue(), sr

        try:
            audio_bytes, sample_rate = await asyncio.to_thread(synth)
        except Exception as e:
            raise TTSProviderError(f"Piper synthesis failed: {e}") from e

        # Compute duration from the WAV we just produced.
        from server.voice.audio import read_wav_info

        info = read_wav_info(audio_bytes)
        return TTSResponse(
            audio=audio_bytes,
            sample_rate=sample_rate,
            channels=info.channels,
            duration_seconds=info.duration_seconds,
            provider=self.id,
            voice=request.voice,
        )
