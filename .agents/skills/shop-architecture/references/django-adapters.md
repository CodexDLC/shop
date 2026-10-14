# Django как потребитель

Статус: Foundation реализован; commerce models отсутствуют.

web.shop.views.EngineStatusView вызывает тот же Engine, что worker. /health/ — liveness, не readiness БД/Redis. Django отвечает за auth, permissions, CSRF, sessions, forms, ORM и migrations. Использовать готовые codex-django механизмы по их installed skill; не подключать все apps или generic URL ради mixin. Cabinet app установлен, общие cabinet URL не открыты; booking не установлен. HTTP input валидируем и переводим в DTO. Схема DB-моделей не является доменной API-схемой автоматически.

## Источники и точки входа

- [src/web/shop/views/engine_status_view.py](../../../../src/web/shop/views/engine_status_view.py)
- [src/web/config/settings/base.py](../../../../src/web/config/settings/base.py)
- [src/web/config/urls.py](../../../../src/web/config/urls.py)
- [tests/web/test_foundation.py](../../../../tests/web/test_foundation.py)
