"""Stub TTS provider.

Returns a real silent WAV with duration proportional to text length so
the API contract works end-to-end without a Piper voice model installed.
The companion can play the result; it just won't hear anything.

Default duration model: 60 ms per character, capped at 8 seconds. This
roughly matches conversational pacing — long enough to verify audio
playback works in the companion, short enough not to block tests.
"""

from __future__ import annotations

from server.voice.audio import DEFAULT_SAMPLE_RATE, silent_wav
from server.voice.base import TTSProvider, TTSRequest, TTSResponse


class StubTTS(TTSProvider):
    id = "stub"
    name = "Stub TTS (silent WAV)"

    SECONDS_PER_CHAR = 0.06
    MIN_DURATION = 0.5
    MAX_DURATION = 8.0

    async def is_available(self) -> bool:
        return True

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        duration = max(
            self.MIN_DURATION,
            min(self.MAX_DURATION, len(request.text) * self.SECONDS_PER_CHAR),
        )
        audio = silent_wav(duration, sample_rate=DEFAULT_SAMPLE_RATE)
        return TTSResponse(
            audio=audio,
            sample_rate=DEFAULT_SAMPLE_RATE,
            channels=1,
            duration_seconds=duration,
            provider=self.id,
            voice=request.voice,
        )
