import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, collections, documents, evaluation, health, history, search
from app.core.config import settings

logger = logging.getLogger("evidenceai.api")


def create_app() -> FastAPI:
    production = settings.environment == "production"
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Search less. Know more.",
        # Don't advertise the API's full shape on the public internet.
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def response_headers(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"  # never cache private data
        # Visible in the browser's Network tab under "Timing".
        response.headers["Server-Timing"] = f"app;dur={elapsed_ms:.1f}"
        if elapsed_ms > 1000:
            logger.warning("Slow request: %s %s took %.0f ms", request.method, request.url.path, elapsed_ms)
        return response

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(collections.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(history.router, prefix="/api")
    app.include_router(evaluation.router, prefix="/api")
    return app


app = create_app()
