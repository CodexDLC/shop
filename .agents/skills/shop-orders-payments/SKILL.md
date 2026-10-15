---
name: shop-orders-payments
description: "Use for inet_mag cart totals, order lifecycle, payment adapters and webhooks, refunds or reservation effects of checkout; not to select or activate live providers implicitly."
---

# shop-orders-payments

Проектный навык inet_mag. Сначала определить затронутую фичу; читать только нужные references. Статус и реальные точки входа указаны в каждом разделе. Будущие требования не означают наличие реализации.

- [Корзина и заказ](references/features/checkout-orders.md) — читать при соответствующей задаче.
- [Оплата и события](references/features/payment-webhooks.md) — читать при соответствующей задаче.
- [Возвраты](references/features/refunds.md) — читать при соответствующей задаче.

Использовать установленные библиотечные навыки при работе с их API, не копировать их руководства сюда. Не редактировать managed skills. После изменения реализации обновлять только затронутые references и их проверки. Этот навык не расширяет разрешение на внешние операции.

Утверждённый платёжный стек первой версии: Stripe Checkout hosted + PayPal через Stripe, один API; сначала sandbox. При реализации читать payment-webhooks reference и docs/project/payment-selection.md. Не возвращаться к выбору Mollie/прямого PayPal без нового решения владельца; live не включать автоматически.
