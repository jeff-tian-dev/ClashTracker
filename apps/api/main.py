import logging
import os
import sys
import time
from pathlib import Path

_apps_root = Path(__file__).resolve().parent.parent
if str(_apps_root) not in sys.path:
    sys.path.insert(0, str(_apps_root))

from shared.logutil import (  # noqa: E402
    configure_logging,
    get_request_id,
    new_correlation_id,
    reset_request_id_ctx,
    set_request_id_ctx,
)

configure_logging("api")

from fastapi import FastAPI, Request, Response  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from .routers import admin, dashboard, health, legends, players, raids, tracked_clans, tracked_players, wars  # noqa: E402

logger = logging.getLogger("api")

app = FastAPI(title="Clash Tracker API", version="0.1.0")


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    incoming = request.headers.get("x-request-id") or new_correlation_id()
    request.state.request_id = incoming
    token = set_request_id_ctx(incoming)
    start = time.perf_counter()
    logger.info(
        "request started",
        extra={
            "event": "api.request.start",
            "method": request.method,
            "path": request.url.path,
            "request_id": incoming,
        },
    )
    try:
        response: Response = await call_next(request)
    except Exception:
        logger.exception(
            "request failed with unhandled exception",
            extra={
                "event": "api.request.error",
                "method": request.method,
                "path": request.url.path,
                "request_id": incoming,
            },
        )
        reset_request_id_ctx(token)
        raise

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-Id"] = incoming
    logger.info(
        "request completed",
        extra={
            "event": "api.request.complete",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "request_id": incoming,
        },
    )
    reset_request_id_ctx(token)
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    rid = getattr(request.state, "request_id", None) or get_request_id()
    logger.info(
        "request validation failed",
        extra={
            "event": "api.request.validation_error",
            "path": request.url.path,
            "errors": exc.errors(),
            "request_id": rid,
        },
    )
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "request_id": rid,
            "hint": "Fix query or body fields to match OpenAPI constraints (e.g. page >= 1).",
        },
    )


_extra_origins = os.environ.get("CORS_ORIGINS", "").split(",")
_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://jeff-tian-dev.github.io",
    "https://clashtracker.duckdns.org",
    "https://julytracker.netlify.app",
    "https://clashjulytracker.netlify.app",
    *[o.strip() for o in _extra_origins if o.strip()],
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(dashboard.router)
app.include_router(players.router)
app.include_router(wars.router)
app.include_router(raids.router)
app.include_router(legends.router)
app.include_router(tracked_clans.router)
app.include_router(tracked_players.router)
app.include_router(admin.router)

