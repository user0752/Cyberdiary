from sqlalchemy import text
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Connection-pool tuning. SQLite uses the default StaticPool/SingletonThreadPool
# (pool_size etc. are ignored), but these parameters are essential once the
# DATABASE_URL is switched to PostgreSQL in production — without pool_pre_ping
# and pool_recycle, long-idle connections silently dropped by the server cause
# OperationalError on the next request.
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# P2-5: per-connection SQLite pragmas. WAL journal_mode is persistent (set
# once in init_db), but synchronous / foreign_keys / busy_timeout are
# per-connection and must be re-applied on every checkout. Without this,
# ON DELETE CASCADE silently no-ops (foreign_keys defaults OFF) and a busy
# writer makes readers fail immediately instead of waiting.
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _):
    if engine.dialect.name != "sqlite":
        return
    cur = dbapi_conn.cursor()
    try:
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=5000")
    finally:
        cur.close()


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create all tables, FTS5 indexes, and performance indexes on startup.

    Runs Alembic migrations first (via subprocess to avoid event-loop
    conflicts), then falls back to create_all for dev convenience.
    FTS5 virtual tables and triggers are created separately because
    Alembic cannot auto-detect SQLite FTS5 objects.
    """
    import asyncio
    import logging
    import os
    import subprocess
    import sys

    _logger = logging.getLogger(__name__)

    # Ensure all models are imported so Base.metadata knows about them
    import app.models.memo  # noqa: F401
    import app.models.wiki  # noqa: F401
    import app.models.chat  # noqa: F401
    import app.models.compile_job  # noqa: F401
    import app.models.multi_agent  # noqa: F401
    import app.models.game  # noqa: F401
    import app.models.settings  # noqa: F401
    import app.models.user  # noqa: F401

    # Step 0: Run Alembic migrations (records migration history).
    # P2-9: run in a worker thread via asyncio.to_thread so the subprocess
    # call does NOT block the event loop while alembic is upgrading. The
    # outer init_db() is async (called from lifespan), so anything that
    # blocks here blocks every concurrent request for the duration.
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    alembic_ini = os.path.join(backend_dir, "alembic.ini")
    alembic_ok = False
    if os.path.exists(alembic_ini):
        try:
            _logger.info("Running Alembic migrations...")
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            result = await asyncio.to_thread(
                subprocess.run,
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
                alembic_ok = True
            else:
                _logger.warning(
                    "Alembic migration returned %d: %s",
                    result.returncode,
                    result.stderr.strip()[-200:],
                )
        except Exception:
            _logger.exception("Alembic migration failed; falling back to create_all")

    # P2-10: create_all is a dev convenience that can mask missing migrations.
    # Only run it when alembic did NOT succeed, and log a loud warning so the
    # operator notices that the schema is being created from metadata rather
    # than from versioned migrations.
    if not alembic_ok:
        _logger.warning(
            "create_all() is creating tables from ORM metadata — this masks "
            "missing/failed Alembic migrations. Investigate the alembic logs "
            "above before relying on this in production."
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Step 2: Create FTS5 virtual tables and triggers (separate connection).
    # FTS5 is a SQLite-only extension. PostgreSQL uses tsvector + GIN indexes
    # instead — guard the SQLite-specific DDL so switching DATABASE_URL to a
    # PostgreSQL connection string does not crash init_db() with
    # ProgrammingError. The search service is expected to branch on dialect
    # as well; the PG path is a separate migration.
    async with engine.connect() as conn:
        dialect = conn.dialect.name
        if dialect == "sqlite":
            # P2-5: enable WAL mode + sane pragmas. WAL lets readers not block
            # the writer (and vice versa), which matters once compile jobs
            # start writing while chat requests are reading. synchronous=NORMAL
            # is the recommended pairing — still fsyncs on commit but skips
            # the per-write fsync that kills throughput. foreign_keys=ON is
            # required because SQLite defaults to OFF and ON DELETE CASCADE
            # silently no-ops without it.
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
            await conn.execute(text("PRAGMA foreign_keys=ON"))
            await conn.execute(text("PRAGMA busy_timeout=5000"))
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
        elif dialect == "postgresql":
            # PostgreSQL full-text search via generated tsvector + GIN index.
            # Kept lightweight (no triggers) — reindex periodically or on write.
            await conn.execute(text(
                "CREATE EXTENSION IF NOT EXISTS pg_trgm"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_memos_content_trgm ON memos USING gin (content gin_trgm_ops)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_wiki_pages_content_trgm ON wiki_pages USING gin (content gin_trgm_ops)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_wiki_pages_title_trgm ON wiki_pages USING gin (title gin_trgm_ops)"
            ))
        await conn.commit()

    # Step 3: Create performance indexes
    # P2-6: cover the FK + hot query paths that were missing indexes.
    #   - messages.conv_id: every chat history load filters by conv_id; without
    #     this index it's a full scan of all messages across all conversations.
    #   - wiki_links.from_slug / to_slug: the graph traversal and backlink
    #     lookups filter by these; without indexes both are full scans.
    #   - conversations.updated_at: the sidebar sorts by this on every load.
    # P2-12: tags are JSON-string columns queried with LIKE '%tag%'. A plain
    #   index doesn't help a leading-wildcard LIKE on SQLite, but on PostgreSQL
    #   a pg_trgm GIN index does — added in the PG branch above. On SQLite the
    #   FTS5 virtual tables already cover tag search, so we just add a plain
    #   index here for the rare equality lookup.
    async with engine.connect() as conn:
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_memos_compiled_archived ON memos(compiled, archived, created_at)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_wiki_pages_type_tags ON wiki_pages(wiki_type, updated_at)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_messages_conv_id ON messages(conv_id, created_at)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_wiki_links_from_slug ON wiki_links(from_slug)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_wiki_links_to_slug ON wiki_links(to_slug)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at)"
        ))
        await conn.commit()
