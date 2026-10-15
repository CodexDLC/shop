# Правила разработки магазина

- `codex_ecommerce` — независимый Python-движок с публичным API, DTO и доменными ошибками. Никаких импортов Django, ORM, settings, requests web framework, ARQ или Celery в движке.
- Django и ARQ импортируют и используют API движка. Python API не означает обязательный HTTP-вызов. Persistence и транзакции задаются через контракты и адаптеры; Django ORM adapter находится вне движка.
- ARQ + Redis — основной асинхронный worker, самостоятельный пакет, зависимости и контейнер. Папки Django в worker не копируются и не импортируются; django.setup() не используется. Worker использует независимые адаптеры либо явно определённый backend API. Общая схема БД имеет одного владельца миграций.
- Celery только для обоснованных сверхтяжёлых задач в отдельных контейнерах. CPU-bound работа не блокирует event loop ARQ: ограниченные процессы/исполнители или heavy worker.
- Используем проверенные возможности Django максимально в его зоне ответственности: auth, sessions, forms, CSRF, escaping, permissions, ORM/migrations. Не пишем собственные аналоги без необходимости.
- Структура по фичам, один класс — один файл, включая models/forms/adapters/DTO. Если требуется несколько классов, модуль превращается в пакет. __init__.py экспортирует API без бизнес-логики. Несколько функций допустимы в одном файле без классов при общей ответственности. Предпочитаем осмысленный ООП и не создаём god objects.
- Scaffold codex-django-cli полезен, но необязателен. Проверяем booking до установки; исключаем или корректно удаляем ненужное после генерации: apps, urls, зависимости, settings, миграции, шаблоны. Общие компоненты вслепую не удаляем.
- Фото в итоге в S3. Django storage adapter и независимый worker adapter разделены.
- Выбор оплаты утверждён 15.10.2026: Stripe Checkout (hosted) и PayPal через Stripe, один платёжный API для карт/PayPal/refunds. Сначала только sandbox; прямой PayPal adapter и live-активация не входят в текущее разрешение.
- Подготовка документации и local prototype не включает реальные платежи или запись в действующий eBay.

См. docs/README.md и docs/project/security-and-correctness.md. Правила утверждены 13.10.2026; магазин пока не реализован.
<!-- codex-core:skill:start -->
<!-- codex-core:skill:separator=0 -->
Use [codex-core](.agents/skills/codex-core/SKILL.md) for codex_core work.
<!-- codex-core:skill:end -->
<!-- codex-platform:skill:start -->
<!-- codex-platform:skill:separator=0 -->
Use [codex-platform](.agents/skills/codex-platform/SKILL.md) for codex_platform work.
<!-- codex-platform:skill:end -->
<!-- codex-django:skill:start -->
<!-- codex-django:skill:separator=0 -->
Use [codex-django](.agents/skills/codex-django/SKILL.md) for codex_django work.
<!-- codex-django:skill:end -->
<!-- codex-django-cli:skill:start -->
<!-- codex-django-cli:skill:separator=0 -->
Use [codex-django-cli](.agents/skills/codex-django-cli/SKILL.md) for codex_django_cli work.
<!-- codex-django-cli:skill:end -->

## Project feature skills

Выбирать один основной навык и нужные references; не загружать все навыки/разделы автоматически.

- [shop-architecture](.agents/skills/shop-architecture/SKILL.md)
- [shop-catalog-media](.agents/skills/shop-catalog-media/SKILL.md)
- [shop-inventory-ebay](.agents/skills/shop-inventory-ebay/SKILL.md)
- [shop-orders-payments](.agents/skills/shop-orders-payments/SKILL.md)
- [shop-operations-security](.agents/skills/shop-operations-security/SKILL.md)
