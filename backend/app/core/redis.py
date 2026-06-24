"""Redis client — optional, for multi-instance deployments.

If REDIS_URL is not set, returns None and callers fall back to in-memory
state (single-process mode). Set REDIS_URL to enable multi-instance support.
"""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis = None


def get_redis():
    """Return the async Redis client, or None if Redis is not configured.

    Callers should check for None and fall back to in-memory mode.
    """
    global _redis
    if not settings.redis_url:
        return None
    if _redis is None:
        try:
            import redis.asyncio as redis_async
            _redis = redis_async.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            logger.info("Redis client initialized: %s", settings.redis_url)
        except Exception:
            logger.exception("Failed to initialize Redis — falling back to in-memory mode")
            return None
    return _redis


async def close_redis():
    """Close the Redis connection on shutdown."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
