"""FastAPI app factory.

The app holds the live `InferenceRouter`, `VoiceRouter`,
`InteractiveLayer`, `EventBus`, `JunoScheduler`, and `BackgroundRuntime`
on `app.state` so route handlers can grab them without globals.

Lifespan ordering (matters):
- Construct routers + bus first (no IO).
- Construct background runtime + register jobs (no scheduler running yet).
- Probe Ollama / voice for clear startup warnings.
- Start the scheduler last, so jobs only fire when the rest of the
  app is ready to handle their side effects.
- Tear down in reverse order on shutdown.
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
from server.agents.background import BackgroundRuntime
from server.agents.interactive import InteractiveLayer
from server.api.logging import AccessLogMiddleware, configure_logging
from server.api.routes import admin as admin_routes
from server.api.routes import background as background_routes
from server.api.routes import chat as chat_routes
from server.api.routes import health as health_routes
from server.api.routes import voice as voice_routes
from server.config import JunoConfig
from server.config.paths import resolve_paths
from server.inference import InferenceRouter
from server.scheduler import EventBus, JunoScheduler
from server.voice import VoiceRouter

log = logging.getLogger(__name__)


def create_app(config: JunoConfig, *, reports_dir: Path | None = None) -> FastAPI:
    """Build the FastAPI app.

    `reports_dir` overrides the path resolution from config — used by tests
    that want a tmpdir-rooted layout. In normal operation the path comes
    from `config.paths`.
    """
    configure_logging()

    paths = resolve_paths(config.paths)
    paths.ensure()
    effective_reports_dir = reports_dir or paths.reports_dir

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # ---- construction (no IO) -----------------------------------
        router = InferenceRouter(config.inference)
        voice_router = VoiceRouter(config.voice)
        bus = EventBus()
        scheduler = JunoScheduler(
            persist_db_path=paths.scheduler_db
            if config.background.persist_jobs
            else None,
        )
        interactive = InteractiveLayer(
            router,
            reports_dir=effective_reports_dir,
        )
        background_runtime: BackgroundRuntime | None = None
        if config.background.enabled:
            background_runtime = BackgroundRuntime(
                config,
                reports_dir=effective_reports_dir,
                inference=router,
                bus=bus,
                scheduler=scheduler,
            )
            background_runtime.register_default_jobs()

        app.state.config = config
        app.state.paths = paths
        app.state.inference_router = router
        app.state.voice_router = voice_router
        app.state.event_bus = bus
        app.state.scheduler = scheduler
        app.state.interactive_layer = interactive
        app.state.background_runtime = background_runtime

        # ---- startup probes -----------------------------------------
        ollama = router.get_provider("ollama")
        if not await ollama.is_available():
            log.warning(
                "Ollama is not reachable at %s — chat requests will fail "
                "until it is started. /api/health will report this.",
                config.inference.providers.ollama.base_url,
            )
        else:
            log.info("Ollama is reachable.")

        if not await voice_router.stt.is_available():
            log.warning(
                "Selected STT provider '%s' is not available. /api/voice/* "
                "will fail until you install the [voice] extra or change "
                "voice.stt.provider.",
                config.voice.stt.provider,
            )
        if not await voice_router.tts.is_available():
            log.warning(
                "Selected TTS provider '%s' is not available. /api/voice/* "
                "will fail until you install the [voice] extra and set "
                "voice.tts.piper.model_path, or change voice.tts.provider.",
                config.voice.tts.provider,
            )

        # ---- start scheduler last -----------------------------------
        if background_runtime is not None:
            scheduler.start()

        log.info("Juno server v%s ready (state at %s).", __version__, paths.base)

        try:
            yield
        finally:
            # ---- shutdown in reverse order --------------------------
            scheduler.shutdown()
            await router.aclose()
            await voice_router.aclose()
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
    app.include_router(voice_routes.router, prefix="/api")
    app.include_router(background_routes.router, prefix="/api")
    app.include_router(background_routes.events_router, prefix="/api")
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
