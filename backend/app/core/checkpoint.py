"""Checkpoint strategy: MemorySaver for dev, SqliteSaver/PostgresSaver for prod.
Cleanup: 7-day delayed cleanup via APScheduler, avoiding long-lived asyncio.sleep.
"""

from datetime import datetime, timedelta


async def schedule_checkpoint_cleanup(job_id: str, ttl_days: int = 7):
    """Scheduled checkpoint cleanup triggered by APScheduler."""
    cutoff = datetime.now() - timedelta(days=ttl_days)
    # Actual cleanup depends on the checkpointer backend (by thread_id)
    pass
