# Остаток функций витрины вне кабинета

Статус: in-progress. Режим: независимый ревизор (выбор пользователя 20.10.2026).

## Исходный запрос

Пользователь передал список оставшихся макетов (коммуникации/персонализация кабинета, товар, каталог, checkout, заказ, письма, юридический раздел) и уточнил: «кабинет отдельный.. шаги а вот все что не кабинет надо заняться».

## Требования

- R1: кабинет покупателя и его коммуникации/персонализация исключены из этой очереди. Сохраняем существующий дизайн и HTML-компоненты.
- R2: товар — галерея/увеличение, описания/характеристики, размеры, рейтинг/отзывы без выдуманных данных.
- R3: каталог — материалы/свойства и обоснованные сортировки; реальные фильтры ORM с ограниченной выдачей.
- R4: checkout — промокоды, платёжный адрес, Packstation; express и примерка требуют подтверждённых условий, не фиктивного success.
- R5: заказ — Stripe sandbox/PayPal через Stripe, документы, DHL tracking/возвраты/refunds с ручным подтверждением после проверки. Реальные деньги, вызов курьера и запись eBay не разрешены.
- R6: письма заказа/отправки через тестовый Mailpit, защита от дублей; отправка после факта передачи перевозчику. Маркетинг зависит от отдельной задачи согласий кабинета и остаётся выключенным.
- R7: юридические тексты — существующий reader сохраняется; подготовка адаптера версионированных текстов, подключение реального поставщика после выбора и доступа. Не придумывать реквизиты/условия или правовую готовность.
- R8: последовательные законченные шаги, целевые тесты, browser desktop/mobile для UI, независимая проверка, документация. Импорты engine/web/worker разделены; тексты по ключам. Без commit/push/deploy автоматически.

## План и статус

| Шаг | Результат | Реализация | Проверка |
|---|---|---|---|
| 1 | PDP: миниатюры, главное фото, native dialog увеличения; цвет меняет набор, размер сохраняет фото, пустой/ошибочный источник; без свайпа фото в мини-карточке | done | pass, независимый pdp_gallery_review; reviewed-awaiting-acceptance |
| 2 | Характеристики и размерные таблицы из ORM; честное отсутствие данных; основа отзывов с модерацией (проверка покупки и публичная отправка отложены по уточнению S2-R3) | done | pass, information_step_reviewer; reviewed-awaiting-acceptance |
| 3 | Материалы/свойства, newest по дате, rating по approved; популярность выключена до источника реальных продаж | done | pass, catalog_step3_reviewer; reviewed-awaiting-acceptance |
| 4 | Промокоды/платёжный адрес/Packstation: серверная валидация, суммы и snapshots заказа; отдельные условия дополнительных сервисов | done | pass, checkout_step4_reviewer; reviewed-awaiting-acceptance |
| 5 | Тестовые письма заказа с outbox/idempotency и Mailpit; API-контракты перевозки и правовых текстов | pending | pending |
| 6 | Stripe sandbox/webhooks/refunds; DHL sandbox labels/pickup/tracking/returns по доступам; финансовые действия остаются ручными | pending | pending |
| 7 | Счета PDF после определения нумерации/налоговых реквизитов; поставщик правовых текстов, end-to-end sandbox | pending | pending |

Шаги — план исполнителя, не добавочные условия пользователя. Зависимости: реальные описания/размерные сетки производителя; утверждённые скидки/условия примерки; API credentials sandbox; реквизиты/налоговая схема; выбор legal provider. Независимые локальные части выполняются без этих доступов. Первым реализуется шаг1; пункты2–7 не объявляются завершёнными вместе с ним.

## Проверка шага 1

План: isolated ORM gallery fixtures, query budget, сохранение фото при размере/новый набор при цвете и позднем ответе API, native dialog клавиатура/закрытие/focus; no gallery и image error; browser на существующих данных без их изменения. Аналитика: новые трекеры/consent cookies не добавляются; события галереи только локальные DOM, без сохранения идентификаторов и запросов аналитики.


## Результат шага 1

