"""Voice API: transcribe / synthesize / full conversational turn.

Phase 2 endpoints. The full turn endpoint orchestrates
`STT → InteractiveLayer.handle_text → TTS` so the InteractiveLayer
itself stays text-in / text-out (no audio in its public interface).
"""

from __future__ import annotations

import base64
import json
import logging

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)

from server.agents.interactive import InteractiveLayer
from server.api.models import (
    SynthesizeRequest,
    TranscribeResponse,
    VoiceTurnResponse,
    WakeWordConfigResponse,
)
from server.config.schema import VoiceConfig
from server.inference.base import InferenceProviderError
from server.voice import VoiceRouter
from server.voice.base import (
    STTProviderError,
    STTRequest,
    TTSProviderError,
    TTSRequest,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/voice")


# Cap upload size to keep memory bounded. 25 MB ~ 25 minutes of 16-bit
# mono 16 kHz WAV — well over a single conversational utterance.
MAX_AUDIO_BYTES = 25 * 1024 * 1024


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    request: Request,
    audio: UploadFile = File(..., description="WAV audio (16-bit PCM mono recommended)."),
    language: str | None = Form(default=None),
) -> TranscribeResponse:
    voice: VoiceRouter = request.app.state.voice_router
    audio_bytes = await _read_upload(audio)
    try:
        result = await voice.transcribe(STTRequest(audio=audio_bytes, language=language))
    except STTProviderError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return TranscribeResponse(
        text=result.text,
        language=result.language,
        duration_seconds=result.duration_seconds,
        provider=result.provider,
        model=result.model,
    )


@router.post("/synthesize")
async def synthesize(payload: SynthesizeRequest, request: Request) -> Response:
    voice: VoiceRouter = request.app.state.voice_router
    try:
        result = await voice.synthesize(TTSRequest(text=payload.text, voice=payload.voice))
    except TTSProviderError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return Response(
        content=result.audio,
        media_type="audio/wav",
        headers={
            "X-Voice-Provider": result.provider,
            "X-Voice-Sample-Rate": str(result.sample_rate),
            "X-Voice-Duration-Seconds": f"{result.duration_seconds:.3f}",
        },
    )


@router.post("/turn", response_model=VoiceTurnResponse)
async def voice_turn(
    request: Request,
    audio: UploadFile = File(..., description="WAV audio of the user utterance."),
    session_id: str | None = Form(default=None),
    language: str | None = Form(default=None),
) -> VoiceTurnResponse:
    """Full conversational turn: audio in → STT → chat → TTS → audio out."""
    voice: VoiceRouter = request.app.state.voice_router
    interactive: InteractiveLayer = request.app.state.interactive_layer

    audio_bytes = await _read_upload(audio)

    try:
        stt_result = await voice.transcribe(
            STTRequest(audio=audio_bytes, language=language)
        )
    except STTProviderError as e:
        raise HTTPException(status_code=502, detail=f"STT failed: {e}") from e

    try:
        chat_response, sid = await interactive.handle_text(
            stt_result.text, session_id=session_id
        )
    except InferenceProviderError as e:
        raise HTTPException(status_code=502, detail=f"Chat failed: {e}") from e

    try:
        tts_result = await voice.synthesize(TTSRequest(text=chat_response.content))
    except TTSProviderError as e:
        raise HTTPException(status_code=502, detail=f"TTS failed: {e}") from e

    return VoiceTurnResponse(
        transcript=stt_result.text,
        response=chat_response.content,
        session_id=sid,
        chat_model=chat_response.model,
        chat_provider=chat_response.provider,
        stt_provider=stt_result.provider,
        tts_provider=tts_result.provider,
        audio_base64=base64.b64encode(tts_result.audio).decode("ascii"),
        audio_sample_rate=tts_result.sample_rate,
        audio_duration_seconds=tts_result.duration_seconds,
    )


