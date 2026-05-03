"""Voice API smoke tests using stub providers + a stubbed inference router.

Verifies the /api/voice/* surface works end-to-end without any real
models installed.
"""

from __future__ import annotations

import base64
import io
import json
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi.testclient import TestClient

from server.api.app import create_app
from server.config import load_config
from server.inference.base import (
    InferenceChunk,
    InferenceProvider,
    InferenceRequest,
    InferenceResponse,
    TokenUsage,
)
from server.voice.audio import silent_wav


class StubChat(InferenceProvider):
    id = "ollama"
    name = "stub"

    async def is_available(self) -> bool:
        return True

    async def complete(self, request: InferenceRequest) -> InferenceResponse:
        return InferenceResponse(
            content=f"reply to: {request.messages[-1].content}",
            model="stub-model",
            provider=self.id,
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

    async def stream(
        self, request: InferenceRequest
    ) -> AsyncIterator[InferenceChunk]:
        for piece in ["reply", " to: ", request.messages[-1].content]:
            yield InferenceChunk(delta=piece, model="stub-model", provider=self.id)
        yield InferenceChunk(model="stub-model", provider=self.id, done=True)


def _app(tmp_path: Path):
    config = load_config(tmp_path / "config.yaml")
    app = create_app(config, reports_dir=tmp_path / "reports")
    return app


def test_health_includes_voice_providers(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        app.state.inference_router._providers["ollama"] = StubChat()
        body = client.get("/api/health").json()
        assert "voice" in body
        assert "stt" in body["voice"] and "tts" in body["voice"]
        assert body["voice"]["stt"]["stub"]["available"] is True
        assert body["voice"]["stt"]["stub"]["selected"] is True
        assert body["voice"]["tts"]["stub"]["available"] is True
        # Real providers report unavailable when their deps / models aren't there.
        assert body["voice"]["tts"]["piper"]["available"] is False


def test_transcribe_endpoint_returns_stub_text(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        app.state.inference_router._providers["ollama"] = StubChat()
        wav = silent_wav(0.5)
        r = client.post(
            "/api/voice/transcribe",
            files={"audio": ("input.wav", io.BytesIO(wav), "audio/wav")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["provider"] == "stub"
        assert "[stub STT]" in body["text"]
        assert body["duration_seconds"] > 0


def test_transcribe_rejects_empty_upload(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        app.state.inference_router._providers["ollama"] = StubChat()
        r = client.post(
            "/api/voice/transcribe",
            files={"audio": ("input.wav", io.BytesIO(b""), "audio/wav")},
        )
        assert r.status_code == 422


def test_synthesize_endpoint_returns_wav_bytes(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        app.state.inference_router._providers["ollama"] = StubChat()
        r = client.post("/api/voice/synthesize", json={"text": "hello there"})
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/wav"
        assert r.headers["x-voice-provider"] == "stub"
        assert r.content.startswith(b"RIFF")


def test_voice_turn_runs_full_pipeline(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        app.state.inference_router._providers["ollama"] = StubChat()
        wav = silent_wav(0.4)
        r = client.post(
            "/api/voice/turn",
            files={"audio": ("input.wav", io.BytesIO(wav), "audio/wav")},
            data={},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "[stub STT]" in body["transcript"]
        assert body["response"].startswith("reply to:")
        assert body["chat_provider"] == "ollama"
        assert body["stt_provider"] == "stub"
        assert body["tts_provider"] == "stub"
        # Audio comes back as base64-encoded WAV.
        audio = base64.b64decode(body["audio_base64"])
        assert audio.startswith(b"RIFF")
        assert body["audio_sample_rate"] > 0
        assert body["audio_duration_seconds"] > 0


def test_voice_turn_stream_websocket(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        app.state.inference_router._providers["ollama"] = StubChat()
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

            transcribed = ws.receive_json()
            assert transcribed["event"] == "transcribed"
            assert "[stub STT]" in transcribed["text"]

            deltas: list[str] = []
            audio_bytes: bytes | None = None
            done_payload = None
            for _ in range(20):
                # Frames are either JSON or binary (the audio); peek by trying
                # JSON first and falling back to bytes.
                try:
                    msg = ws.receive()
                except Exception:
                    break
                if msg.get("text") is not None:
                    frame = json.loads(msg["text"])
                    if frame["event"] == "delta":
                        deltas.append(frame["delta"])
                    elif frame["event"] == "done":
                        done_payload = frame
                        break
                    elif frame["event"] == "error":
                        raise AssertionError(f"server error: {frame['detail']}")
                elif msg.get("bytes") is not None:
                    audio_bytes = msg["bytes"]

            assert "".join(deltas).strip().startswith("reply to:")
            assert audio_bytes is not None and audio_bytes.startswith(b"RIFF")
            assert done_payload is not None
            assert done_payload["session_id"]


def test_wakeword_endpoint_exposes_config(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        body = client.get("/api/voice/wakeword").json()
        assert body["enabled"] is True
        assert body["keyword"] == "juno"
        assert 0.0 <= body["sensitivity"] <= 1.0
