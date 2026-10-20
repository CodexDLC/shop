# Связь с eBay

Статус: Запланировано.

Variant ↔ item ID + variation identifier при наличии. Сохраняем действующие объявления и item ID. Тип listing определяет API; не мигрировать все listings в Inventory API автоматически. Проверить SKU/EAN и реальные варианты на небольшой read-only выборке. Quantity=0 не означает безусловно завершить объявление.

Приёмка: существующие отдельные listings объединены карточкой сайта; не создан новый listing; повтор сопоставления не удваивает запас.

## Источники и точки входа

- [docs/предварительный-стек/catalog-ebay-photos.md](../../../../../docs/предварительный-стек/catalog-ebay-photos.md)
- [docs/предварительный-стек/koongo.md](../../../../../docs/предварительный-стек/koongo.md)

## Авторизация продавца — 16.10.2026

Фича `web.ebay_oauth` реализует одноразовое приглашение, browser-bound state, OAuth callback, проверку ожидаемого продавца через GetUser и Fernet-шифрование access/refresh tokens. Руководство: [ebay-seller-oauth.md](../../../../../docs/project/ebay-seller-oauth.md). Команда `create_ebay_oauth_invite --seller sonne_fuer_alle --output <private-file>` не печатает ссылку. `cleanup_ebay_oauth` очищает истёкшие приглашения/попытки; расписание ещё не включено.

Разрешения фиксированы: base, inventory.readonly, listing.read, fulfillment.readonly и commerce.notification.subscription. Последнее только для настройки доставки событий, не для изменения товаров/заказов. Базовый Trading scope не является технически read-only: сетевой adapter допускает только OAuth exchange и фиксированный GetUser. Не добавлять произвольные методы/пути/XML.

Токен сотрудника prime_8088 не открыл объявления sonne_fuer_alle; приглашение предназначено владельцу магазина. Portal accepted/declined URL должны вести на `/integrations/ebay/oauth/callback/`, а не deletion callback. Внешний завершённый OAuth ещё требует входа владельца; тесты не заменяют его.

Запрошено будущее наблюдение за продажами и ORDER_CONFIRMATION, но polling, refresh scheduling и seller subscription этой фичей не включаются. Проверить доступные topics/scopes после входа; не запрашивать sell.fulfillment write автоматически. До импорта order data завершить политику удаления; минимизировать payload до ID/количества/статуса и дедуплицировать webhook+reconciliation.
