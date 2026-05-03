"""faster-whisper STT provider.

Optional. Requires `pip install -e '.[voice]'`. The class imports
faster-whisper lazily so the rest of the server still loads when the
extra isn't installed — `is_available()` returns False and the router
falls back accordingly.

Model files are downloaded automatically on first use into the
configured `download_root` (or HuggingFace's default cache).
"""

from __future__ import annotations

import asyncio
import io
import logging
from typing import TYPE_CHECKING

from server.config.schema import WhisperConfig
from server.voice.audio import AudioFormatError, read_wav_info
from server.voice.base import (
    STTProvider,
    STTProviderError,
    STTRequest,
    STTResponse,
)

if TYPE_CHECKING:
    from faster_whisper import WhisperModel  # noqa: F401  (typing only)

log = logging.getLogger(__name__)


def _try_import_whisper():
    """Best-effort import. Returns the module or None.

    Wrapped so the server still boots when faster-whisper isn't installed.
    """
    try:
        import faster_whisper  # type: ignore[import-not-found]

        return faster_whisper
    except ImportError:
        return None


class WhisperSTT(STTProvider):
    id = "whisper"
    name = "faster-whisper"

    def __init__(self, config: WhisperConfig) -> None:
        self._config = config
        # Model is lazy: first transcription triggers download + load.
        self._model: WhisperModel | None = None
        self._lib = _try_import_whisper()

    async def is_available(self) -> bool:
        return self._lib is not None

    async def _ensure_model(self) -> "WhisperModel":
        if self._lib is None:
            raise STTProviderError(
                "faster-whisper is not installed. Run "
                "`pip install -e '.[voice]'` to enable real transcription."
            )
        if self._model is None:
            # Loading reads disk + may download — push to a worker thread so
            # we don't block the asyncio loop.
            def load() -> "WhisperModel":
                return self._lib.WhisperModel(
                    self._config.model_size,
                    compute_type=self._config.compute_type,
                    download_root=self._config.download_root,
                )

            log.info(
                "Loading faster-whisper model %s (%s)…",
                self._config.model_size,
                self._config.compute_type,
            )
            self._model = await asyncio.to_thread(load)
            log.info("faster-whisper model ready.")
        return self._model

    async def transcribe(self, request: STTRequest) -> STTResponse:
        try:
            info = read_wav_info(request.audio)
        except AudioFormatError as e:
            raise STTProviderError(str(e)) from e

        model = await self._ensure_model()
        language = request.language or self._config.default_language

        def run() -> tuple[str, str | None]:
            # faster-whisper accepts a file-like object and returns a
            # generator of segments + an info struct. We materialise the
            # generator to a single text string here.
            segments, transcribe_info = model.transcribe(
                io.BytesIO(request.audio),
                language=language,
                beam_size=5,
            )
            text = "".join(seg.text for seg in segments).strip()
            return text, transcribe_info.language

        try:
            text, detected_language = await asyncio.to_thread(run)
        except Exception as e:  # faster-whisper raises bare Exceptions
            raise STTProviderError(f"Whisper transcription failed: {e}") from e

        return STTResponse(
            text=text,
            language=detected_language,
            duration_seconds=info.duration_seconds,
            provider=self.id,
            model=self._config.model_size,
        )
