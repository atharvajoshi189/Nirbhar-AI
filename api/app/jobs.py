import logging
from typing import Optional
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from app.config import settings

logger = logging.getLogger("nirbhar.jobs")
_redis_pool: Optional[ArqRedis] = None

async def get_redis_pool() -> Optional[ArqRedis]:
    global _redis_pool
    if _redis_pool is None:
        try:
            redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
            redis_settings.conn_retries = 0
            redis_settings.conn_timeout = 1.0
            _redis_pool = await create_pool(redis_settings, retry=0)
        except Exception as e:
            logger.warning(f"Redis pool unavailable ({e}); background enqueue bypassed")
            _redis_pool = None
    return _redis_pool

async def enqueue_coordinator_agent(task_id: str, user_id: str) -> Optional[str]:
    """
    Enqueues the Coordinator agent background job into Redis via ARQ.
    Returns the ARQ job_id immediately so the API never blocks.
    """
    try:
        pool = await get_redis_pool()
        if pool:
            job = await pool.enqueue_job("run_coordinator_job", task_id, user_id)
            logger.info(f"Enqueued coordinator job {job.job_id} for task {task_id}")
            return job.job_id if job else None
        return None
    except Exception as e:
        logger.warning(f"Failed to enqueue coordinator job to Redis: {e}")
        return None
