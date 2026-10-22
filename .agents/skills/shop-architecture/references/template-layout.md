# Django Templates и локализация

Статус: 15.10.2026 перенесены 30 согласованных HTML-композиций в Django. Статический прототип docs/prototype сохранён отдельно, его дизайн не заменять самодельной упрощённой версией.

- Общие base/header/footer: src/web/templates; общие static: src/web/static/storefront. Шаблоны фич: src/web/<feature>/templates/<feature> с namespace. Фичи shop, catalog, cart, orders, payments, customer, support. Не дублировать логотип/шапку/футер и не менять компонент без задания.
- Страницы соединены именованными Django URL; LocaleMiddleware, немецкий без префикса, /ru/ с немецким fallback. Полный русский перевод не выполнен.
- Тексты через {% load shop_i18n %} и {% text 'stable.key' %}; немецкий каталог src/web/localization/messages/de.json. Новые блоки получают смысловой ключ, параметры отдельно; не писать немецкий текст прямо в шаблоне/JS. Бренды/SKU/данные модели не являются UI-текстами. gettext и escaping не обходить.
- Полные правила [локализации](../../../../docs/project/django-localization.md). Compiler tools/compile_shop_messages.py создаёт PO/MO из JSON. Не переносить сырой HTML в перевод/mark_safe. JS получает безопасный json_script и использует shopText с escaping при HTML-вставке.
- Модели/миграции каталога, корзины, заказов и попыток оплаты/возврата созданы, но витрина пока использует presentation-моки. Никаких реальных финансовых операций, писем, DHL или eBay; demo не называть подключённой Stripe sandbox. GET не создаёт заказы/платежи. Auth/account — демонстрационные формы, настоящий Django auth подключается отдельно.
- Главная и суммы/строки заказа получают данные через context; развитие остальной выдачи до ORM selectors — следующий этап. Сохранять единый формат денежных значений, не добавлять бизнес-логику в templates.
- Для мобильной главной: одна карточка и край следующей, горизонтально листаются товары; смена цвета определяет набор фото, при отсутствии другого фото допустим общий fallback, не подменять цвет CSS-фильтром.
- tools/import_storefront_templates.py — однократный/осознанный импорт из docs/prototype, не runtime и не команда для слепого перезаписывания вручную развитых шаблонов. Сначала diff/сохранение ручных доработок.
- Сначала запуск/проверка по [плану переноса](../../../../docs/project/django-template-migration.md). Внешние фото/шрифты пока сохранены из исходников; локализация assets/production CSS остаётся отдельным этапом.
- Проверять key/fallback/escaping, reverse URL, отсутствие мутаций и 30 screens; desktop/mobile браузер, JS errors и модальные окна. Моки/иллюстративные claims не выдавать за live-функции.

Историческая demo shop.css/shop.js остаётся в checkout, но текущие страницы используют storefront static, не прежнюю интерпретацию SVG-товаров.

## Рабочий кабинет — 16.10.2026

web.staff: staff/base.html наследует codex cabinet; module registry в staff/cabinet.py, проектный context processor не создаёт настройки при GET. Навигация: две верхние группы, общий quick access через библиотечные helpers, внизу sidebar — настройки раздела/магазина. Единый Django/allauth вход /accounts/login/ обслуживает customer/staff; /staff/login/ только redirect. Обязательный staff MFA и endpoint permissions проверяются сервером; см. docs/project/identity-and-mfa.md. Создание модели всегда draft; редактор вариантов не меняет существующий SKU. Проектные overrides не правят установленную библиотеку. Точки входа/права/ограничения: docs/project/staff-cabinet-run.md; tests/web/test_staff_*. Галереи, публикация и генерация SKU ещё не реализованы.

Auth templates account/mfa принадлежат customer/templates и имеют приоритет перед библиотечными account overrides. data-real-auth исключает их из demo JS. Реальные password/email/MFA links в customer overview; reference orders/profile пока protected demo.


## Кабинет покупателя: восстановленный reference — 16.10.2026

/konto/ использует customer/overview.html, CustomerOverviewView наследует CustomerPageView. Не заменять его auth-only списком настроек. Сохранены HTML-композиции overview/profile/orders/order_detail, общий include sidebar; CSS customer-account.css адаптирует те же блоки на mobile. В identity-полях текущие имя (full_name/username), email и date_joined, escaping обязателен. Reference commerce-блоки остаются явно demo, не удалять их из-за отсутствия backend.

Реальные email/password/MFA/logout ссылки — includes/account_security.html, настройки личности и безопасности в profile. Персонализация/адреса/маркетинг пока demo. Не отправлять password из mockформ: disabled fieldset/inputs; customer-account.js перехватывает mocksubmit и заменяет ложные success toast на demo. Нельзя заменять allauth logout защищённый POST на прямой GET logout. Hash tabs profile должны работать при same-page hashchange и первом открытии.

