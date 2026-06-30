"""CyberNote FastAPI application entry point."""

import asyncio
import contextvars
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.database import init_db

# Configure root logger once at application level.
# All other modules should only use logging.getLogger(__name__) — do NOT
# call logging.getLogger().setLevel() or logging.basicConfig() elsewhere.
# P2-3: structured-ish format with request_id context var so every log line
# for a given request can be correlated end-to-end (frontend echoes the same
# id back via the X-Request-Id response header).
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [req=%(request_id)s] %(name)s: %(message)s',
)

logger = logging.getLogger(__name__)


# P2-3: context-bound request id. Set by the middleware below; read by the
# logging filter so each log line carries the trace id without callers
# having to thread it through every function.
_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar('request_id', default='-')


class _RequestIdFilter(logging.Filter):
    """Inject the current request_id into every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get()
        return True


# Attach the filter to the root HANDLER(s), NOT the root logger.
# Filters on a logger are only applied when that logger is the ORIGINATOR
# of the log call. When child loggers (litellm, app.core.database, etc.)
# emit records that propagate up to root, the root logger's filter is NOT
# re-applied — only the originating logger's filter runs. That caused
# KeyError: 'request_id' on every line logged by a child logger, because
# the formatter expected the field but the filter never injected it.
# Handler filters, by contrast, run on every record the handler processes,
# regardless of which logger originated it.
for _h in logging.getLogger().handlers:
    _h.addFilter(_RequestIdFilter())

# Reference to managed background compile tasks (populated during lifespan)
_background_tasks: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events with graceful task cleanup."""
    await init_db()
    app.state.background_tasks = _background_tasks

    if settings.auth_mode == "none":
        logger.warning(
            "AUTH_MODE=none — authentication is DISABLED. "
            "Do NOT expose this service to a public network. "
            "Set AUTH_MODE=jwt and configure a strong SECRET_KEY for production."
        )

    # Warn if ENCRYPTION_KEY is not set separately (S1 mitigation)
    if not settings.encryption_key:
        logger.warning(
            "ENCRYPTION_KEY is not set — API keys will be encrypted with "
            "a key derived from SECRET_KEY. For production, set a separate "
            "ENCRYPTION_KEY so that a leaked JWT secret cannot decrypt stored API keys."
        )

    yield
    # Graceful shutdown: cancel pending background tasks
    for task in list(_background_tasks):
        if not task.done():
            task.cancel()
    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)
        _background_tasks.clear()

    # Close Redis and LLM cache connections
    from app.core.redis import close_redis
    from app.core.llm_cache import LLMCache
    await close_redis()
    # llm_cache is a global in llm_service; close its SQLite connection if fallback mode
    from app.services.llm_service import llm_cache as _llm_cache_instance
    if isinstance(_llm_cache_instance, LLMCache):
        await _llm_cache_instance.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)


# P2-3: request-id middleware. Generates (or trusts an inbound X-Request-Id)
# short id per request, binds it to the logging context var, and echoes it
# back on the response so the frontend / operator can correlate logs to a
# specific request without grepping by timestamp + path.
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    inbound = request.headers.get("x-request-id")
    rid = inbound if inbound and len(inbound) <= 64 else uuid.uuid4().hex[:12]
    token = _request_id_var.set(rid)
    try:
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        return response
    finally:
        _request_id_var.reset(token)

# CORS
# allow_credentials=True is incompatible with a wildcard origin (browsers
# reject it) and is also a CSRF risk once cookie-based auth is enabled.
# Resolve origins defensively: if the config is "*" but credentials are on,
# fall back to the safe local dev set instead of building an invalid policy.
_cors_raw = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
if "*" in _cors_raw:
    logger.warning(
        "CORS: wildcard origin requested with allow_credentials=True — "
        "this is invalid (browsers reject it) and insecure. "
        "Falling back to local dev origins. Set ALLOWED_ORIGINS explicitly "
        "for production."
    )
    _cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
else:
    _cors_origins = _cors_raw

# Warn if default dev origins are used with JWT auth (production-like setup)
_DEFAULT_DEV_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}
if settings.auth_mode == "jwt" and set(_cors_origins) == _DEFAULT_DEV_ORIGINS:
    logger.warning(
        "CORS: using default local dev origins with AUTH_MODE=jwt. "
        "Set ALLOWED_ORIGINS to your production frontend URL(s) for deployment."
    )

# Warn if Redis is configured (implies production intent) but CORS still on dev defaults
if settings.redis_url and set(_cors_origins) == _DEFAULT_DEV_ORIGINS:
    logger.warning(
        "CORS: Redis is configured (multi-instance mode) but ALLOWED_ORIGINS "
        "still defaults to local dev origins. Set ALLOWED_ORIGINS to your "
        "production frontend URL(s) for deployment."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Exception Handlers ---

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Return proper HTTP status codes for intentional HTTPExceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": -1, "message": exc.detail, "data": None},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for unexpected errors. The request_id (already in the log
    filter context) is echoed in the response so the user can paste it into
    a bug report and we can grep it out of the logs."""
    rid = _request_id_var.get()
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"code": -1, "message": "Internal server error", "data": {"trace_id": rid if rid != "-" else None}},
    )


# Health check
@app.get("/api/health")
async def health_check():
    return {"code": 0, "message": "ok", "data": {"status": "healthy"}}


# Public config endpoint — exposes non-sensitive settings to the frontend.
# Used by the SPA to decide whether to show the login page (jwt) or skip
# auth entirely (none). No secrets are exposed here.
@app.get("/api/config")
async def public_config():
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "auth_mode": settings.auth_mode,
            "app_name": settings.app_name,
            "app_version": settings.app_version,
        },
    }


# --- Register API Routers ---
# Each router is registered as its module is implemented

# Memo
from app.api.v1.memo import router as memo_router
app.include_router(memo_router, prefix="/api/v1")

# Model
from app.api.v1.model import router as model_router
app.include_router(model_router, prefix="/api/v1")

# Chat
from app.api.v1.chat import router as chat_router
app.include_router(chat_router, prefix="/api/v1")

# Compile
from app.api.v1.compile import router as compile_router
app.include_router(compile_router, prefix="/api/v1")

# Wiki
from app.api.v1.wiki import router as wiki_router
app.include_router(wiki_router, prefix="/api/v1")

# Game
from app.api.v1.game import router as game_router
app.include_router(game_router, prefix="/api/v1")

# Multi-Agent Compile
from app.api.v1.multi_agent_compile import router as multi_agent_compile_router
app.include_router(multi_agent_compile_router, prefix="/api/v1")

# Knowledge Graph
from app.api.v1.knowledge_graph import router as knowledge_graph_router
app.include_router(knowledge_graph_router, prefix="/api/v1")

# Auth (register/login — no auth dependency itself so users can sign up)
from app.api.v1.auth import router as auth_router
app.include_router(auth_router, prefix="/api/v1")
