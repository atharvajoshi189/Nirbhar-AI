import logging
from typing import Optional
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from app.config import settings

logger = logging.getLogger("nirbhar.jobs")
_redis_pool: Optional[ArqRedis] = None

async def get_redis_pool() -> ArqRedis:
    global _redis_pool
    if _redis_pool is None:
        redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
        redis_settings.conn_retries = 1
        redis_settings.conn_timeout = 1
        _redis_pool = await create_pool(redis_settings, retry=0)
    return _redis_pool

async def enqueue_coordinator_agent(task_id: str, user_id: str) -> Optional[str]:
    """
    Enqueues the Coordinator agent background job into Redis via ARQ.
    Returns the ARQ job_id immediately so the API never blocks.
    """
    try:
        pool = await get_redis_pool()
        job = await pool.enqueue_job("run_coordinator_job", task_id, user_id)
        logger.info(f"Enqueued coordinator job {job.job_id} for task {task_id}")
        return job.job_id if job else None
    except Exception as e:
        logger.error(f"Failed to enqueue coordinator job to Redis: {e}")
        # In case Redis connection encounters transient glitch, raise error per Rule 1 & 4 (Fail closed)
        raise RuntimeError(f"Job queue failure (Redis/ARQ): {e}")

