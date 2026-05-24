"""Memo REST API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.memo import ApiResponse, MemoCreate, MemoListResponse, MemoResponse, MemoUpdate
from app.services import memo_service

router = APIRouter(prefix="/memos", tags=["memos"])


@router.post("", response_model=ApiResponse[MemoResponse])
async def create_memo(data: MemoCreate, db: AsyncSession = Depends(get_db)):
    memo = await memo_service.create_memo(db, data)
    return ApiResponse(data=MemoResponse.model_validate(memo))


@router.get("", response_model=ApiResponse[MemoListResponse])
async def list_memos(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    memo_type: str | None = None,
    tag: str | None = None,
    archived: bool = False,
    db: AsyncSession = Depends(get_db),
):
    items, total = await memo_service.list_memos(
        db, page=page, page_size=page_size, memo_type=memo_type, tag=tag, archived=archived,
    )
    return ApiResponse(data=MemoListResponse(
        items=[MemoResponse.model_validate(m) for m in items],
        total=total,
        page=page,
        page_size=page_size,
    ))


@router.get("/search", response_model=ApiResponse[list[MemoResponse]])
async def search_memos(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    items = await memo_service.search_memos(db, q, limit=limit)
    return ApiResponse(data=[MemoResponse.model_validate(m) for m in items])


@router.get("/{memo_id}", response_model=ApiResponse[MemoResponse])
async def get_memo(memo_id: str, db: AsyncSession = Depends(get_db)):
    memo = await memo_service.get_memo(db, memo_id)
    if not memo:
        raise HTTPException(status_code=404, detail="Memo not found")
    return ApiResponse(data=MemoResponse.model_validate(memo))


@router.patch("/{memo_id}", response_model=ApiResponse[MemoResponse])
async def update_memo(memo_id: str, data: MemoUpdate, db: AsyncSession = Depends(get_db)):
    memo = await memo_service.update_memo(db, memo_id, data)
    if not memo:
        raise HTTPException(status_code=404, detail="Memo not found")
    return ApiResponse(data=MemoResponse.model_validate(memo))


@router.delete("/{memo_id}", response_model=ApiResponse)
async def delete_memo(memo_id: str, db: AsyncSession = Depends(get_db)):
    ok = await memo_service.delete_memo(db, memo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Memo not found")
    return ApiResponse(message="Memo deleted")