@router.websocket("/turn/stream")
async def voice_turn_stream(websocket: WebSocket) -> None:
    """Streaming voice turn over WebSocket.

    Wire format:
      Client -> JSON header:
                 {"event": "start",
                  "session_id": str | null,
                  "language": str | null,
                  "audio_size": int}      bytes the server should expect
              -> binary audio (one or more frames totalling audio_size bytes)
      Server -> {"event": "transcribed", "text": str}
              -> {"event": "delta", "delta": str}   ... per token chunk
              -> binary frame: WAV bytes (the synthesized response)
              -> {"event": "done", "session_id": str,
                   "tts_provider": str, "audio_sample_rate": int,
                   "audio_duration_seconds": float}
              -> {"event": "error", "detail": str}  on any failure
    """
    await websocket.accept()
    voice: VoiceRouter = websocket.app.state.voice_router
    interactive: InteractiveLayer = websocket.app.state.interactive_layer

    try:
        header_raw = await websocket.receive_text()
    except WebSocketDisconnect:
        return

    try:
        header = json.loads(header_raw)
        if header.get("event") != "start":
            raise ValueError("first frame must be {'event': 'start', ...}")
        audio_size = int(header["audio_size"])
        if audio_size <= 0 or audio_size > MAX_AUDIO_BYTES:
            raise ValueError(
                f"audio_size must be 1..{MAX_AUDIO_BYTES} bytes, got {audio_size}"
            )
        session_id = header.get("session_id")
        language = header.get("language")
    except (ValueError, KeyError, json.JSONDecodeError, TypeError) as e:
        await websocket.send_json({"event": "error", "detail": f"bad header: {e}"})
        await websocket.close(code=1003)
        return

    # Drain the binary audio. WS messages arrive as bytes; concatenate
    # until we have audio_size bytes or the socket closes.
    audio_buf = bytearray()
    try:
        while len(audio_buf) < audio_size:
            chunk = await websocket.receive_bytes()
            audio_buf.extend(chunk)
            if len(audio_buf) > audio_size:
                # Truncate. Client sent more than it announced — accept the
                # announced amount and ignore the rest rather than failing.
                del audio_buf[audio_size:]
                break
    except WebSocketDisconnect:
        return

    audio_bytes = bytes(audio_buf)

    try:
        stt_result = await voice.transcribe(
            STTRequest(audio=audio_bytes, language=language)
        )
    except STTProviderError as e:
        await _safe_send(websocket, {"event": "error", "detail": f"STT failed: {e}"})
        await websocket.close()
        return

    await websocket.send_json({"event": "transcribed", "text": stt_result.text})

    collected: list[str] = []
    sid_out = session_id or interactive.new_session_id()
    try:
        async for chunk, sid in interactive.stream_text(
            stt_result.text, session_id=sid_out
        ):
            sid_out = sid
            if chunk.delta:
                collected.append(chunk.delta)
                await websocket.send_json({"event": "delta", "delta": chunk.delta})
    except InferenceProviderError as e:
        await _safe_send(websocket, {"event": "error", "detail": f"Chat failed: {e}"})
        await websocket.close()
        return

    final_text = "".join(collected).strip()
    if not final_text:
        # The model returned nothing — no point synthesising silence.
        await _safe_send(
            websocket,
            {"event": "error", "detail": "Empty model response; nothing to synthesise."},
        )
        await websocket.close()
        return

    try:
        tts_result = await voice.synthesize(TTSRequest(text=final_text))
    except TTSProviderError as e:
        await _safe_send(websocket, {"event": "error", "detail": f"TTS failed: {e}"})
        await websocket.close()
        return

    # Audio first (so the client can begin buffering it), then the done frame.
    await websocket.send_bytes(tts_result.audio)
    await websocket.send_json(
        {
            "event": "done",
            "session_id": sid_out,
            "tts_provider": tts_result.provider,
            "audio_sample_rate": tts_result.sample_rate,
            "audio_duration_seconds": tts_result.duration_seconds,
        }
    )
    await websocket.close()


@router.get("/wakeword", response_model=WakeWordConfigResponse)
async def wakeword(request: Request) -> WakeWordConfigResponse:
    """Companion fetches wake word config to run detection locally."""
    cfg: VoiceConfig = request.app.state.config.voice
    return WakeWordConfigResponse(
        enabled=cfg.wakeword.enabled,
        keyword=cfg.wakeword.keyword,
        sensitivity=cfg.wakeword.sensitivity,
        model=cfg.wakeword.model,
    )


async def _read_upload(upload: UploadFile) -> bytes:
    data = await upload.read()
    if not data:
        raise HTTPException(status_code=422, detail="audio upload was empty")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"audio upload exceeds {MAX_AUDIO_BYTES} bytes",
        )
    return data


async def _safe_send(websocket: WebSocket, payload: dict) -> None:
    try:
        await websocket.send_json(payload)
    except (RuntimeError, WebSocketDisconnect):
        # Socket already closed; nothing to do.
        pass