- Реализация: presentation.initial_gallery; PDP gallery include и product-gallery.js/css; catalog:gallery-события и page-local confirmed gallery cache в catalog-selection. Без нового SQL, схемы, изменения товаров и внешних записей.
- Red до реализации: KeyError initial_gallery, 1failed. Целевые проверки проверяют реальные URL/prefetch/querybudget, пустой набор, thumbnail/state/keyboard/error; много фото в isolated fixtures.
- Независимый pdp_gallery_review нашёл2 P2: повторный выбор сломанного src скрывал ошибку; size мог вернуть старый SSR gallery после confirmed API. Оба воспроизведены и исправлены; добавлены regression checks и ранняя ошибка SSR до deferred boot. Повторная независимая проверка28passed, оба замечания закрыты; точные итоговые утверждения подтверждены.
- Финальный полный набор ведущего:436passed за20.25s, лог .local/product-gallery-tests-final.txt. Ruff src/tests clean; Django check clean и makemigrations --check --dry-run без изменений (до последних JS-only corrections).
- Browser ведущего: desktop/390px, увеличение/закрытие, Escape/focus back, цвет и SKU/alt. Скриншоты .local/product-gallery-review/desktop-zoom.png, mobile-zoom.png. Текущая реальная модель имеет1фото с общей fallback gallery; много кадров проверено fixtures, не заявляется live-browser multi-image проверка. Ревизор просмотрел скриншоты, native Escape лично не выполнял.
- Только шаг1 reviewed-awaiting-acceptance. Задача в целом in-progress: R2 остальная часть/R3–R7 и шаги2–7 pending. Кабинет исключён. Никаких commit/push/deploy.

## Шаг 2: запрос и план до реализации

Пользователь: «давай следующий шаг — характеристики товара и таблицы размеров, отзывы тоже заложим но без выдуманных оценок. дизайн сохраняем, с независимым ревизором».

- S2-R1: реальные description/composition/care/fit/origin/certification из редактируемого ORM контента товара; отсутствующие данные явно отсутствуют. Контент — обычный экранируемый текст, интерфейс — ключи переводов. Никакого наполнения выдуманными сертификатами/обещаниями/характеристиками.
- S2-R2: опубликованная размерная таблица бренда/категории (категория приоритетнее общей), строки мерок в cm и перевод в inch, источник и инструкции; при отсутствии опубликованных данных честное пустое состояние. Не выводить наличие по таблице: оно относится к SKU.
- S2-R3: заложить модель отзывов с pending/approved/rejected и рейтингом1–5, отображать только approved; реальные count/average, пустое состояние вместо4.9(48). Сейчас нет публичной отправки, писем, проверки покупки и fake verified badges. Moderation стандартными разрешениями Django admin. Публичный список ограничен10, без публикации PII пользователя из auth.
- S2-R4: сохранить композицию, размеры блоков, tabs, size modal, цвета/типографику reference; подключить рабочие tabs и доступный dialog/focus/Escape/mobile. Мини-карточки и галерею шага1 не менять.
- S2-R5: новый detail-only context с bounded ORM и предсказуемым бюджетом; home/list бюджеты не увеличиваются. Миграции локально, без изменения имеющихся пользовательских товаров/seed, eBay/финансовых/внешних API/публикаций.
- S2-R6: тесты до замены placeholder поведения, ORM constraints/publication/escaping/brand isolation/querybudget, browser desktop/mobile, независимая ревизия с разбором находок. Аналитика: новые tracking/consent/cookies/events на сервер не добавляются; отзывы — публичный модерируемый контент без auth email/адресов, сроки/удаление нуждаются в отдельной политике до публичного сбора.

План: (1) backend models+migration+admin+detail context и isolated fixtures; (2) подключение сохранённых reference blocks к context, удаление фиктивных значений и старого inline modal script, локализованные empty states; (3) тесты+local migrate+desktop/mobile; (4) независимая ревизия и документы. Реализация pending, проверка pending. Данные производителя не предоставлены, поэтому на текущей базе ожидаются пустые сведения/размерная таблица/отзывы; наполнение фиктивными числами запрещено.

Шаг2: принятый HTTP SQL budget PDP9 без таблицы /10 с таблицей (прежние5 +information1/guide1/summary1/reviewlist1 и rows1 при guide). Home5 и listing context10 не меняются. Отдельный feature context4/5, измеряется при росте отзывов/строк. Старые проверки полного PDP обновлены только на эти дополнительные чтения.


## Результат шага 2 — reviewed-awaiting-acceptance

