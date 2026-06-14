"""Knowledge graph API — aggregated graph data for visualization."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.graph_data_service import graph_data_service

router = APIRouter(prefix="/compile", tags=["knowledge-graph"])
logger = logging.getLogger(__name__)


@router.get("/jobs/{job_id}/knowledge-graph")
async def get_knowledge_graph(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get the full knowledge graph for a completed compilation job."""
    try:
        data = await graph_data_service.get_knowledge_graph(db, job_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"code": 0, "message": "ok", "data": data}


@router.get("/jobs/{job_id}/knowledge-graph/node/{node_id}")
async def get_node_detail(
    job_id: str, node_id: str, db: AsyncSession = Depends(get_db)
):
    """Get a single node with its related edges and wiki pages."""
    try:
        detail = await graph_data_service.get_node_detail(db, job_id, node_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    if not detail:
        raise HTTPException(404, f"Node {node_id} not found")
    return {"code": 0, "message": "ok", "data": detail}


@router.get("/jobs/{job_id}/knowledge-graph/search")
async def search_graph_nodes(
    job_id: str, q: str = Query(..., min_length=1), db: AsyncSession = Depends(get_db)
):
    """Search graph nodes by label (fuzzy match)."""
    try:
        results = await graph_data_service.search_nodes(db, job_id, q)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"code": 0, "message": "ok", "data": results}


@router.get("/jobs/{job_id}/knowledge-graph/filter")
async def filter_knowledge_graph(
    job_id: str,
    types: str | None = Query(None, description="Comma-separated node types"),
    edge_types: str | None = Query(None, description="Comma-separated edge types"),
    db: AsyncSession = Depends(get_db),
):
    """Filter the knowledge graph by node/edge types."""
    node_types = [t.strip() for t in types.split(",")] if types else None
    edge_type_list = [t.strip() for t in edge_types.split(",")] if edge_types else None
    try:
        data = await graph_data_service.filter_subgraph(
            db, job_id, node_types, edge_type_list
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"code": 0, "message": "ok", "data": data}


@router.get("/jobs/{job_id}/knowledge-graph/stream")
async def stream_graph_updates(job_id: str):
    """SSE stream for real-time graph updates during compilation.

    Currently a placeholder — emits graph_complete when compilation finishes.
    Full incremental updates will be implemented in Phase 4.
    """
    from app.services.compile_service import _compile_progress

    async def event_generator():
        last_status = None
        while True:
            progress = _compile_progress.get(job_id)
            if not progress:
                yield f"data: {json.dumps({'event': 'error', 'data': {'message': 'Job not found'}})}\n\n"
                break

            status = progress.get("status")
            if status != last_status:
                last_status = status
                if status == "completed":
                    # Emit graph_complete with the full graph
                    try:
                        from app.core.database import async_session
                        async with async_session() as db:
                            graph = await graph_data_service.get_knowledge_graph(db, job_id)
                        yield f"data: {json.dumps({'event': 'graph_complete', 'data': graph}, ensure_ascii=False)}\n\n"
                    except Exception as e:
                        logger.error("Graph stream error: %s", e)
                        yield f"data: {json.dumps({'event': 'error', 'data': {'message': str(e)}})}\n\n"
                    yield "data: [DONE]\n\n"
                    break
                elif status == "failed":
                    yield f"data: {json.dumps({'event': 'error', 'data': progress})}\n\n"
                    break

            import asyncio
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
