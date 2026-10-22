# Корзина и заказ

Статус 20.10.2026: локальные session-cart и test-order checkout реализованы. Это не Stripe sandbox и не рабочая оплата/резерв.

Сервер рассчитывает сумму по SKU; цены браузера недоверенные. Decimal/целые minor units, явная валюта и округление. Заказ сохраняет snapshot строк/цен. Order, Payment и Shipment имеют отдельные статусы с разрешёнными переходами. Выделять последовательность checkout только после правил резерва. Не создавать один god OrderService для всего магазина.

Приёмка: подмена суммы, повтор оформления, изменение цены каталога после заказа, отсутствие SKU, конкурирующий резерв.

## Источники и точки входа

- [docs/project/security-and-correctness.md](../../../../../docs/project/security-and-correctness.md)


## Локальный тестовый контур

- `web.cart.session_cart`: SKU/quantity по principal в Django session; цены/активность/EUR/demo_quantity проверяются сервером, POST+CSRF для add/update/remove. `codex_ecommerce.cart` — независимые DTO/ошибки/Decimal расчёт без Django.
- `web.orders.address_form`, `checkout_state`, `persistence`: Германия, intent создаётся на POST адреса; review signed token привязан к owner+nonce и fingerprint. Уникальная идентичность операции зависит от валидированного owner+nonce, не от timestamp полной подписи. Изменённые цена/состав/адрес требуют повторного review.
- Атомарные Order/OrderLine snapshots; статус test_created, is_test=True, адрес JSON, user либо guest session owner. Подтверждение/кабинет проверяют владельца. Повторный submit возвращает тот же заказ; новая корзина получает новый intent. GET не создаёт заказов или платежей.
- Локальная доставка 0 EUR явно тестовая. Нет списания/резерва склада, провайдера, DHL или письма. Не называть это полноценным production checkout. Реальные платежи, финансовая бухгалтерия, счета и возвраты — следующие фичи.
- Карточки home/list/PDP передают выбранный SKU в native POST; customer history/details показывают собственные тестовые snapshots. Сохранять reference-компоненты, неподключённые сервисы — явные planned/disabled.
- Проверки: tests/web/test_local_commerce.py, test_customer_test_orders.py, tests/engine/test_local_commerce_domain.py. Полноценный PostgreSQL concurrency stress не проводился; unique-conflict recovery проверяется целевым тестом.
- Описание и ограничения: [локальные функции](../../../../../docs/project/prototype-functionality.md).
## Промокоды и адреса — локальный шаг20.10.2026

- Промокоды: `cart.PromoCode` (inactive по умолчанию), отдельный principal session key; POST+CSRF `cart:coupon_apply/coupon_remove`. Один код, percent/fixed EUR, сроки/minimum; применять через независимый `DiscountRule/discount_amount`, не считать деньги в JS/template. Не добавлять активные образцовые акции в реальную БД.
- Quote: gross `subtotal`, `discount_amount`, net `total`, `coupon_code/coupon_signature`; выбранный недействительный код сохраняется с ошибкой до удаления/замены. Review/create всегда перечитывают условия; fingerprint включает суммы/подпись условий. Atomic persistence блокирует SKU+правило и сохраняет неизменяемые суммы в Order; не обходить unique intent.
- Адресная форма: home либо Packstation; отдельно billing. Для Packstation Postnummer6–10 ASCII цифр и трёхзначный номер станции, PLZ/город/DE, обязательный обычный billing. Это локальная проверка структуры, не проверка DHL. Неактивные поля очищать до валидации; старый home POST поддержан. Два независимых снимка адресов сохраняются в Order.
- Native/no-JS POST остаётся рабочим; JS только раскрывает ветки. При скрытии grid учитывать CSS `[hidden]`, отключать неактивные inputs, серверные ошибки не заменять browser-only проверкой. Reference sections и неподключённые услуги сохранять.
- Проверки: test_cart_discounts, test_checkout_promotions, test_checkout_addresses, test_checkout_address_flow + прежний local_commerce/customer flow. Не объявлять PostgreSQL concurrency stress или production VAT/refunds завершёнными по SQLite tests.
- [Подробности](../../../../../docs/project/checkout-promotions-addresses.md). Адреса/Postnummer не логировать/не отправлять внешним службам; используются session/TEST snapshots, без маркетингового согласия или новых трекеров.
