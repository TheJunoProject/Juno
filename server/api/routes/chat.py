"""Chat endpoints — REST + WebSocket streaming."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from server.agents.interactive import InteractiveLayer
from server.api.models import ChatRequest, ChatResponse, TokenUsageWire
from server.inference.base import InferenceProviderError

log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    interactive: InteractiveLayer = request.app.state.interactive_layer
    try:
        response, sid = await interactive.handle_text(
            payload.message, session_id=payload.session_id
        )
    except InferenceProviderError as e:
        # 502: an upstream the server depends on (Ollama) failed.
        raise HTTPException(status_code=502, detail=str(e)) from e

    return ChatResponse(
        response=response.content,
        session_id=sid,
        model=response.model,
        provider=response.provider,
        usage=TokenUsageWire(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
        ),
    )


@router.websocket("/chat/stream")
async def chat_stream(websocket: WebSocket) -> None:
    """Streaming chat over WebSocket.

    Wire format:
      Client -> {"message": str, "session_id": str | null}
      Server -> {"delta": str, "session_id": str, "model": str, "provider": str}
                ... one frame per chunk ...
                {"done": true, "session_id": str}
      Server -> {"error": str}  on any failure
    """
    await websocket.accept()
    interactive: InteractiveLayer = websocket.app.state.interactive_layer

    try:
        raw = await websocket.receive_text()
    except WebSocketDisconnect:
        return

    try:
        payload = ChatRequest.model_validate_json(raw)
    except ValidationError as e:
        await websocket.send_json({"error": "invalid_request", "detail": e.errors()})
        await websocket.close(code=1003)
        return

    try:
        async for chunk, sid in interactive.stream_text(
            payload.message, session_id=payload.session_id
        ):
            if chunk.delta:
                await websocket.send_text(
                    json.dumps(
                        {
                            "delta": chunk.delta,
                            "session_id": sid,
                            "model": chunk.model,
                            "provider": chunk.provider,
                        }
                    )
                )
            if chunk.done:
                await websocket.send_text(
                    json.dumps({"done": True, "session_id": sid})
                )
    except InferenceProviderError as e:
        log.warning("Inference failure during stream: %s", e)
        try:
            await websocket.send_json({"error": "inference_failed", "detail": str(e)})
        except RuntimeError:
            # Socket already closed; nothing to do.
            pass
    except WebSocketDisconnect:
        # Client hung up mid-stream. Not exceptional.
        return

    await websocket.close()