| Требование | Реализация | Проверка |
|---|---|---|
| S2-R1 | done: ProductInformation по языку, реальный manufacturer_article, plain escaped text | pass: fixtures, fallback, XSS escaping; независимый ревизор |
| S2-R2 | done: опубликованные SizeGuide/Row с источником, приоритет категории, cm/inch, пустое состояние | pass: constraints/isolation/conversion; browser desktop/390 и HTML-fixture; независимый ревизор |
| S2-R3 | done в уточнённом объёме: pending по умолчанию, approved-only count/average/list10 | pass: изолированные отзывы, ограничение/агрегат; публичной отправки и проверки покупки нет |
| S2-R4 | done: сохранены блоки reference, ARIA tabs и native size dialog, keyboard/hash links | pass: browser focus/Escape, скриншоты desktop/mobile; JS и guard tests; ревизор просмотрел снимки |
| S2-R5 | done: только detail context, добавочная catalog.0004 локально | pass: feature4/5, HTTP9/10, home5/list10; Django checks и migration drift clean |
| S2-R6 | done: red→green, независимая ревизия и документы/проектная инструкция | pass, оба этапа ревизии и итоговые утверждения подтверждены |

- Backend исполнитель product_details_backend: четыре модели (по классу в файле), context, admin и migration; red на отсутствии ProductInformation; 21 целевой тест. Ведущий интегрировал HTML/JS/тексты/проверки.
- Red при замене шаблона: видимое4.9 осталось в исходном PDP, тест упал как ожидалось. Guard legacy preview тоже сначала упал: browser показал native dialog.open=true при display:none. Удалена устаревшая строка reference-navigation, которая добавляла hidden; прямые hash links сохранены новым компонентом. Старый inline modal/unit script удалён, режим replacement-only для этого макета.
- Замечание ревизора по конфликтующим классам активного INCH устранено: muted снимается, white/green проверены computed styles. Укреплена проверка hash-перехода с другой вкладки, обновлён снимок desktop после исправления лишней внешней прокрутки.
- Финальный полный прогон ведущего: 457 passed за26.10s, .local/product-information-tests-final.txt. Ruff src/tests, Django check, makemigrations --check --dry-run clean. После усиления hash-test: отдельный test_product_information_behavior прошёл. Независимый information_step_reviewer лично26 целевых +49 regression tests, просмотрел снимки и полный лог, подтвердил итоговые утверждения; блокирующих замечаний нет.
- Browser: фактическая локальная база без новых content/review/size записей. Empty info/reviews и native dialog desktop/mobile, открытие/Escape/focus назад, units, tabs. Заполненная таблица проверена отдельным маркированным UI TESTDATEN HTML (не данные производителя), cm→inch и selected row; временный сервер8032 остановлен, временная вкладка закрыта. Основной Django8030 работает.
- Снимки .local/product-information-review: desktop-information-empty.png, desktop-size-empty.png, desktop-reviews-empty.png, mobile-size-empty.png; fixture-size-inch-desktop/mobile.png — только маркированная проверка вёрстки. Последний desktop-information-empty содержит окончательные тексты. Никаких sample ratings/мерок в действующий каталог не записывали.
- Документация: docs/project/product-information-size-reviews.md; обновлены README, catalog-read-api и принадлежащий проекту reference products-and-variants. Не менялись managed library skills, кабинет, eBay/DHL/платежи. Commit/push/deploy не выполнялись.
- Настоящие сведения производителя и публикация размерных таблиц требуют подтверждённых источников и ручного заполнения; готовность механизма не означает наличие этих данных. Дальше в очереди шаг3 каталога; шаги3–7 pending.

## Шаг 3: требования и план до реализации

Запрос: «каталог: фильтры по материалу и свойствам, сортировку по новизне. популярность и рейтинг только по реальным данным, без выдумок. дизайн сохраняем, с независимым ревизором».

