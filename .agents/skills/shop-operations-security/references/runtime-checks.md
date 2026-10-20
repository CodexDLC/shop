# Окружение и проверки

Статус: Foundation реализован и проверен 13.10.2026; результаты не заменяют повтор после изменений.

uv.lock фиксирует зависимости, web/worker/dev groups раздельны. uv sync --locked; uv run pytest -q; uv run ruff check src tests; uv run python manage.py check --settings=web.config.settings.test. SQLite test settings только для wiring, не доказательство PostgreSQL concurrency. ARQ asyncio на Windows sandbox может блокироваться loopback: сообщить конкретное ограничение и использовать разрешённый runtime, не подменять тест ручной прокруткой coroutine.

Compose local only: DEBUG local settings, web loopback, DB/Redis без host ports. Secrets вручную в .env, не в выводаx compose config. Сборки web/worker проверять по затронутой поверхности; worker не должен включать Django. Запуск, миграции и остановка в документации, production deployment ещё нет.

## Источники и точки входа

- [docs/project/foundation-run.md](../../../../docs/project/foundation-run.md)
- [pyproject.toml](../../../../pyproject.toml)
- [deploy/compose.yml](../../../../deploy/compose.yml)
- [deploy/worker/Dockerfile](../../../../deploy/worker/Dockerfile)

## Изолированный HTTPS-стенд

С 16.10.2026 настроен отдельный `shop-staging` на `shop.pinlite.dev`: собственные PostgreSQL/Redis/Mailpit/web/ARQ, Basic Auth и noindex. Это не production и не live-интеграция оплаты/DHL. Руководство и фактические проверки: [staging-deployment.md](../../../../docs/project/staging-deployment.md).

Менять только shop Compose-проект и отдельный shop vhost; конфиги, контейнеры и volumes DLC не затрагивать. Перед обновлением сверить health DLC и его конфиги, после — повторить. Worker без Django. Почта только внутренний Mailpit, доступ через SSH-туннель на loopback 8026. Все секреты в приватных env/access файлах, никогда не в Git или выводе команд.

Только точный eBay callback открыт без Basic Auth; подпись обязательна для POST. GET challenge не доказывает приём подписанного события или завершение удаления данных. Исходящие запросы eBay ограничены OAuth token и чтением public key, любые записи требуют отдельного разрешения. Подробнее: [ebay-notifications.md](../../../../docs/project/ebay-notifications.md).
