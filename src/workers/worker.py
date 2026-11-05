"""ARQ entry point: arq workers.worker.WorkerSettings."""

import os

from arq import cron
from arq.connections import RedisSettings
from codex_platform.workers.arq import BaseArqWorkerSettings

from .lifecycle import worker_shutdown, worker_startup
from .tasks import engine_status, inventory_expiry
from .tasks.inventory_expiry import enabled


class WorkerSettings(BaseArqWorkerSettings):
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    )
    queue_name = "inet_mag:arq"
    functions = [engine_status, inventory_expiry]
    cron_jobs = [cron(inventory_expiry, second=0, run_at_startup=False, unique=True,
                      timeout=15, max_tries=3)] if enabled() else []
    on_startup = worker_startup
    on_shutdown = worker_shutdown
    max_jobs = 10
    job_timeout = 30
    keep_result = 60
    max_tries = 3