- S3-R1: Material и ProductProperty — структурированные справочники со slug/name, M2M товара; фильтры material/property комбинируются с существующими search/section/new/sale/brand/category/tag/color/size/price/stock. OR внутри группы, AND между группами, неизвестные значения дают пустую выдачу; никаких выводов свойств/состава из свободного текста или фиктивного наполнения.
- S3-R2: сортировка newest по nullable Product.published_at (первая фактическая публикация), неизвестная дата последней; стабильный tie-break name/pk. Миграция не приписывает дату существующим товарам, не использует pk/new_until как давность. Новый механизм live-публикации не входит в шаг; поле заполняется подтверждённой датой через admin.
- S3-R3: рейтинг по approved ProductReview, среднее реальных одобренных оценок; без отзывов NULL last, затем стабильные tie-break. Pending/rejected не влияют, никаких sample ratings в реальной базе.
- S3-R4: популярность требует подтверждённых реальных продаж. Сейчас PaymentAttempt допускает только demo/sandbox; Order.is_test=True и локальные TEST orders не источник. Опция остаётся disabled с понятным объяснением; прямой неподдерживаемый sort безопасно нормализуется с ошибкой. Не писать фиктивный счётчик и не считать просмотры согласившимися на аналитику.
- S3-R5: сохранить reference sidebar/checkboxes/toolbar/cards/mobile rail; формы GET, chips, pagination сохраняют оба новых multi-value фильтра и сортировку. Справочники только по видимому каталогу, до200 значений + выбранные до20, без N+1/дублей и загрузки всех товаров.
- S3-R6: тесты до замены старых disabled controls, schema constraints, фильтры в сочетании/валидация/caps/URL/escaping, approved-only ranking/unknown dates/stability и bounded query budget при1/12 карточках. Browser desktop/mobile на реальных данных без sample assignments; независимая ревизия. Без кабинета, eBay/платежей/DHL, реальных продаж, commit/push/deploy.
- S3-R7: UI тексты через ключи, справочники — редактируемые названия данных. Новые tracking cookies, просмотры, события аналитики/передача данных не добавляются; штатный search GET остаётся операционным чтением. До источника реальных продаж популярность не реализуется через обход ограничений оплаты.

План: backend models/migration/parser/selectors/facets + targeted tests; ведущий подключает ListingContext/HTML/ключи и проверяет URL/дизайн; local migrate, regression suite и browser; независимый ревизор, документы и project reference. Статус реализации pending, проверка pending. Бюджет listing context увеличится с10 до12 SQL только за счёт двух фасетов; rating/newest остаются в SQL выдачи, не на карточку. Home/PDP не используют новые M2M prefetch и сохраняют бюджеты.


## Результат шага 3 — reviewed-awaiting-acceptance

| Требование | Реализация | Проверка |
|---|---|---|
| S3-R1 | done: Material/ProductProperty, M2M, Exists + OR/AND | pass: сочетания всех фильтров, duplicates/unknown/active EUR, изолированные fixtures и ревизор |
| S3-R2 | done: nullable published_at, newest NULL last + name/pk | pass: датировки/равенство/NULL, миграция без backfill, ревизор |
| S3-R3 | done: approved-only Avg/count subqueries, NULL last | pass: pending/rejected не влияют, ties/listing, ревизор |
| S3-R4 | done в согласованной границе: popular disabled и безопасная ошибка URL | pass: нет чтения TEST orders/обхода payment_no_live, ревизор |
| S3-R5 | done: существующие sidebar/checkboxes/toolbar/rail, URL/chips/caps | pass: pagination/removal/selected beyond200 + browser submit/reset/mobile; ревизор |
| S3-R6 | done: tests first, local0005, regression/browser/независимый review | pass, замечаний нет; контекст12 при1/12 карточках |
| S3-R7 | done: UI ключи, справочники plain escaped data, нет новых трекеров | pass: escaping/границы/прочитанный diff; ревизор |

