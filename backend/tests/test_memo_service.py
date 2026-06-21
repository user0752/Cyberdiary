"""Unit tests for memo_service: CRUD + search operations."""

import json
from datetime import datetime, timezone

import pytest

from app.schemas.memo import MemoCreate, MemoUpdate
from app.services import memo_service


@pytest.mark.asyncio
async def test_create_memo(db_session):
    data = MemoCreate(content="Hello world", memo_type="note")
    memo = await memo_service.create_memo(db_session, data)

    assert memo.id is not None
    assert memo.content == "Hello world"
    assert memo.memo_type == "note"
    assert memo.pinned is False
    assert memo.archived is False
    assert memo.compiled is False
    assert memo.tags == "[]"


@pytest.mark.asyncio
async def test_create_memo_with_tags(db_session):
    data = MemoCreate(content="Tagged memo", tags=["python", "fastapi"])
    memo = await memo_service.create_memo(db_session, data)

    assert json.loads(memo.tags) == ["python", "fastapi"]


@pytest.mark.asyncio
async def test_get_memo(db_session):
    created = await memo_service.create_memo(db_session, MemoCreate(content="Get me"))
    fetched = await memo_service.get_memo(db_session, created.id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.content == "Get me"


@pytest.mark.asyncio
async def test_get_memo_not_found(db_session):
    result = await memo_service.get_memo(db_session, "nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_list_memos(db_session):
    m1 = await memo_service.create_memo(db_session, MemoCreate(content="memo 1"))
    m2 = await memo_service.create_memo(db_session, MemoCreate(content="memo 2", pinned=True))
    m3 = await memo_service.create_memo(db_session, MemoCreate(content="memo 3"))

    m1.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    m2.created_at = datetime(2024, 1, 2, tzinfo=timezone.utc)
    m3.created_at = datetime(2024, 1, 3, tzinfo=timezone.utc)
    await db_session.flush()

    items, total = await memo_service.list_memos(db_session)

    assert total == 3
    assert len(items) == 3
    assert items[0].id == m2.id
    assert items[1].id == m3.id
    assert items[2].id == m1.id


@pytest.mark.asyncio
async def test_list_memos_pagination(db_session):
    for i in range(5):
        await memo_service.create_memo(db_session, MemoCreate(content=f"page memo {i}"))

    items, total = await memo_service.list_memos(db_session, page=1, page_size=2)

    assert len(items) == 2
    assert total == 5


@pytest.mark.asyncio
async def test_list_memos_filter_by_type(db_session):
    await memo_service.create_memo(db_session, MemoCreate(content="note 1", memo_type="note"))
    await memo_service.create_memo(db_session, MemoCreate(content="idea 1", memo_type="idea"))
    await memo_service.create_memo(db_session, MemoCreate(content="idea 2", memo_type="idea"))

    items, total = await memo_service.list_memos(db_session, memo_type="idea")

    assert total == 2
    assert len(items) == 2
    assert all(m.memo_type == "idea" for m in items)


@pytest.mark.asyncio
async def test_list_memos_filter_by_tag(db_session):
    await memo_service.create_memo(db_session, MemoCreate(content="t1", tags=["python", "web"]))
    await memo_service.create_memo(db_session, MemoCreate(content="t2", tags=["python"]))
    await memo_service.create_memo(db_session, MemoCreate(content="t3", tags=["rust"]))

    items, total = await memo_service.list_memos(db_session, tag="python")

    assert total == 2
    assert len(items) == 2
    assert all("python" in json.loads(m.tags) for m in items)


@pytest.mark.asyncio
async def test_list_memos_excludes_archived(db_session):
    m1 = await memo_service.create_memo(db_session, MemoCreate(content="active"))
    m2 = await memo_service.create_memo(db_session, MemoCreate(content="to archive"))
    await memo_service.delete_memo(db_session, m2.id)

    items, total = await memo_service.list_memos(db_session, archived=False)

    assert total == 1
    assert len(items) == 1
    assert items[0].id == m1.id


@pytest.mark.asyncio
async def test_update_memo(db_session):
    memo = await memo_service.create_memo(
        db_session, MemoCreate(content="original", tags=["old"])
    )

    updated = await memo_service.update_memo(
        db_session, memo.id, MemoUpdate(content="updated", tags=["new"])
    )

    assert updated is not None
    assert updated.content == "updated"
    assert json.loads(updated.tags) == ["new"]


@pytest.mark.asyncio
async def test_update_memo_not_found(db_session):
    result = await memo_service.update_memo(
        db_session, "nonexistent-id", MemoUpdate(content="x")
    )
    assert result is None


@pytest.mark.asyncio
async def test_delete_memo(db_session):
    memo = await memo_service.create_memo(db_session, MemoCreate(content="delete me"))

    result = await memo_service.delete_memo(db_session, memo.id)

    assert result is True
    fetched = await memo_service.get_memo(db_session, memo.id)
    assert fetched is not None
    assert fetched.archived is True


@pytest.mark.asyncio
async def test_delete_memo_not_found(db_session):
    result = await memo_service.delete_memo(db_session, "nonexistent-id")
    assert result is False


@pytest.mark.asyncio
async def test_search_memos(db_session):
    await memo_service.create_memo(db_session, MemoCreate(content="Python is a great language"))
    await memo_service.create_memo(db_session, MemoCreate(content="Rust is also great"))
    await memo_service.create_memo(db_session, MemoCreate(content="Unrelated content"))

    results = await memo_service.search_memos(db_session, "Python")

    assert len(results) == 1
    assert "Python" in results[0].content


@pytest.mark.asyncio
async def test_search_memos_empty_query(db_session):
    await memo_service.create_memo(db_session, MemoCreate(content="some content"))

    results = await memo_service.search_memos(db_session, "   ")

    assert results == []
