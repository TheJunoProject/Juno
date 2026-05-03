"""Audio helper unit tests."""

from __future__ import annotations

import math

import pytest

from server.voice.audio import (
    AudioFormatError,
    DEFAULT_SAMPLE_RATE,
    read_wav_info,
    silent_wav,
    tone_wav,
)


def test_silent_wav_round_trip() -> None:
    wav = silent_wav(0.5)
    info = read_wav_info(wav)
    assert info.sample_rate == DEFAULT_SAMPLE_RATE
    assert info.channels == 1
    assert info.sample_width_bytes == 2
    # Within one frame of 0.5s.
    assert math.isclose(info.duration_seconds, 0.5, abs_tol=1.0 / DEFAULT_SAMPLE_RATE)


def test_tone_wav_is_audible_shape() -> None:
    wav = tone_wav(0.25, frequency_hz=440.0)
    info = read_wav_info(wav)
    assert info.channels == 1
    assert info.sample_width_bytes == 2
    assert info.duration_seconds > 0


def test_silent_wav_zero_duration_still_valid_wav() -> None:
    # Edge case: 0s should not crash and should still parse as a WAV.
    wav = silent_wav(0.0)
    info = read_wav_info(wav)
    assert info.frames >= 1


def test_read_wav_info_rejects_garbage() -> None:
    with pytest.raises(AudioFormatError):
        read_wav_info(b"this is not a wav file")