- Backend catalog_attributes_backend: red ImportError отсутствующего Material, затем14 новых и53 связанных теста. Migration0005 — только CreateModel2 + пустая nullable date + M2M2; текущие товары/остатки не заполнены или изменены. Ведущий выполнил HTML/ListingContext/UI tests/локальную интеграцию.
- Red ведущего: новый template test упал на отсутствии input name=material. Disabled reference groups заменены общим filter_options, popularity оставлена disabled с объяснением. Существующие query budget tests только listing context10→12; другие бюджеты не повышались.
- Полный прогон:478passed за24.37s (.local/catalog-step3-tests.txt). После CSS/HTML переноса —12 UI/template tests passed3.59s. Ruff src/tests, Django check, makemigrations --check --dry-run clean. Локально0005 применена; повторная схема без drift.
- Независимый catalog_step3_reviewer лично46 tests + checks/drift, просмотрел код/документы/снимки и общий лог; подтвердил итоговые утверждения, блокирующих замечаний нет. Браузером и миграцией реальной local DB лично не управлял; это доказательства ведущего.
- Browser desktop и390px: select newest/rating, unknown selected material/property, оба checked сохраняются при submit нового sort; chip material убирается отдельно, property и sort остаются; reset возвращает4 модели. Ведущий нашёл overflow для выбранного material из120 символов: scrollWidth1863 приclientWidth390. CSS перенос sidebar labels/chips дал390/390; исходный дизайн/мобильный rail сохранены.
- Снимки .local/catalog-step3-review/{desktop-newest,mobile-catalog,mobile-selected}.png. Доисправленный mobile-selected-before.png — только история воспроизведения, не итог.
- Read-only actual DB counts: materials0/properties0/dated_products0/approved_reviews0/products4. Значения в справочниках и даты остаются неизвестными; реальная выдача не наполнена тестовыми признаками. Положительные совпадения/порядок разных дат/оценок проверены isolated tests, не объявлены заполненным live browser.
- PostgreSQL EXPLAIN newest/rating сохранены в .local/catalog-step3-review/postgres-*-plan.txt на имеющихся четырёх товарах, без ANALYZE/записи; это не нагрузочный benchmark.
- Обновлены docs/project/catalog-listing.md, связанные бюджеты в product-information-size-reviews.md и проектных references ORM/products-and-variants. Не менялись managed skills, кабинет, деньги/eBay/DHL; нет новых cookies/analytics events. Commit/push/deploy не выполнялись.
- Задача в целом in-progress; шаги1–3 проверены, ожидают принятия пользователем. Шаги4–7 pending. Популярность требует отдельного источника подтверждённых реальных продаж до включения.

## Шаг 4: запрос, требования и план до реализации

Пользователь: «оформление: промокоды, отдельный платёжный адрес и Packstation. пока без реальных оплат и DHL, дизайн сохраняем, с независимым ревизором».

- S4-R1: один промокод на корзину, percent/fixed EUR, активация/сроки/minimum subtotal, Decimal и серверный расчёт с ограничением скидки стоимостью товаров. Никаких предустановленных маркетинговых условий или действующих образцовых кодов в реальной базе. POST+CSRF apply/remove; код разделён по principal как корзина. Нет stacking/usage limits/product restrictions в этом шаге — это явные последующие возможности.
- S4-R2: скидка пересчитывается из текущих цен/количеств/правил при каждом review/create. Недействительный выбранный код не замалчивается: понятная ошибка/удаление, без оформления с ложной скидкой. Signed fingerprint включает итог/код/условия; изменённые сумма/правила/адрес требуют нового review. Повторный submit сохраняет один TEST order; фиксация снимка subtotal/discount/coupon/total и блокировка прочитанных правил в транзакции.
- S4-R3: отдельный billing address (имя/фамилия/улица с домом/PLZ/город/DE), server-side validation. По умолчанию совпадает с домашним shipping; прежние POST остаются корректными. Неиспользуемые поля очищаются. Снимки shipping/billing независимы от последующих изменений формы/профиля.
- S4-R4: shipping_type home/packstation, имя получателя/Postnummer/Packstationsnummer/PLZ/город/DE. Структура локально валидируется; существование станции, соответствие Postnummer человеку и пригодность посылки не проверяются без DHL. Для Packstation нужен отдельный обычный платёжный адрес. Поиск станций/карта/этикетки/курьер не подключаются.
- S4-R5: сохраняем reference accordion промокода, адресную форму/переключатели, summary/review/confirmation, токены/типографику; реальные field errors, состояния без JS и mobile. Express, примерка, оплата/реальная доставка остаются выключенными.
- S4-R6: движок скидки независим от Django; ORM/session/forms/transactions в adapters. Тесты до замены макетов: деньги/границы/округление, expiry/minimum/подмена/смена правил, stale token/idempotency/isolation/CSRF, обе адресные ветки, snapshot и UI. Проверить браузером desktop/390px и независимым ревизором. Local migrations только добавочные; без изменения чужих рабочих данных, eBay/API оплат/DHL, commit/push/deploy.
- S4-R7: UI тексты ключами, данные адресов не передаются наружу, tracking/cookies сверх существующей session не добавляются. Новые поля адресов — только для локального checkout/TEST snapshot; необязательная аналитика/рассылки не включаются. Не логировать адреса и Postnummer; политика удаления тестовых заказов остаётся отдельной эксплуатационной настройкой.

