"""Memo business logic."""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func, text, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memo import Memo
from app.schemas.memo import MemoCreate, MemoUpdate

logger = logging.getLogger(__name__)


async def create_memo(db: AsyncSession, data: MemoCreate) -> Memo:
    memo = Memo(
        content=data.content,
        tags=json.dumps(data.tags, ensure_ascii=False),
        memo_type=data.memo_type,
        source_url=data.source_url,
        pinned=data.pinned,
    )
    db.add(memo)
    await db.flush()
    await db.refresh(memo)
    return memo


async def list_memos(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    memo_type: str | None = None,
    tag: str | None = None,
    archived: bool = False,
) -> tuple[list[Memo], int]:
    conditions = [Memo.archived == archived]

    if memo_type:
        conditions.append(Memo.memo_type == memo_type)
    if tag:
        conditions.append(Memo.tags.like(f'%"{tag}"%'))

    # Count
    count_stmt = select(func.count()).select_from(Memo)
    for c in conditions:
        count_stmt = count_stmt.where(c)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Query (pinned first, then by created_at desc)
    stmt = select(Memo)
    for c in conditions:
        stmt = stmt.where(c)
    stmt = stmt.order_by(Memo.pinned.desc(), Memo.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return items, total


async def get_memo(db: AsyncSession, memo_id: str) -> Memo | None:
    result = await db.execute(select(Memo).where(Memo.id == memo_id))
    return result.scalar_one_or_none()


async def update_memo(db: AsyncSession, memo_id: str, data: MemoUpdate) -> Memo | None:
    memo = await get_memo(db, memo_id)
    if not memo:
        return None

    update_data = data.model_dump(exclude_unset=True)
    if "tags" in update_data and update_data["tags"] is not None:
        update_data["tags"] = json.dumps(update_data["tags"], ensure_ascii=False)

    for key, value in update_data.items():
        setattr(memo, key, value)

    memo.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(memo)
    return memo


async def delete_memo(db: AsyncSession, memo_id: str) -> bool:
    """Soft delete: set archived=True."""
    memo = await get_memo(db, memo_id)
    if not memo:
        return False
    memo.archived = True
    memo.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return True


async def search_memos(db: AsyncSession, query: str, limit: int = 20) -> list[Memo]:
    """Full-text search using FTS5 (SQLite only) or LIKE fallback."""
    try:
        # Try FTS5
        stmt = text("""
            SELECT m.* FROM memos m
            JOIN memos_fts fts ON m.rowid = fts.rowid
            WHERE memos_fts MATCH :query AND m.archived = 0
            ORDER BY rank
            LIMIT :limit
        """)
        result = await db.execute(stmt, {"query": query, "limit": limit})
        rows = result.fetchall()
        if rows:
            return [Memo(**dict(zip(result.keys(), row))) for row in rows]
    except Exception as e:
        logger.warning("Memo FTS5 search failed, falling back to LIKE: %s", e)

    # LIKE fallback
    stmt = (
        select(Memo)
        .where(Memo.archived == False, Memo.content.like(f"%{query}%"))
        .order_by(Memo.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
