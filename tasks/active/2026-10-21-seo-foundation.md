# SEO-каркас магазина

Дата:21.10.2026. Статус: reviewed-awaiting-acceptance. Проверка: независимый ревизор, выбран пользователем.

## Исходное поручение

После сверки глобального seo-architecture пользователь поручил «делай»: общий SEO-каркас без изменения дизайна, с сохранением запрета индексации стенда. Обсуждались title/description/OpenGraph, canonical, правила фильтров/поиска/пагинации/вариантов, JSON-LD, sitemap/robots и hreflang. Реальные деньги/DHL/eBay, публикация, commit/push/deploy не разрешены.

## Требования

- R1: общий head-контракт прямо в base.html: переопределяемые title/description/robots/canonical/OG/schema/hreflang; ровно один title/description/canonical, удалить дубли из импортированных child head. Визуальный контент/компоненты не менять. Динамические публичные metadata из данных, UI ключи переводимые.
- R2: закрытая индексация по умолчанию local/staging, существующая staging-защита не ослабляется. Production-ready режим только явным безопасным setting+валидным публичным HTTPS origin, без автоматической активации. Служебные auth/cart/checkout/cabinet/admin/integrations/preview/error и внутренний поиск/фасеты всегда noindex. Canonical не строится из недоверенного Host/query; персональные токены/запросы не попадают в OG/schema/canonical.
- R3: постоянный URL модели; цвета/размеры не порождают индексируемые дубли. Консервативно query facets/sort/search noindex, без генерации бесконечных страниц; чистый каталог и страницы пагинации self canonical с валидным page, поисковые query в canonical не отражаются. Существующие prototype aliases noindex. Не вводить новые SEO-landing URL/редиректы без необходимости.
- R4: безопасный JSON-LD Product и BreadcrumbList по отображаемым данным. Только настоящие approved review summaries; без фиктивных звёзд/цен/наличия/сертификатов/реквизитов. Текущие demo price/stock не выдавать за реальные offers. Absolute безопасные image URLs, JSON escaping script-safe. Без новых ORM-запросов на каждую карточку/вариант.
- R5: robots.txt и sitemap.xml существуют. В закрытом режиме disallow all и sitemap пустой; в явно включённом public режиме sitemap только clean public home/catalog/brands/active real product URLs, bounded/paginated ORM, no private/query/mobile/demo aliases. Без выдуманных lastmod дат. Origin централизован.
- R6: языковой фундамент: lang/locale-aware URL, hreflang только для действительно опубликованных переводов. Сейчас нет полноценного RU магазина: не рекламировать RU как готовый перевод. Не генерировать фиктивный x-default или страницы вариантов. Описать точный критерий подключения языков и предел текущей реализации.
- R7: targeted tests first (metadata duplicates, escaping, robots/status/utility/noindex, filtered canonical, origin/Host safety, sitemap/caps, demo offers, i18n), regression suite, browser отсутствие визуальных изменений, независимый reviewer. Не трогать существующие dirty задачи, managed/global skills, реальные данные. Обновить документацию/project reference. Новые cookies/tracking/external sends не добавлять.

## План

Один исполнитель: изолированная web.seo feature и интеграция source/templates/tests. Ведущий: границы/приёмка, docs и project reference, проверка UI и отдельный reviewer. Сначала подтвердить пригодность уже установленной библиотеки, не копировать её generic API без проверки. Без модели SEO-редактора/массового заполнения товаров: это отдельная будущая возможность.

| ID | Реализация | Проверка |
|---|---|---|
| R1 | done: root head blocks, metadata, child title deduplication | pass, independent reviewer + desktop exact SHA |
| R2 | done: fail-closed origin/settings, utility/header policy | pass, reviewer tests + actual HTTP |
| R3 | done: query/alias policy and rendered pagination canonical | pass, reviewer + isolated pagination tests |
| R4 | done: Product/BreadcrumbList, safe JSON, approved summaries, no offers | pass, reviewer + zero SQL metadata test |
| R5 | done: robots and bounded sitemap/index + publication gate | pass, reviewer + closed HTTP + public isolated tests |
| R6 | done: language-aware paths, no fictitious RU alternate publication | pass, reviewer; full RU translation remains future |
| R7 | done: test-first/regression/browser/docs/project reference | pass, independent reviewer; limits below |
## Уточнения реализации до приёмки

