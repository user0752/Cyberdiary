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
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(",") if settings.allowed_origins != "*" else ["*"],
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
