# Собранная основа

13.10.2026: Python 3.13, Django web, независимый codex_ecommerce и отдельный ARQ worker. Это foundation, не рабочий магазин. Каталог/заказы/оплата/eBay ещё не реализованы.

## Установка и проверка

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv sync --locked
uv run pytest -q
uv run ruff check src tests
uv run python manage.py check --settings=web.config.settings.test
```

Тестовые settings используют SQLite только для проверки wiring/auth foundation. Конкуренцию остатков в будущем проверяем на PostgreSQL.

Навыки опубликованных codex-core, codex-platform, codex-django и CLI установлены в `.agents/skills` официальными установщиками. После upgrade используем их команды update/status, не редактируем управляемые копии. CLI — dev dependency, scaffold не запускался. codex-services приходит транзитивно с CLI; booking отсутствует в INSTALLED_APPS.

## Локальные контейнеры

Скопировать `.env.example` в `.env`, самостоятельно задать случайные DJANGO_SECRET_KEY и POSTGRES_PASSWORD. Не использовать test credentials. Затем:

```powershell
docker compose --env-file .env -f deploy/compose.yml up --build -d
docker compose --env-file .env -f deploy/compose.yml exec web python manage.py migrate
docker compose --env-file .env -f deploy/compose.yml exec web python manage.py createsuperuser
```

Compose предназначен только для local: порт web привязан к 127.0.0.1, Postgres/Redis без опубликованных портов, local settings с DEBUG. Не использовать как production deployment. Django не загружает .env автоматически при прямом запуске manage.py; Compose получает переменные через --env-file.

`http://127.0.0.1:8000/health/` — liveness и вызов общего engine API, не проверка готовности БД/Redis. `/admin/` — штатный Django admin. Cabinet-примитивы установлены, общий набор library URL пока не опубликован.

Worker запускается `arq workers.worker.WorkerSettings`, очередь `inet_mag:arq`. В контейнере доступны только workers и engine, без web-кода и Django runtime. Диагностическая задача engine_status не выполняет внешние операции.

Фото в текущем foundation не импортируются; local storage временный, S3 адаптер реализуется на этапе media import. Платежи и запись eBay не имеют реализации, их нельзя включить простым env-флагом.
