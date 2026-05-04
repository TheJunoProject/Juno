"""Chat endpoints — REST + WebSocket streaming.

Phase 4 introduces intent-aware routing inside the InteractiveLayer.
The streaming endpoint emits a richer wire format that surfaces the
intent decision and (for agentic tasks) the per-step tool calls and
results, so a companion can render a live trace.

Backwards compatibility: the {"delta": ..., "done": true} frames the
Phase 1 client expects are still sent, so an old client keeps working
— it just ignores the new {"event": ...} frames.
"""

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
    """Streaming chat over WebSocket — Phase 4 intent-aware surface.

    Wire format (server frames):

        {"event": "intent",  "path": "direct" | "agentic",
         "skills": [...], "reports": [...], "rationale": str,
         "session_id": str}

        {"event": "plan",        "text": str, "session_id": str}     # path=agentic only
        {"event": "tool_call",   "id": str, "name": str, "arguments": {...}, "session_id": str}
        {"event": "tool_result", "id": str, "name": str, "ok": bool,
         "summary": str, "error": str | null, "session_id": str}

        {"delta": str, "session_id": str, "model": "interactive", "provider": "interactive"}
        ... one frame per chunk for the direct path,
            or one consolidated frame for the agentic final answer ...

        {"done": true, "session_id": str}

        {"error": str, "detail": str | null}     # on any failure

    Backwards compatibility: the `delta` and `done` frames have the same
    shape Phase 1 used. Phase 1 clients that ignore unknown keys keep
    working.
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
        async for ev in interactive.stream_turn(
            payload.message, session_id=payload.session_id
        ):
            sid = ev.session_id
            if ev.kind == "intent":
                await websocket.send_text(
                    json.dumps({"event": "intent", **(ev.payload or {}), "session_id": sid})
                )
            elif ev.kind == "plan":
                await websocket.send_text(
                    json.dumps({"event": "plan", **(ev.payload or {}), "session_id": sid})
                )
            elif ev.kind == "tool_call":
                await websocket.send_text(
                    json.dumps({"event": "tool_call", **(ev.payload or {}), "session_id": sid})
                )
            elif ev.kind == "tool_result":
                await websocket.send_text(
                    json.dumps({"event": "tool_result", **(ev.payload or {}), "session_id": sid})
                )
            elif ev.kind == "delta":
                await websocket.send_text(
                    json.dumps(
                        {
                            "delta": ev.text,
                            "session_id": sid,
                            "model": "interactive",
                            "provider": "interactive",
                        }
                    )
                )
            elif ev.kind == "done":
                await websocket.send_text(
                    json.dumps({"done": True, "session_id": sid})
                )
            elif ev.kind == "error":
                await websocket.send_json(
                    {"error": "turn_failed", "detail": (ev.payload or {}).get("detail")}
                )
                break
    except InferenceProviderError as e:
        log.warning("Inference failure during stream: %s", e)
        try:
            await websocket.send_json({"error": "inference_failed", "detail": str(e)})
        except RuntimeError:
            pass
    except WebSocketDisconnect:
        return

    try:
        await websocket.close()
    except RuntimeError:
        pass
