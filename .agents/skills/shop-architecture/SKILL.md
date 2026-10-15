---
name: shop-architecture
description: "Use when placing or changing code across the independent commerce engine, Django adapters, ARQ workers, or feature packages in inet_mag."
---

# shop-architecture

Проектный навык inet_mag. Сначала определить затронутую фичу; читать только нужные references. Статус и реальные точки входа указаны в каждом разделе. Будущие требования не означают наличие реализации.

- [Границы движка](references/engine-boundaries.md) — читать при соответствующей задаче.
- [Django как потребитель](references/django-adapters.md) — читать при соответствующей задаче.
- [Отдельный ARQ](references/arq-workers.md) — читать при соответствующей задаче.
- [Структура по фичам](references/code-structure.md) — читать при соответствующей задаче.
- [Шаблоны и дизайн](references/template-layout.md) — при размещении web templates, общих компонентов и первой демонстрации.

Использовать установленные библиотечные навыки при работе с их API, не копировать их руководства сюда. Не редактировать managed skills. После изменения реализации обновлять только затронутые references и их проверки. Этот навык не расширяет разрешение на внешние операции.

- [Эффективность Django ORM](references/django-query-efficiency.md) — при моделях, selectors, выдаче и загрузке связанных данных; предотвращать N+1 и проверять бюджет фичи.

- [Контракт ошибок](references/error-contract.md) — при новых фичах, ответах API/HTML, обработке исключений и внешних сбоев; общий формат, ошибки фич, понятные тексты и безопасные действия.