Проверка: tests/web/test_customer_account.py, tests/web/test_storefront_templates.py и browser desktop/mobile: sidebar, hash tabs, auth links, текущая identity и отсутствие document overflow. Точки входа/границы: docs/project/customer-account.md. Это не разрешает реализацию newsletter/заказов.


Кабинет: имя и адреса сохраняются (customer.0001). Реальные формы с data-real-auth: profile-name-form и customer-address-form, card default/delete POST. Не перехватывать их demo-JS. CustomerPageView теперь в views/customer_page_view.py, owner-list одним запросом, json_script для редактирования/одна primary наUser. Empty address list — пустое состояние, не придуманные адреса. Name/email/addresses реальные; маркетинг/счета/заказы остаются demo. Customer-account.js/addresses.js разделяют mock и live; пароль остаётся allauth. Детали: docs/project/customer-account.md, tests/web/test_customer_persistence.py.

## Общий каталог и поиск — 20.10.2026

Общий каталог больше не presentation mock: CatalogPageView → ListingRequest → ListingContext → listing_products/listing_facets → product_presentation; основной /katalog/ и исторические search/mobile/empty aliases используют общую композицию. См. docs/project/catalog-listing.md и tasks/active/2026-10-20-catalog-database-binding.md. У карточек реальные ссылки/варианты, действие preview, checkout выключен.

data-real-catalog исключает GET формы из demo-перехватчиков reference-navigation.js/django-preview.js. Не убирать исключения и не возвращать статические карточки или счётчики. При изменении общих обработчиков проверить главную/PDP/auth: для listing_page static URLs получают версию, остальные страницы сохраняют контракт. Начальный catalog snapshot не дублируется запросами вариантов; явная смена цвета/размера проверяется сервером. Mobile rail — одна карточка и край следующей; toolbar должен переноситься без document overflow. Исходные unsupported filter-компоненты disabled с пояснением; не выдавать их за работающие.


## Витрина: актуализация 20.10.2026

Вместо прежних commerce-mock: реальная локальная сессионная корзина/выбор количества, адрес, signed review и атомарный TEST order; personal history/details — собственные snapshots. Настоящие платежи/резерв/доставка/возвраты/письма заказа выключены. Home/PDP/listing используют catalog-selection.js и hidden native POST формы base с CSRF; data-real-commerce/data-real-support исключены из legacy form interception. Избранное тоже native POST, ограниченная session feature. Не восстанавливать fake payment navigation к confirmation и auto-linking каждого article h3.

Футер/категории — явные Django links, юридические документы — отдельные public routes/reader, контакт — локальный ContactTicket. Рекомендательные блоки используют bounded реальные ORM модели, не выдуманные upsell/SKU. Неподключённые provider/club/fit-профили обозначать planned; нельзя давать фиктивные success/доставку или обещать, что все будущие функции реализованы. [Инвентаризация и ограничения](../../../../docs/project/prototype-functionality.md).

## Staff workspace22.10.2026

Top: Магазин/Операции/Управление; left: разделы выбранной группы; RU/DE справа с пользователем, настройки снизу. Навигация через существующий codex cabinet registry, сохранённые quickaccesskeys не переставлять. [Действующие страницы/права/границы](../../../../docs/project/staff-workspace.md). Будущие настройки показывать как явный неработающий проект с отключёнными полями, не имитировать сохранение/подключённый API. Реальные списки/формы брать из текущих моделей/сервисов.

Общие cabinet/includes overrides размещены в src/web/templates/cabinet/includes (DIRS priority), не в staff/templates/cabinet при library-first INSTALLED_APPS. Проверять get_template.origin и реальный browserCSS, не только наличие файла. Общий библиотечный код не изменять. Новые staffключи сразу RU/DE, все endpoints staff+modelpermissions; список не является авторизацией детали.

Настройки staff (S1–S3): различать общие бизнес-настройки магазина, настройки каталога/операций и общий быстрый доступ кабинета. Пока нет operational model — typed disabled design с явным статусом, без fake-save. Быстрый доступ общий: actor-bound signed revision/fingerprint + условное сохранение, hiddenpermission pins и порядок старых закреплений сохраняются; stale/race409, аудит атомарен. Не возвращать overwrite singleton всей отфильтрованной формой. Generic detail использует явные allowlisted projections, компактные facts/почтовые адреса и раскрываемые технические реквизиты, не перебор concrete_fields. Сохранять отдельные permissions на адреса/связанные записи/имена исполнителей. Проверки test_staff_settings_workspace.py и test_staff_record_cards.py; актуальный контракт docs/project/staff-workspace.md.

