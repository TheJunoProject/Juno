"""Stub STT provider.

The default until the user installs the `[voice]` extra and switches
to the real Whisper provider. Returns a deterministic placeholder
string so the API contract works end-to-end and tests have something
they can assert on.

Not silently broken: the placeholder is unmistakably a stub, so a user
reading the response immediately knows transcription isn't really
running yet.
"""

from __future__ import annotations

from server.voice.audio import AudioFormatError, read_wav_info
from server.voice.base import (
    STTProvider,
    STTProviderError,
    STTRequest,
    STTResponse,
)


class StubSTT(STTProvider):
    id = "stub"
    name = "Stub STT (no-op placeholder)"

    PLACEHOLDER_PREFIX = "[stub STT]"

    async def is_available(self) -> bool:
        return True

    async def transcribe(self, request: STTRequest) -> STTResponse:
        try:
            info = read_wav_info(request.audio)
        except AudioFormatError as e:
            raise STTProviderError(str(e)) from e

        text = (
            f"{self.PLACEHOLDER_PREFIX} received "
            f"{info.duration_seconds:.2f}s of audio "
            f"({len(request.audio)} bytes). Install `pip install -e '.[voice]'` "
            f"and set voice.stt.provider=whisper for real transcription."
        )
        return STTResponse(
            text=text,
            language=request.language,
            duration_seconds=info.duration_seconds,
            provider=self.id,
            model=None,
        )
