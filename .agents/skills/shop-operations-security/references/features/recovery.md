# Восстановление

Статус: Запланировано; production backup jobs отсутствуют.

Postgres, файлы и нужная конфигурация входят в проверенное восстановление. Replica/Redis persistence не заменяют backup. Финансовые операции provider могут быть новее восстановленной БД: сверить операции до возобновления торговли. Outbox/event IDs должны позволять безопасное восстановление, не повторную оплату. Мониторим stuck reservations, payment/eBay errors и worker lag; ограниченные retries, видимая ручная очередь.

Приёмка: restore в изолированной среде, сверка внешнего исхода, повтор worker после crash без двойного эффекта. Не запускать destructive restore на действующей среде как обычный тест.

## Источники и точки входа

- [docs/project/security-and-correctness.md](../../../../../docs/project/security-and-correctness.md)
