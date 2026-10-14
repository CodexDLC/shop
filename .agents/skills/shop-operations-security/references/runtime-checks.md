# Окружение и проверки

Статус: Foundation реализован и проверен 13.10.2026; результаты не заменяют повтор после изменений.

uv.lock фиксирует зависимости, web/worker/dev groups раздельны. uv sync --locked; uv run pytest -q; uv run ruff check src tests; uv run python manage.py check --settings=web.config.settings.test. SQLite test settings только для wiring, не доказательство PostgreSQL concurrency. ARQ asyncio на Windows sandbox может блокироваться loopback: сообщить конкретное ограничение и использовать разрешённый runtime, не подменять тест ручной прокруткой coroutine.

Compose local only: DEBUG local settings, web loopback, DB/Redis без host ports. Secrets вручную в .env, не в выводаx compose config. Сборки web/worker проверять по затронутой поверхности; worker не должен включать Django. Запуск, миграции и остановка в документации, production deployment ещё нет.

## Источники и точки входа

- [docs/project/foundation-run.md](../../../../docs/project/foundation-run.md)
- [pyproject.toml](../../../../pyproject.toml)
- [deploy/compose.yml](../../../../deploy/compose.yml)
- [deploy/worker/Dockerfile](../../../../deploy/worker/Dockerfile)
