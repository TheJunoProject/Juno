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
            saw_intent = False
            saw_agentic_path = False
            saw_done = False
            session_id = None
            for _ in range(500):  # generous frame ceiling
                frame = ws.receive_json()
                if "error" in frame:
                    raise AssertionError(f"server error: {frame}")
                ev = frame.get("event")
                if ev == "intent":
                    saw_intent = True
                    saw_agentic_path = frame.get("path") == "agentic"
                    continue
                if frame.get("done"):
                    saw_done = True
                    session_id = frame["session_id"]
                    break
                if frame.get("delta"):
                    chunks.append(frame["delta"])

            assert saw_intent, "Phase 4 wire format must lead with an intent frame"
            assert saw_done
            assert session_id
            assert "".join(chunks).strip() != ""
            # Direct path produces token-level streaming (multiple chunks).
            # Agentic path emits a single consolidated final-text delta.
            # Either is valid; just don't accept zero deltas.
            if not saw_agentic_path:
                assert len(chunks) > 1, (
                    f"direct path should stream, got {len(chunks)} chunk(s)"
                )


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


def test_live_agentic_file_write_flow(tmp_path: Path) -> None:
    """End-to-end Phase 4: classifier routes to agentic, model calls
    file_write, the file actually appears on disk, and the agent
    produces a final answer.

    Pinned to file_write because it has a deterministic verifiable side
    effect (file size, file contents) — web_search results would be
    flaky to assert against."""
    cfg = _live_config(tmp_path / "reports")
    cfg.paths.base = str(tmp_path / "juno")
    app = create_app(cfg, reports_dir=tmp_path / "reports")
    with TestClient(app) as client:
        with client.websocket_connect("/api/chat/stream") as ws:
            ws.send_json(
                {
                    "message": (
                        "Write a file called phase4-test.md with the exact "
                        "single line 'pass' (lowercase, no quotes). Then "
                        "confirm in one short sentence what you did."
                    ),
                    "session_id": None,
                }
            )
            saw_intent = False
            saw_tool_call = False
            saw_tool_result_ok = False
            saw_final = False
            saw_done = False
            for _ in range(2000):
                frame = ws.receive_json()
                ev = frame.get("event")
                # Top-level errors have no `event` key; tool_result frames
                # carry an `error` field (which is null on success).
                if ev is None and "error" in frame and "delta" not in frame and not frame.get("done"):
                    raise AssertionError(f"server error: {frame}")
                if ev == "intent":
                    saw_intent = True
                elif ev == "tool_call" and frame.get("name") == "file_write":
                    saw_tool_call = True
                elif ev == "tool_result" and frame.get("name") == "file_write":
                    saw_tool_result_ok = bool(frame.get("ok"))
                elif "delta" in frame:
                    saw_final = True
                elif frame.get("done"):
                    saw_done = True
                    break

            assert saw_intent
            assert saw_tool_call, "model never called file_write"
            assert saw_tool_result_ok, "file_write tool reported failure"
            assert saw_final, "no final text emitted"
            assert saw_done

        # Verify the side effect.
        path = tmp_path / "juno" / "skill-data" / "phase4-test.md"
        assert path.is_file(), f"file_write did not produce {path}"
        # Trim model-side trailing whitespace/newlines that don't change semantics.
        assert path.read_text(encoding="utf-8").strip() == "pass"


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
