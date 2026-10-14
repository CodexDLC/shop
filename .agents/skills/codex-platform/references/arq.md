# ARQ workers

`codex_platform.workers.arq` exports `BaseArqWorkerSettings`, `BaseArqService`, `CORE_FUNCTIONS`, `base_startup`, `base_shutdown`, and `arq_task`. Configure the worker in the consumer and supply ARQ's `RedisSettings`.

This worker configuration fragment assumes the consuming app puts `order_service` into ARQ's task context during startup:

```python
from arq.connections import RedisSettings
from codex_platform.workers.arq import BaseArqWorkerSettings, CORE_FUNCTIONS, arq_task

@arq_task(retry_backoff=30, max_retries=3)
async def process_order(ctx: dict, order_id: int) -> None:
    await ctx["order_service"].process(order_id)

class WorkerSettings(BaseArqWorkerSettings):
    redis_settings = RedisSettings(host="localhost", port=6379)
    functions = [process_order, *CORE_FUNCTIONS]
```

`arq_task` retries exceptions while `job_try < max_retries`; after that it logs and returns `None`. It defaults to omitting task arguments from logs; keep `log_args=False` for sensitive data. Extend startup and shutdown hooks in the consumer when dependencies must be put into `ctx`.
