# Отдельный ARQ

Статус: диагностический worker и opt-in inventory expiry task реализованы; working cron не включён.

WorkerSettings наследует BaseArqWorkerSettings; REDIS_URL → RedisSettings, очередь inet_mag:arq. Lifecycle создаёт Engine в ctx, engine_status возвращает JSON-compatible DTO. Import не вызывает network или Django. Worker image получает только src/workers и src/codex_ecommerce, dependency group worker. Поставляемый arq_task имеет свои правила повторов — перед использованием прочитать codex-platform reference, не предполагать поведение по имени decorator. Ошибки финансовых задач не скрывать. CPU-bound работу не выполнять в event loop; Celery только при обоснованных тяжёлых задачах отдельно.

## Источники и точки входа

- [src/workers/worker.py](../../../../src/workers/worker.py)
- [src/workers/lifecycle.py](../../../../src/workers/lifecycle.py)
- [tests/workers/test_worker.py](../../../../tests/workers/test_worker.py)
- [deploy/worker/Dockerfile](../../../../deploy/worker/Dockerfile)

## Inventory expiry — шаг4

Добавлена независимая task workers.tasks.inventory_expiry.inventory_expiry и opt-in cron раз вминуту. ENV INVENTORY_EXPIRY_ENABLED=1 включаетcron; default0. Worker вызывает narrow authenticated backend /internal/inventory/expiry/ через stdlib HTTP вexecutor; не импортируетDjango и не дублирует алгоритм/схему БД. Настройки/транспорт/таймауты/безопасное включение — docs/project/inventory-contract.md раздел Истечениешага4. Callbackсоздаёт serverUTC/actor/batch; bearer dedicated, no redirects/proxies, URL/token не jobargs/logs. Native ARQ errors остаются ошибками; следующийcron тик может повторитьcleanup. max_tries сам по себе не означает retry произвольного RuntimeError. Lifecycle и engine_status сохранены. Реальный working cron сейчас не включён, исходная.env/контейнеры не меняются. Тесты: tests/workers/test_worker_inventory_expiry.py, tests/web/test_inventory_expiry_endpoint.py, tests/web/test_inventory_expiry_http.py; последний проверяетнастоящийtask→HTTP→Django→disposableDB, не Redisdelivery.

Шаг4 прошёл независимуюревизию: полный993/19PGskips,129PG+realHTTPchain. Не обещатьhardwallclockdeadline8/16s: DNS/opener phases имеютотдельныепределы, socket/readbudget не общийdeadline. Настоящая очередьRedis/cron deployment не проверялись/неактивированы.
