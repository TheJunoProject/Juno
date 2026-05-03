"""Audio format helpers for the voice pipeline.

Pure-stdlib (`wave` + `struct`). No ffmpeg, no numpy, no soundfile —
keeps the server install lean and the format guarantees explicit.

The canonical Juno audio format is **WAV, 16-bit PCM, mono**. STT
providers may accept other formats internally; TTS providers must
produce WAV.
"""

from __future__ import annotations

import io
import math
import struct
import wave
from dataclasses import dataclass


# Default sample rate for stub-generated audio. 22050 Hz matches Piper's
# typical output and keeps the silent stub WAVs comparable in shape to
# real TTS.
DEFAULT_SAMPLE_RATE = 22050


@dataclass(frozen=True)
class WavInfo:
    sample_rate: int
    channels: int
    sample_width_bytes: int
    frames: int

    @property
    def duration_seconds(self) -> float:
        return self.frames / self.sample_rate if self.sample_rate else 0.0


class AudioFormatError(ValueError):
    """The supplied bytes are not a valid WAV file we can work with."""


def read_wav_info(data: bytes) -> WavInfo:
    """Parse a WAV header. Raises AudioFormatError on anything we can't read."""
    try:
        with wave.open(io.BytesIO(data), "rb") as wf:
            return WavInfo(
                sample_rate=wf.getframerate(),
                channels=wf.getnchannels(),
                sample_width_bytes=wf.getsampwidth(),
                frames=wf.getnframes(),
            )
    except (wave.Error, EOFError, struct.error) as e:
        raise AudioFormatError(f"Not a valid WAV: {e}") from e


def silent_wav(
    duration_seconds: float,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> bytes:
    """Build a WAV containing `duration_seconds` of silence.

    Used by the stub TTS provider so the API contract works end-to-end
    even when no real TTS backend is installed.
    """
    if duration_seconds < 0:
        raise ValueError("duration_seconds must be non-negative")
    n_frames = max(1, int(duration_seconds * sample_rate))
    silence = b"\x00\x00" * n_frames  # 16-bit zero samples
    return _pcm_to_wav(silence, sample_rate=sample_rate)


def tone_wav(
    duration_seconds: float,
    *,
    frequency_hz: float = 440.0,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    amplitude: float = 0.2,
) -> bytes:
    """Build a WAV containing a sine tone. Useful for diagnostic stubs."""
    if duration_seconds < 0:
        raise ValueError("duration_seconds must be non-negative")
    n_frames = max(1, int(duration_seconds * sample_rate))
    peak = int(32767 * max(0.0, min(1.0, amplitude)))
    samples = bytearray()
    two_pi_f_over_sr = 2.0 * math.pi * frequency_hz / sample_rate
    for i in range(n_frames):
        sample = int(peak * math.sin(two_pi_f_over_sr * i))
        samples += struct.pack("<h", sample)
    return _pcm_to_wav(bytes(samples), sample_rate=sample_rate)


def _pcm_to_wav(pcm: bytes, *, sample_rate: int) -> bytes:
    """Wrap raw 16-bit mono PCM in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()
