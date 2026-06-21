"""Progress tracking — Redis-backed with in-memory fallback.

Replaces the module-level _compile_progress dict. When REDIS_URL is set,
progress is stored in Redis hashes (shared across processes). Otherwise,
an in-memory dict is used (single-process only).
"""

import asyncio
import json
import logging
import time

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

# In-memory fallback (used when Redis is not configured)
_memory_progress: dict[str, dict] = {}
_memory_lock = asyncio.Lock()

_TTL_SECONDS = 3600


async def get_progress(job_id: str) -> dict | None:
    """Get current progress for a compile job."""
    r = get_redis()
    if r:
        data = await r.hgetall(f"compile:progress:{job_id}")
        if not data:
            return None
        result = {}
        for k, v in data.items():
            try:
                result[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                result[k] = v
        return result
    return _memory_progress.get(job_id)


async def init_progress(job_id: str, **initial) -> None:
    """Initialize progress for a new job."""
    initial.setdefault("_created_at", time.monotonic())
    r = get_redis()
    if r:
        key = f"compile:progress:{job_id}"
        mapping = {k: json.dumps(v) for k, v in initial.items()}
        await r.hset(key, mapping=mapping)
        await r.expire(key, _TTL_SECONDS)
    else:
        async with _memory_lock:
            _memory_progress[job_id] = dict(initial)


async def update_progress(job_id: str, **kwargs) -> None:
    """Update progress fields for a job. Creates the entry if it doesn't exist."""
    r = get_redis()
    if r:
        key = f"compile:progress:{job_id}"
        mapping = {k: json.dumps(v) for k, v in kwargs.items()}
        await r.hset(key, mapping=mapping)
        await r.expire(key, _TTL_SECONDS)
    else:
        async with _memory_lock:
            if job_id not in _memory_progress:
                _memory_progress[job_id] = {"_created_at": time.monotonic()}
            _memory_progress[job_id].update(kwargs)


async def append_progress_list(job_id: str, field: str, item: dict) -> None:
    """Append an item to a list field in progress (e.g. compilation_log)."""
    r = get_redis()
    if r:
        key = f"compile:progress:{job_id}"
        current = await r.hget(key, field)
        lst = json.loads(current) if current else []
        lst.append(item)
        await r.hset(key, {field: json.dumps(lst)})
        await r.expire(key, _TTL_SECONDS)
    else:
        async with _memory_lock:
            if job_id not in _memory_progress:
                _memory_progress[job_id] = {"_created_at": time.monotonic()}
            lst = _memory_progress[job_id].get(field, [])
            lst.append(item)
            _memory_progress[job_id][field] = lst


async def delete_progress(job_id: str) -> None:
    """Remove progress entry for a job."""
    r = get_redis()
    if r:
        await r.delete(f"compile:progress:{job_id}")
    else:
        async with _memory_lock:
            _memory_progress.pop(job_id, None)


async def gc_stale_progress() -> int:
    """Remove progress entries older than TTL. Returns count purged."""
    r = get_redis()
    if r:
        # Redis handles TTL via EXPIRE — nothing to do
        return 0
    now = time.monotonic()
    purged = 0
    async with _memory_lock:
        stale = [
            jid for jid, entry in _memory_progress.items()
            if now - entry.get("_created_at", 0) > _TTL_SECONDS
        ]
        for jid in stale:
            del _memory_progress[jid]
            purged += 1
    if purged:
        logger.debug("gc_stale_progress: purged %d stale entries", purged)
    return purged