План: независимый engine discount + PromoCode/session adapter/quote/atomic order snapshots; форма home/Packstation/billing и общий адресный renderer; подключение reference templates/summary и валидации; targeted/full tests, local migrations и ручная проверка без внешних запросов; отдельный ревизор, документы/project reference. Реализация pending, проверка pending. Packstation-структуру сверить с официальной документацией DHL; локальная форма не объявляется подтверждением доставки.


## Результат шага4 (проверка завершена21.10.2026)

Состояние: reviewed-awaiting-acceptance. Первоначальные требования/план выше сохранены; шаги5–7 pending. Общий остаток витрины остаётся in-progress.

| ID | Реализация | Проверка |
|---|---|---|
| S4-R1 | done: независимый Decimal discount, PromoCode, native POST+CSRF apply/remove, principal session | pass, reviewer: деньги/сроки/minimum/ограничения/изоляция |
| S4-R2 | done: current quote + fingerprint условий/денег/адресов, atomic locks, order snapshots и unique intent | pass, reviewer: stale/idempotency/подмена; concurrency stress не заявлен |
| S4-R3 | done: отдельная billing-ветка, legacy home, очистка полей, два snapshots | pass, reviewer: unit/HTTP flow/доступ только владельцу |
| S4-R4 | done: Packstation/Postnummer/станция/PLZ/DE + обязательный обычный billing | pass, reviewer: формат/валидация/нет DHL вызовов |
| S4-R5 | done: accordion, адресные формы, review/confirmation/customer snapshot, reference секции и disabled extras | pass, reviewer: source + SSR/native POST и снимки desktop/mobile |
| S4-R6 | done: additive cart0002/orders0004, test-first, полная локальная цепочка, отдельный reviewer | pass с указанными ниже пределами |
| S4-R7 | done: UI ключи, session/TEST data, нет новых адресных отправок/логирования/трекеров | pass, reviewer: прочитана цепочка |

- Backend checkout_discounts_backend: сначала red отсутствующих DiscountRule/PromoCode, затем65 engine/promotions/local commerce tests passed; root red12 address tests сначала упал KeyError shipping_type, затем12 passed. Root integration набор68passed.
- При SQLite cent-constraint тест10.05−1.01=9.04 обнаружил floating equality: в ещё не применённой миграции/модели итоговая consistency constraint сравнивает ROUND(expected,2). Локальный PostgreSQL принял0002/0004 без изменения существующих строк.
- Финальный полный suite531passed24.20s: `.local/checkout-step4-tests.txt`; Ruff src/tests clean, Django check0issues, makemigrations --check --dry-run clean: `.local/checkout-step4-checks.txt`. До финального CSS/текстового исправления также531passed33.34s. Не суммировать эти прогоны как разные тесты.
- Browser8030: выбрана CALIDA demo SKU, invalidcoupon дал понятную немецкую400, затем home→Packstation раскрыл обязательный billing, review показал оба адреса. Сохранён один TEST order975fac61-07ae-4a2a-84e8-fb97c79e0189 с вымышленными данными, без оплаты/DHL/почты. Рабочие промокоды в реальной локальной БД не создавались; положительные скидки проверены изолированными fixtures.
- Browser обнаружил, что Tailwind grid перекрывает native hidden; добавлен scoped `#checkout-address-form [hidden] {display:none!important}`, после restart переключение проверено повторно. JS не рассчитывает суммы и не заменяет серверную проверку. No-JS проверен SSR/native HTTP POST, отдельная browser-сессия с выключенным JS не запускалась.
- UI доказательства: `.local/checkout-step4-desktop.png`, `checkout-step4-mobile.png` — fullpage; `checkout-step4-confirmation.png` — viewport с итоговыми адресами. Fullpage mobile файл375px, отдельно DOM при заданном viewport390px показал scrollWidth390/innerWidth390. Не называть файл375px снимком390px.
- Независимый checkout_step4_reviewer, fresh без истории, зафиксировал первоначальный вердикт до отчёта ведущего. Лично116 целевых/regression tests, прочитал деньги/адреса/права/migrations/JS/templates, просмотрел снимки и сопоставил итоговые утверждения. Итог pass в согласованном локальном TEST scope, блокирующих находок нет. Полный531/actualDB migration/browser лично не повторял. PostgreSQL concurrency stress не проводился.
- [Документация checkout](../../docs/project/checkout-promotions-addresses.md), docs/README/prototype-functionality/development-workplan и проектный checkout reference обновлены. Managed/global skills не менялись. Commit/push/deploy не выполнялись; сервер8030 обновлён для ручной проверки.
