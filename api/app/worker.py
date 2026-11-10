import asyncio
from arq.connections import RedisSettings
from app.config import settings
from app.services.coordinator import coordinator_service

async def run_coordinator_job(ctx, task_id: str, user_id: str):
    """
    ARQ Worker job to execute the Coordinator Agent in the background.
    """
    print(f"[ARQ Worker] Starting coordinator job for task={task_id}, user={user_id}")
    result = coordinator_service.execute_plan_generation(task_id=task_id, user_id=user_id)
    print(f"[ARQ Worker] Completed coordinator job for task={task_id}. Run ID: {result.get('run_id')}")
    return result

class WorkerSettings:
    functions = [run_coordinator_job]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10
    job_timeout = 60

if __name__ == "__main__":
    from arq import run_worker
    asyncio.run(run_worker(WorkerSettings))

