"""Unit tests for wiki_service - CRUD, search, links."""

import os
import sys

import pytest
from sqlalchemy import select, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.models  # noqa: F401 - register all models with Base.metadata
from app.services import wiki_service
from app.models.wiki import WikiLink


@pytest.mark.asyncio
async def test_save_wiki_page_create(db_session):
    page = await wiki_service.save_wiki_page(
        db_session,
        slug="test-page",
        title="Test Page",
        wiki_type="concept",
        content="Some content",
        summary="A test page",
        tags=["test"],
        source_memo_ids=[],
        wiki_links=[],
    )
    assert page.slug == "test-page"
    assert page.title == "Test Page"
    assert page.wiki_type == "concept"
    assert page.content == "Some content"
    assert page.summary == "A test page"
    assert page.version == 1


@pytest.mark.asyncio
async def test_save_wiki_page_update(db_session):
    await wiki_service.save_wiki_page(
        db_session,
        slug="update-page",
        title="Original",
        wiki_type="concept",
        content="original content",
        summary=None,
        tags=[],
        source_memo_ids=[],
        wiki_links=[],
    )
    page = await wiki_service.save_wiki_page(
        db_session,
        slug="update-page",
        title="Updated",
        wiki_type="concept",
        content="updated content",
        summary="updated summary",
        tags=["updated"],
        source_memo_ids=[],
        wiki_links=[],
    )
    assert page.title == "Updated"
    assert page.content == "updated content"
    assert page.summary == "updated summary"
    assert page.version == 2


@pytest.mark.asyncio
async def test_save_wiki_page_with_links(db_session):
    await wiki_service.save_wiki_page(
        db_session,
        slug="page-with-links",
        title="Page With Links",
        wiki_type="concept",
        content="Links to [[Other Page]]",
        summary=None,
        tags=[],
        source_memo_ids=[],
        wiki_links=["other-page"],
    )
    result = await db_session.execute(
        select(WikiLink).where(WikiLink.from_slug == "page-with-links")
    )
    links = result.scalars().all()
    assert len(links) == 1
    assert links[0].to_slug == "other-page"


@pytest.mark.asyncio
async def test_save_wiki_page_no_self_links(db_session):
    await wiki_service.save_wiki_page(
        db_session,
        slug="self-link-page",
        title="Self Link Page",
        wiki_type="concept",
        content="Links to [[Self Link Page]]",
        summary=None,
        tags=[],
        source_memo_ids=[],
        wiki_links=["self-link-page"],
    )
    result = await db_session.execute(
        select(WikiLink).where(WikiLink.from_slug == "self-link-page")
    )
    links = result.scalars().all()
    assert len(links) == 0


@pytest.mark.asyncio
async def test_get_wiki_page(db_session):
    await wiki_service.save_wiki_page(
        db_session,
        slug="get-page",
        title="Get Page",
        wiki_type="entity",
        content="content",
        summary=None,
        tags=[],
        source_memo_ids=[],
        wiki_links=[],
    )
    page = await wiki_service.get_wiki_page(db_session, "get-page")
    assert page is not None
    assert page.slug == "get-page"
    assert page.title == "Get Page"


@pytest.mark.asyncio
async def test_get_wiki_page_not_found(db_session):
    page = await wiki_service.get_wiki_page(db_session, "nonexistent")
    assert page is None


@pytest.mark.asyncio
async def test_list_wiki_pages(db_session):
    for i in range(3):
        await wiki_service.save_wiki_page(
            db_session,
            slug=f"list-page-{i}",
            title=f"List Page {i}",
            wiki_type="concept",
            content=f"content {i}",
            summary=None,
            tags=[],
            source_memo_ids=[],
            wiki_links=[],
        )
    items, total = await wiki_service.list_wiki_pages(db_session)
    assert total == 3
    assert len(items) == 3


@pytest.mark.asyncio
async def test_list_wiki_pages_filter_by_type(db_session):
    await wiki_service.save_wiki_page(
        db_session, slug="concept-1", title="Concept 1", wiki_type="concept",
        content="c", summary=None, tags=[], source_memo_ids=[], wiki_links=[],
    )
    await wiki_service.save_wiki_page(
        db_session, slug="entity-1", title="Entity 1", wiki_type="entity",
        content="c", summary=None, tags=[], source_memo_ids=[], wiki_links=[],
    )
    await wiki_service.save_wiki_page(
        db_session, slug="concept-2", title="Concept 2", wiki_type="concept",
        content="c", summary=None, tags=[], source_memo_ids=[], wiki_links=[],
    )
    items, total = await wiki_service.list_wiki_pages(db_session, wiki_type="concept")
    assert total == 2
    assert all(item.wiki_type == "concept" for item in items)


@pytest.mark.asyncio
async def test_list_wiki_pages_pagination(db_session):
    for i in range(5):
        await wiki_service.save_wiki_page(
            db_session,
            slug=f"pag-page-{i}",
            title=f"Pag Page {i}",
            wiki_type="concept",
            content=f"content {i}",
            summary=None,
            tags=[],
            source_memo_ids=[],
            wiki_links=[],
        )
    page1, total = await wiki_service.list_wiki_pages(db_session, page=1, page_size=2)
    page2, _ = await wiki_service.list_wiki_pages(db_session, page=2, page_size=2)
    page3, _ = await wiki_service.list_wiki_pages(db_session, page=3, page_size=2)
    assert total == 5
    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1


