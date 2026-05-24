from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI dependency: yield an async database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables and FTS5 indexes on startup."""
    # Step 1: Create ORM tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Step 2: Create FTS5 virtual tables and triggers (separate connection)
    async with engine.connect() as conn:
        # Memo FTS5
        await conn.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memos_fts USING fts5(
                content, tags, content=memos, content_rowid=rowid
            )
        """))
        # Wiki FTS5
        await conn.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
                title, content, summary, content=wiki_pages, content_rowid=rowid
            )
        """))
        # Triggers to keep FTS5 in sync
        await conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS memos_ai AFTER INSERT ON memos BEGIN
                INSERT INTO memos_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
            END
        """))
        await conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS memos_ad AFTER DELETE ON memos BEGIN
                INSERT INTO memos_fts(memos_fts, rowid, content, tags) VALUES('delete', old.rowid, old.content, old.tags);
            END
        """))
        await conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS memos_au AFTER UPDATE ON memos BEGIN
                INSERT INTO memos_fts(memos_fts, rowid, content, tags) VALUES('delete', old.rowid, old.content, old.tags);
                INSERT INTO memos_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
            END
        """))
        await conn.commit()
