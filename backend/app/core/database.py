from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create all tables, FTS5 indexes, and performance indexes on startup.

    Runs Alembic migrations first (via subprocess to avoid event-loop
    conflicts), then falls back to create_all for dev convenience.
    FTS5 virtual tables and triggers are created separately because
    Alembic cannot auto-detect SQLite FTS5 objects.
    """
    import logging
    import os
    import subprocess
    import sys

    _logger = logging.getLogger(__name__)

    # Ensure all models are imported so Base.metadata knows about them
    import app.models.multi_agent  # noqa: F401

    # Step 0: Run Alembic migrations (records migration history).
    # Use subprocess to avoid event-loop conflicts with the FastAPI lifespan.
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    alembic_ini = os.path.join(backend_dir, "alembic.ini")
    if os.path.exists(alembic_ini):
        try:
            _logger.info("Running Alembic migrations...")
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            result = subprocess.run(
                [sys.executable, "-m", "alembic", "-c", alembic_ini, "upgrade", "head"],
                cwd=backend_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                env=env,
            )
            if result.returncode == 0:
                _logger.info("Alembic migrations complete.")
            else:
                _logger.warning(
                    "Alembic migration returned %d: %s",
                    result.returncode,
                    result.stderr.strip()[-200:],
                )
        except Exception:
            _logger.exception("Alembic migration failed; falling back to create_all")

    # Step 1: Create ORM tables (idempotent — safe to call after migration)
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

    # Step 3: Create performance indexes
    async with engine.connect() as conn:
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_memos_compiled_archived ON memos(compiled, archived, created_at)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_wiki_pages_type_tags ON wiki_pages(wiki_type, updated_at)"
        ))
        await conn.commit()
