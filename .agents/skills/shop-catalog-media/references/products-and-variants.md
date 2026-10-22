# Товары и варианты

Статус: 15.10.2026 модели/миграция/seed/selector реализованы; витрина пока presentation demo, реальная торговля и eBay binding не подключены.

Одна модель товара объединяет отдельные позиции eBay. Product хранит бренд/артикул/общий текст; Variant — конкретные размер, цвет, SKU/EAN, цену и количество. Channel binding хранится отдельно. В корзину передаётся Variant, не Product. Не складывать количества listings одного SKU, пока не доказано, что это разные физические запасы. Перед реализацией уточнить источник названий/цен, размерные сетки и правила группировки.

Приёмка: несколько моделей и вариантов, разные цвета/размеры, отсутствующий вариант; нет дубликатов SKU и ошибочного объединения разных моделей.

## Источники и точки входа

- [docs/предварительный-стек/catalog-ebay-photos.md](../../../../docs/предварительный-стек/catalog-ebay-photos.md)
- [docs/project/open-questions.md](../../../../docs/project/open-questions.md)

## Поиск и теги

Согласовано: поиск является фичей каталога, а не отдельным продуктовым модулем. Общая выдача, карточки, фильтры, сортировка и пагинация; поисковый запрос и категория задают условия одной выборки и могут сочетаться. Разные генераторные стили приводим к общей дизайн-системе.

Теги: отдельная Tag entity и M2M связь с товарами, для подборок/поиска/фильтрации. Размер, цвет, бренд и материал остаются структурированными характеристиками. Схема, нормализация/уникальность и поисковое поведение тегов уточняются при реализации. Для выдачи prefetch тегов и вариантов, корректная обработка M2M дубликатов. См. [ORM](../../shop-architecture/references/django-query-efficiency.md).

## Реализовано 15.10.2026

Persistence-основа каталога: src/web/catalog/models (Brand, Category, Product, ProductVariant, ProductImage, Tag), migrations/0001_initial.py, стандартная admin и management command seed_demo_catalog. Демонстрационный seed идемпотентен: 4 товара, 32 условных варианта; это не импорт реальных остатков. selectors.storefront_products() требует ограничения выдачи и даёт фиксированные 4 SQL с prefetch, gallery_for_color() использует уже загруженную галерею цвета/общий fallback.

Витрина пока использует presentation-моки, не ORM как источник всех экранов. Каталог/list/detail/search templates находятся в web.catalog/templates/catalog, тексты через shop_i18n и ключи. Запуск и ограничения: docs/project/django-template-migration.md. Проверки: tests/web/test_catalog_models.py и tests/web/test_storefront_templates.py. Реальные резервы/синхронизация/платежи не реализованы этим этапом.

## Привязка главной и PDP — 16.10.2026

HomeView и ProductDetailView читают ORM; presentation.product_presentation преобразует prefetched продукт без SQL в цикле и использует независимый VariantSelector. catalog-selection.js проверяет выбор через read-only preview, блокирует CTA при загрузке/ошибке/недоступности и отбрасывает устаревшие ответы. Другие каталожные экраны/рекомендации пока demo. Общие фото не подтверждают цвет; не подставлять фото чужого цвета. Корзина пока не подключена, не возвращать ложное сообщение об успешном добавлении. Документы: docs/project/catalog-read-api.md; проверки: tests/web/test_catalog_bound_pages.py и visuals/catalog-binding.


## Характеристики, размеры и отзывы — 20.10.2026

PDP больше не использует статические состав, сертификат, рейтинг 4.9 (48) или примерные мерки. ProductInformation — обычный текст по product + language, запрошенный язык → de; UI labels через shop_i18n. Размеры: SizeGuide (brand/category, конкретная категория приоритетнее общей, is_published + source), SizeGuideRow (положительные парные границы waist/hip в cm, уникальный размер, Decimal для inch). Черновик/чужая категория не превращаются в подтверждённую таблицу. Источник URL при выводе только HTTP(S), HTML не разрешён. Не копировать статические таблицы из reference обратно в runtime.

ProductReview: pending по умолчанию, rating 1–5, только approved в count/average и списке десяти новейших. Это основа, не публичный сбор или проверка покупки; не выводить auth email/адреса и фиктивный verified purchase. Редактирование и модерация через штатные Django admin model permissions. Нет образцовых оценок/мерок в реальной базе; отсутствие данных — пустое состояние. Политика хранения/удаления до публичного сбора — отдельная задача.

Detail-only product_information_context: 4 SQL без таблицы, 5 с ней; полный PDP 9/10, home 5 без изменений; listing context шага2 был10, после шага3 —12 (два новых фасета). Строки таблицы производителя выводятся целиком, список отзывов ограничен десятью; query budget не доказывает production latency. UI: includes/product_information и size_guide + product-information.js/css; ARIA tabs/native dialog, cm/inch, выбранный размер без автоматического изменения SKU, мобильная внутренняя прокрутка. Legacy reference-navigation больше не скрывает sizeGuideModal; не возвращать hidden-класс native dialog. Hash-ссылки sizeGuideModal и панелей сохранены. Сохранять галерею шага1 и жесты мини-карточек.

Точки входа/ограничения: docs/project/product-information-size-reviews.md. Проверки test_product_information_context/page/behavior.py и tests/js/product-information.cjs; browser desktop/mobile проверяет реальную видимость/focus/contrast, mock JS это не заменяет. Новые трекеры/consent cookies не добавлены. Редакционный composition остаётся текстом; шаг3 добавляет отдельные структурированные Material/ProductProperty и M2M для каталожных фильтров, без автоматического извлечения из текста.


## Каталог: материалы, свойства и порядок выдачи — шаг3

Material/ProductProperty (slug/name) и Product.materials/properties редактируются через admin. Фильтры material/property — OR внутри группы и AND между полями; Exists исключает размножение моделей. UI сохраняет выбранные неизвестные/beyond-cap значения в checkbox, chips, sort/pagination URL; фасеты до200 значений + до20 выбранных. Labels справочников — экранируемые данные, UI заголовки/ошибки — ключи. Не назначать свойства/материалы на основании догадок или demo HTML.

Product.published_at — nullable дата первой фактической публикации, без автоматического default/backfill; newest сортирует NULL последними, tie-break name/pk. Это отдельно от badge new_until, не расписание публикации. Rating использует только approved ProductReview: Avg, затем count и name/pk; товары без отзывов NULL last, без придуманного0. Popularity disabled до источника подтверждённых реальных продаж; TEST orders/demo/sandbox/просмотры не подходят. Нельзя обходить payment_no_live или добавлять фиктивный counter ради этой сортировки.

ListingRequest принимает до20 значений material/property длиной до120; неподдерживаемый sort=popular нормализуется с ошибкой. ListingContext теперь12 SQL при1/12 карточках, один дополнительный SQL header отдельно; home5 и PDP9/10 сохраняются. Карточкам не нужен prefetch materials/properties. Длинные названия должны переноситься и в sidebar, и в chips на390px; общая горизонтальная прокрутка страницы недопустима, мобильный rail товаров сохранён.

Документы и проверки: docs/project/catalog-listing.md, tests/web/test_catalog_attributes.py и test_catalog_attribute_templates.py. Миграция0005 добавляет только схему, текущие справочники/даты/оценки не заполняются sample данными. PostgreSQL EXPLAIN на dev данных не называть production benchmark. Новых analytics events/cookies нет, финансовых/eBay операций нет.
