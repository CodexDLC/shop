# SEO магазина

Применять вместе с глобальным навыком `seo-architecture`, когда меняются head, публичные URL, товарные данные для JSON-LD, фильтры/пагинация, sitemap или языковые версии. Этот reference задаёт политику магазина, не копирует общий учебник.

- SEO принадлежит Django adapter, не независимому commerce engine/ARQ. Подключение стандартных возможностей Django предпочтительно. Generic SEO-механизмы codex-django сначала проверять: библиотечные defaults всех LANGUAGES/alternates не означают, что переводы сайта опубликованы.
- Не открывать индексирование автоматически. Local/staging/preview закрыты; разрешение на код не разрешает deployment/production indexing. Origin доверенный и настроенный, не request Host/GET. Не вставлять token/reference/search/private query в canonical/OG/schema. Без origin не выдумывать абсолютные URL.
- Head блоки прямо в base.html; child page_head содержит assets, не дубли metadata. Templates остаются server-rendered. Сохранять дизайн, цвета/размеры и компоненты body. Проверять дубли title/description/canonical и JSON script escaping.
- Один URL модели с вариантами; не плодить SEO-страницы размеров и цветов. Internal search/facets/sort noindex, canonical к чистой коллекции. Чистая пагинация не канонизируется вся на страницу1. Private/utility/aliases/errors всегда noindex, даже при будущем публичном режиме.
- Sitemap ограничен ORM-пагинацией, без N+1/материализации всего каталога; только разрешённые URL и реальные publication facts. Не добавлять demo-товарам даты/флаги для прохождения фильтра. Не подставлять текущую дату как lastmod без основания.
- Product JSON-LD совпадает с видимыми данными. Не публиковать demo price/demo_quantity как реальные Offer/наличие; aggregateRating только по approved и при count>0. Не придумывать delivery/return promises или реквизиты. Проверять absolute image URL и безопасную сериализацию.
- LANGUAGES не равно published languages. Русский fallback пока не перевод; не объявлять RU hreflang или sitemap до действительной локализации. Языковые URL сохраняют язык, alternate должны быть взаимными.
- Никаких новых analytics SDK/cookies/внешних отправок в рамках технического SEO. Метаданные строятся из уже загруженного контекста; не допускать дополнительных запросов на каждую карточку/вариант.

Фактическая реализация и пределы: [SEO-каркас](../../../../docs/project/seo-foundation.md), [задача и проверка](../../../../tasks/active/2026-10-21-seo-foundation.md). Проверки меняющихся правил должны включать закрытый и явно включённый публичный режим, origin/Host safety, demo exclusion, utility paths, ошибки и локализацию.
