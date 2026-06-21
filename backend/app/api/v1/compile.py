"""Compile API endpoints - trigger compilation, track jobs, stream progress."""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.schemas.compile import CompileJobResponse, CompileTriggerRequest
from app.schemas.memo import ApiResponse
from app.services import compile_service

router = APIRouter(
    prefix="/compile",
    tags=["compile"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/trigger", response_model=ApiResponse[CompileJobResponse])
async def trigger_compile(data: CompileTriggerRequest, db: AsyncSession = Depends(get_db)):
    """Trigger a new compile job. Runs asynchronously in the background."""
    job = await compile_service.trigger_compile(db, data.memo_ids, data.model_id)
    return ApiResponse(data=CompileJobResponse.model_validate(job))


@router.get("/jobs", response_model=ApiResponse[list[CompileJobResponse]])
async def list_jobs(db: AsyncSession = Depends(get_db)):
    """List all compile jobs, newest first."""
    jobs = await compile_service.list_jobs(db)
    return ApiResponse(data=[CompileJobResponse.model_validate(j) for j in jobs])


@router.get("/jobs/{job_id}", response_model=ApiResponse[CompileJobResponse])
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single compile job by ID."""
    job = await compile_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return ApiResponse(data=CompileJobResponse.model_validate(job))


@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(job_id: str):
    """SSE stream of compile job progress.

    Falls back to database when in-memory progress is unavailable
    (e.g. after process restart), so terminal states are always visible.
    """
    async def event_generator():
        last_progress = -1
        while True:
            progress = await compile_service.get_progress(job_id)
            if progress is None:
                # In-memory cache miss — check database for terminal state
                progress = await compile_service.get_progress_from_db(job_id)
                if progress is None:
                    yield f"data: {json.dumps({'status': 'unknown', 'message': 'Job not found'})}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                # DB has a record (likely terminal state after restart)
                yield f"data: {json.dumps(progress)}\n\n"
                yield "data: [DONE]\n\n"
                return

            current = progress.get('progress', 0)
            # Only send if progress changed
            if current != last_progress:
                last_progress = current
                yield f"data: {json.dumps(progress)}\n\n"

            status = progress.get('status', '')
            if status in ('done', 'failed', 'completed'):
                yield "data: [DONE]\n\n"
                return

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
