"""ARQ entry point: arq workers.worker.WorkerSettings."""

import os

from arq.connections import RedisSettings
from codex_platform.workers.arq import BaseArqWorkerSettings

from .lifecycle import worker_shutdown, worker_startup
from .tasks import engine_status


class WorkerSettings(BaseArqWorkerSettings):
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    )
    queue_name = "inet_mag:arq"
    functions = [engine_status]
    on_startup = worker_startup
    on_shutdown = worker_shutdown
    max_jobs = 10
    job_timeout = 30
    keep_result = 60
    max_tries = 3
