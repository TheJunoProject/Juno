"""Background layer API.

- List jobs and their schedules / last run.
- Trigger a job manually (out of schedule).
- List + read context reports.
- Stream events from the EventBus over WebSocket.

Phase 3 surface. Phase 5 will populate the email/calendar/messages jobs
with real data; the API surface stays the same.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from server.agents.background import BackgroundRuntime
from server.api.models import (
    JobInfoResponse,
    JobLastRun,
    JobsListResponse,
    ReportInfo,
    ReportsListResponse,
)
from server.scheduler import EventBus

log = logging.getLogger(__name__)

router = APIRouter(prefix="/background")


@router.get("/jobs", response_model=JobsListResponse)
async def list_jobs(request: Request) -> JobsListResponse:
    runtime: BackgroundRuntime | None = getattr(
        request.app.state, "background_runtime", None
    )
    if runtime is None:
        return JobsListResponse(jobs=[])
    return JobsListResponse(jobs=[_to_job_info(j) for j in runtime.list_jobs()])


@router.post("/jobs/{name}/run", response_model=JobInfoResponse)
async def run_job(name: str, request: Request) -> JobInfoResponse:
    runtime: BackgroundRuntime | None = getattr(
        request.app.state, "background_runtime", None
    )
    if runtime is None:
        raise HTTPException(status_code=409, detail="background layer is disabled")
    try:
        await runtime.run_now(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no such job: {name}") from None
    # Return the freshly-updated info for the run we just executed.
    for j in runtime.list_jobs():
        if j["name"] == name:
            return _to_job_info(j)
    # Should be unreachable — run_now would have raised KeyError already.
    raise HTTPException(status_code=500, detail="job vanished after run")  # pragma: no cover


@router.get("/reports", response_model=ReportsListResponse)
async def list_reports(request: Request) -> ReportsListResponse:
    runtime: BackgroundRuntime | None = getattr(
        request.app.state, "background_runtime", None
    )
    if runtime is None:
        return ReportsListResponse(reports=[])
    return ReportsListResponse(
        reports=[ReportInfo(**r) for r in runtime.list_reports()]
    )


@router.get("/reports/{name}", response_class=PlainTextResponse)
async def read_report(name: str, request: Request) -> PlainTextResponse:
    runtime: BackgroundRuntime | None = getattr(
        request.app.state, "background_runtime", None
    )
    if runtime is None:
        raise HTTPException(status_code=404, detail="background layer is disabled")
    # Restrict to plain filenames in the reports_dir to stop traversal.
    safe = name.lstrip("/")
    if "/" in safe or ".." in safe:
        raise HTTPException(status_code=400, detail="invalid report name")
    path = runtime.reports_dir / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"no such report: {safe}")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")


def _to_job_info(d: dict) -> JobInfoResponse:
    last = d.get("last_run")
    return JobInfoResponse(
        name=d["name"],
        schedule=d.get("schedule"),
        next_run=d.get("next_run"),
        report_filename=d["report_filename"],
        last_run=JobLastRun(**last) if last else None,
    )


# ---- Event-bus stream (Background -> companion) -------------------------

events_router = APIRouter()


@events_router.websocket("/events/stream")
async def events_stream(websocket: WebSocket) -> None:
    """Subscribe to the EventBus interrupt topic.

    Wire format:
      Server -> {"event": "subscribed", "topic": "interrupts"}
              -> {"event": "interrupt",
                  "timestamp": float,
                  "payload": {...}}    one per published event
              ...

    The companion connects once at startup and keeps the socket open.
    Failures (publisher gone, network blip) are not surfaced — the
    companion is expected to reconnect with backoff.
    """
    await websocket.accept()
    bus: EventBus | None = getattr(websocket.app.state, "event_bus", None)
    if bus is None:
        await websocket.send_json({"event": "error", "detail": "no event bus"})
        await websocket.close()
        return

    await websocket.send_json({"event": "subscribed", "topic": "interrupts"})
    try:
        async with bus.subscribe("interrupts") as stream:
            async for event in stream:
                try:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "event": "interrupt",
                                "timestamp": event.timestamp,
                                "payload": event.payload,
                            }
                        )
                    )
                except WebSocketDisconnect:
                    return
    except WebSocketDisconnect:
        return
