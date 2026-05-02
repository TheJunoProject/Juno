"""FastAPI app factory.

The app holds the live `InferenceRouter` and `InteractiveLayer` on
`app.state` so route handlers can grab them without globals.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from server import __version__
from server.agents.interactive import InteractiveLayer
from server.api.logging import AccessLogMiddleware, configure_logging
from server.api.routes import admin as admin_routes
from server.api.routes import chat as chat_routes
from server.api.routes import health as health_routes
from server.config import JunoConfig
from server.inference import InferenceRouter

log = logging.getLogger(__name__)


def create_app(config: JunoConfig, *, reports_dir: Path | None = None) -> FastAPI:
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        router = InferenceRouter(config.inference)
        interactive = InteractiveLayer(
            router,
            reports_dir=reports_dir or _default_reports_dir(),
        )
        app.state.config = config
        app.state.inference_router = router
        app.state.interactive_layer = interactive

        # Probe Ollama once at startup so the operator sees a clear warning
        # immediately if it's unreachable, instead of discovering it on the
        # first chat request. We do not treat this as fatal — the health
        # endpoint will reflect the real state, and Ollama may come up later.
        ollama = router.get_provider("ollama")
        if not await ollama.is_available():
            log.warning(
                "Ollama is not reachable at %s — chat requests will fail "
                "until it is started. /api/health will report this.",
                config.inference.providers.ollama.base_url,
            )
        else:
            log.info("Ollama is reachable.")

        # Don't log host/port here — the CLI may have overridden them, and
        # uvicorn already logs the actual bound address.
        log.info("Juno server v%s ready.", __version__)

        try:
            yield
        finally:
            await router.aclose()
            log.info("Juno server stopped cleanly.")

    app = FastAPI(
        title="Juno",
        version=__version__,
        description="Local-first personal AI assistant — server.",
        lifespan=lifespan,
    )

    app.add_middleware(AccessLogMiddleware)

    app.include_router(health_routes.router, prefix="/api")
    app.include_router(chat_routes.router, prefix="/api")
    app.include_router(admin_routes.router, prefix="/api")

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail or "http_error"},
        )

    @app.exception_handler(ValidationError)
    async def _validation_exc(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "validation_error", "detail": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "detail": str(exc)},
        )

    return app


def _default_reports_dir() -> Path:
    # The reports directory is colocated with the repo for now. Phase 3 will
    # likely move it under ~/.juno/ alongside the config so background-layer
    # outputs live with user state instead of source code.
    return Path(__file__).resolve().parents[2] / "memory" / "reports"
