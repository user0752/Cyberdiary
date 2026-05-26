"""Wiki API endpoints - CRUD, search, graph, backlinks."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.memo import ApiResponse
from app.schemas.wiki import (
    GraphEdge,
    GraphNode,
    WikiGraphData,
    WikiPageListResponse,
    WikiPageResponse,
    WikiUpdate,
)
from app.services import wiki_service

router = APIRouter(prefix="/wiki", tags=["wiki"])


@router.get("", response_model=ApiResponse[WikiPageListResponse])
async def list_wiki(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    wiki_type: str | None = None,
    tag: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List wiki pages with pagination and optional filters."""
    items, total = await wiki_service.list_wiki_pages(
        db, page=page, page_size=page_size, wiki_type=wiki_type, tag=tag,
    )
    return ApiResponse(data=WikiPageListResponse(
        items=[WikiPageResponse.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    ))


@router.get("/search", response_model=ApiResponse[list[WikiPageResponse]])
async def search_wiki(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Full-text search across wiki pages."""
    items = await wiki_service.search_wiki(db, q, limit=limit)
    return ApiResponse(data=[WikiPageResponse.model_validate(p) for p in items])


@router.get("/graph", response_model=ApiResponse[WikiGraphData])
async def get_graph(db: AsyncSession = Depends(get_db)):
    """Get knowledge graph data (nodes + edges) for visualization."""
    nodes, edges = await wiki_service.get_graph_data(db)
    return ApiResponse(data=WikiGraphData(
        nodes=[GraphNode(**n) for n in nodes],
        edges=[GraphEdge(**e) for e in edges],
    ))


@router.get("/backlinks/{slug}", response_model=ApiResponse[list[WikiPageResponse]])
async def get_backlinks(slug: str, db: AsyncSession = Depends(get_db)):
    """Get pages that link to the given slug (backlinks)."""
    pages = await wiki_service.get_backlinks(db, slug)
    return ApiResponse(data=[WikiPageResponse.model_validate(p) for p in pages])


@router.get("/{slug}", response_model=ApiResponse[WikiPageResponse])
async def get_wiki(slug: str, db: AsyncSession = Depends(get_db)):
    """Get a wiki page by slug."""
    page = await wiki_service.get_wiki_page(db, slug)
    if not page:
        raise HTTPException(status_code=404, detail="Wiki page not found")
    return ApiResponse(data=WikiPageResponse.model_validate(page))


@router.put("/{slug}", response_model=ApiResponse[WikiPageResponse])
async def update_wiki(slug: str, data: WikiUpdate, db: AsyncSession = Depends(get_db)):
    """Update a wiki page."""
    page = await wiki_service.update_wiki_page(
        db,
        slug,
        title=data.title,
        content=data.content,
        summary=data.summary,
        tags=data.tags,
        wiki_type=data.wiki_type,
    )
    if not page:
        raise HTTPException(status_code=404, detail="Wiki page not found")
    return ApiResponse(data=WikiPageResponse.model_validate(page))


@router.delete("/{slug}", response_model=ApiResponse)
async def delete_wiki(slug: str, db: AsyncSession = Depends(get_db)):
    """Delete a wiki page and all associated links."""
    deleted = await wiki_service.delete_wiki_page(db, slug)
    if not deleted:
        raise HTTPException(status_code=404, detail="Wiki page not found")
    return ApiResponse(code=0, message="ok", data=None)
