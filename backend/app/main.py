"""CyberNote FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.database import init_db

# Configure root logger once at application level.
# All other modules should only use logging.getLogger(__name__) — do NOT
# call logging.getLogger().setLevel() or logging.basicConfig() elsewhere.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)

logger = logging.getLogger(__name__)

# Reference to managed background compile tasks (populated during lifespan)
_background_tasks: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events with graceful task cleanup."""
    await init_db()
    app.state.background_tasks = _background_tasks
    yield
    # Graceful shutdown: cancel pending background tasks
    for task in list(_background_tasks):
        if not task.done():
            task.cancel()
    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)
        _background_tasks.clear()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

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
    """Catch-all for unexpected errors. Logs full traceback, returns generic message."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"code": -1, "message": "Internal server error", "data": None},
    )


# Health check
@app.get("/api/health")
async def health_check():
    return {"code": 0, "message": "ok", "data": {"status": "healthy"}}


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
