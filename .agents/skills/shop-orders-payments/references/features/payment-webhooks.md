# Оплата и события

Статус: выбор владельца от 15.10.2026 — Stripe Checkout hosted + PayPal через Stripe, один платёжный API. Интеграция ещё не реализована; сначала sandbox, live не разрешён этим решением.

Карты и PayPal, статусы и full/partial refunds — через Stripe API и официальный Python SDK в адаптере. Прямой PayPal adapter и Mollie не подключать в первой версии. Аккаунт DE, EUR; тариф PayPal = тариф PayPal плюс надбавка Stripe 0,2% + 0,10 €, не карточная ставка. PaymentGateway independent, SDK в adapter. Hosted checkout, без PAN/CVV в наших данных. Return URL не подтверждает платёж. Проверять authenticity webhook по выбранному provider, order binding/amount/currency/status; durable event ID и ключ операции защищают от повторов. После timeout выяснять исход, не создавать повтор с новым ключом.

Приёмка: forged/duplicate/out-of-order event, repeated click, wrong amount/currency, missed webhook reconciliation, paid-after-expired-reserve. До sandbox/provider contract нет runtime настройки для live enable.

## Источники и точки входа

- [docs/project/payment-selection.md](../../../../../docs/project/payment-selection.md)
- [docs/project/security-and-correctness.md](../../../../../docs/project/security-and-correctness.md)
- [src/codex_ecommerce/status.py](../../../../../src/codex_ecommerce/status.py)

Поток hosted Checkout: оформление на сайте → Stripe (платёжная форма) → PayPal при выборе этого метода → результат заказа. Не собирать PAN/CVV в Django. Сохранять заказ при отмене/закрытии вкладки, не подтверждать оплату return URL. Live активация PayPal Business и settlement отдельно; тестовый Authorize/Fail не доказывает готовность production. Деньги возвращает сотрудник после подтверждения суммы, не событие DHL. Подробности и актуальные расчёты — в payment-selection.md/payment-provider-comparison.md.
