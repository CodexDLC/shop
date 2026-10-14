# Границы движка

Статус: Реализована диагностическая основа; commerce API ещё планируется.

Engine.status() возвращает неизменяемый EngineStatus; никаких платежей и eBay writes. Публичный импорт — from codex_ecommerce import Engine, EngineStatus.

Домен и orchestration не импортируют Django/ORM/settings или очереди. DTO и доменные ошибки принадлежат движку; web/persistence/provider-specific представления переводят адаптеры. Python API не требует HTTP. Persistence и unit-of-work вводим под реальную операцию, не создаём пустые универсальные repository abstractions. Один владелец миграций общей схемы; worker не получает Django ради доступа к БД.

## Источники и точки входа

- [src/codex_ecommerce/api.py](../../../../src/codex_ecommerce/api.py)
- [src/codex_ecommerce/status.py](../../../../src/codex_ecommerce/status.py)
- [tests/engine/test_engine.py](../../../../tests/engine/test_engine.py)
- [docs/project/architecture.md](../../../../docs/project/architecture.md)
