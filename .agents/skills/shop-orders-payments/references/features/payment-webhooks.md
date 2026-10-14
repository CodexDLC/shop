# Оплата и события

Статус: Запланировано; provider не выбран, диагностический флаг всегда False.

Требование PayPal + карты; Mollie/Stripe кандидаты, не активные integrations. PaymentGateway independent, SDK в adapter. Hosted checkout, без PAN/CVV в наших данных. Return URL не подтверждает платёж. Проверять authenticity webhook по выбранному provider, order binding/amount/currency/status; durable event ID и ключ операции защищают от повторов. После timeout выяснять исход, не создавать повтор с новым ключом.

Приёмка: forged/duplicate/out-of-order event, repeated click, wrong amount/currency, missed webhook reconciliation, paid-after-expired-reserve. До sandbox/provider contract нет runtime настройки для live enable.

## Источники и точки входа

- [docs/project/payment-selection.md](../../../../../docs/project/payment-selection.md)
- [docs/project/security-and-correctness.md](../../../../../docs/project/security-and-correctness.md)
- [src/codex_ecommerce/status.py](../../../../../src/codex_ecommerce/status.py)
