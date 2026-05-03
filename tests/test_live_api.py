"""Live API integration tests.

Skipped unless `JUNO_TEST_OLLAMA=1` is set. When enabled, these boot the
real FastAPI app against a live Ollama (using the model named in
JUNO_TEST_MODEL, defaulting to qwen2.5:7b) and exercise the public
endpoints end-to-end.

This catches orchestration regressions the unit + mocked tests can't see:
- The InteractiveLayer + InferenceRouter glue actually drives Ollama.
- WebSocket streaming yields real token chunks, not a single buffered blob.
- The voice turn pipeline (STT stub → real chat → TTS stub) round-trips
  through the API as a coherent JSON response.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.api.app import create_app
from server.config import (
    InferenceConfig,
    JunoConfig,
    OllamaProviderConfig,
    ProvidersConfig,
)
from server.voice.audio import silent_wav

LIVE = os.environ.get("JUNO_TEST_OLLAMA") == "1"
MODEL = os.environ.get("JUNO_TEST_MODEL", "qwen2.5:7b")

pytestmark = pytest.mark.skipif(
    not LIVE, reason="Set JUNO_TEST_OLLAMA=1 to run live API integration tests."
)


def _live_config(reports_dir: Path) -> JunoConfig:
    return JunoConfig(
        inference=InferenceConfig(
            providers=ProvidersConfig(
                ollama=OllamaProviderConfig(default_model=MODEL),
            ),
        ),
    )


def test_live_chat_round_trip(tmp_path: Path) -> None:
    cfg = _live_config(tmp_path / "reports")
    app = create_app(cfg, reports_dir=tmp_path / "reports")
    with TestClient(app) as client:
        r = client.post(
            "/api/chat",
            json={"message": "Reply with exactly the single word: Pong."},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["provider"] == "ollama"
        assert body["model"] == MODEL
        assert body["response"].strip() != ""
        # Real responses always carry usage numbers.
        assert body["usage"]["completion_tokens"] is not None
        assert body["usage"]["completion_tokens"] > 0


def test_live_chat_streaming_yields_real_chunks(tmp_path: Path) -> None:
    cfg = _live_config(tmp_path / "reports")
    app = create_app(cfg, reports_dir=tmp_path / "reports")
    with TestClient(app) as client:
        with client.websocket_connect("/api/chat/stream") as ws:
            ws.send_json({"message": "Count from 1 to 5.", "session_id": None})

            chunks: list[str] = []
            saw_done = False
            session_id = None
            for _ in range(500):  # generous frame ceiling
                frame = ws.receive_json()
                if "error" in frame:
                    raise AssertionError(f"server error: {frame}")
                if frame.get("done"):
                    saw_done = True
                    session_id = frame["session_id"]
                    break
                if frame.get("delta"):
                    chunks.append(frame["delta"])

            assert saw_done
            assert session_id
            # Real streaming arrives as multiple chunks. If we got one chunk
            # something is buffering server-side.
            assert len(chunks) > 1, f"expected >1 chunk, got {len(chunks)}"
            assert "".join(chunks).strip() != ""


def test_live_session_continuity(tmp_path: Path) -> None:
    cfg = _live_config(tmp_path / "reports")
    app = create_app(cfg, reports_dir=tmp_path / "reports")
    with TestClient(app) as client:
        first = client.post(
            "/api/chat",
            json={
                "message": "My favourite colour is teal. Just acknowledge.",
            },
        ).json()
        sid = first["session_id"]

        second = client.post(
            "/api/chat",
            json={
                "message": "What is my favourite colour? One word.",
                "session_id": sid,
            },
        ).json()
        # Model recall: the answer must contain "teal" (case-insensitive).
        assert "teal" in second["response"].lower(), second["response"]
        assert second["session_id"] == sid


def test_live_voice_turn_full_pipeline(tmp_path: Path) -> None:
    """Stub STT → real chat → stub TTS, all through the API."""
    cfg = _live_config(tmp_path / "reports")
    app = create_app(cfg, reports_dir=tmp_path / "reports")
    with TestClient(app) as client:
        wav = silent_wav(0.4)
        r = client.post(
            "/api/voice/turn",
            files={"audio": ("in.wav", io.BytesIO(wav), "audio/wav")},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["chat_provider"] == "ollama"
        assert body["chat_model"] == MODEL
        assert body["stt_provider"] == "stub"
        assert body["tts_provider"] == "stub"
        # The model should have produced *something* against the stub
        # transcript ("[stub STT] received 0.40s of audio ...").
        assert body["response"].strip() != ""
        assert body["audio_duration_seconds"] > 0


def test_live_voice_turn_stream_full_pipeline(tmp_path: Path) -> None:
    """Same flow over the WebSocket. Verifies the streaming wire format
    survives a real model in the middle."""
    cfg = _live_config(tmp_path / "reports")
    app = create_app(cfg, reports_dir=tmp_path / "reports")
    with TestClient(app) as client:
        wav = silent_wav(0.3)
        with client.websocket_connect("/api/voice/turn/stream") as ws:
            ws.send_text(
                json.dumps(
                    {
                        "event": "start",
                        "session_id": None,
                        "language": None,
                        "audio_size": len(wav),
                    }
                )
            )
            ws.send_bytes(wav)

            transcribed = False
            deltas: list[str] = []
            audio_bytes: bytes | None = None
            done_payload: dict | None = None

            for _ in range(2000):
                msg = ws.receive()
                if msg.get("text") is not None:
                    frame = json.loads(msg["text"])
                    ev = frame["event"]
                    if ev == "transcribed":
                        transcribed = True
                        assert "[stub STT]" in frame["text"]
                    elif ev == "delta":
                        deltas.append(frame["delta"])
                    elif ev == "done":
                        done_payload = frame
                        break
                    elif ev == "error":
                        raise AssertionError(f"server error: {frame}")
                elif msg.get("bytes") is not None:
                    audio_bytes = msg["bytes"]

            assert transcribed
            assert len(deltas) > 1, "expected real streaming, got 0/1 chunks"
            assert audio_bytes is not None and audio_bytes.startswith(b"RIFF")
            assert done_payload is not None
            assert done_payload["session_id"]
