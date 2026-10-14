# Отдельный ARQ

Статус: Диагностический worker реализован.

WorkerSettings наследует BaseArqWorkerSettings; REDIS_URL → RedisSettings, очередь inet_mag:arq. Lifecycle создаёт Engine в ctx, engine_status возвращает JSON-compatible DTO. Import не вызывает network или Django. Worker image получает только src/workers и src/codex_ecommerce, dependency group worker. Поставляемый arq_task имеет свои правила повторов — перед использованием прочитать codex-platform reference, не предполагать поведение по имени decorator. Ошибки финансовых задач не скрывать. CPU-bound работу не выполнять в event loop; Celery только при обоснованных тяжёлых задачах отдельно.

## Источники и точки входа

- [src/workers/worker.py](../../../../src/workers/worker.py)
- [src/workers/lifecycle.py](../../../../src/workers/lifecycle.py)
- [tests/workers/test_worker.py](../../../../tests/workers/test_worker.py)
- [deploy/worker/Dockerfile](../../../../deploy/worker/Dockerfile)
