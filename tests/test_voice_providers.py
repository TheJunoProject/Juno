"""Voice provider behaviour: stubs always work; real providers report
unavailability cleanly when their dep / model isn't installed."""

from __future__ import annotations

import pytest

from server.config.schema import PiperConfig, WhisperConfig
from server.voice.audio import silent_wav
from server.voice.base import (
    STTProviderError,
    STTRequest,
    TTSProviderError,
    TTSRequest,
)
from server.voice.providers.stt_stub import StubSTT
from server.voice.providers.stt_whisper import WhisperSTT
from server.voice.providers.tts_piper import PiperTTS
from server.voice.providers.tts_stub import StubTTS


# ---- Stub STT -----------------------------------------------------------


async def test_stub_stt_is_always_available() -> None:
    p = StubSTT()
    assert await p.is_available() is True


async def test_stub_stt_returns_placeholder_with_audio_size() -> None:
    p = StubSTT()
    wav = silent_wav(0.5)
    resp = await p.transcribe(STTRequest(audio=wav))
    assert resp.provider == "stub"
    assert StubSTT.PLACEHOLDER_PREFIX in resp.text
    # Surfaces the byte count so callers know the upload reached us.
    assert str(len(wav)) in resp.text
    assert resp.duration_seconds is not None and resp.duration_seconds > 0


async def test_stub_stt_rejects_non_wav() -> None:
    p = StubSTT()
    with pytest.raises(STTProviderError):
        await p.transcribe(STTRequest(audio=b"not a wav"))


# ---- Whisper (real provider, gracefully unavailable) --------------------


async def test_whisper_unavailable_when_lib_missing() -> None:
    """faster-whisper is not in the dev install; provider must report it
    as unavailable rather than crashing the server."""
    p = WhisperSTT(WhisperConfig())
    available = await p.is_available()
    # If the [voice] extra is not installed (default for the dev env),
    # is_available is False. If it is installed, it's True. Either is fine
    # — the contract is "must not raise".
    assert isinstance(available, bool)


async def test_whisper_raises_clear_error_when_unavailable() -> None:
    p = WhisperSTT(WhisperConfig())
    if await p.is_available():
        pytest.skip("faster-whisper is installed; nothing to assert here.")
    with pytest.raises(STTProviderError) as exc:
        await p.transcribe(STTRequest(audio=silent_wav(0.1)))
    assert "faster-whisper" in str(exc.value)


# ---- Stub TTS -----------------------------------------------------------


async def test_stub_tts_returns_real_silent_wav() -> None:
    p = StubTTS()
    resp = await p.synthesize(TTSRequest(text="hello world"))
    assert resp.provider == "stub"
    assert resp.channels == 1
    assert resp.audio.startswith(b"RIFF")
    assert resp.duration_seconds >= StubTTS.MIN_DURATION


async def test_stub_tts_duration_scales_with_text_up_to_cap() -> None:
    p = StubTTS()
    short = await p.synthesize(TTSRequest(text="hi"))
    long = await p.synthesize(TTSRequest(text="hi" * 10_000))
    assert short.duration_seconds == StubTTS.MIN_DURATION
    assert long.duration_seconds == StubTTS.MAX_DURATION


# ---- Piper (real provider, gracefully unavailable) ----------------------


async def test_piper_unavailable_without_model() -> None:
    p = PiperTTS(PiperConfig())
    assert await p.is_available() is False


async def test_piper_raises_clear_error_when_unavailable() -> None:
    p = PiperTTS(PiperConfig())
    with pytest.raises(TTSProviderError):
        await p.synthesize(TTSRequest(text="hello"))
