"""CyberNote FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    await init_db()
    yield


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


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"code": -1, "message": f"Internal error: {str(exc)}", "data": None},
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