-21.10.2026: origin берётся только из явной настройки. Если доверенный origin не задан, абсолютные canonical/OG URL/schema не выдумываются; соответствующие теги отсутствуют, индексация закрыта. При известном origin — максимум один canonical, без Host/query. Требование R1 про отсутствие дубликатов не требует подставлять фиктивный домен.
-21.10.2026: в текущем коде нет реального stock adapter, product presentation всегда demo. Поэтому Offer/наличие из demo_quantity не публикуются. Для sitemap кандидаты требуют is_active + явно указанную published_at + активный EUR SKU и исключают подтверждённые seed-маркеры (demo tag/description key/DEMO- SKU), не имена брендов. Существующие товары не заполнять датами/флагами автоматически.

-21.10.2026: критерий DEMO- SKU ограничен активными вариантами, одинаково в detail snapshot и sitemap EXISTS. Неактивный исторический SKU не определяет текущую публикацию; demo tag/description остаются самостоятельными запретами. Это исключает расхождение из-за фильтрованного prefetch без увеличения SQL.


## Результат и доказательства21.10.2026

- Реализация seo_foundation_impl: новая web.seo feature, root head blocks в base.html, middleware/context processor/settings/routes, удаление прежних child title и SEO keys. Body/CSS/commerce logic не менялись. Модели/миграции/рабочие товары не менялись. Установленный codex-django SEO изучен: model/Redis StaticPageSeo и автоматические всеязычные sitemap alternates не подходят текущей fail-closed policy; штатные Django ORM/Paginator/escaping переиспользованы без нового CMS/cache.
- Red сначала missing title на каталоге. Финально39 новых SEO tests; полный итог570passed33.84s в `.local/seo-regression-final2.log` (531 прежний +39 новых). Metadata snapshot0 SQL, sitemap≤2SQL/shard; существующие query budgets не повышались. Ruff src/tests clean, Django check0issues, makemigrations nochanges: `.local/seo-review/checks.txt`.
- Первый полный прогон568pass/1fail обнаружил разницу wire header API `noindex`→`noindex,nofollow`. Финальный middleware сохраняет существующий explicit non-HTML noindex/none header; HTML merge сохраняет более строгие ограничения/noarchive. Прежние variant_preview tests не ослаблялись. Поправка проверена targeted и полным зелёным прогоном.
- Публикация detail/sitemap согласована по активным SKU; неактивный исторический DEMO- SKU не является текущим demo marker. При активном DEMO- или demo tag/description публикация закрыта. Независимый reviewer воспроизвёл обе ветки отдельным isolated test. Фиктивные оценки/наличие/offers не генерируются.
- После final restart локального8030 девять read-only GET проверены `.local/seo-review/probe.py`; протокол `.local/seo-review/http-heads.json`: home/catalog/search/PDP/brands/login/cart/robots/sitemap200; HTML title ровно1 и robotsnoindex; robotsDisallowAll; пустой urlset. Origin остаётся пустым, поэтому нет canonical/og:url/JSON-LD; безопасный внешний og:image допустим. API variant actual200application/jsonXRobotsnoindex.
- Browser desktop PDP до/после: `.local/seo-review/pdp-before.png`, `pdp-after.png`, оба1564×1232, ImageChops bbox=None и независимый SHA256 совпал. Это доказательство указанного viewport/PDP, не всех экранов магазина. Mobile after `.local/seo-review/pdp-mobile-after.png`: заданный viewport390×844, DOMinnerWidth390/scrollWidth375, переполнения нет; отдельного mobile before нет. JSON/OG/canonical/public mode доказаны isolated HTTP tests, не включением индексации локального сайта.
- Independent seo_foundation_reviewer fresh без истории: первоначальный verdict до отчёта ведущего; лично61targeted до lastfix,48послеfix + отдельный publication test (наборы пересекаются, не суммировать). Прочитал финальный570лог/checks, снимки/HTTPdump, code и docs. Первоначальные замечания в промежуточной незастывшей версии исправлены, итог R1–R7pass без открытых code findings. Единственное финальное docs-уточнение об absolute metadata исправлено и перепроверено.
- Docs `docs/project/seo-foundation.md`, README/development-workplan и app-owned architecture reference `references/seo.md` обновлены; глобальный seo-architecture и managed library skills не менялись. Источники правил Google связаны в документе.
- Production domain не выбран/не активирован. Local/preview/staging FORCE_NOINDEX=True; публичный режим проверен только через isolated override_settings. Никаких внешних API writes, deployment, commit/push, SearchConsole/sitemap submission/реальной индексации. Новых tracking/cookies/рассылок нет. Ждём пользовательской приёмки, не объявляем production readiness.
