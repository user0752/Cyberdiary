"""Progress tracking for compile jobs.

Provides safe progress updates that persist to both the progress store
(Redis or in-memory) and the database, so progress survives restarts.
"""

import logging

from sqlalchemy import update

from app.core.database import async_session
from app.core.progress_store import gc_stale_progress, update_progress
from app.models.compile_job import CompileJob

logger = logging.getLogger(__name__)


async def safe_progress_update(job_id: str, **kwargs):
    """Async-safe progress update.

    Updates the progress store (Redis or in-memory) and persists key
    fields to the database so progress survives process restarts.
    """
    await gc_stale_progress()
    await update_progress(job_id, **kwargs)

    # Persist key fields to database (best-effort, non-blocking)
    _db_fields = {}
    if 'status' in kwargs:
        _db_fields['status'] = kwargs['status']
    if 'progress' in kwargs:
        _db_fields['progress'] = kwargs['progress']
    if 'message' in kwargs and 'status' in kwargs and kwargs['status'] in ('done', 'failed'):
        # Store message as result_summary/error_msg for terminal states
        if kwargs['status'] == 'done':
            _db_fields['result_summary'] = kwargs['message']
        elif kwargs['status'] == 'failed':
            _db_fields['error_msg'] = kwargs['message']

    if _db_fields:
        try:
            async with async_session() as db:
                await db.execute(
                    update(CompileJob)
                    .where(CompileJob.id == job_id)
                    .values(**_db_fields)
                )
                await db.commit()
        except Exception:
            pass  # DB write is best-effort; progress store is the primary source
