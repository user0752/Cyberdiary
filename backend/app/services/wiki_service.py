"""Wiki business logic - CRUD, search, graph, backlinks."""

import json
from datetime import datetime, timezone

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wiki import WikiPage, WikiLink


async def list_wiki_pages(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    wiki_type: str | None = None,
    tag: str | None = None,
) -> tuple[list[WikiPage], int]:
    """List wiki pages with pagination and optional filters."""
    conditions = []
    if wiki_type:
        conditions.append(WikiPage.wiki_type == wiki_type)
    if tag:
        conditions.append(WikiPage.tags.like(f'%"{tag}"%'))

    # Count
    count_stmt = select(func.count()).select_from(WikiPage)
    for c in conditions:
        count_stmt = count_stmt.where(c)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Query
    stmt = select(WikiPage)
    for c in conditions:
        stmt = stmt.where(c)
    stmt = stmt.order_by(WikiPage.updated_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    items = list(result.scalars().all())
    return items, total


async def get_wiki_page(db: AsyncSession, slug: str) -> WikiPage | None:
    """Get a wiki page by slug."""
    result = await db.execute(select(WikiPage).where(WikiPage.slug == slug))
    return result.scalar_one_or_none()


async def update_wiki_page(
    db: AsyncSession,
    slug: str,
    title: str | None = None,
    content: str | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
    wiki_type: str | None = None,
) -> WikiPage | None:
    """Update a wiki page. Returns None if not found."""
    page = await get_wiki_page(db, slug)
    if not page:
        return None

    if title is not None:
        page.title = title
    if content is not None:
        page.content = content
    if summary is not None:
        page.summary = summary
    if tags is not None:
        page.tags = json.dumps(tags, ensure_ascii=False)
    if wiki_type is not None:
        page.wiki_type = wiki_type

    page.version += 1
    page.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(page)
    return page


async def search_wiki(db: AsyncSession, query: str, limit: int = 20) -> list[WikiPage]:
    """Full-text search using FTS5 with LIKE fallback."""
    try:
        stmt = text("""
            SELECT w.* FROM wiki_pages w
            JOIN wiki_fts fts ON w.rowid = fts.rowid
            WHERE wiki_fts MATCH :query
            ORDER BY rank
            LIMIT :limit
        """)
        result = await db.execute(stmt, {"query": query, "limit": limit})
        rows = result.fetchall()
        if rows:
            return [WikiPage(**dict(zip(result.keys(), row))) for row in rows]
    except Exception:
        pass  # FTS5 not available or parse error

    # LIKE fallback
    stmt = (
        select(WikiPage)
        .where(
            WikiPage.title.like(f"%{query}%")
            | WikiPage.content.like(f"%{query}%")
            | WikiPage.summary.like(f"%{query}%")
        )
        .order_by(WikiPage.updated_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_graph_data(db: AsyncSession) -> tuple[list[dict], list[dict]]:
    """Get knowledge graph nodes and edges for visualization."""
    # Nodes from all wiki pages
    result = await db.execute(
        select(WikiPage.id, WikiPage.title, WikiPage.wiki_type, WikiPage.slug)
    )
    nodes = [
        {"id": row[0], "label": row[1], "type": row[2], "slug": row[3]}
        for row in result.all()
    ]

    # Edges from wiki_links
    result = await db.execute(select(WikiLink.from_slug, WikiLink.to_slug))
    edges = [{"source": row[0], "target": row[1]} for row in result.all()]

    return nodes, edges


async def get_backlinks(db: AsyncSession, slug: str) -> list[WikiPage]:
    """Get pages that link to the given slug."""
    stmt = (
        select(WikiPage)
        .join(WikiLink, WikiPage.slug == WikiLink.from_slug)
        .where(WikiLink.to_slug == slug)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_wiki_summaries(db: AsyncSession, limit: int = 50) -> list[WikiPage]:
    """Get recent wiki page summaries for chat context injection."""
    result = await db.execute(
        select(WikiPage)
        .where(WikiPage.summary.isnot(None))
        .order_by(WikiPage.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def save_wiki_page(
    db: AsyncSession,
    slug: str,
    title: str,
    wiki_type: str,
    content: str,
    summary: str | None,
    tags: list[str],
    source_memo_ids: list[str],
    wiki_links: list[str],
) -> WikiPage:
    """Create or update a wiki page from compile output. Also updates wiki_links."""
    existing = await get_wiki_page(db, slug)

    if existing:
        existing.title = title
        existing.wiki_type = wiki_type
        existing.content = content
        existing.summary = summary
        existing.tags = json.dumps(tags, ensure_ascii=False)
        existing.source_memo_ids = json.dumps(source_memo_ids, ensure_ascii=False)
        existing.version += 1
        existing.updated_at = datetime.now(timezone.utc)
        page = existing
    else:
        page = WikiPage(
            slug=slug,
            title=title,
            wiki_type=wiki_type,
            content=content,
            summary=summary,
            tags=json.dumps(tags, ensure_ascii=False),
            source_memo_ids=json.dumps(source_memo_ids, ensure_ascii=False),
        )
        db.add(page)

    await db.flush()

    # Update outgoing links: delete old, insert new
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(WikiLink).where(WikiLink.from_slug == slug))

    for target_slug in wiki_links:
        if target_slug != slug:  # no self-links
            link = WikiLink(from_slug=slug, to_slug=target_slug)
            db.add(link)

    await db.flush()
    return page