@pytest.mark.asyncio
async def test_update_wiki_page(db_session):
    await wiki_service.save_wiki_page(
        db_session,
        slug="update-test",
        title="Original Title",
        wiki_type="concept",
        content="original content",
        summary=None,
        tags=[],
        source_memo_ids=[],
        wiki_links=[],
    )
    page = await wiki_service.update_wiki_page(
        db_session, slug="update-test",
        title="New Title", content="new content",
    )
    assert page.title == "New Title"
    assert page.content == "new content"
    assert page.version == 2


@pytest.mark.asyncio
async def test_update_wiki_page_relinks(db_session):
    await wiki_service.save_wiki_page(
        db_session,
        slug="relink-page",
        title="Relink Page",
        wiki_type="concept",
        content="Links to [[Old Target]]",
        summary=None,
        tags=[],
        source_memo_ids=[],
        wiki_links=["old-target"],
    )
    result = await db_session.execute(
        select(WikiLink).where(WikiLink.from_slug == "relink-page")
    )
    old_links = result.scalars().all()
    assert len(old_links) == 1
    assert old_links[0].to_slug == "old-target"

    await wiki_service.update_wiki_page(
        db_session, slug="relink-page",
        content="Now links to [[New Target]]",
    )
    result = await db_session.execute(
        select(WikiLink).where(WikiLink.from_slug == "relink-page")
    )
    new_links = result.scalars().all()
    assert len(new_links) == 1
    assert new_links[0].to_slug == "new-target"


@pytest.mark.asyncio
async def test_update_wiki_page_not_found(db_session):
    page = await wiki_service.update_wiki_page(
        db_session, slug="nonexistent", title="New Title",
    )
    assert page is None


@pytest.mark.asyncio
async def test_delete_wiki_page(db_session):
    await wiki_service.save_wiki_page(
        db_session,
        slug="delete-page",
        title="Delete Page",
        wiki_type="concept",
        content="content with [[Target Page]]",
        summary=None,
        tags=[],
        source_memo_ids=[],
        wiki_links=["target-page"],
    )
    result = await wiki_service.delete_wiki_page(db_session, "delete-page")
    assert result is True

    page = await wiki_service.get_wiki_page(db_session, "delete-page")
    assert page is None

    link_result = await db_session.execute(
        select(WikiLink).where(WikiLink.from_slug == "delete-page")
    )
    links = link_result.scalars().all()
    assert len(links) == 0


@pytest.mark.asyncio
async def test_delete_wiki_page_not_found(db_session):
    result = await wiki_service.delete_wiki_page(db_session, "nonexistent")
    assert result is False


@pytest.mark.asyncio
async def test_search_wiki(db_session):
    await wiki_service.save_wiki_page(
        db_session,
        slug="python-page",
        title="Python Tutorial",
        wiki_type="concept",
        content="Learn Python programming basics",
        summary="Python basics",
        tags=[],
        source_memo_ids=[],
        wiki_links=[],
    )
    await wiki_service.save_wiki_page(
        db_session,
        slug="java-page",
        title="Java Tutorial",
        wiki_type="concept",
        content="Learn Java programming basics",
        summary="Java basics",
        tags=[],
        source_memo_ids=[],
        wiki_links=[],
    )
    results = await wiki_service.search_wiki(db_session, "Python")
    assert len(results) >= 1
    assert any(r.slug == "python-page" for r in results)


@pytest.mark.asyncio
async def test_get_backlinks(db_session):
    await wiki_service.save_wiki_page(
        db_session,
        slug="page-a",
        title="Page A",
        wiki_type="concept",
        content="References [[Page B]]",
        summary=None,
        tags=[],
        source_memo_ids=[],
        wiki_links=["page-b"],
    )
    await wiki_service.save_wiki_page(
        db_session,
        slug="page-b",
        title="Page B",
        wiki_type="concept",
        content="Target page",
        summary=None,
        tags=[],
        source_memo_ids=[],
        wiki_links=[],
    )
    backlinks = await wiki_service.get_backlinks(db_session, "page-b")
    assert len(backlinks) == 1
    assert backlinks[0].slug == "page-a"


@pytest.mark.asyncio
async def test_get_wiki_summaries(db_session):
    await wiki_service.save_wiki_page(
        db_session,
        slug="summary-page-1",
        title="Summary Page 1",
        wiki_type="concept",
        content="content 1",
        summary="Summary 1",
        tags=[],
        source_memo_ids=[],
        wiki_links=[],
    )
    await wiki_service.save_wiki_page(
        db_session,
        slug="summary-page-2",
        title="Summary Page 2",
        wiki_type="concept",
        content="content 2",
        summary=None,
        tags=[],
        source_memo_ids=[],
        wiki_links=[],
    )
    summaries = await wiki_service.get_wiki_summaries(db_session)
    assert len(summaries) == 1
    assert summaries[0].slug == "summary-page-1"
    assert summaries[0].summary == "Summary 1"
