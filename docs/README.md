# Документация проекта

[Статический прототип для GitHub Pages](prototype/README.md): отдельная папка, вход через docs/index.html.

[Собранная основа: установка и локальный запуск](project/foundation-run.md).

[Остаток функций витрины вне кабинета](../tasks/active/2026-10-20-storefront-remaining.md) · [Текущий план разработки](project/development-workplan.md) · [Каталог, варианты и привязка ORM](project/catalog-read-api.md).

[Характеристики товара, размерные таблицы и отзывы](project/product-information-size-reviews.md).

[Общий каталог из базы, поиск и фильтры](project/catalog-listing.md) · [Задача и независимая приёмка](../tasks/active/2026-10-20-catalog-database-binding.md).

[Локальная корзина, тестовые заказы, избранное и обращения](project/prototype-functionality.md) · [Юридические черновики](project/legal-documents.md) · [Требования и проверка](../tasks/active/2026-10-20-prototype-completion-legal.md).

[План рабочего кабинета: навигация, настройки и создание товаров](project/staff-cabinet-plan.md).

[Кабинет покупателя: референс и реальные настройки](project/customer-account.md).

[Единый вход и MFA: настройка и ограничения](project/identity-and-mfa.md).

[Реализованный рабочий кабинет: вход, права и ограничения](project/staff-cabinet-run.md).

[Сохранение реквизитов и публичных контактов магазина](project/store-identity.md).

[Редактор товара: фото, характеристики и публикация](project/staff-product-editor.md) · [Следующие задачи кабинета K1–K8](project/staff-cabinet-roadmap.md).

[Перенос витрины в Django: статус и запуск](project/django-template-migration.md), [ключи локализации](project/django-localization.md).

Foundation, общий каталог из ORM, выбор вариантов, авторизация и сохранение профиля реализованы. Корзина и оформление заказа остаются демонстрационными; наличие моделей оплаты не означает работающий платёжный API. Исторические документы ниже читать с учётом более свежих записей реализации.

Порядок чтения:

1. [Требования прототипа](project/requirements.md).
2. [Архитектура и границы модулей](project/architecture.md).
3. [Окружение и структура проекта](project/environment.md).
4. [План и критерии готовности](project/roadmap.md).
5. [Открытые решения и входные данные](project/open-questions.md).
6. [Предварительный стек](предварительный-стек/README.md), [API](предварительный-стек/external-api.md), [Datenschutz](предварительный-стек/datenschutz.md).
7. [eBay, варианты и фотографии](предварительный-стек/catalog-ebay-photos.md).
8. [Безопасность и корректность кода магазина](project/security-and-correctness.md): деньги, транзакции, доступ, файлы, юридические тексты и восстановление.
9. [Sandbox-стенд и слой ошибок](project/sandbox-and-error-handling.md): ручная проверка без денег/курьера, понятные ответы, журнал и защита от повторов.
10. [Аналитика каждой фичи](project/analytics-and-consent.md): паспорт данных, основания/согласия, хранение, отзыв и очистка.

Требования пользователя имеют приоритет над ранними рекомендациями. Koongo исследован как альтернатива; текущий основной путь — прямой eBay-адаптер. Даты проверки внешних сервисов указаны в соответствующих файлах и не означают проверку доступа нашего аккаунта.

Правила реализации: [AGENTS.md](../AGENTS.md). [Оплата: методы и выбор PSP](project/payment-selection.md).

Проектные навыки в `.agents/skills/shop-*`: архитектура, каталог/фото, остатки/eBay, заказы/оплата и эксплуатация/безопасность. Короткий SKILL.md маршрутизирует к нужным references, включая подразделы будущих фич. Точки входа перечислены в AGENTS.md; библиотечные навыки управляются отдельно установщиками.

[Промокоды, платёжный адрес и Packstation в тестовом checkout](project/checkout-promotions-addresses.md).

[SEO-каркас: head, правила индексации, sitemap и языки](project/seo-foundation.md).

[Рабочий кабинет: верхние группы, левое меню, реальные разделы и проекты настроек](project/staff-workspace.md).

- [Рабочий раздел SEO](project/seo-workspace.md) — отдельные права, автоматика и тексты страниц.
