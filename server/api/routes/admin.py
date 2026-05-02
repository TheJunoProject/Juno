"""Admin endpoints — currently just shutdown."""

from __future__ import annotations

import logging
import os
import signal

from fastapi import APIRouter

log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/shutdown")
async def shutdown() -> dict[str, str]:
    """Graceful shutdown.

    Sends SIGTERM to ourselves so uvicorn runs its shutdown lifecycle —
    which in turn triggers the FastAPI lifespan teardown that closes the
    inference router.
    """
    log.info("Shutdown requested via API")
    os.kill(os.getpid(), signal.SIGTERM)
    return {"status": "shutting_down"}
